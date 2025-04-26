import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

async def create_google_doc(title: str, access_token: str):
    """
    Creates a Google Doc with the given title.
    Returns (docId, docUrl).
    """
    creds = Credentials(token=access_token)
    service = build('docs', 'v1', credentials=creds)

    document = service.documents().create(body={
        "title": title
    }).execute()

    doc_id = document.get('documentId')
    doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
    return doc_id, doc_url
