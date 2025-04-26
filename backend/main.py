from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import google_auth_oauthlib.flow
import os

app = FastAPI()

# Session middleware - needed for session handling
app.add_middleware(SessionMiddleware, secret_key="askgjdhslgs12r4")

# Google OAuth settings
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/documents"]
REDIRECT_URI = "http://localhost:8000/oauth2callback"

@app.get("/")
async def root():
    return {"message": "Hello, go to /login to start Google Auth!"}

@app.get("/login")
async def login(request: Request):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI

    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

    request.session['state'] = state
    return RedirectResponse(authorization_url)

@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    state = request.session.get('state')
    if not state:
        return {"error": "State not found in session. Please start the authentication process again."}

    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        scopes=SCOPES,
        state=state
    )
    flow.redirect_uri = REDIRECT_URI

    authorization_response = str(request.url)
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    return {"message": "Authentication successful!"}
