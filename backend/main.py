from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import google_auth_oauthlib.flow
import os
import json
import uvicorn
from datetime import datetime
import httpx

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # ADD THIS LINE FOR LOCAL DEV

app = FastAPI()

# Session middleware - needed for session handling
app.add_middleware(SessionMiddleware, secret_key="askgjdhslgs12r4")

# CORS middleware to allow requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models for request data
class StudyGuideRequest(BaseModel):
    startTime: Optional[str] = None
    endTime: Optional[str] = None

class QuizRequest(BaseModel):
    studyGuideContent: Optional[str] = None

# Helper function to check if user is authenticated
def get_auth_credentials(request: Request):
    credentials = request.session.get('credentials')
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return credentials

# Google OAuth settings
SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/documents"]
REDIRECT_URI = "http://localhost:8000/oauth2callback"

# --- Configuration ---
# Replace with your deployed Apps Script Web App URL
APPS_SCRIPT_URL = "YOUR_APPS_SCRIPT_WEB_APP_URL"

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
    
    # Store credentials in session for later use
    request.session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }
    
    # Redirect to frontend dashboard after successful authentication
    frontend_url = "http://localhost:5173/dashboard"
    return RedirectResponse(frontend_url)

# New API endpoints
@app.post("/logout")
async def logout(request: Request):
    # Clear the session
    request.session.clear()
    return {"message": "Successfully logged out"}

@app.post("/api/generate-study-guide")
async def generate_study_guide(request: Request, study_data: StudyGuideRequest, credentials: Dict = Depends(get_auth_credentials)):
    # This would use the Google Drive API to fetch documents and generate a study guide
    # For now, we'll return mock data
    return {
        "title": "Your Study Guide",
        "content": "This is a sample study guide generated based on your Google Docs. In a real implementation, this would analyze your documents from the time period and create a personalized study guide."
    }

@app.post("/api/generate-quiz")
async def generate_quiz(request: Request, quiz_data: QuizRequest, credentials: Dict = Depends(get_auth_credentials)):
    # This would use the study guide content to generate a quiz
    # For now, we'll return mock data
    return {
        "title": "Quiz Based on Your Study Materials",
        "questions": [
            {
                "question": "What is the capital of France?",
                "options": ["Paris", "London", "Berlin", "Madrid"],
                "answer": 0
            },
            {
                "question": "What is 2 + 2?",
                "options": ["3", "4", "5", "6"],
                "answer": 1
            },
            {
                "question": "Who wrote Romeo and Juliet?",
                "options": ["Charles Dickens", "Jane Austen", "William Shakespeare", "Mark Twain"],
                "answer": 2
            }
        ]
    }

async def call_apps_script(action: str, payload: dict, script_token: Optional[str] = None):
    """Sends a POST request to the Apps Script Web App endpoint."""
    if not APPS_SCRIPT_URL or APPS_SCRIPT_URL == "YOUR_APPS_SCRIPT_WEB_APP_URL":
        print("ERROR: APPS_SCRIPT_URL is not configured in main.py")
        return {"error": "Backend configuration error: Apps Script URL not set."}

    headers = {
        'Content-Type': 'application/json',
    }
    # If your Apps Script requires authentication, pass the token.
    # Make sure your Apps Script *validates* this token!
    if script_token:
        headers['Authorization'] = f'Bearer {script_token}'

    request_body = {
        "action": action,
        "data": payload
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"Calling Apps Script: {action} with payload: {payload}") # Debug log
            response = await client.post(APPS_SCRIPT_URL, json=request_body, headers=headers, timeout=30.0) # Added timeout
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            
            # Try to parse JSON, fall back to text if it fails
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"response_text": response.text} # Return raw text if not JSON

        except httpx.HTTPStatusError as exc:
            print(f"HTTP error calling Apps Script: {exc.response.status_code} - {exc.response.text}")
            return {"error": f"Apps Script Error: {exc.response.status_code}", "details": exc.response.text}
        except httpx.RequestError as exc:
            print(f"Request error calling Apps Script: {exc}")
            return {"error": f"Could not connect to Apps Script: {exc}"}
        except Exception as e:
            print(f"Generic error calling Apps Script: {e}")
            return {"error": f"An unexpected error occurred: {e}"}

if __name__ == "__main__":
    # Create a sample client_secret.json file if it doesn't exist
    # This is just for testing - in production, you'd use your actual Google OAuth credentials
    if not os.path.exists('client_secret.json'):
        print("Creating sample client_secret.json file for testing purposes")
        sample_config = {
            "web": {
                "client_id": "your-client-id.apps.googleusercontent.com",
                "project_id": "your-project-id",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": "your-client-secret",
                "redirect_uris": ["http://localhost:8000/oauth2callback"]
            }
        }
        with open('client_secret.json', 'w') as f:
            json.dump(sample_config, f)
        print("Sample client_secret.json created. Replace with real credentials for production use.")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)