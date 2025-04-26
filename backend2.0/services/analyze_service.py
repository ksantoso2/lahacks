import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# Consider a different model or prompt structure for analysis tasks
GEMINI_MODEL_NAME = "models/gemini-2.0-flash" 

async def analyze_content(user_query: str, context: str = None) -> dict:
    """ 
    Analyzes content using the Gemini API based on the user's query.

    Args:
        user_query: The specific question or analysis task requested by the user.
        context: Optional additional context, potentially fetched from a Google Drive item.

    Returns:
        A dictionary containing the analysis result or an error.
    """
    if not GEMINI_API_KEY:
        print("Error: Gemini API Key not configured.")
        return {"error": "Gemini service not configured."}
    
    genai.configure(api_key=GEMINI_API_KEY)
    
    # --- Prepare the prompt for Gemini --- 
    # This needs refinement. How do we combine the user_query and context?
    # For now, let's just use the user_query directly.
    # A more complex prompt might involve instructions like:
    # "Based on the following context, answer the user's question: {user_query}\n\nContext:\n{context}"
    
    prompt_text = user_query
    if context:
        # Simple combination for now, might need better structuring
        prompt_text = f"User Question: {user_query}\n\nProvided Context:\n{context}"
        print(f"Analyzing with context (first 100 chars): {context[:100]}...")
    else:
        print(f"Analyzing based on query: {user_query}")

    try:
        model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        print(f"Sending analysis prompt to Gemini ({GEMINI_MODEL_NAME})...")
        response = await model.generate_content_async(prompt_text)
        
        analysis_result = response.text
        print(f"Gemini analysis result: {analysis_result[:100]}...") # Log snippet
        return {"success": True, "analysis": analysis_result}

    except Exception as e:
        print(f"Error during Gemini analysis call: {e}")
        return {"error": f"Failed to analyze content: {e}"}

# Example usage (for testing):
# if __name__ == "__main__":
#     import asyncio
#     async def main():
#         # result = await analyze_content("Summarize this document.", "This is a test document about AI assistants.")
#         result = await analyze_content("What is the capital of France?") # Test without context
#         print(result)
#     asyncio.run(main())
