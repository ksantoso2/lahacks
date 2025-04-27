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
pending_requests = {} 

# --- Chat History Storage ---
chat_histories = {}

class UserQuery(BaseModel):
    message: str
    confirmation: bool | None = None
    regenerate: bool | None = None
    skip_preview: bool | None = None

@router.post("/ask")
async def handle_user_query(query: UserQuery, token_info: tuple[str, Credentials] = Depends(verify_google_token)):
    user_id, creds = token_info
    user_message = query.message
    confirmation_choice = query.confirmation
    regenerate_request = query.regenerate
    skip_request = query.skip_preview

    print(f"User token: {user_id[:10]}...")
    pending_data = pending_requests.get(user_id)
    print(f"Pending data: {pending_data}")
    print(f"Received query: message='{user_message}', confirmation={confirmation_choice}, regenerate={regenerate_request}, skip_preview={skip_request}")

    if user_id in pending_requests:
        pending = pending_requests[user_id]
        pending_state = pending['state']

        if pending_state == 'moveDoc':
            doc_name = pending['doc_name']

            if not pending.get('source_folder'):
                pending['source_folder'] = user_message
                return {"message": f"Where would you like to move '{doc_name}' to?"}

            elif not pending.get('target_folder'):
                pending['target_folder'] = user_message
                return {
                    "message": (
                        f"⚠️ Confirm: Move '{doc_name}' from '{pending['source_folder']}' "
                        f"to '{pending['target_folder']}'? (yes/no)"
                    ),
                    "needsConfirmation": True,
                    "confirmationType": "moveDoc"
                }

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

        elif pending_state in ['confirm_preview_gen', 'confirm_create']:
            file_name = pending['file_name']
            original_message = pending.get('original_message')

            if pending_state == 'confirm_preview_gen':
                if confirmation_choice is True:
                    try:
                        print(f"Generating preview for '{file_name}'")
                        preview = await generate_doc_preview(file_name)
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
                            "confirmationType": "doc_create",
                            "allowRegenerate": True
                        }
                    except Exception as e:
                        print(f"Error generating preview: {e}")
                        del pending_requests[user_id]
                        raise HTTPException(status_code=500, detail=f"Failed to generate preview: {e}")
                elif confirmation_choice is False:
                    print("User cancelled preview generation.")
                    del pending_requests[user_id]
                    return {"success": False, "message": "❌ Preview generation canceled."}
                else:
                    del pending_requests[user_id]
                    print("Confirmation ambiguity. Clearing state and reprocessing message.")

            elif pending_state == 'confirm_create':
                preview = pending_requests[user_id].get('preview', '[Preview not available]')
                
                if regenerate_request is True:
                    try:
                        print(f"Regenerating preview for '{file_name}'")
                        new_preview = await generate_doc_preview(file_name)
                        pending_requests[user_id]['preview'] = new_preview
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
                            del pending_requests[user_id]
                            print(f"Document '{file_name}' created successfully (skipped preview). ID: {doc_id}")
                            return {
                                "message": f"OK, I've created the Google Doc: '{file_name}'. You can view it [here]({doc_url}).",
                                "action_required": None,
                                "doc_url": doc_url
                            }
                        else:
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
                            del pending_requests[user_id]
                            return {
                                "success": True,
                                "message": response_message,
                                "docUrl": doc_url
                            }
                    except Exception as e:
                        print(f"Error creating doc after confirmation: {e}")
                        del pending_requests[user_id]
                        raise HTTPException(status_code=500, detail=f"Failed to create document: {e}")
                
                elif confirmation_choice is False:
                    print("User cancelled document creation.")
                    del pending_requests[user_id]
                    return {"success": False, "message": "❌ Document creation canceled."}
                
                else:
                    del pending_requests[user_id]
                    print("Confirmation ambiguity. Clearing state and reprocessing message.")

    print("No pending request found or handled, parsing new message.")
    parsed = await parse_user_message(user_message)
    action = parsed.get("action_to_perform")

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

        if not source_folder:
            return {"message": f"Please provide the origin folder for '{doc_name}'."}
        if not target_folder:
            return {"message": f"Where would you like to move '{doc_name}' to?"}

        return {
            "message": (
                f"⚠️ Confirm: Move '{doc_name}' from '{source_folder}' to '{target_folder}'? (yes/no)"
            ),
            "needsConfirmation": True,
            "confirmationType": "moveDoc"
        }

    if action == "createDoc":
        file_name = parsed.get("name", "Untitled Document")
        try:
            pending_requests[user_id] = {
                'state': 'confirm_preview_gen',
                'file_name': file_name,
                'original_message': user_message
            }
            print(f"📝 Storing initial pending request for {user_id}: state=confirm_preview_gen, file={file_name}")

            return {
                "success": True,
                "message": f"I can create a document named **'{file_name}'**. Would you like me to generate a preview first?",
                "needsConfirmation": True,
                "confirmationType": "preview_gen"
            }
        except Exception as e:
             print(f"Error initiating createDoc flow: {e}")
             if user_id in pending_requests:
                 del pending_requests[user_id]
             raise HTTPException(status_code=500, detail=f"Failed to process document creation request: {e}")

    elif action == "analyze":
        target_name = parsed.get("target")
        analysis_query = parsed.get("query")

        if not analysis_query:
            raise HTTPException(status_code=400, detail="Analysis query is missing.")

        file_content_context = None
        if target_name:
            print(f"Attempting to fetch context for target: {target_name}")
            try:
                file_content_context = await get_drive_item_content(target_name, creds)
                if not file_content_context:
                    print(f"❌ Could not find content for '{target_name}'.")
                    raise HTTPException(status_code=404, detail=f"❌ I couldn't find a document named '{target_name}' in your Drive.")
                else:
                    print(f"✅ Successfully fetched file context for '{target_name}'.")
            except Exception as e:
                print(f"Error fetching file context for '{target_name}': {e}")
                raise HTTPException(status_code=500, detail=f"Error accessing document '{target_name}': {e}")

        drive_index = load_index(user_id) or []
        print(f"Loaded drive index for analysis context ({len(drive_index)} items).")
        current_history = chat_histories.get(user_id, [])

        analysis_result = await analyze_content(
            analysis_query,
            file_content_context=file_content_context,
            drive_index=drive_index,
            chat_history=current_history
        )

        # Unpack result and updated history
        analysis_result_dict, updated_history = analysis_result
        chat_histories[user_id] = updated_history  # Store updated history

        if analysis_result_dict.get("error"):
            raise HTTPException(status_code=500, detail=analysis_result_dict["error"])

        # --- New: Actually update the doc ---
        rewritten_content = analysis_result_dict.get("analysis")
        if target_name and rewritten_content:
            from services.google_service import find_doc_id_by_name, update_google_doc
            doc_id = await find_doc_id_by_name(target_name, creds)
            if doc_id:
                success = await update_google_doc(doc_id, rewritten_content, creds)
                if success:
                    return {
                        "success": True,
                        "message": f"✅ Document '{target_name}' has been updated successfully.",
                        "type": "analysis_result"
                    }
                else:
                    return {
                        "success": False,
                        "message": f"⚠️ Couldn't update the document '{target_name}'.",
                        "type": "analysis_result"
                    }
            else:
                return {
                    "success": False,
                    "message": f"❌ Couldn't find the document '{target_name}' in your Drive.",
                    "type": "analysis_result"
                }
        else:
            return {
                "success": True,
                "message": rewritten_content or "Analysis complete.",
                "type": "analysis_result"
            }

            
    elif parsed.get("error"):
        raise HTTPException(status_code=400, detail=parsed.get("error"))
    else:
        print(f"Unrecognized action parsed: {action}. Falling back to general response.")
        try:
            drive_index = load_index(user_id) or []
            current_history = chat_histories.get(user_id, [])

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
                chat_history=current_history
            )
            
            response_text, updated_history = response_content 
            chat_histories[user_id] = updated_history
            
            return {
                "success": True,
                "message": response_text,
                "type": "fallback_message"
            }
                
        except Exception as e: 
            print(f"Error generating fallback response: {e}")
            raise HTTPException(status_code=500, detail="Sorry, I encountered an error trying to respond.")
