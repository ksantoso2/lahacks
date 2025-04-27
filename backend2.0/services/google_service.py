import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io
import asyncio
import datetime
import re

# --- LangChain Imports ---
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Use direct imports assuming main.py is run from the backend2.0 directory
from langchain_google_doc.llms import gemini_llm # Correct variable name
from langchain_google_doc.prompts import content_generation_template

def sanitize_content(text: str) -> str:
    """
    Cleans the content by:
    - Removing markdown formatting (*, **, _, ~, #)
    - Replacing bullet points (•) with hyphens (-)
    """
    text = re.sub(r'^(#{1,6})\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'(\*\*|\*|__|_|~~)', '', text)
    text = re.sub(r'^\s*•\s+', '- ', text, flags=re.MULTILINE)
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'`([^`]*)`', r'\1', text)
    text = re.sub(r'^-{3,}$', '', text, flags=re.MULTILINE)
    return text.strip()

async def list_all_drive_items(creds: Credentials) -> list[dict]:
    """Return every file & folder’s id, name, mimeType, parents, modifiedTime."""
    service = build("drive", "v3", credentials=creds)
    items, page_token = [], None
    while True:
        resp = service.files().list(
            q="trashed=false",
            fields="nextPageToken, files(id,name,mimeType,parents,modifiedTime)",
            pageSize=1000,
            pageToken=page_token,
        ).execute()
        items.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items
from .drive_cache import load_index, save_index

async def ensure_drive_index(user_id: str, creds: Credentials) -> list[dict]:
    """If no cache or >24 h old, (re)build the index.
    Passes Credentials object to list_all_drive_items.
    """
    needs_update = False
    current_index = load_index(user_id)
    if not current_index: # Always update if no cache
        needs_update = True
    # elif last_updated and (datetime.datetime.utcnow() - last_updated).total_seconds() > 86400: # Update if older than 24h
    #     needs_update = True

    if needs_update:
        print(f"Updating Drive index cache for user {user_id}...")
        index = await list_all_drive_items(creds)
        save_index(user_id, index)
        print(f"Saved updated Drive index for user {user_id}.")
        return index
    else:
        print(f"Using existing Drive index cache for user {user_id}.")
        return current_index

async def create_google_doc(title: str, creds: Credentials, content: str | None = None):
    """
    Creates a Google Doc with the given title and optional content and optionally inserts content.
    Returns (docId, docUrl).
    """
    service = build('docs', 'v1', credentials=creds)

    try:
        # 1. Create the document with the title
        document = service.documents().create(body={
            "title": title
        }).execute()

        doc_id = document.get('documentId')
        doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"Created Google Doc: ID={doc_id}, Title='{title}'")

        # 2. If content is provided, insert it
        if content and doc_id:
            print(f"Inserting content into doc {doc_id}...")
            # Documents start with a newline character, insert at index 1
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': 1, # Insert at the beginning of the document body
                        },
                        'text': content
                    }
                }
            ]
            # Execute the batch update to insert the text
            service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
            print(f"Successfully inserted content into doc {doc_id}")

        return doc_id, doc_url

    except HttpError as error:
        print(f"An API error occurred while creating/updating the doc: {error}")
        # Depending on the error, you might want to raise it or return None
        # For now, let's print and return None to indicate failure
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred in create_google_doc: {e}")
        return None, None


async def run_langchain_doc_creation(original_request: str, generated_title: str, creds: Credentials):
    """
    Generates Google Doc content using LangChain based on the original request,
    then creates the document with the generated title and content.
    Returns (docId, docUrl) or (None, None) on failure.
    """
    print(f"Running LangChain generation for request: '{original_request}'")
    try:
        # 1. Prepare the LangChain prompt and chain for content generation
        # Use the specific prompt template designed for content generation
        content_prompt = ChatPromptTemplate.from_template(content_generation_template)
        # Chain: Prompt -> LLM -> String Output
        content_chain = content_prompt | gemini_llm | StrOutputParser() # Use the imported gemini_llm

        # 2. Invoke the chain asynchronously to generate content
        print("Invoking LangChain content generation chain...")
        # Pass the original request using the key expected by the prompt ('topic')
        generated_content = await content_chain.ainvoke({"topic": original_request})
        print("LangChain content generation complete.")
        # print(f"Generated Content Preview (first 100 chars): {generated_content[:100]}...") # Optional: Log preview

        if not generated_content:
             print("Error: LangChain generation failed to produce content.")
             return None, None # Indicate failure

        # 3. Call the modified create_google_doc with title and the generated content
        print(f"Creating Google Doc '{generated_title}' using LangChain flow...")
        cleaned_content = sanitize_content(generated_content)
        doc_id, doc_url = await create_google_doc(
            title=generated_title,
            creds=creds,
            content=cleaned_content # Pass the full content here
        )

        return doc_id, doc_url

    except Exception as e:
        # Log the exception for debugging
        print(f"An error occurred during LangChain document creation process: {e}")
        import traceback
        traceback.print_exc() # Print detailed traceback
        return None, None # Indicate failure

async def move_doc_to_folder(doc_name: str, source_folder: str, target_folder: str, creds: Credentials) -> str:
    """
    Moves a document (by name) from source_folder to target_folder.
    Returns a status message.
    """
    service = build('drive', 'v3', credentials=creds)

    try:
        # Search for the document by name
        doc_results = service.files().list(
            q=f"name = '{doc_name}' and trashed = false",
            fields="files(id, name, parents)",
            pageSize=1
        ).execute()
        if not doc_results['files']:
            return f"❌ Document '{doc_name}' not found."

        doc = doc_results['files'][0]
        doc_id = doc['id']
        current_parents = ",".join(doc.get('parents', []))

        # --- List all folders with pagination ---
        all_folders = []
        page_token = None

        while True:
            response = service.files().list(
                q="mimeType = 'application/vnd.google-apps.folder'",
                fields="nextPageToken, files(id, name)",
                pageSize=1000,
                corpora="allDrives",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageToken=page_token
            ).execute()

            all_folders.extend(response.get('files', []))
            page_token = response.get('nextPageToken', None)

            if not page_token:
                break  # No more pages

        # --- Log folders for debugging ---
        print(f"Found folders: {[f['name'] for f in all_folders]}")

        # --- Search manually (case-insensitive) ---
        target_folder_match = next(
            (f for f in all_folders if f['name'].lower() == target_folder.lower()),
            None
        )

        if not target_folder_match:
            return f"❌ Target folder '{target_folder}' not found."

        target_folder_id = target_folder_match['id']
        print(f"Matched target folder ID: {target_folder_id}")



        # Perform the move
        service.files().update(
            fileId=doc_id,
            addParents=target_folder_id,
            removeParents=current_parents,
            fields='id, parents'
        ).execute()

        return f"✅ Moved '{doc_name}' to '{target_folder}'."

    except HttpError as error:
        print(f"An API error occurred: {error}")
        return f"❌ Failed to move '{doc_name}': {error._get_reason()}"


async def get_drive_item_content(target_name: str, creds: Credentials) -> str | None:
    """
    Searches for a file/folder by name in Google Drive and attempts to retrieve its text content.

    Args:
        target_name: The name of the file or folder to search for.
        creds: The user's Google OAuth credentials.

    Returns:
        The text content of the item, a summary (for folders),
        or None if not found or content cannot be extracted.
    """
    print(f"Attempting to get content for '{target_name}'...")
    service = build('drive', 'v3', credentials=creds)

    try:
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
