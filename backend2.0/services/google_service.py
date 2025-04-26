import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io

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

async def get_drive_item_content(target_name: str, access_token: str) -> str | None:
    """
    Searches for a file/folder by name in Google Drive and attempts to retrieve its text content.

    Args:
        target_name: The name of the file or folder to search for.
        access_token: The user's Google OAuth access token.

    Returns:
        The text content of the item, a summary (for folders),
        or None if not found or content cannot be extracted.
    """
    creds = Credentials(token=access_token)
    try:
        service = build('drive', 'v3', credentials=creds)

        # --- Search for the file/folder by name ---
        # Note: This finds the first match. Might need refinement if names collide.
        print(f"Searching Drive for: '{target_name}'")
        results = service.files().list(
            q=f"name = '{target_name}' and trashed = false",
            spaces='drive',
            fields='files(id, name, mimeType)',
            pageSize=1 # Limit to the first match for simplicity
        ).execute()
        
        items = results.get('files', [])

        if not items:
            print(f"Item '{target_name}' not found in Drive.")
            return None # Or raise a specific exception?

        item = items[0]
        item_id = item['id']
        item_name = item['name']
        mime_type = item['mimeType']
        print(f"Found item: ID={item_id}, Name='{item_name}', Type={mime_type}")

        # --- Extract content based on MIME type ---
        
        # Handle Folders
        if mime_type == 'application/vnd.google-apps.folder':
            print(f"Item '{item_name}' is a folder. Listing contents...")
            folder_contents = service.files().list(
                q=f"'{item_id}' in parents and trashed = false",
                spaces='drive',
                fields='files(name, mimeType)',
                pageSize=10 # Limit number of listed items for brevity
            ).execute()
            children = folder_contents.get('files', [])
            if not children:
                return f"Folder '{item_name}' is empty."
            else:
                content_summary = f"Folder '{item_name}' contains:\n" + \
                                  "\n".join([f"- {child['name']} ({child['mimeType']})" for child in children])
                if len(folder_contents.get('files', [])) >= 10:
                     content_summary += "\n(and possibly more...)"
                return content_summary

        # Handle Google Docs
        elif mime_type == 'application/vnd.google-apps.document':
            print(f"Exporting Google Doc '{item_name}' as text...")
            request = service.files().export_media(fileId=item_id, mimeType='text/plain')
            # Use io.BytesIO to handle the downloaded bytes
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%.")
            fh.seek(0)
            return fh.read().decode('utf-8')

        # Handle Plain Text files
        elif mime_type.startswith('text/'):
             print(f"Downloading text file '{item_name}'...")
             request = service.files().get_media(fileId=item_id)
             fh = io.BytesIO()
             downloader = MediaIoBaseDownload(fh, request)
             done = False
             while done is False:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%.")
             fh.seek(0)
             return fh.read().decode('utf-8')
        
        # Handle Google Slides (Attempt export as text, might not be ideal)
        elif mime_type == 'application/vnd.google-apps.presentation':
            print(f"Attempting to export Google Slides '{item_name}' as text...")
            try:
                request = service.files().export_media(fileId=item_id, mimeType='text/plain')
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                    print(f"Download {int(status.progress() * 100)}%.")
                fh.seek(0)
                # Often slide text export includes speaker notes etc., might need cleaning
                return fh.read().decode('utf-8') 
            except HttpError as export_error:
                print(f"Could not export slides as text: {export_error}")
                return f"Cannot directly extract text content from Google Slides '{item_name}'."


        # Add more handlers here? (Spreadsheets -> CSV?, PDFs -> OCR?)
        
        # Unsupported types
        else:
            print(f"Unsupported MIME type for content extraction: {mime_type}")
            return f"Cannot extract text content from file type: {mime_type}"

    except HttpError as error:
        print(f"An API error occurred: {error}")
        # Handle specific errors? (e.g., 401 Unauthorized, 403 Forbidden, 404 Not Found)
        # Depending on error.resp.status, you might return different messages
        return f"Error accessing Google Drive: {error.resp.status} {error._get_reason()}"
    except Exception as e:
         print(f"An unexpected error occurred in get_drive_item_content: {e}")
         # Propagate or handle? For now, return an error message
         return f"An unexpected error occurred while fetching content: {e}"
