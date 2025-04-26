from langchain_google_genai import ChatGoogleGenerativeAI
from .config import GEMINI_API_KEY, GEMINI_MODEL_NAME

def get_gemini_llm():
    """Initializes and returns the LangChain Gemini LLM."""
    if not GEMINI_API_KEY:
        raise ValueError("Gemini API Key not configured. Please check your .env file.")

    # Adjust temperature for creativity vs consistency as needed
    llm = ChatGoogleGenerativeAI(model=GEMINI_MODEL_NAME, google_api_key=GEMINI_API_KEY, temperature=0.7)
    return llm

# Initialize once
gemini_llm = get_gemini_llm()
