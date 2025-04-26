import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes, allowing frontend requests

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")

if not supabase_url or not supabase_key:
    raise ValueError("Supabase URL and Key must be set in the environment variables.")

supabase: Client = create_client(supabase_url, supabase_key)

# --- Helper Function to Get User from Token ---
def get_user_from_token():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None, jsonify({"error": "Missing or invalid Authorization header"}), 401

    token = auth_header.split(' ')[1]
    try:
        # Verify the token and get user data
        user_response = supabase.auth.get_user(token)
        user = user_response.user
        if not user:
             return None, jsonify({"error": "Invalid or expired token"}), 401
        return user, None, None
    except Exception as e:
        print(f"Error validating token: {e}")
        return None, jsonify({"error": "Token validation failed", "details": str(e)}), 401

# --- API Routes ---
@app.route('/')
def home():
    return jsonify({"message": "Study Buddy Backend is running!"})

@app.route('/api/generate-study-guide', methods=['POST'])
def generate_study_guide_route():
    user, error_response, status_code = get_user_from_token()
    if error_response:
        return error_response, status_code

    # Placeholder: Get data from request if needed
    # data = request.json
    # start_time = data.get('startTime')
    # end_time = data.get('endTime')

    print(f"Generating study guide for user: {user.id}")

    # TODO: Implement Google Drive API interaction
    # 1. Get Google OAuth token (likely stored/retrieved via Supabase session)
    # 2. Use token to list/read relevant Google Drive files
    # 3. Pass content to Google Gemini API
    # 4. Format and return the study guide

    # Mock response for now
    mock_study_guide = {
        "title": f"Study Guide for {user.email}",
        "content": "This is a placeholder study guide. Integration with Google Drive and Gemini is pending."
    }
    return jsonify(mock_study_guide)

@app.route('/api/generate-quiz', methods=['POST'])
def generate_quiz_route():
    user, error_response, status_code = get_user_from_token()
    if error_response:
        return error_response, status_code

    print(f"Generating quiz for user: {user.id}")

    # TODO: Implement Google Drive and Gemini interaction (similar to study guide)

    # Mock response for now
    mock_quiz = {
        "title": f"Quiz for {user.email}",
        "questions": [
            {"question": "Backend: Sample Q1?", "options": ["A", "B"], "answer": 0},
            {"question": "Backend: Sample Q2?", "options": ["X", "Y"], "answer": 1}
        ]
    }
    return jsonify(mock_quiz)

# --- Run the App ---
if __name__ == '__main__':
    # Use port 5001 to avoid conflict with frontend dev server (often 5173)
    app.run(debug=True, port=5001)