import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "models/gemini-2.0-flash"  # Use 2.0 flash for potentially better instruction following

# --- Updated System Prompt ---
SYSTEM_PROMPT = """You are an instruction parser for a Google Drive Assistant. Your goal is to understand if the user wants to 'createDoc' or 'analyze' something in their Drive.

Analyze keywords include: summarize, analyze, explain, what is in, tell me about.

ONLY return a JSON object with 'action_to_perform'.

If the action is 'createDoc', include the 'name' for the document.
Example: {"action_to_perform": "createDoc", "name": "Meeting Notes"}

If the action is 'analyze', include the 'target' (the file/folder name if specified) and the user's specific 'query'.
Example: {"action_to_perform": "analyze", "target": "Project Plan Doc", "query": "summarize the main points"}
Example: {"action_to_perform": "analyze", "target": null, "query": "What is the capital of France?"} # Handle general queries

If the user wants to move a document, respond with:
{"action_to_perform": "moveDoc", "doc_name": "Document Title", "source_folder": null, "target_folder": null}

Only include folder names if specified.

If the user’s query does not relate to Google Drive actions, respond with:
{"action_to_perform": "none"}

DO NOT provide any other explanations or text outside of the JSON object."""

# --- System Prompt for Response Generation ---
RESPONSE_SYSTEM_PROMPT = """
You are a helpful AI assistant integrated with Google Drive. Your primary functions are to:
1. Analyze user queries about their Drive contents.
2. Generate content for new Google Docs based on user requests.
3. Assist with moving files between folders.
4. Provide general conversational assistance using the provided chat history and Drive context.

**IMPORTANT INSTRUCTIONS:**
*   **Drive Context:** You will be given a list of the user's Google Drive files and folders, often with URLs.
    *   **When mentioning a specific file or folder from this list in your response, ALWAYS use the Markdown link format: `[Exact File or Folder Name](URL provided in context)`**. If a URL wasn't provided for an item in the context, just mention the name.
    *   **DO NOT include the file/folder ID in your response text**, rely solely on the hyperlinked name when a URL is available.
*   **Actions:** Determine the user's intent (analyze, create, move, general) based on the ongoing conversation context.
*   **Analysis:** If asked to analyze or find files, use the Drive context to answer. Mention relevant files/folders using the **hyperlink format** described above.
*   **Document Creation:** If the user confirms document creation:
    *   You might be asked to simply acknowledge the creation is starting, or provide a summary.
    *   Refer to the document being created by its name.
*   **Document Moving:** If confirming a move or reporting success/failure:
    *   Clearly state the document name and the source/target folders involved.
    *   Use the **hyperlink format** for the folders if their URLs were provided in the context.
*   **Clarity:** Ask clarifying questions if the user's request is ambiguous.
*   **Tone:** Be polite, concise, and helpful.
*   **History:** Use the provided chat history for context continuity.
*   **Brevity:** Be concise in your responses. Try to keep your responses under 300 words.
"""

async def parse_user_message(user_message: str) -> dict:
    """Parses the user's message to determine the desired action and parameters."""
    if not GEMINI_API_KEY:
        print("Error: Gemini API Key not configured.")
        return {"error": "Gemini service not configured."}
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    try:
        print(f"Parsing user message with Gemini ({GEMINI_MODEL_NAME})...")
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )

        response = await model.generate_content_async(user_message)
        
        # Attempt to parse the JSON response
        raw_response = response.text
        
        # Clean potential markdown ```json ... ``` artifacts
        if raw_response.strip().startswith("```json"):
            raw_response = raw_response.strip()[7:-3].strip()
        elif raw_response.strip().startswith("```"):
             raw_response = raw_response.strip()[3:-3].strip()

        parsed_json = json.loads(raw_response)
        print(f"Parsed action: {parsed_json}")
        return parsed_json

    except json.JSONDecodeError as e:
        print(f"Error decoding Gemini JSON response: {e}\nRaw response was: {response.text}")
        return {"error": "Failed to parse Gemini response", "details": response.text}
    except Exception as e:
        print(f"Gemini parsing error: {e}")
        return {"error": "Failed to parse"}

async def generate_doc_preview(file_name: str) -> str:
    try:
        prompt = f"Generate an informative preview for a Google Doc titled '{file_name}'. The preview should hint at the content of the document but DO NOT include introductory phrases like 'Here's a preview' or offer multiple options."

        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction="You are a content creator that generates an informative preview for a Google Doc based on its title. Do NOT include multiple options, explanations, or introductory lines. Only output the preview text directly."
        )
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini preview error: {e}")
        return "Failed to generate preview."
    
async def generate_gemini_response(
    prompt: str, 
    drive_context: str | None = None,
    chat_history: list | None = None
) -> tuple[str, list]: 
    """Generates a response from Gemini, potentially using Drive context and chat history."""
    if not GEMINI_API_KEY:
        print("Error: Gemini API Key not configured.")
        return "⚠️ Gemini service not configured.", chat_history or []
 
    genai.configure(api_key=GEMINI_API_KEY)
 
    try:
        full_prompt = prompt
        if drive_context:
            # Prepend the drive context to the user's actual prompt
            full_prompt = f"{drive_context}\n\nUser Question: {prompt}"
            print(f"[Debug] Using Drive context for Gemini generation.")
        else:
            print(f"[Debug] No Drive context provided for Gemini generation.")

        # Enhance prompt for document creation
        full_prompt = f"Generate detailed content for a Google Doc based on this request: {prompt}"
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction=RESPONSE_SYSTEM_PROMPT # <-- Use the response prompt
        )
        
        # Start chat session with existing history
        chat = model.start_chat(history=chat_history or [])
        
        # Send the new message (including context)
        response = await chat.send_message_async(full_prompt)
        
        # Return response text and the updated history from the chat object
        return response.text.strip(), chat.history
    except Exception as e:
        print(f"Error generating Gemini response: {e}")
        return "⚠️ Gemini failed to generate a response.", chat_history or [] # Return original history on error

# Example usage (for testing):
# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         # test_message = "create a document called My Awesome Plan"
#         test_message = "summarize the document 'Project Proposal'"
#         # test_message = "what is the capital of spain?"
#         result = await parse_user_message(test_message)
#         print("Final parsed result:", result)
#     asyncio.run(main())

# Example usage (for testing):
# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         # test_message = "create a document called My Awesome Plan"
#         test_message = "summarize the document 'Project Proposal'"
#         # test_message = "what is the capital of spain?"
#         result = await parse_user_message(test_message)
#         print("Final parsed result:", result)
#     asyncio.run(main())
