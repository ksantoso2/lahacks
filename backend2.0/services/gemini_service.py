import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "models/gemini-1.5-flash"  # Use 1.5 flash for potentially better instruction following

# --- Updated System Prompt ---
SYSTEM_PROMPT = """You are an instruction parser for a Google Drive Assistant. Your goal is to understand if the user wants to 'createDoc' or 'analyze' something in their Drive. 

Analyze keywords include: summarize, analyse, explain, what is in, tell me about.

ONLY return a JSON object with 'action_to_perform'.

If the action is 'createDoc', include the 'name' for the document.
Example: {"action_to_perform": "createDoc", "name": "Meeting Notes"}

If the action is 'analyze', include the 'target' (the file/folder name if specified) and the user's specific 'query'.
Example: {"action_to_perform": "analyze", "target": "Project Plan Doc", "query": "summarize the main points"}
Example: {"action_to_perform": "analyze", "target": null, "query": "What is the capital of France?"} # Handle general queries

DO NOT return any other text, explanations, or markdown formatting."""

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
        print(f"Raw Gemini parser response: {raw_response}")
        
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
        prompt = f"Create a short preview for a Google Doc titled '{file_name}'."

        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction="You are a content creator that generates document previews."
        )
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini preview error: {e}")
        return "Failed to generate preview."
    
async def generate_gemini_response(prompt: str, drive_context: str | None = None) -> str:
    """Generates a response using Gemini, optionally prepending Drive context."""
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
            system_instruction="You are a helpful Google Drive assistant. Use the provided context about the user's Drive files if available."
            system_instruction="You are a document content generator."
        )
        response = await model.generate_content_async(full_prompt) # Use the combined prompt
        return response.text
        response = await model.generate_content_async(full_prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating Gemini response: {e}")
        return "⚠️ Gemini failed to generate a response."

        print(f"Error during Gemini content generation: {e}")
        return "⚠️ Failed to generate document content."

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
