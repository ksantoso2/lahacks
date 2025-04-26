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
import google.generativeai as genai
import os

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

class ChatMessage(BaseModel):
    message: str
    scriptToken: Optional[str] = None

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
# Gemini API Key (read from environment variable)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("\nWARNING: GEMINI_API_KEY environment variable not set. Intent parsing will fail.\n")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"\nERROR configuring Gemini SDK: {e}\n")
        GEMINI_API_KEY = None # Disable Gemini if config fails

# Gemini Model Configuration
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Or another suitable model
GEMINI_SYSTEM_PROMPT = """You are an instruction analyzer that parses the text request of a user using a Google Drive related AI Agent. You are looking for several specific types of instructions, which you will send back in the form of a json object containing ONLY the fields relevant to the detected instruction. DO NOT add any explanation or surrounding text, ONLY output the JSON.

The instructions and corresponding JSON fields are:
1. Internet Search: If the user wants to search the internet, return: {"search": true, "query": "<search query>"}
2. Find File: If the user wants to find/list/search files in Drive, return: {"action_to_perform": "listFiles", "query": "<optional file name or description>"}
3. Create File: If the user wants to create a file (e.g., doc, sheet), return: {"action_to_perform": "createDoc", "name": "<file name>"}
4. Delete File: If the user wants to delete a file, return: {"action_to_perform": "deleteFile", "name": "<file name>"}
5. Unclear/General Chat: If the instruction doesn't match the above or seems like general conversation, return: {"action_to_perform": "chat", "text": "<original user text>"}

Extract the relevant parameters like file name or search query accurately. If a parameter isn't provided by the user, you can omit it from the JSON or set it to null. Always include "action_to_perform" unless it's an internet search.

Example User Request: "Can you create a google doc called 'My Project Ideas'?"
Example JSON Output: {"action_to_perform": "createDoc", "name": "My Project Ideas"}

Example User Request: "search the web for recent AI news"
Example JSON Output: {"search": true, "query": "recent AI news"}

Example User Request: "list my recent documents"
Example JSON Output: {"action_to_perform": "listFiles", "query": "recent documents"}

Example User Request: "delete the file named report.docx"
Example JSON Output: {"action_to_perform": "deleteFile", "name": "report.docx"}

Example User Request: "hello there"
Example JSON Output: {"action_to_perform": "chat", "text": "hello there"}
"""

# Replace with your deployed Apps Script Web App URL
APPS_SCRIPT_URL = "https://script.googleapis.com/v1/scripts/AKfycbzMfveFqS3OBodrIsfUrsB-u0T4ZvxyOXwJwq2-z_PTmN1f2rJTGOqZ523MHA0-zC1L:run/"

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

@app.post("/api/chat")
async def handle_chat(chat_message: ChatMessage, request: Request):
    user_message = chat_message.message
    token = chat_message.scriptToken # Passed from frontend (originally from Apps Script)
    
    print(f"User Message: {user_message}, Token provided: {'Yes' if token else 'No'}")

    # --- 1. Get Instructions from Gemini --- 
    instructions = await get_instructions_from_gemini(user_message)
    print(f"Gemini Instructions: {instructions}") # Debug log

    agent_response = "Sorry, I couldn't process that request." # Default error response

    # --- 2. Handle Gemini Response --- 
    if not instructions or 'error' in instructions:
        agent_response = instructions.get('details', agent_response)
        print(f"Error from Gemini or parsing: {agent_response}")
        # Return error or default response directly

    elif instructions.get('search') is True:
        # TODO: Implement web search logic here if needed
        search_query = instructions.get('query', 'Unknown query')
        agent_response = f"Okay, searching the web for: '{search_query}' (Web search not implemented yet)."
        # Return search confirmation

    elif 'action_to_perform' in instructions:
        action = instructions['action_to_perform']
        
        if action == "chat":
            # Handle simple chat - maybe use Gemini again for a conversational response?
            # For now, just acknowledge
            agent_response = f"Received chat message: '{instructions.get('text', user_message)}'"
            # Return chat acknowledgement
        
        elif action in ["listFiles", "createDoc", "deleteFile"]:
            # Prepare payload for Apps Script
            # We assume Gemini returns the correct keys ('query', 'name') based on the action
            payload = {k: v for k, v in instructions.items() if k != 'action_to_perform'}
            
            # Call the Apps Script helper function
            apps_script_response = await call_apps_script(action, payload, token)
            
            # Formulate response based on Apps Script result
            if apps_script_response and 'error' in apps_script_response:
                 agent_response = f"Error interacting with Google Drive: {apps_script_response['error']} - {apps_script_response.get('details', '')}"
            elif apps_script_response:
                 # Format the successful response nicely
                 try:
                    response_str = json.dumps(apps_script_response, indent=2)
                 except TypeError:
                    response_str = str(apps_script_response)
                 agent_response = f"Google Drive action '{action}' completed. Response:\n```json\n{response_str}\n```"
            else:
                 agent_response = f"Google Drive action '{action}' called, but received no response."
            # Return Apps Script result processing

        else:
            # Unknown action from Gemini
            agent_response = f"Received unknown action '{action}' from analysis."
            # Return unknown action message

    else:
        # Gemini response format unexpected
        agent_response = f"Received unexpected analysis format: {instructions}"
        # Return unexpected format message
        
    # --- 3. Return final response to Frontend --- 
    return {"response": agent_response}

async def get_instructions_from_gemini(user_message: str) -> dict:
    """Uses Gemini to parse the user message and return structured instructions."""
    if not GEMINI_API_KEY:
        print("Gemini API Key not configured, skipping analysis.")
        # Fallback behavior: treat as simple chat
        return {"action_to_perform": "chat", "text": user_message}
        
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME, system_instruction=GEMINI_SYSTEM_PROMPT)
        print(f"Sending to Gemini: {user_message}") # Debug log
        response = await model.generate_content_async(user_message)

        # Clean up potential markdown/formatting issues
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        print(f"Gemini Raw Response: {cleaned_text}") # Debug log
        
        # Attempt to parse the JSON response
        instructions = json.loads(cleaned_text)
        return instructions
    except json.JSONDecodeError as e:
        print(f"Error decoding Gemini JSON response: {e}")
        print(f"Gemini raw text was: {response.text}")
        return {"error": "Failed to parse analysis", "details": response.text}
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return {"error": f"Gemini API Error: {e}"}

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