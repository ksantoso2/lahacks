import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Consider a different model or prompt structure for analysis tasks
GEMINI_MODEL_NAME = "models/gemini-2.0-flash" 

async def analyze_content(
    user_query: str, 
    file_content_context: str | None = None, 
    drive_index: list[dict] | None = None,
    chat_history: list | None = None
) -> tuple[dict, list]: 
    """ 
    Analyzes content using the Gemini API based on the user's query,
    optionally using specific file content and/or the user's Drive index as context,
    and an optional existing conversation history.

    Args:
        user_query: The specific question or analysis task requested by the user.
        file_content_context: Optional content fetched from a specific Google Drive item.
        drive_index: Optional list representing the user's Google Drive file/folder structure.
        chat_history: Optional existing conversation history.

    Returns:
        A tuple containing the analysis result dictionary and the updated chat history.
    """
    if not GEMINI_API_KEY:
        print("Error: Gemini API Key not configured.")
        return {"error": "Gemini service not configured."}, chat_history or []

    genai.configure(api_key=GEMINI_API_KEY)
    
    # --- Format Drive Index Context ---
    drive_context_string = ""
    if drive_index:
        try:
            index_prompt_lines = [
                f"- {item['name']} ({'Folder' if item.get('mimeType') == 'application/vnd.google-apps.folder' else 'File'}, id:{item['id']})"
                for item in drive_index[:100] # Limit index size for prompt
            ]
            formatted_index = "\n".join(index_prompt_lines)
            drive_context_string = f"Context: User's Google Drive Contents (partial list):\n{formatted_index}\n---\n"
            print(f"[analyze_content] Formatted drive index context ({len(index_prompt_lines)} items).")
        except Exception as e:
            print(f"[analyze_content] Error formatting drive_index: {e}")
            # Continue without drive index context if formatting fails

    # --- Format File Content Context ---
    file_context_string = ""
    if file_content_context:
        file_context_string = f"Context: Content from relevant file:\n```\n{file_content_context[:2000]}\n```\n---\n" # Limit context size
        print(f"[analyze_content] Added file content context ({len(file_context_string)} chars).")

    # --- Prepare the prompt for Gemini ---
    prompt = f"""
{drive_context_string}
{file_context_string}
User Query: {user_query}

Based on the provided context (if any) and the user query, please perform the requested analysis. Provide the result clearly.
"""
    print(f"[analyze_content] Sending prompt to Gemini (length: {len(prompt)} chars).")
    # print(f"Prompt Preview:\n{prompt[:500]}...") # Optional: Log prompt preview

    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        # Start chat session with existing history
        chat = model.start_chat(history=chat_history or [])
        
        # Send the new analysis prompt
        response = await chat.send_message_async(prompt)
        analysis_result = response.text
        print(f"[analyze_content] Received analysis from Gemini.")
        
        # Return analysis result and updated history
        return {"analysis": analysis_result}, chat.history

    except Exception as e:
        print(f"Error during Gemini API call in analyze_content: {e}")
        # Return error and original history
        return {"error": f"Failed to get analysis from AI: {e}"}, chat_history or []

# Example usage (for testing):
# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         # result = await analyze_content("Summarize this document.", "This is a test document about AI assistants.")
#         result = await analyze_content("What is the capital of France?") # Test without context
#         print(result)
#     asyncio.run(main())
