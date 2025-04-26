from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth.auth import verify_google_token

from services.gemini_service import parse_user_message, generate_doc_preview, generate_gemini_response
from services.google_service import create_google_doc, get_drive_item_content
from services.analyze_service import analyze_content

router = APIRouter()

# --- Pending confirmation storage ---
pending_requests = {}  # {user_token: file_name}

class UserQuery(BaseModel):
    message: str  # user message can include 'yes' or 'no' response
    confirmation: bool | None = None  # True/False for confirmation

@router.post("/api/ask")
async def handle_user_query(query: UserQuery, token_info: tuple[str, dict] = Depends(verify_google_token)):
    user_message = query.message
    user_token, _ = token_info # This is the Access Token

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
                    f"Do you want to proceed? Please use the buttons below."
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
    
    action = parsed.get("action_to_perform")
    
    # --- Handle Create Document Action ---
    if action == "createDoc":
        file_name = parsed.get("name", "Untitled Document")
        try:
            # 1. Generate the preview based on the original message
            preview = await generate_doc_preview(user_message)

            # 2. Store the file name for confirmation
            pending_requests[user_token] = file_name
            print(f"📝 Storing pending request for {user_token}: {file_name}")

            # 3. Return the preview and ask for confirmation
            #    Do NOT create the document yet.
            return {
            "success": True,
            "message": (
                f"📝 I’ve drafted a preview for **'{file_name}'** based on your request:\n\n"
                f"> {preview}\n\n"
                f"Would you like me to create this document? Please use the buttons below."
            ),
            "needsConfirmation": True # Indicate frontend needs confirmation
            }
        except Exception as e:
             print(f"Error during preview generation or storing pending request: {e}")
             # Clean up pending request if it was stored before error
             if user_token in pending_requests:
                 del pending_requests[user_token]
             raise HTTPException(status_code=500, detail=f"Failed to process document creation request: {e}")

    # --- Handle Analyze Action ---
    elif action == "analyze":
        target_name = parsed.get("target")
        analysis_query = parsed.get("query")
        
        if not analysis_query:
            raise HTTPException(status_code=400, detail="Analysis query is missing.")

        context = None
        if target_name:
            print(f"Attempting to fetch context for target: {target_name}")
            try:
                # ASSUMPTION: get_drive_item_content exists in google_service
                context = await get_drive_item_content(target_name, user_token)
                if not context:
                     print(f"Warning: No content found or retrieved for target '{target_name}'. Proceeding without context.")
                     # Optionally inform the user item not found?
                     # return {"success": False, "message": f"Could not find or access '{target_name}'."}
                else:
                     print(f"Successfully fetched context for '{target_name}'.")
            except Exception as e:
                print(f"Error fetching context for '{target_name}': {e}")
                # Decide if we proceed without context or return error
                # For now, let's proceed without context but log the error
                # raise HTTPException(status_code=500, detail=f"Failed to fetch content for '{target_name}': {e}")
        
        # Call the analysis service with the query and potentially context
        analysis_result = await analyze_content(analysis_query, context)
        
        if analysis_result.get("error"):
             # Pass Gemini error back to client
             raise HTTPException(status_code=500, detail=analysis_result["error"])
        else:
            return {
                "success": True,
                "message": analysis_result.get("analysis", "Analysis complete."),
                "type": "analysis_result" # Add type for frontend
            }
            
    # --- Handle Unrecognized Action --- 
    elif parsed.get("error"):
        # If the parser itself returned an error
        raise HTTPException(status_code=400, detail=parsed.get("error"))
    else:
        # If parser succeeded but action wasn't recognized
        # Maybe Gemini hallucinated an action? Or prompt needs refinement?
        print(f"Unrecognized action parsed: {action}")
        # Return a generic response or try a general Gemini query?
        # For now, return a simple message.
        # Alternative: Call analyze_content with just the original user_message? 
        # analysis_result = await analyze_content(user_message, None)
        # ... return analysis_result ...
        return {
            "success": False,
            "message": "Sorry, I can only create documents or analyze content right now.",
            "type": "fallback_message"
        }
