import os
import uvicorn
from fastapi import FastAPI, Depends, Request
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from routers import action_router 
from auth.auth import router as auth_router, verify_google_token
from services.drive_cache import load_index

load_dotenv()

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
async def get_initial_context(token_info: tuple = Depends(verify_google_token)):
    """
    Provides initial context to the frontend upon loading,
    confirming the user is logged in and returning their ID
    and the cached Google Drive index.
    """
    user_id, _ = token_info # Unpack user_id from the dependency result
    print(f"Providing initial context for user_id: {user_id}")

    # Load the cached index for the user
    drive_index = load_index(user_id)
    print(f"Loaded drive index cache for initial context. Found {len(drive_index or [])} items.")

    return {
        "user_id": user_id,
        "drive_index": drive_index or []
    }
# +++++++++++++++++++++++++++++++++++++

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
