import os
import json
import urllib.parse
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from google_auth_oauthlib.flow import Flow
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

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

# --- Token Verification ---
async def verify_google_token(request: Request) -> tuple[str, dict]:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")
    
    token = auth_header.split("Bearer ")[1]

    # No longer attempt to decode it
    print(f"✅ Access token received: {token[:10]}... (truncated)")
    return token, {}

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
        print(f"❌ Error fetching token: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch token: {e}")

    credentials = flow.credentials
    access_token = credentials.token
    id_token_value = getattr(credentials, 'id_token', None)

    if not access_token or not id_token_value:
        raise HTTPException(status_code=500, detail="Failed to retrieve tokens.")

    # 🚀 Send both tokens back to frontend
    params = {
        "access_token": access_token,
        "id_token": id_token_value,
    }
    redirect_url = f"{FRONTEND_URL}#{urllib.parse.urlencode(params)}"
    print(f"🚀 Redirecting frontend to: {redirect_url}")
    return RedirectResponse(redirect_url)

# --- Debugging Endpoint ---
@router.get("/api/userinfo")
async def get_userinfo(token_info: tuple[str, dict] = Depends(verify_google_token)):
    _, id_info = token_info
    return {
        "email": id_info.get("email"),
        "name": id_info.get("name"),
        "picture": id_info.get("picture"),
    }
