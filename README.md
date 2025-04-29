# DocuPilot - Your AI-Powered Google Drive Agent

[![Built for LA Hacks 2025](https://img.shields.io/badge/Built_for-LA_Hacks_2025-blue)](https://lahacks.com/)
[![Devpost](https://img.shields.io/badge/Devpost-Project_Page-0088CC)](https://devpost.com/software/docupilot)

**Live Demo:** [**Try DocuPilot Here!**](https://lahacks-tau.vercel.app/)

DocuPilot transforms Google Drive into an intelligent, conversational workspace, allowing you to manage your files using natural language.

## Inspiration

Managing files in Google Drive can quickly become overwhelming. Tasks like moving files, summarizing documents, or safely deleting resources often require multiple manual steps. We built DocuPilot to streamline Drive management for educators, students, and anyone needing efficient file organization, leveraging an agentic assistant that interprets natural language commands and confirms user intent before acting.

## What it Does

With natural language commands, users can:

-   **Move files:** *"move my doc titled budget from drafts to final"* (even across nested folders).
-   **Summarize documents:** *"summarize my project proposal doc"* (generates a concise summary).
-   **Create new Google Docs:** *"create a document called Q2 Strategy Plan"* (with confirmation).

## How We Built It

-   **Natural Language Understanding:** Gemini API parses user commands and identifies intent (e.g., `moveFile`, `summarizeDoc`, `createDoc`).
-   **Contextual Awareness:** A cache of the user's Drive structure is fed to Gemini for accurate file/folder identification.
-   **Backend (FastAPI + LangChain):** Manages the agentic workflow, including intent confirmation, calling Google Drive APIs, and handling sessions.
-   **Frontend (React + Vite):** Provides an interactive chat interface with real-time updates and confirmation prompts.
-   **Google Drive API:** Executes the requested file operations.
-   **Security:** Uses OAuth2 for secure, consent-based access to Google Drive.

## Setup and Running Locally

**Prerequisites:**

*   Node.js and npm (for frontend)
*   Python 3.x and pip (for backend)
*   Google Cloud Project with Drive API and Gemini API enabled.
*   Google OAuth Credentials (Client ID, Client Secret).
*   Gemini API Key.

**Backend Setup (`backend2.0`):**

1.  Navigate to the backend directory: `cd backend2.0`
2.  Create a virtual environment (optional but recommended): `python3 -m venv venv` and `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
3.  Install dependencies: `pip install -r requirements.txt`
4.  Configure environment variables (e.g., in a `.env` file):
    *   `GOOGLE_CLIENT_ID`
    *   `GOOGLE_CLIENT_SECRET`
    *   `GEMINI_API_KEY`
    *   `REDIRECT_URI` (e.g., `http://localhost:5173/auth/callback` or your frontend dev server callback)
5.  Run the backend server: `uvicorn main:app --reload --port 8000` (adjust port if needed)

**Frontend Setup (`frontend2.0`):**

1.  Navigate to the frontend directory: `cd ../frontend2.0`
2.  Install dependencies: `npm install`
3.  Configure environment variables (e.g., in a `.env.local` file):
    *   `VITE_API_BASE_URL="http://localhost:8000"` (or your backend URL)
    *   `VITE_GOOGLE_CLIENT_ID="YOUR_GOOGLE_CLIENT_ID"`
    *   `VITE_REDIRECT_URI="http://localhost:5173/auth/callback"` (must match backend)
4.  Run the frontend development server: `npm run dev`
5.  Open your browser to the URL provided (usually `http://localhost:5173`).

## Challenges We Ran Into

-   Managing Google OAuth token expiration and refresh cycles.
-   Crafting precise prompts for Gemini to ensure structured, actionable responses.

## Accomplishments

-   Built a multi-functional Drive assistant (create, move, analyze) using natural language.
-   Integrated Gemini and Google Drive APIs for contextual understanding and action execution.
-   Developed multi-turn conversational flows with confirmations for safety and usability.

## What We Learned

-   Managing state and workflows for reliable agentic systems.
-   The importance of LLM prompt engineering for structured output.
-   Handling OAuth2 complexities within user sessions.
-   Using context caching (like Drive structure) to improve LLM accuracy.

## What's Next

-   Support for Google Sheets, Slides, and Forms.
-   Enhanced intent detection for more complex prompts.
-   Multimodal capabilities (e.g., image uploads).
-   Document sharing and permission management via chat.
-   Undo functionality.

---
*Built for LA Hacks 2025*
