# import asyncio
# from googleapiclient.discovery import build
# from google.oauth2.credentials import Credentials

# async def create_google_doc(title: str, access_token: str):
#     """Creates a new Google Doc and returns the document ID and URL."""
#     creds = Credentials(token=access_token)
#     docs_service = build('docs', 'v1', credentials=creds)

#     doc = await asyncio.to_thread(
#         lambda: docs_service.documents().create(body={"title": title}).execute()
#     )

#     document_id = doc.get('documentId')
#     doc_url = f"https://docs.google.com/document/d/{document_id}/edit"

#     return document_id, doc_url
