import os
import json
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.oauth2.credentials import Credentials
import google.auth.transport.requests
from services.google_service import ensure_drive_index
import asyncio
from datetime import datetime

router = APIRouter()

# --- Config ---
CLIENT_SECRETS_FILE = "client_secret.json"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173/")

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")  # Must match exactly in Google Console!

# --- Token Verification (Session Based) ---
async def verify_google_token(request: Request) -> tuple[str, Credentials]:
    session_creds_dict = request.session.get('google_credentials')
    user_id = request.session.get('user_id')

    if not session_creds_dict or not user_id:
        print("Verification failed: No token or user_id in session")
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # Reconstruct credentials object from stored dictionary
        creds = Credentials(**session_creds_dict)

        # Handle expiry string conversion back to datetime
        if creds.expiry and isinstance(creds.expiry, str):
            creds.expiry = datetime.fromisoformat(creds.expiry)

        # Check if token is expired and needs refresh
        if creds.expired and creds.refresh_token:
            print(f"Token expired for user {user_id}, attempting refresh...")
            try:
                auth_req = google.auth.transport.requests.Request()
                creds.refresh(auth_req)
                print(f"Token refreshed successfully for user {user_id}.")
                # Update session with refreshed credentials
                refreshed_creds_dict = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,  # Use potentially new refresh token
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                }
                request.session['google_credentials'] = refreshed_creds_dict
            except Exception as refresh_error:
                print(f"Error refreshing token for user {user_id}: {refresh_error}")
                # If refresh fails, force re-authentication
                request.session.pop('google_credentials', None)
                request.session.pop('user_id', None)
                raise HTTPException(status_code=401, detail="Token expired, refresh failed. Please login again.")

        print(f"✅ Session check OK: user_id={user_id}, creds_valid={creds.valid}")
        return user_id, creds

    except Exception as e:
        # Handle potential errors during verification (e.g., invalid token format)
        print(f"Token verification exception: {e}")

# --- Start OAuth2 Login ---
@router.get("/local-login")
async def local_login(request: Request):
    if not GOOGLE_CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google Client ID or Redirect URI not configured.")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    # Force using v2 endpoint
    flow.client_type = "web"
    flow.authorization_url_base = "https://accounts.google.com/o/oauth2/v2/auth"

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    print(f"🚀 Forced v2 Authorization URL: {authorization_url}")

    return RedirectResponse(authorization_url)

# --- Handle OAuth2 Callback ---
@router.get("/oauth2callback")
async def oauth2callback(request: Request):
    """Handles the redirect from Google after user authentication."""
    if not GOOGLE_CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google Client ID or Redirect URI not configured.")

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code in OAuth callback.")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
    )

    try:
        print(f"🚀 Fetching token with code: {code}")
        flow.fetch_token(code=code)
        print(f"✅ Token successfully fetched.")
    except Exception as e:
        # Check if the exception has response attribute with details
        error_detail = str(e)
        if hasattr(e, 'response') and e.response:
            try:
                error_data = e.response.json()
                error_detail = error_data.get('error_description', error_detail)
            except Exception:  # Ignore if response is not JSON or parsing fails
                pass

        print(f"❌ Error fetching token: {error_detail}")
        # Redirect back to frontend with error message
        error_params = {"error": "token_fetch_failed", "error_description": error_detail}
        error_redirect_url = f"{FRONTEND_URL}#{urllib.parse.urlencode(error_params)}"
        return RedirectResponse(error_redirect_url)

    credentials = flow.credentials
    access_token = credentials.token
    id_token_value = getattr(credentials, 'id_token', None)

    if not access_token or not id_token_value:
        error_params = {"error": "missing_tokens", "error_description": "Failed to retrieve access or ID token after fetch."}
        error_redirect_url = f"{FRONTEND_URL}#{urllib.parse.urlencode(error_params)}"
        return RedirectResponse(error_redirect_url)

    # Verify ID Token and get user_id (sub)
    try:
        id_info = id_token.verify_oauth2_token(
            id_token_value, google_requests.Request(), GOOGLE_CLIENT_ID
        )
        user_id = id_info.get('sub')
        if not user_id:
            raise ValueError("Could not extract user ID (sub) from ID token.")
        print(f"✅ ID Token verified for user_id: {user_id}")
    except Exception as e:
        print(f"❌ ID Token verification failed: {e}")
        error_params = {"error": "id_token_verify_failed", "error_description": str(e)}
        error_redirect_url = f"{FRONTEND_URL}#{urllib.parse.urlencode(error_params)}"
        return RedirectResponse(error_redirect_url)

    # Store essential, serializable credential info in session
    session_credentials = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        # Store expiry as ISO format string for JSON serialization
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
    }
    request.session['google_credentials'] = session_credentials
    request.session['user_id'] = user_id  # Store user_id separately

    # Also update/create the drive index immediately after login
    # We need the Credentials object here, so reconstruct it temporarily
    # NOTE: This reconstruction is okay here as we just got the creds
    login_creds = Credentials(**session_credentials)
    # Handle expiry string conversion back to datetime
    if login_creds.expiry and isinstance(login_creds.expiry, str):
        login_creds.expiry = datetime.fromisoformat(login_creds.expiry)

    # await ensure_drive_index(user_id, login_creds)  # Pass Credentials object

    # 🚀 Build redirect URL for frontend (no longer sending tokens in fragment)
    params = {
        "login_success": "true",
    "cache_status": "pending"  # Indicate successful login via session
    }
    redirect_url = f"{FRONTEND_URL}#{urllib.parse.urlencode(params)}"
    print(f"🚀 Redirecting frontend to: {redirect_url}")

    # Run Drive indexing in the background (don't block redirect)
    # await ensure_drive_index(user_id, access_token)
    asyncio.create_task(ensure_drive_index(user_id, login_creds))
    print("🚀 Spawned background task for Drive indexing.")

    return RedirectResponse(redirect_url)

# --- Debugging Endpoint ---
@router.get("/api/userinfo")
async def get_userinfo(token_info: tuple[str, Credentials] = Depends(verify_google_token)):
    user_id, _ = token_info
    return {
        "user_id": user_id,
    }
