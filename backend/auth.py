import os
import json
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from requests_oauthlib import OAuth2Session
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

router = APIRouter() # Use APIRouter for modular routes

# --- OAuth Configuration --- 
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
    "https://www.googleapis.com/auth/drive.readonly", # Read access to Drive files
    "https://www.googleapis.com/auth/documents.readonly" # Read access for Google Docs
]

# Load client secrets and set redirect URI
CLIENT_ID = None
CLIENT_SECRET = None
REDIRECT_URI = "http://localhost:8000/oauth2callback" # Should match Google Cloud console

try:
    with open(CLIENT_SECRETS_FILE, 'r') as f:
        secrets = json.load(f)
        CLIENT_ID = secrets['web']['client_id']
        CLIENT_SECRET = secrets['web']['client_secret']
except FileNotFoundError:
    print(f"\nERROR: {CLIENT_SECRETS_FILE} not found. Please download it from Google Cloud Console.\n")
except KeyError:
    print(f"\nERROR: Invalid format in {CLIENT_SECRETS_FILE}. Missing 'web' -> 'client_id' or 'client_secret'.\n")


# Helper function to check if user is authenticated
def get_auth_credentials(request: Request) -> Credentials:
    credentials_dict = request.session.get('credentials')
    if not credentials_dict:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # Add token refresh logic if necessary (or handle it in API calls)
    credentials = Credentials(**credentials_dict)
    # Example refresh (if needed before making an API call):
    # if credentials.expired and credentials.refresh_token:
    #     try:
    #         credentials.refresh(Request())
    #         request.session['credentials'] = json.loads(credentials.to_json())
    #     except Exception as e:
    #         print(f"Error refreshing token: {e}")
    #         raise HTTPException(status_code=401, detail="Could not refresh token")
            
    return credentials


# --- Authentication Routes --- 

@router.get("/login")
async def login(request: Request):
    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="OAuth client secrets not configured.")
        
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true"
    )
    request.session['state'] = state
    return RedirectResponse(authorization_url)

@router.get("/oauth2callback")
async def oauth2callback(request: Request):
    state = request.session.get('state')
    # Basic state validation (consider more robust validation)
    if not state or state != request.query_params.get('state'): 
        raise HTTPException(status_code=403, detail="Invalid state parameter")

    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI
    )
    # Use the full URL for fetch_token
    flow.fetch_token(authorization_response=str(request.url))

    credentials = flow.credentials
    request.session['credentials'] = json.loads(credentials.to_json()) 

    # Redirect to frontend (adjust URL if needed)
    frontend_url = "http://localhost:5173/"
    return RedirectResponse(frontend_url)

@router.post("/logout")
async def logout(request: Request):
    request.session.pop('credentials', None)
    request.session.pop('state', None)
    return {"message": "Successfully logged out"}

@router.get("/api/userinfo")
async def get_userinfo(request: Request, credentials: Credentials = Depends(get_auth_credentials)):
    try:
        google_session = OAuth2Session(CLIENT_ID, token=json.loads(credentials.to_json()))
        userinfo = google_session.get('https://www.googleapis.com/oauth2/v3/userinfo').json()
        return userinfo
    except Exception as e:
        print(f"Error fetching user info: {e}")
        # Attempt to clear potentially bad credentials
        request.session.pop('credentials', None) 
        raise HTTPException(status_code=500, detail="Failed to fetch user info")
