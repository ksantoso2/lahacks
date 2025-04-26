import os
from dotenv import load_dotenv

# Load variables from the main .env file in the parent directory
dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# You might want to use a specific model optimized for generation
GEMINI_MODEL_NAME = "gemini-1.5-flash" # Or another suitable model

if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY not found in .env file.")
