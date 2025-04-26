import os
from langchain.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type, Optional
# IMPORTANT: Assumes google_service.py is accessible relative to backend2.0 root
# Adjust import path if necessary based on how you run the experiment
try:
    # Assumes running from backend2.0 directory
    from services.google_service import create_google_doc
except ImportError:
    print("Warning: Could not import create_google_doc from services.google_service.")
    print("Ensure the script is run from the backend2.0 directory or adjust PYTHONPATH.")
    # Define a dummy function if import fails, so the script doesn't crash immediately
    async def create_google_doc(title: str, access_token: str):
        print(f"[Dummy Tool] Would create doc '{title}' if service was imported.")
        return "dummy-doc-id", "http://example.com/dummy-doc"


class GoogleDocCreatorInput(BaseModel):
    """Input schema for the CreateGoogleDocTool."""
    title: str = Field(description="The title for the new Google Document.")
    content: str = Field(description="The main content/body for the new Google Document.")
    access_token: str = Field(description="The user's Google OAuth access token required for API calls.")


from typing import Type
from langchain.tools import BaseTool
from .google_service import create_google_doc
from .schemas import GoogleDocCreatorInput  # Assuming you have a Pydantic schema

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import asyncio

class CreateGoogleDocTool(BaseTool):
    """Tool that creates a Google Document with specified title and content."""
    name: str = "google_doc_creator"
    description: str = (
        "Useful for creating a new Google Document in the user's Drive "
        "when you have the desired title and content."
    )
    args_schema: Type[BaseModel] = GoogleDocCreatorInput

    # Use _arun for async compatibility with our service function
    async def _arun(self, title: str, content: str, access_token: str) -> str:
        """Uses the tool asynchronously."""
        if not access_token or access_token == "YOUR_ACCESS_TOKEN_HERE": # Basic check
             return "Error: A valid Google OAuth access token is required to use this tool."
        try:
            print(f"Tool: Attempting to create Google Doc titled '{title}'...")
            # Step 1: Create the doc
            doc_id, doc_url = await create_google_doc(title=title, access_token=access_token)
            print(f"Tool: Successfully created document - URL: {doc_url}")

            # 🚀 Step 2: Insert content (only small patch added here)
            creds = Credentials(token=access_token)
            docs_service = build('docs', 'v1', credentials=creds)

            await asyncio.to_thread(
                lambda: docs_service.documents().batchUpdate(
                    documentId=doc_id,
                    body={"requests": [
                        {
                            "insertText": {
                                "location": {"index": 1},
                                "text": f"{title}\n\n{content}"
                            }
                        },
                        {
                            "updateParagraphStyle": {
                                "range": {
                                    "startIndex": 1,
                                    "endIndex": 1 + len(title),
                                },
                                "paragraphStyle": {
                                    "namedStyleType": "HEADING_1"
                                },
                                "fields": "namedStyleType"
                            }
                        }
                    ]}
                ).execute()
            )

            return f"Successfully created Google Doc: {doc_url}"

        except Exception as e:
            print(f"Tool: Error creating Google Doc: {e}")
            return f"Error creating Google Doc: {e}"

    # Sync run is not implemented as the underlying service is async
    def _run(self):
        raise NotImplementedError("Use arun for asynchronous execution.")


# class CreateGoogleDocTool(BaseTool):
#     """Tool that creates a Google Document with specified title and content."""
#     name: str = "google_doc_creator"
#     description: str = (
#         "Useful for creating a new Google Document in the user's Drive "
#         "when you have the desired title and content."
#     )
#     args_schema: Type[BaseModel] = GoogleDocCreatorInput

#     # Use _arun for async compatibility with our service function
#     async def _arun(self, title: str, content: str, access_token: str) -> str:
#         """Uses the tool asynchronously."""
#         if not access_token or access_token == "YOUR_ACCESS_TOKEN_HERE": # Basic check
#              return "Error: A valid Google OAuth access token is required to use this tool."
#         try:
#             print(f"Tool: Attempting to create Google Doc titled '{title}'...")
#             # Here, we call the actual async function from our service layer
#             # Note: The original service function doesn't take 'content' yet.
#             # We'd need to modify `create_google_doc` or add a new function
#             # `create_google_doc_with_content` in google_service.py for this tool to fully work.
#             # For now, it will just create an empty doc with the title.
#             # TODO: Enhance google_service.create_google_doc to accept content.
#             doc_id, doc_url = await create_google_doc(title=title, access_token=access_token)
#             print(f"Tool: Successfully created document - URL: {doc_url}")
#             # We might want to return just the URL or a confirmation message
#             return f"Successfully created Google Doc: {doc_url}"
#         except Exception as e:
#             print(f"Tool: Error creating Google Doc: {e}")
#             return f"Error creating Google Doc: {e}"

#     # Sync run is not implemented as the underlying service is async
#     def _run(self):
#         raise NotImplementedError("Use arun for asynchronous execution.")
