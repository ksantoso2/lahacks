import os
import json
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from services.google_service import ensure_drive_index
import asyncio

router = APIRouter()

# --- Config ---
CLIENT_SECRETS_FILE = "client_secret.json"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173/")

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/documents",
]

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")  # Must match exactly in Google Console!

# --- Token Verification (Session Based) ---
async def verify_google_token(request: Request) -> tuple[str, str]:
    user_id = request.session.get('user_id')
    access_token = request.session.get('access_token')

    if not user_id or not access_token:
        # If not in session, perhaps try header as fallback or just fail
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="User not authenticated or session expired. Please login again."
        )

    print(f"✅ Session check OK: user_id={user_id}, token={access_token[:10]}...")
    return user_id, access_token

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
            except Exception: # Ignore if response is not JSON or parsing fails
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

    # --- Trigger Drive Index Update ---
    print(f"Login successful for user_id: {user_id}. Triggering Drive index update...")
    try:
        await ensure_drive_index(user_id, access_token)
        print(f"Drive index updated/checked for user_id: {user_id}")
    except Exception as e:
        print(f"Error updating Drive index for user {user_id} during login: {e}")
        # Optionally log this more formally
        # Do not raise HTTPException here, allow login to continue
    # ----------------------------------

    # Store user_id and access_token in session
    request.session['user_id'] = user_id
    request.session['access_token'] = access_token
    print("✅ Stored user_id and access_token in session.")

    # 🚀 Build redirect URL for frontend (no longer sending tokens in fragment)
    params = {
        "login_success": "true" # Indicate successful login via session
    }
    redirect_url = f"{FRONTEND_URL}#{urllib.parse.urlencode(params)}"
    print(f"🚀 Redirecting frontend to: {redirect_url}")

    # Run Drive indexing in the background (don't block redirect)
    # await ensure_drive_index(user_id, access_token)
    asyncio.create_task(ensure_drive_index(user_id, access_token))
    print("🚀 Spawned background task for Drive indexing.")

    return RedirectResponse(redirect_url)

# --- Debugging Endpoint ---
@router.get("/api/userinfo")
async def get_userinfo(token_info: tuple[str, str] = Depends(verify_google_token)):
    user_id, _ = token_info
    return {
        "user_id": user_id,
    }
