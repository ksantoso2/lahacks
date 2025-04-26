from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth.auth import verify_google_token
from services.gemini_service import parse_user_message
from services.google_service import create_google_doc

router = APIRouter()

class UserQuery(BaseModel):
    message: str

@router.post("/api/ask")
async def handle_user_query(query: UserQuery, token_info: tuple[str, dict] = Depends(verify_google_token)):
    user_message = query.message
    user_token, _ = token_info

    parsed = await parse_user_message(user_message)

    # Log parsed output for debugging
    print("Gemini Parsed Output:", parsed)

    if parsed.get("action_to_perform") == "createDoc":
        file_name = parsed.get("name", "Untitled Document")
        file_id, file_url = await create_google_doc(file_name, user_token)
        return {
            "success": True,
            "message": f"✅ Document '{file_name}' created!",
            "docUrl": file_url
        }
    else:
        # Send back Gemini's understanding as feedback
        return {
            "success": False,
            "message": "⚠️ Sorry, only document creation is supported right now.",
            "geminiParsed": parsed
        }
