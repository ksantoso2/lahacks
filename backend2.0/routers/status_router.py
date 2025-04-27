from fastapi import APIRouter, Depends, HTTPException
# Make sure this import path is correct for your project structure
from auth.auth import verify_google_token
from services import drive_cache
# Needed for the type hint in verify_google_token dependency
from google.oauth2.credentials import Credentials

router = APIRouter()

@router.get("/api/cache-status")
async def get_cache_status(token_info: tuple[str, Credentials] = Depends(verify_google_token)):
    """Checks if the drive cache file for the logged-in user exists."""
    user_id, _ = token_info # Get user_id from verified session
    cache_file = drive_cache.cache_path(user_id)

    if cache_file.exists():
        return {"status": "ready"}
    else:
        # The file doesn't exist, implying the background crawl isn't finished
        return {"status": "pending"}
