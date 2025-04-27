import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = "models/gemini-2.0-flash"

async def analyze_content(
    user_query: str,
    file_content_context: str | None = None,
    drive_index: list[dict] | None = None,
    chat_history: list | None = None
) -> tuple[dict, list]:
    """Analyzes or edits document content based on the user's instruction."""

    if not GEMINI_API_KEY:
        print("Error: Gemini API Key not configured.")
        return {"error": "Gemini service not configured."}, chat_history or []

    genai.configure(api_key=GEMINI_API_KEY)

    # --- Format file content (basic) ---
    file_context_string = file_content_context[:4000] if file_content_context else ""

    # --- Decide which prompt to use ---
    # Lowercase the instruction for easier keyword detection
    user_query_lower = user_query.lower()

    if any(keyword in user_query_lower for keyword in ["summarize", "shorter", "summarization", "make concise", "cut down", "condense", "make briefer"]):
        prompt = f"""
You are a professional summarizer.

Here is the original document:

{file_context_string}

The user has requested:

"{user_query}"

Your task:
- Summarize the document as requested.
- Cut unnecessary details.
- Focus only on core ideas.
- Output the shortened and clean version of the document.

Important Rules:
- Do NOT suggest creating new documents.
- Do NOT explain your reasoning.
- Output ONLY the summarized document text.
"""
        print("[analyze_content] Detected summarization/editing task. Using summarization prompt.")

    else:
        prompt = f"""
You are a professional document editor.

Here is the original document:

{file_context_string}

The user has requested:

"{user_query}"

Your task:
- Rewrite or enhance the document to satisfy the instruction.
- Maintain the original meaning unless instructed otherwise.

Important Rules:
- Do NOT suggest creating new documents.
- Do NOT explain your reasoning.
- Output ONLY the updated document text.
"""
        print("[analyze_content] Using standard editing prompt.")

    print(f"[analyze_content] Sending prompt to Gemini (length: {len(prompt)} chars).")

    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        chat = model.start_chat(history=chat_history or [])
        response = await chat.send_message_async(prompt)
        analysis_result = response.text
        print("[analyze_content] Received analysis result.")

        return {"analysis": analysis_result.strip()}, chat.history

    except Exception as e:
        print(f"Error during Gemini API call in analyze_content: {e}")
        return {"error": f"Failed to get analysis from AI: {e}"}, chat_history or []
