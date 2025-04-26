import os
import json
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

GEMINI_MODEL_NAME = "models/gemini-1.5-pro-latest"  # use latest if 2.5 is mapped like this
SYSTEM_PROMPT = """You are an instruction parser for a Google Drive Assistant. Only return a JSON like:

{"action_to_perform": "createDoc", "name": "My Plan"}

DO NOT return anything else. No extra text or explanations."""

async def parse_user_message(user_message: str) -> dict:
    if not GEMINI_API_KEY:
        return {"error": "Gemini not configured"}
    
    try:
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction=SYSTEM_PROMPT,
        )

        response = await model.generate_content_async(user_message)

        cleaned = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f"Gemini parsing error: {e}")
        return {"error": "Failed to parse"}
