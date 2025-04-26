import os
import json
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

# Import routers from other modules
from auth import router as auth_router
from chat import router as chat_router

# --- FastAPI App Setup --- 

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1' # For local development over HTTP

app = FastAPI()

# Session middleware - needed for session handling
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "a_default_secret_key_if_not_set")) # Use env var or default

# CORS middleware to allow requests from frontend
frontend_origins = [
    "http://localhost:5173", # Default Vite dev port
    "http://localhost:5174", # Another possible Vite port
    # Add production frontend URL(s) here eventually
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers --- 
app.include_router(auth_router)
app.include_router(chat_router)

# --- Root Endpoint (Optional) --- 
@app.get("/")
async def root():
    return {"message": "Welcome to the Google Drive AI Agent Backend"}

# --- Utility Functions (Example: Ensure client_secret.json exists) ---

def check_client_secret():
    CLIENT_SECRETS_FILE = "client_secret.json"
    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"\nWARNING: {CLIENT_SECRETS_FILE} not found.")
        print("Please download your OAuth 2.0 client credentials from Google Cloud Console")
        print("and save them as 'client_secret.json' in the backend directory.\n")
        # Optionally create a dummy file to avoid errors during initial setup?
        # try:
        #     with open(CLIENT_SECRETS_FILE, 'w') as f:
        #         json.dump({"web": {"client_id": "YOUR_CLIENT_ID", "client_secret": "YOUR_CLIENT_SECRET"}}, f)
        #     print("Created a placeholder client_secret.json. Please replace with your actual credentials.")
        # except Exception as e:
        #     print(f"Could not create placeholder file: {e}")

# --- Start the App --- 

if __name__ == "__main__":
    check_client_secret() # Check for credentials file before starting
    print(f"Starting server on http://0.0.0.0:8000")
    print(f"Allowed frontend origins: {frontend_origins}")
    uvicorn.run(app, host="0.0.0.0", port=8000)