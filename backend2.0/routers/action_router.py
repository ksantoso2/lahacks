from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth.auth import verify_google_token
from google.oauth2.credentials import Credentials

from services.gemini_service import parse_user_message, generate_doc_preview, generate_gemini_response
from services.google_service import get_drive_item_content, run_langchain_doc_creation
from services.analyze_service import analyze_content
from services.drive_cache import load_index
import json

router = APIRouter()

# --- Pending confirmation storage ---
# Structure: {user_token: {'state': 'state_name', 'file_name': 'name', 'original_message': 'msg', 'preview': '...'}}
# States: 'confirm_preview_gen', 'confirm_create'
pending_requests = {} 

# --- Chat History Storage ---
# Structure: {user_id: [{'role': 'user'/'model', 'parts': ['message content']}]}
chat_histories = {}

class UserQuery(BaseModel):
    message: str  # user message
    confirmation: bool | None = None  # True/False for standard confirmation
    regenerate: bool | None = None # True if user wants to regenerate preview
    skip_preview: bool | None = None # True if user wants to skip preview and create directly

@router.post("/ask")
async def handle_user_query(query: UserQuery, token_info: tuple[str, Credentials] = Depends(verify_google_token)):
    user_id, creds = token_info # Unpack user_id and Credentials object
    user_message = query.message
    confirmation_choice = query.confirmation
    regenerate_request = query.regenerate
    skip_request = query.skip_preview

    # --- Log state ---
    print(f"User token: {user_id[:10]}...")
    pending_data = pending_requests.get(user_id)
    print(f"Pending data: {pending_data}")
    print(f"Received query: message='{user_message}', confirmation={confirmation_choice}, regenerate={regenerate_request}, skip_preview={skip_request}")

    if user_id in pending_requests:
        pending = pending_requests[user_id]
        pending_state = pending['state']

        # --- Handle moveDoc pending state ---
        if pending_state == 'moveDoc':
            doc_name = pending['doc_name']

            # Step 1: Collect source_folder
            if not pending.get('source_folder'):
                pending['source_folder'] = user_message  # Capture source folder
                return {"message": f"Where would you like to move '{doc_name}' to?"}

            # Step 2: Collect target_folder
            elif not pending.get('target_folder'):
                pending['target_folder'] = user_message  # Capture target folder
                return {
                    "message": (
                        f"⚠️ Confirm: Move '{doc_name}' from '{pending['source_folder']}' "
                        f"to '{pending['target_folder']}'? (yes/no)"
                    ),
                    "needsConfirmation": True,
                    "confirmationType": "moveDoc"
                }

            # Step 3: Handle confirmation
            elif pending.get('confirmation_needed', True):
                if user_message.lower() in ["yes", "y"]:
                    from services.google_service import move_doc_to_folder
                    result_message = await move_doc_to_folder(
                        doc_name=pending['doc_name'],
                        source_folder=pending['source_folder'],
                        target_folder=pending['target_folder'],
                        creds=creds
                    )
                    del pending_requests[user_id]
                    return {"message": result_message}
                elif user_message.lower() in ["no", "n"]:
                    del pending_requests[user_id]
                    return {"message": "❌ Move operation canceled."}
                else:
                    return {"message": "Please respond with 'yes' or 'no'."}

        # --- Handle confirm_preview_gen / confirm_create pending states ---
        elif pending_state in ['confirm_preview_gen', 'confirm_create']:
            file_name = pending['file_name']
            original_message = pending.get('original_message')

            # --- State: Confirm Preview Generation --- 
            if pending_state == 'confirm_preview_gen':
                if confirmation_choice is True:
                    try:
                        print(f"Generating preview for '{file_name}'")
                        preview = await generate_doc_preview(file_name) # Pass only file_name
                        # Update state to confirm creation, store preview
                        pending_requests[user_id]['state'] = 'confirm_create'
                        pending_requests[user_id]['preview'] = preview
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
                        del pending_requests[user_id] # Clear pending on error
                        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {e}")
                elif confirmation_choice is False:
                    print("User cancelled preview generation.")
                    del pending_requests[user_id]
                    return {"success": False, "message": "❌ Preview generation canceled."}
                else:
                    # User sent a message instead of confirming - should not happen with buttons?
                    # For now, just remind them.
                    del pending_requests[user_id] # Clear state and re-parse message
                    print("Confirmation ambiguity. Clearing state and reprocessing message.")
                    # Fall through to re-process the message outside the confirmation block
            
            # --- State: Confirm Document Creation (or Regenerate) ---
            elif pending_state == 'confirm_create':
                preview = pending_requests[user_id].get('preview', '[Preview not available]')
                
                if regenerate_request is True:
                    try:
                        print(f"Regenerating preview for '{file_name}'")
                        new_preview = await generate_doc_preview(file_name) # Pass only file_name
                        pending_requests[user_id]['preview'] = new_preview # Update stored preview
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
                
                elif skip_request is True:
                    print(f"User skipped preview. Running LangChain creation for: {original_message}")
                    try:
                        doc_id, doc_url = await run_langchain_doc_creation(
                            original_request=original_message,
                            generated_title=file_name,
                            creds=creds
                        )

                        if doc_id and doc_url:
                            # Clear pending state on success
                            if user_id in pending_requests:
                                del pending_requests[user_id]
                            print(f"Document '{file_name}' created successfully (skipped preview). ID: {doc_id}")
                            # Return success message and document URL
                            return {
                                "message": f"OK, I've created the Google Doc: '{file_name}'. You can view it [here]({doc_url}).",
                                "action_required": None,
                                "doc_url": doc_url
                            }
                        else:
                            # Don't clear pending state on failure, maybe they want to retry?
                            # (Or maybe clear it? For now, keep it.)
                            print(f"Document creation failed for '{file_name}' (skipped preview).")
                            return {"message": f"Sorry, I couldn't create the document '{file_name}'. Please try again.", "action_required": None}
                    except Exception as e:
                        print(f"Error during skip preview creation: {e}")
                        return {"message": f"An error occurred while creating the document: {e}", "action_required": None}
                
                elif confirmation_choice is True:
                    try:
                        print(f"User confirmed. Running LangChain creation for: {original_message}")
                        doc_id, doc_url = await run_langchain_doc_creation(
                            original_request=original_message,
                            generated_title=file_name,
                            creds=creds
                        )

                        if doc_id and doc_url:
                            response_message = f"Document '{file_name}' created successfully! You can access it here: {doc_url}"
                            del pending_requests[user_id] # Clear state on success
                            return {
                                "success": True,
                                "message": response_message,
                                "docUrl": doc_url
                            }
                    except Exception as e:
                        print(f"Error creating doc after confirmation: {e}")
                        del pending_requests[user_id] # Clear pending on error
                        raise HTTPException(status_code=500, detail=f"Failed to create document: {e}")
                
                elif confirmation_choice is False:
                    print("User cancelled document creation.")
                    del pending_requests[user_id]
                    return {"success": False, "message": "❌ Document creation canceled."}
                
                else:
                    # User sent a message instead of confirming
                    del pending_requests[user_id] # Clear state and re-parse message
                    print("Confirmation ambiguity. Clearing state and reprocessing message.")
                    # Fall through to re-process the message outside the confirmation block


    # --- Step 2: No pending request - Parse user message with Gemini --- 
    # (This part runs only if no pending request was handled above)
    print("No pending request found or handled, parsing new message.")
    parsed = await parse_user_message(user_message)
    action = parsed.get("action_to_perform")

    # --- Handle Move Document Action ---
    if action == "moveDoc":
        doc_name = parsed.get("doc_name")
        source_folder = parsed.get("source_folder")
        target_folder = parsed.get("target_folder")

        pending_requests[user_id] = {
            'state': 'moveDoc',
            'doc_name': doc_name,
            'source_folder': source_folder,
            'target_folder': target_folder,
            'confirmation_needed': True
        }

        # Prompt for missing info
        if not source_folder:
            return {"message": f"Please provide the origin folder for '{doc_name}'."}
        if not target_folder:
            return {"message": f"Where would you like to move '{doc_name}' to?"}

        # If both folders are provided, ask for confirmation
        return {
            "message": (
                f"⚠️ Confirm: Move '{doc_name}' from '{source_folder}' to '{target_folder}'? (yes/no)"
            ),
            "needsConfirmation": True,
            "confirmationType": "moveDoc"
        }

    
    # --- Handle Create Document Action (Initial request) ---
    if action == "createDoc":
        file_name = parsed.get("name", "Untitled Document")
        try:
            # Store initial state: confirm preview generation
            pending_requests[user_id] = {
                'state': 'confirm_preview_gen',
                'file_name': file_name,
                'original_message': user_message # Store original msg for preview gen
            }
            print(f"📝 Storing initial pending request for {user_id}: state=confirm_preview_gen, file={file_name}")

            # Ask user to confirm PREVIEW generation
            return {
                "success": True,
                "message": f"I can create a document named **'{file_name}'**. Would you like me to generate a preview first?",
                "needsConfirmation": True,
                "confirmationType": "preview_gen" # Signal frontend type
            }
        except Exception as e:
             print(f"Error initiating createDoc flow: {e}")
             if user_id in pending_requests:
                 del pending_requests[user_id]
             raise HTTPException(status_code=500, detail=f"Failed to process document creation request: {e}")

    # --- Handle Analyze Action ---
    elif action == "analyze":
        target_name = parsed.get("target")
        analysis_query = parsed.get("query")
        
        if not analysis_query:
            raise HTTPException(status_code=400, detail="Analysis query is missing.")

        file_content_context = None # Renamed for clarity
        if target_name:
            print(f"Attempting to fetch context for target: {target_name}")
            try:
                # ASSUMPTION: get_drive_item_content exists in google_service
                file_content_context = await get_drive_item_content(target_name, creds) # Pass creds object
                if not file_content_context:
                     print(f"Warning: No content found or retrieved for target '{target_name}'. Proceeding without file context.")
                else:
                     print(f"Successfully fetched file context for '{target_name}'.")
            except Exception as e:
                print(f"Error fetching file context for '{target_name}': {e}")
                # Decide if you want to raise an error or proceed without file context

        # +++ Load Drive Index +++
        drive_index = load_index(user_id) or []
        print(f"Loaded drive index for analysis context ({len(drive_index)} items).")
        # +++ Get Chat History +++
        current_history = chat_histories.get(user_id, [])
        # +++++++++++++++++++++++
         
        # Call the analysis service with the query and potentially context
        analysis_result = await analyze_content(
            analysis_query,
            file_content_context=file_content_context, # Pass file content
            drive_index=drive_index,                # Pass drive index
            chat_history=current_history            # Pass chat history
        )
        
        # Unpack result and updated history
        analysis_result_dict, updated_history = analysis_result
        chat_histories[user_id] = updated_history # Store updated history

        if analysis_result_dict.get("error"):
            raise HTTPException(status_code=500, detail=analysis_result_dict["error"])
        else:
            return {
                "success": True,
                "message": analysis_result_dict.get("analysis", "Analysis complete."),
                "type": "analysis_result"
            }
            
    # --- Handle Unrecognized Action or Fallback --- 
    elif parsed.get("error"):
        raise HTTPException(status_code=400, detail=parsed.get("error"))
    else:
        print(f"Unrecognized action parsed: {action}. Falling back to general response.")
        try:
            drive_index = load_index(user_id) or []
            current_history = chat_histories.get(user_id, []) # Get current history

            if drive_index:
                index_prompt_lines = [f"- {item['name']} ({'Folder' if item.get('mimeType') == 'application/vnd.google-apps.folder' else 'File'}, id:{item['id']})" for item in drive_index[:200]]
                formatted_index = "\n".join(index_prompt_lines)
                drive_context = f"\nUser's Google Drive Contents (partial list):\n{formatted_index}\n---"
            else:
                drive_context = "\nUser's Google Drive Contents: (Could not load or is empty)"
            
            print(f"[Debug] Drive context length: {len(drive_context)} chars for fallback")
            response_content = await generate_gemini_response(
                user_message, 
                drive_context=drive_context,
                chat_history=current_history # Pass history
            )
            
            # Unpack response and updated history
            response_text, updated_history = response_content 
            chat_histories[user_id] = updated_history # Store updated history
            
            # Return the text response directly
            return {
                "success": True,
                "message": response_text,
                "type": "fallback_message"
            }
                
        except Exception as e: 
            print(f"Error generating fallback response: {e}")
            raise HTTPException(status_code=500, detail="Sorry, I encountered an error trying to respond.")
        
        except Exception as e:
            print(f"An error occurred in handle_user_query: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "message": f"An internal error occurred: {e}"}
