import asyncio
import argparse
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os
from dotenv import load_dotenv

from .doc_gen_chain import run_generation_with_hitl

# Define the scopes required by your application
# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive'] # Or ['https://www.googleapis.com/auth/documents']
# Path to store the user's access and refresh tokens.
TOKEN_PATH = 'token.json' # Stores token in the directory where the script is run (backend2.0)

async def get_google_credentials():
    """Gets valid Google credentials, handling the OAuth flow if necessary."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        # Load env vars - needed if script is run standalone
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env')) # Load from backend2.0/.env
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        client_secret = os.getenv('GOOGLE_CLIENT_SECRET')

        if not client_id or not client_secret:
            raise ValueError("Missing GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET in environment variables/.env file.")

        client_config = {
            "installed": { # Use "installed" for scripts like this
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                # redirect_uris often use urn:ietf:wg:oauth:2.0:oob for installed apps if run_local_server isn't used
            }
        }

        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
            except Exception as e:
                print(f"Failed to refresh token: {e}. Need to re-authenticate.")
                creds = None # Force re-authentication if refresh fails
        else:
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            # Recommended to run on a specific port (e.g., 8100) to avoid conflicts
            # and ensure it matches a potential redirect URI in Google Console if needed.
            print("Starting local server for authentication on port 8100...")
            creds = flow.run_local_server(port=8100)
        # Save the credentials for the next run
        with open(TOKEN_PATH, 'w') as token_file:
            token_file.write(creds.to_json())
            print(f"Credentials saved to {TOKEN_PATH}")

    if not creds or not creds.token:
         raise Exception("Failed to obtain valid Google credentials.")

    return creds

# --- !!! IMPORTANT !!! ---
# This script requires a valid Google OAuth Access Token with Drive/Docs scopes.
# For a real application, this token would be obtained via a proper OAuth flow.
# For this experiment, you need to provide it manually via command line argument
# or hardcode it (NOT RECOMMENDED for anything other than temporary testing).
# --- / IMPORTANT ---

async def main():
    parser = argparse.ArgumentParser(description="Generate and create a Google Doc using LangChain and Gemini.")
    parser.add_argument("topic", help="The topic for the Google Document.")
    args = parser.parse_args()

    print("Acquiring Google credentials...")
    try:
        credentials = await get_google_credentials()
        access_token = credentials.token
    except Exception as e:
        print(f"Error getting credentials: {e}")
        return

    if not access_token:
        print("Could not obtain access token.")
        return

    print(f"Starting experiment for topic: {args.topic}")
    # Pass the obtained access token to the chain function
    result = await run_generation_with_hitl(topic=args.topic, access_token=access_token)
    print("\n" + "="*30)
    print("Experiment Result:")
    print(result)
    print("="*30)

if __name__ == "__main__":
    # Ensure you are in the backend2.0 directory when running,
    # or adjust Python path so imports work.
    # Example Run:
    # python -m langchain.run_experiment "The History of LangChain" --token YOUR_ACCESS_TOKEN_HERE
    # NEW Example Run (no --token needed):
    # python3 -m langchain.run_experiment "The Future of AI"
    asyncio.run(main())
