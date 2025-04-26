from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from google_auth_oauthlib import Flow
from googleapiclient.discovery import build
import os, pathlib 

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

# Path to your OAuth 2.0 client secrets
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/documents"]
REDIRECT_URI = "http://localhost:8000/oauth2callback"

# Start OAuth flow
@app.get("/auth")
async def auth(request: Request):
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI
    )
    auth_url, state = flow.authorization_url(prompt='consent')
    request.session['state'] = state
    return RedirectResponse(auth_url)

# OAuth callback
@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    state = request.session.get('state')
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRETS_FILE,
        scopes=SCOPES,
        state=state,
        redirect_uri=REDIRECT_URI
    )
    flow.fetch_token(authorization_response=str(request.url))

    credentials = flow.credentials
    request.session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    return RedirectResponse("/success")

@app.get("/success")
async def success():
    return {"message": "Authorization successful. You can now create files."}

# Create a Google Doc
@app.post("/create-doc")
async def create_doc(request: Request):
    creds_info = request.session.get("credentials")
    if not creds_info:
        return {"error": "User not authenticated"}

    from google.oauth2.credentials import Credentials
    creds = Credentials(**creds_info)

    docs_service = build('docs', 'v1', credentials=creds)
    document = docs_service.documents().create(body={"title": "Gemini Study Guide"}).execute()

    return {"docId": document.get("documentId"), "title": document.get("title")}