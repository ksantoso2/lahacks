import os
from dotenv import load_dotenv
load_dotenv()

import uvicorn
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2.credentials import Credentials
from starlette.middleware.sessions import SessionMiddleware
from routers import action_router 
from routers import status_router # Add this line
from auth.auth import router as auth_router, verify_google_token
from services.drive_cache import load_index
from services.google_service import list_all_drive_items, ensure_drive_index
import json

# --- App Setup ---
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # Allow OAuth over HTTP for local dev

app = FastAPI()

# --- Session Middleware ---
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "a_default_secret_key"),
    max_age=7 * 24 * 60 * 60, 
    https_only=False, 
    # same_site='lax' 
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(action_router.router, prefix="/api", tags=["actions"]) # Corrected: Access the 'router' attribute
app.include_router(status_router.router) # Add this line
# --- Root endpoint ---
@app.get("/")
async def root():
    return {"message": "Google Drive Copilot Backend"}

# --- Protected User Info Endpoint --- 
@app.get("/api/userinfo")
async def get_user_info(request: Request, token_info: tuple = Depends(verify_google_token)):
    user_id, _ = token_info
    return {"user_id": user_id}

# +++ NEW Initial Context Endpoint +++
@app.get("/api/initial-context")
async def get_initial_context(token_info: tuple[str, Credentials] = Depends(verify_google_token)):
    """Endpoint called on frontend load to get user ID and ensure Drive index is ready."""
    user_id, creds = token_info
    if not user_id or not creds:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        # Ensure the index is up-to-date (or created)
        drive_index = await ensure_drive_index(user_id, creds)
        print(f"Loaded drive index cache for initial context. Found {len(drive_index or [])} items.")

        return {
            "user_id": user_id,
            "drive_index": drive_index or []
        }
    except Exception as e:
        print(f"--- Error fetching initial context: {e} ---")
        raise HTTPException(status_code=500, detail="Failed to fetch initial context")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
