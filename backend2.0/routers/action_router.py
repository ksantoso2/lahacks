from fastapi import APIRouter, Depends
from pydantic import BaseModel
from auth.auth import verify_google_token
from services.gemini_service import parse_user_message, generate_doc_preview, generate_gemini_response
from services.google_service import create_google_doc

router = APIRouter()

# --- Pending confirmation storage ---
pending_requests = {}  # {user_token: file_name}

class UserQuery(BaseModel):
    message: str  # user message can include 'yes' or 'no' response
    confirmation: bool | None = None  # True/False for confirmation

@router.post("/api/ask")
async def handle_user_query(query: UserQuery, token_info: tuple[str, dict] = Depends(verify_google_token)):
    user_message = query.message
    user_token, _ = token_info

    # --- Log pending requests ---
    print(f"User token: {user_token}")
    print(f"Pending requests: {pending_requests}")

    # --- Step 1: Check for pending confirmation ---
    if user_token in pending_requests:
        print(f"⚠️ Pending request detected for {user_token}: {pending_requests[user_token]}")
    
        file_name = pending_requests[user_token]  # <-- Don't pop here!

        if query.confirmation is None:
            return {
                "success": True,
                "message": (
                    f"📝 You are about to create a document named **'{file_name}'**.\n"
                    f"Do you want to proceed? Reply **yes** or **no**."
                )
            }

        # Only pop after processing confirmation
        file_name = pending_requests.pop(user_token)

        if query.confirmation is True:
            file_id, file_url = await create_google_doc(file_name, user_token)
            return {
                "success": True,
                "message": f"✅ Document '{file_name}' created! Here's the link: {file_url}",
                "docUrl": file_url
            }
        elif query.confirmation is False:
            return {
                "success": False,
                "message": "❌ Action canceled. No document was created."
            }


    # --- Step 2: No pending request - Parse user message with Gemini ---
    parsed = await parse_user_message(user_message)
    print(f"Gemini parsed output: {parsed}")

    if parsed.get("action_to_perform") == "createDoc":
        file_name = parsed.get("name", "Untitled Document")
        preview = await generate_doc_preview(file_name)

        # Store pending confirmation (waiting for user response)
        pending_requests[user_token] = file_name

        return {
            "success": True,
            "message": (
                f"📝 I’ve drafted a preview for **'{file_name}'**:\n\n"
                f"{preview}\n\n"
                f"Would you like me to create this document? Reply **yes** or **no**."
            )
        }
    else:
        response = await generate_gemini_response(user_message)
        return {
            "success": False,
            "message": response
        }

