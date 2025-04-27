from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from auth.auth import verify_google_token
from google.oauth2.credentials import Credentials
import traceback

from services.gemini_service import parse_user_message, generate_doc_preview, generate_gemini_response
from services.google_service import (
    get_drive_item_content,
    run_langchain_doc_creation,
    get_google_drive_url, 
    find_item_by_name,    
    move_doc_to_folder    
)
from services.analyze_service import analyze_content
from services.drive_cache import load_index
import json
FOLDER_MIME = "application/vnd.google-apps.folder"
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

    try:
        user_message = query.message
        confirmation_choice = query.confirmation
        regenerate_request = query.regenerate
        skip_request = query.skip_preview

        # --- Log state ---
        print(f"User token: {user_id[:10]}...")
        pending_data = pending_requests.get(user_id)
        print(f"Pending data: {pending_data}")
        print(f"Received query: message='{user_message}', confirmation={confirmation_choice}, regenerate={regenerate_request}, skip_preview={skip_request}")

        pending_state = None  # Initialize pending_state here

        # --- Step 1: Check for pending confirmation request & Extract State ---
        if user_id in pending_requests:
            pending = pending_requests[user_id]
            print(f"Pending data: {pending}") # Debug log pending data

            if 'state' not in pending:
                print(f"ERROR: Pending data for user {user_id[:10]} missing 'state' key: {pending}. Clearing state.")
                del pending_requests[user_id]
                # Let pending_state remain None, fall through
            else:
                pending_state = pending['state'] # Assign state if valid
                print(f"User {user_id[:10]} has pending state: {pending_state}")

        # --- Step 2: Handle Pending State (if one was found) ---
        if pending_state:
            # Re-fetch pending data in case it was cleared above (though unlikely needed now)
            if user_id not in pending_requests:
                 print(f"WARNING: Pending state '{pending_state}' detected but request data missing for user {user_id[:10]}. Treating as new request.")
                 pending_state = None # Force fallthrough
            else:
                 pending = pending_requests[user_id]

                 # --- Handle moveDoc pending state --- (This block runs only if pending_state is valid)
                 if pending_state == 'moveDoc_initial':
                    # Step 1: Ask for destination folder
                    file_to_move = pending.get('file_to_move')
                    file_url = get_google_drive_url(file_to_move) if file_to_move else pending.get('doc_name')
                    file_display_name = f"[{pending['doc_name']}]({file_url})" if file_url else pending['doc_name']

                    pending['state'] = 'moveDoc_target_pending' # Update state
                    print(f"State updated to moveDoc_target_pending for user {user_id[:10]}...")
                    return {
                        "message": f"Where would you like to move {file_display_name} to? Please specify the destination folder name."
                    }
                 elif pending_state == 'moveDoc_target_pending':
                    # Step 2: Validate destination folder and ask for confirmation
                    target_folder_name = user_message
                    target_folder = find_item_by_name(target_folder_name, user_id)

                    file_to_move = pending.get('file_to_move') # Retrieve stored file info
                    file_display_name = pending.get('file_display_name', pending.get('doc_name')) # Use stored display name

                    if not target_folder:
                        return {"message": f"❌ Sorry, I couldn't find a folder named '{target_folder_name}'. Please specify a valid destination folder name."}
                    elif target_folder.get('mimeType') != FOLDER_MIME:
                        return {"message": f"❌ Sorry, '{target_folder_name}' is not a folder. Please specify a valid destination folder name."}
                    else:
                        # Valid folder found, store details and ask for confirmation
                        pending['target_folder'] = target_folder
                        pending['state'] = 'moveDoc_confirm_pending'
                        target_folder_url = get_google_drive_url(target_folder)
                        target_folder_display_name = f"[{target_folder_name}]({target_folder_url})" if target_folder_url else target_folder_name

                        print(f"State updated to moveDoc_confirm_pending for user {user_id[:10]}...")
                        return {
                            "message": f"Confirm: Move {file_display_name} to the folder {target_folder_display_name}?",
                            "needsConfirmation": True,
                            "confirmationType": "moveDoc" # Make sure frontend handles this type
                        }
                 elif pending_state == 'moveDoc_confirm_pending':
                    # Step 3: Handle confirmation and execute move
                    if confirmation_choice is True:
                        file_to_move = pending['file_to_move']
                        target_folder = pending['target_folder']
                        current_parent_id = file_to_move.get('parents', [None])[0] # Get first parent

                        if not current_parent_id:
                            # This shouldn't happen if find_item_by_name worked, but handle defensively
                            print(f"Error: Could not determine current parent for file ID {file_to_move.get('id')}")
                            # Return the error *before* deleting the state
                            return {"message": "❌ Error: Could not determine the file's current location."}

                        print(f"Executing move: file_id={file_to_move['id']}, current_parent={current_parent_id}, target_folder={target_folder['id']}")
                        result_message = await move_doc_to_folder(
                            file_id=file_to_move['id'],
                            current_parent_id=current_parent_id,
                            target_folder_id=target_folder['id'],
                            creds=creds,
                            doc_name=file_to_move.get('name', 'Unknown File') # Pass name for logging
                        )
                        del pending_requests[user_id] # Delete state after successful move
                        print(f"Move operation finished for user {user_id[:10]}, pending state cleared.")
                        return {"message": result_message}
                    elif confirmation_choice is False:
                        del pending_requests[user_id] # Delete state on cancellation
                        print(f"Move operation cancelled by user {user_id[:10]}, pending state cleared.")
                        return {"message": "❌ Move operation canceled."}
                    else:
                        # Should not happen if frontend sends True/False, but handle just in case
                        print(f"Invalid confirmation choice received: {confirmation_choice}")
                        return {"message": "Please confirm by clicking 'Yes' or 'No'."}
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
            # --- Handle unexpected state --- (This is the 'else' for the pending_state checks)
        else:
            print(f"WARNING: Unhandled pending state '{pending_state}' for user {user_id[:10]}. Clearing state.")
            if user_id in pending_requests: # Check before deleting
                del pending_requests[user_id]
            pending_state = None # Ensure fallthrough
            # Fall through to Step 3 (treat as new request)

        # --- Step 3: No pending request OR fallthrough from unhandled/missing state ---
        # This section is reached if pending_state remained None OR if an unhandled state fell through
        if not pending_state: # Explicitly check if we need to handle as new request
            print("Parsing user message as a new request (no pending action handled).") # Clarify log message
            parsed = await parse_user_message(user_message)
            action = parsed.get("action_to_perform")

            # --- Handle specific actions first ---
            if action == "moveDoc":
                doc_name = parsed.get("doc_name")
                if not doc_name:
                     # Handle case where Gemini couldn't extract the doc name
                    return {"message": "Which document would you like to move?"}

                # Find the file first
                file_to_move = find_item_by_name(doc_name, user_id)
                if not file_to_move:
                    # Don't set pending state if file not found
                    return {"message": f"❌ Sorry, I couldn't find a file named '{doc_name}' in your Drive."}
                else:
                    # File found, store details and set state to ask for target
                    file_url = get_google_drive_url(file_to_move)
                    file_display_name = f"[{doc_name}]({file_url})" if file_url else doc_name

                    pending_requests[user_id] = {
                        'state': 'moveDoc_initial', # Set the state
                        'doc_name': doc_name,
                        'file_to_move': file_to_move,
                        'file_display_name': file_display_name
                    }
                    print(f"File '{doc_name}' found (ID: {file_to_move.get('id')}). Setting state to moveDoc_initial for user {user_id[:10]}...")

                    # --- Instead of recursing, return the prompt for the 'moveDoc_initial' state ---
                    return {
                        "message": f"Where would you like to move {file_display_name} to? Please specify the destination folder name."
                    }
                    # --- Remove recursive call ---
                    # return await handle_user_query(query, token_info)

            # --- Handle Create Document Action (Initial request) ---
            elif action == "createDoc":
                file_name = parsed.get("name", "Untitled Document")
                original_message = user_message # Store the original request for LangChain
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
                # Format index with URLs for the analysis prompt
                index_prompt_lines = []
                for item in drive_index:
                    url = get_google_drive_url(item)
                    name = item.get('name', 'Unnamed Item')
                    item_type = 'Folder' if item.get('mimeType') == 'application/vnd.google-apps.folder' else 'File'
                    if url:
                        index_prompt_lines.append(f"- [{name}]({url}) ({item_type})")
                    else:
                        index_prompt_lines.append(f"- {name} ({item_type})") # Fallback if no URL

                formatted_index = "\n".join(index_prompt_lines)
                drive_context = f"\nUser's Google Drive Contents:\n{formatted_index}\n---"
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
                    # Load chat history
                    current_history = chat_histories.get(user_id, [])
                    
                    # Call Gemini directly
                    response_content = await generate_gemini_response(
                        user_message,
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

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"An unexpected error occurred in handle_user_query for user {user_id[:10]}: {e}")
        traceback.print_exc() # Print detailed traceback for debugging
        if user_id in pending_requests:
            del pending_requests[user_id]
        raise HTTPException(status_code=500, detail="An unexpected internal error occurred.")
