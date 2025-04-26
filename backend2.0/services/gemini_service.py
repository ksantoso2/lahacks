import os
import json
import google.generativeai as genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

GEMINI_MODEL_NAME = "models/gemini-2.0-flash"  # use latest if 2.5 is mapped like this
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
        print(f"Gemini raw response: {response.text}")

        cleaned = response.text.strip().replace('```json', '').replace('```', '').strip()
        return json.loads(cleaned)
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
    
async def generate_gemini_response(prompt: str) -> str:
    try:
        # Custom prompt specific to this function
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            system_instruction="You are a response generator for any queries."
        )
        response = await model.generate_content_async(prompt)
        return response.text
    except Exception as e:
        return "⚠️ Gemini failed to generate a response."

