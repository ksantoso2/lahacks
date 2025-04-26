import os
import json
from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer 
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

router = APIRouter() 

# --- OAuth Configuration --- 
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid", 
    "https://www.googleapis.com/auth/drive", 
    # Add other scopes like documents, sheets etc. if needed by Apps Script
]

FRONTEND_URL = "http://localhost:5173/"

CLIENT_ID = None
REDIRECT_URI = None

try:
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
        CLIENT_ID = secrets['web']['client_id']
        REDIRECT_URI = next((uri for uri in secrets['web']['redirect_uris'] if uri.endswith('/local-oauth2callback')), None)
        if not REDIRECT_URI:
             REDIRECT_URI = "http://localhost:8000/local-oauth2callback" 
             print(f"WARN: Could not find specific /local-oauth2callback in redirect_uris, using default: {REDIRECT_URI}")
except FileNotFoundError:
    print(f"\nERROR: {CLIENT_SECRETS_FILE} not found. Required for audience verification and local OAuth flow.\n")
except KeyError:
    print(f"\nERROR: Invalid format in {CLIENT_SECRETS_FILE}. Missing 'web' -> 'client_id' or 'redirect_uris'.\n")
except Exception as e:
    print(f"Error loading client secrets: {e}")

# --- Token Verification Dependency --- 

async def verify_google_token(request: Request) -> tuple[str, dict]:
    """
    Verifies the Google OAuth2 ID token present in the Authorization header.
    Returns the raw token string and the decoded id_info dictionary if valid.
    Raises HTTPException otherwise.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = auth_header.split("Bearer ")[1]
    
    if not CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="OAuth Client ID not configured on backend for token verification."
        )

    try:
        request_session = google_requests.Request()
        id_info = id_token.verify_oauth2_token(
            token, request_session, CLIENT_ID
        )
        
        # Optional: Add more checks here (e.g., issuer, specific hosted domain `hd`)
        # if id_info['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
        #     raise ValueError('Wrong issuer.')
        # if id_info.get('hd') != 'your_domain.com': # If you want to restrict to a domain
        #     raise ValueError('Wrong hosted domain.')
            
        print(f"Token verified for user: {id_info.get('email')}") # Debug log
        return token, id_info # Return both raw token and decoded info

    except ValueError as e:
        print(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        print(f"Unexpected error during token verification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not verify token: {e}",
        )

# --- Local Development Authentication Routes --- 

@router.get("/local-login", tags=["Local Dev Auth"])
async def local_login(request: Request):
    """Initiates the OAuth flow specifically for local development.
    Redirects the user to Google for authentication.
    """
    if not CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="OAuth client secrets or redirect URI not configured correctly for local login.")
        
    print("Starting local OAuth flow (state parameter not rigorously checked in callback for this local dev setup)")
    
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline", 
        include_granted_scopes="true",
        prompt="consent" 
    )
    return RedirectResponse(authorization_url)

@router.get("/local-oauth2callback", tags=["Local Dev Auth"])
async def local_oauth2callback(request: Request):
    """Handles the callback from Google after user authentication during local dev.
    Fetches the token and redirects back to the frontend with the ID token in the URL fragment.
    """
    print("Received callback from Google for local dev flow.")

    if not CLIENT_ID or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="OAuth client secrets or redirect URI not configured correctly for local callback.")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    try:
        flow.fetch_token(authorization_response=str(request.url))
    except Exception as e:
        print(f"Error fetching token from Google: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch token: {e}")

    credentials = flow.credentials
    id_token_value = getattr(credentials, 'id_token', None)

    if not id_token_value:
         print("Error: ID token not found in credentials received from Google.")
         raise HTTPException(status_code=500, detail="Could not retrieve ID token from Google.")

    redirect_url = f"{FRONTEND_URL}#id_token={id_token_value}"
    print(f"Redirecting frontend to: {FRONTEND_URL}#id_token=... (token truncated)")
    return RedirectResponse(redirect_url)


# --- Original API Routes --- 

@router.get("/api/userinfo")
# Secure this endpoint with the new token verification dependency
async def get_userinfo(token_info: tuple[str, dict] = Depends(verify_google_token)):
    # The dependency already verified the token, we can just return the info
    _ , id_info = token_info # Unpack tuple, we only need id_info here
    # Return relevant user details from the decoded token
    return {
        "email": id_info.get("email"),
        "name": id_info.get("name"),
        "picture": id_info.get("picture"),
        # Add other fields from id_info if needed
    }
