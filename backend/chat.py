import os
import json
import httpx
import google.generativeai as genai
from fastapi import APIRouter, Request, HTTPException, Depends 
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import the dependency function and Credentials type from auth.py
from auth import verify_google_token 

router = APIRouter() # Use APIRouter for modular routes

# --- Models --- 
class ChatMessage(BaseModel):
    message: str

# --- Configuration --- 

# Gemini API Key (read from environment variable)
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("\nWARNING: GEMINI_API_KEY environment variable not set. Intent parsing will fail.\n")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"\nERROR configuring Gemini SDK: {e}\n")
        GEMINI_API_KEY = None # Disable Gemini if config fails

# Gemini Model Configuration
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Check if 2.0 exists, else use 1.5
GEMINI_SYSTEM_PROMPT = """You are an instruction analyzer that parses the text request of a user using a Google Drive related AI Agent. You are looking for several specific types of instructions, which you will send back in the form of a json object containing ONLY the fields relevant to the detected instruction. DO NOT add any explanation or surrounding text, ONLY output the JSON.

The instructions and corresponding JSON fields are:
1. Internet Search: If the user wants to search the internet, return: {"search": true, "query": "<search query>"}
2. Find File: If the user wants to find/list/search files in Drive, return: {"action_to_perform": "listFiles", "query": "<optional file name or description>"}
3. Create File: If the user wants to create a file (e.g., doc, sheet), return: {"action_to_perform": "createDoc", "name": "<file name>"}
4. Delete File: If the user wants to delete a file, return: {"action_to_perform": "deleteFile", "name": "<file name>"}
5. Unclear/General Chat: If the instruction doesn't match the above or seems like general conversation, return: {"action_to_perform": "chat", "text": "<original user text>"}

Extract the relevant parameters like file name or search query accurately. If a parameter isn't provided by the user, you can omit it from the JSON or set it to null. Always include "action_to_perform" unless it's an internet search.

Example User Request: "Can you create a google doc called 'My Project Ideas'?"
Example JSON Output: {"action_to_perform": "createDoc", "name": "My Project Ideas"}

Example User Request: "search the web for recent AI news"
Example JSON Output: {"search": true, "query": "recent AI news"}

Example User Request: "list my recent documents"
Example JSON Output: {"action_to_perform": "listFiles", "query": "recent documents"}

Example User Request: "delete the file named report.docx"
Example JSON Output: {"action_to_perform": "deleteFile", "name": "report.docx"}

Example User Request: "hello there"
Example JSON Output: {"action_to_perform": "chat", "text": "hello there"}
"""

# Replace with your deployed Apps Script Web App URL
APPS_SCRIPT_URL = os.getenv('APPS_SCRIPT_URL', "https://script.googleapis.com/v1/scripts/AKfycbzMfveFqS3OBodrIsfUrsB-u0T4ZvxyOXwJwq2-z_PTmN1f2rJTGOqZ523MHA0-zC1L:run/")

# --- Helper Functions ---

async def get_instructions_from_gemini(user_message: str) -> dict:
    """Uses Gemini to parse the user message and return structured instructions."""
    if not GEMINI_API_KEY:
        print("Gemini API Key not configured, skipping analysis.")
        # Fallback behavior: treat as simple chat
        return {"action_to_perform": "chat", "text": user_message}
        
    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME, system_instruction=GEMINI_SYSTEM_PROMPT)
        print(f"Sending to Gemini: {user_message}") # Debug log
        response = await model.generate_content_async(user_message)

        # Clean up potential markdown/formatting issues
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '').strip()
        print(f"Gemini Raw Response: {cleaned_text}") # Debug log
        
        # Attempt to parse the JSON response
        instructions = json.loads(cleaned_text)
        return instructions
    except json.JSONDecodeError as e:
        print(f"Error decoding Gemini JSON response: {e}")
        print(f"Gemini raw text was: {response.text}")
        return {"error": "Failed to parse analysis", "details": response.text}
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # Check for specific Gemini errors if needed, e.g., API key issues
        # if "API_KEY_INVALID" in str(e):
        #     return {"error": "Invalid Gemini API Key"} 
        return {"error": f"Gemini API Error: {e}"}

async def call_apps_script(action: str, payload: dict, user_token: str) -> Dict[str, Any]:
    """Sends a POST request to the Apps Script Web App endpoint using the user's OAuth token."""
    if not APPS_SCRIPT_URL or APPS_SCRIPT_URL == "YOUR_APPS_SCRIPT_WEB_APP_URL":
        print("APPS_SCRIPT_URL is not configured.")
        return {"error": "Backend configuration error", "details": "APPS_SCRIPT_URL not set."}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {user_token}" # Use the user's OAuth token
    }

    request_body = {
        "action": action,
        "data": payload,
    }

    async with httpx.AsyncClient(timeout=45.0) as client: # Increased timeout slightly
        try:
            print(f"Calling Apps Script: {APPS_SCRIPT_URL} with action: {action}")
            response = await client.post(APPS_SCRIPT_URL, json=request_body, headers=headers)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            print(f"Apps Script Response Status: {response.status_code}")
            # Check if response is empty before trying to decode JSON
            if not response.content:
                print("Apps Script returned empty response.")
                # Decide what to return in this case, maybe success with empty body?
                return {"status": "success", "details": "Action performed, no content returned."}
            return response.json()
        except httpx.HTTPStatusError as exc:
            error_details = f"HTTP error calling Apps Script: {exc.response.status_code} - {exc.response.text}"
            print(error_details)
            return {"error": "Apps Script communication failed", "details": error_details}
        except httpx.RequestError as exc:
            error_details = f"Request error calling Apps Script: {exc}"
            print(error_details)
            return {"error": "Apps Script communication failed", "details": error_details}
        except json.JSONDecodeError as exc:
             # Handle cases where Apps Script returns non-JSON (e.g., HTML error page)
            response_text = exc.doc # Original text that failed to parse
            error_details = f"Failed to decode JSON response from Apps Script: {exc} - Response text: {response_text[:200]}..."
            print(error_details)
            return {"error": "Invalid response from Apps Script", "details": error_details}
        except Exception as e:
            error_details = f"An unexpected error occurred during Apps Script call: {e}"
            print(error_details)
            return {"error": "Unexpected backend error", "details": error_details}

# --- Chat Route --- 

@router.post("/api/chat")
# Use the new token verification dependency
# It returns a tuple: (raw_token_string, decoded_id_info_dict)
async def handle_chat(chat_message: ChatMessage, request: Request, token_info: tuple[str, dict] = Depends(verify_google_token)):
    user_message = chat_message.message
    # Get the raw token string from the dependency result
    user_oauth_token, id_info = token_info 
    
    print(f"User Message: {user_message}, Token verified for: {id_info.get('email')}")

    # --- 1. Get Instructions from Gemini --- 
    instructions = await get_instructions_from_gemini(user_message)
    print(f"Gemini Instructions: {instructions}") # Debug log

    agent_response = "Sorry, I couldn't process that request." # Default error response

    # --- 2. Handle Gemini Response --- 
    if not instructions or 'error' in instructions:
        agent_response = instructions.get('details', agent_response)
        print(f"Error from Gemini or parsing: {agent_response}")

    elif instructions.get('search') is True:
        # TODO: Implement web search logic here if needed
        search_query = instructions.get('query', 'Unknown query')
        agent_response = f"Okay, searching the web for: '{search_query}' (Web search not implemented yet)."

    elif 'action_to_perform' in instructions:
        action = instructions['action_to_perform']
        
        if action == "chat":
            # Handle simple chat - maybe use Gemini again for a conversational response?
            agent_response = f"Received chat message: '{instructions.get('text', user_message)}'"
        
        elif action in ["listFiles", "createDoc", "deleteFile"]:
            payload = {k: v for k, v in instructions.items() if k != 'action_to_perform'}
            # Pass the user's verified OAuth token to call_apps_script
            apps_script_response = await call_apps_script(action, payload, user_oauth_token)
            
            # Formulate response based on Apps Script result
            if apps_script_response and 'error' in apps_script_response:
                 agent_response = f"Error interacting with Google Drive: {apps_script_response['error']} - {apps_script_response.get('details', '')}"
            elif apps_script_response:
                 try:
                    # Attempt to pretty-print if it's likely JSON/dict, otherwise stringify
                    if isinstance(apps_script_response, (dict, list)):
                        response_str = json.dumps(apps_script_response, indent=2)
                        agent_response = f"Google Drive action '{action}' completed. Response:\n```json\n{response_str}\n```"
                    else:
                        agent_response = f"Google Drive action '{action}' completed. Response: {apps_script_response}"
                 except Exception as format_exc: # Catch potential formatting errors
                    print(f"Error formatting Apps Script response: {format_exc}")
                    agent_response = f"Google Drive action '{action}' completed, but response formatting failed: {apps_script_response}" 
            else:
                 agent_response = f"Google Drive action '{action}' called, but received no response or an empty response."
        else:
            agent_response = f"Received unknown action '{action}' from analysis."

    else:
        agent_response = f"Received unexpected analysis format: {instructions}"
        
    # --- 3. Return final response to Frontend --- 
    return {"response": agent_response}
