from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth.auth import verify_google_token

from services.gemini_service import parse_user_message, generate_doc_preview, generate_gemini_response
from services.google_service import create_google_doc, get_drive_item_content
from services.analyze_service import analyze_content

router = APIRouter()

# --- Pending confirmation storage ---
# Structure: {user_token: {'state': 'state_name', 'file_name': 'name', 'original_message': 'msg', 'preview': '...'}}
# States: 'confirm_preview_gen', 'confirm_create'
pending_requests = {} 

class UserQuery(BaseModel):
    message: str  # user message
    confirmation: bool | None = None  # True/False for standard confirmation
    regenerate: bool | None = None # True if user wants to regenerate preview

@router.post("/api/ask")
async def handle_user_query(query: UserQuery, token_info: tuple[str, dict] = Depends(verify_google_token)):
    user_message = query.message
    user_token, _ = token_info
    confirmation_choice = query.confirmation
    regenerate_request = query.regenerate

    # --- Log state ---
    print(f"User token: {user_token[:10]}...")
    pending_data = pending_requests.get(user_token)
    print(f"Pending data: {pending_data}")
    print(f"Received query: message='{user_message}', confirmation={confirmation_choice}, regenerate={regenerate_request}")

    # --- Step 1: Check for and handle pending confirmation --- 
    if user_token in pending_requests:
        pending_state = pending_requests[user_token]['state']
        file_name = pending_requests[user_token]['file_name']
        original_message = pending_requests[user_token].get('original_message')

        print(f"⚠️ Handling pending state: {pending_state} for file: {file_name}")

        # --- State: Confirm Preview Generation --- 
        if pending_state == 'confirm_preview_gen':
            if confirmation_choice is True:
                try:
                    print(f"Generating preview for '{file_name}' based on: {original_message}")
                    preview = await generate_doc_preview(original_message)
                    # Update state to confirm creation, store preview
                    pending_requests[user_token]['state'] = 'confirm_create'
                    pending_requests[user_token]['preview'] = preview
                    print(f"Preview generated. New state: confirm_create")
                    return {
                        "success": True,
                        "message": (
                            f"📝 Okay, here's a preview for **'{file_name}'**:\n\n"
                            f"> {preview}\n\n"
                            f"Would you like me to create this document?"
                        ),
                        "needsConfirmation": True,
                        "confirmationType": "doc_create", # Signal frontend type
                        "allowRegenerate": True      # Signal frontend can show regenerate
                    }
                except Exception as e:
                    print(f"Error generating preview: {e}")
                    del pending_requests[user_token] # Clear pending on error
                    raise HTTPException(status_code=500, detail=f"Failed to generate preview: {e}")
            elif confirmation_choice is False:
                print("User cancelled preview generation.")
                del pending_requests[user_token]
                return {"success": False, "message": "❌ Preview generation canceled."}
            else:
                # User sent a message instead of confirming - should not happen with buttons?
                # For now, just remind them.
                del pending_requests[user_token] # Clear state and re-parse message
                print("Confirmation ambiguity. Clearing state and reprocessing message.")
                # Fall through to re-process the message outside the confirmation block
        
        # --- State: Confirm Document Creation (or Regenerate) ---
        elif pending_state == 'confirm_create':
            preview = pending_requests[user_token].get('preview', '[Preview not available]')
            
            if regenerate_request is True:
                try:
                    print(f"Regenerating preview for '{file_name}' based on: {original_message}")
                    new_preview = await generate_doc_preview(original_message)
                    pending_requests[user_token]['preview'] = new_preview # Update stored preview
                    print(f"Preview regenerated.")
                    return {
                        "success": True,
                        "message": (
                            f"📝 Okay, here's a new preview for **'{file_name}'**:\n\n"
                            f"> {new_preview}\n\n"
                            f"Would you like me to create this document now?"
                        ),
                        "needsConfirmation": True,
                        "confirmationType": "doc_create",
                        "allowRegenerate": True
                    }
                except Exception as e:
                    print(f"Error regenerating preview: {e}")
                    # Don't delete pending state here, let user try again or cancel
                    raise HTTPException(status_code=500, detail=f"Failed to regenerate preview: {e}")
            
            elif confirmation_choice is True:
                try:
                    print(f"User confirmed creation for '{file_name}'. Creating document...")
                    file_id, file_url = await create_google_doc(file_name, user_token)
                    del pending_requests[user_token] # Clear state on success
                    return {
                        "success": True,
                        "message": f"✅ Document '{file_name}' created! Here's the link: {file_url}",
                        "docUrl": file_url
                    }
                except Exception as e:
                    print(f"Error creating doc after confirmation: {e}")
                    del pending_requests[user_token] # Clear pending on error
                    raise HTTPException(status_code=500, detail=f"Failed to create document: {e}")
            
            elif confirmation_choice is False:
                print("User cancelled document creation.")
                del pending_requests[user_token]
                return {"success": False, "message": "❌ Document creation canceled."}
            
            else:
                # User sent a message instead of confirming
                del pending_requests[user_token] # Clear state and re-parse message
                print("Confirmation ambiguity. Clearing state and reprocessing message.")
                # Fall through to re-process the message outside the confirmation block

    # --- Step 2: No pending request - Parse user message with Gemini --- 
    # (This part runs only if no pending request was handled above)
    print("No pending request found or handled, parsing new message.")
    parsed = await parse_user_message(user_message)
    action = parsed.get("action_to_perform")
    
    # --- Handle Create Document Action (Initial request) ---
    if action == "createDoc":
        file_name = parsed.get("name", "Untitled Document")
        try:
            # Store initial state: confirm preview generation
            pending_requests[user_token] = {
                'state': 'confirm_preview_gen',
                'file_name': file_name,
                'original_message': user_message # Store original msg for preview gen
            }
            print(f"📝 Storing initial pending request for {user_token}: state=confirm_preview_gen, file={file_name}")

            # Ask user to confirm PREVIEW generation
            return {
                "success": True,
                "message": f"I can create a document named **'{file_name}'**. Would you like me to generate a preview first?",
                "needsConfirmation": True,
                "confirmationType": "preview_gen" # Signal frontend type
            }
        except Exception as e:
             print(f"Error initiating createDoc flow: {e}")
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
                else:
                     print(f"Successfully fetched context for '{target_name}'.")
            except Exception as e:
                print(f"Error fetching context for '{target_name}': {e}")
        
        # Call the analysis service with the query and potentially context
        analysis_result = await analyze_content(analysis_query, context)
        
        if analysis_result.get("error"):
             raise HTTPException(status_code=500, detail=analysis_result["error"])
        else:
            return {
                "success": True,
                "message": analysis_result.get("analysis", "Analysis complete."),
                "type": "analysis_result"
            }
            
    # --- Handle Unrecognized Action or Fallback --- 
    elif parsed.get("error"):
        raise HTTPException(status_code=400, detail=parsed.get("error"))
    else:
        print(f"Unrecognized action parsed: {action}. Falling back to general response.")
        # Fallback: Use Gemini for a general response instead of specific action
        try:
            fallback_response = await generate_gemini_response(user_message)
            return {
                "success": True, 
                "message": fallback_response,
                "type": "fallback_message"
            }
        except Exception as e:
            print(f"Error generating fallback response: {e}")
            raise HTTPException(status_code=500, detail="Sorry, I encountered an error trying to respond.")
