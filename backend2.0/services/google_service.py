from services import drive_cache
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

async def find_doc_id_by_name(doc_name: str, creds: Credentials) -> str | None:
    """
    Finds the Google Doc ID by its name (case-insensitive).
    """
    service = build('drive', 'v3', credentials=creds)
    try:
        results = service.files().list(
            q=f"mimeType='application/vnd.google-apps.document' and trashed=false",
            spaces='drive',
            fields='files(id, name)',
            pageSize=1000
        ).execute()

        items = results.get('files', [])
        for item in items:
            if item['name'].lower() == doc_name.lower():
                return item['id']
        
        return None  # Not found
    except Exception as e:
        print(f"Error finding doc ID by name: {e}")
        return None


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

    # --- Build full path for each item ---
    # Create a mapping from ID -> item to allow parent lookups
    id_to_item: dict[str, dict] = {item["id"]: item for item in items}

    # Cache computed paths to avoid repeated traversal
    path_cache: dict[str, str] = {}

    def compute_path(item_id: str) -> str:
        """Recursively builds the full path for a Drive item by traversing parents."""
        if item_id in path_cache:
            return path_cache[item_id]

        item = id_to_item.get(item_id)
        if not item:
            return ""  # Should not happen

        name = item.get("name", "(untitled)")
        parents = item.get("parents", [])

        # Root-level items (no parents)
        if not parents:
            path_cache[item_id] = name
            return name

        # Google Drive API usually provides a single parent ID in the list (first element)
        parent_id = parents[0]
        parent_path = compute_path(parent_id)
        full_path = f"{parent_path}/{name}" if parent_path else name
        path_cache[item_id] = full_path
        return full_path

    # Compute and attach the path to each item
    for item in items:
        item["path"] = compute_path(item["id"])

    return items
from .drive_cache import load_index, save_index

# --- Google Drive Folder MIME ---
FOLDER_MIME = "application/vnd.google-apps.folder"

# --- Drive Item URL Generation ---

def get_google_drive_url(item: dict) -> str:
    """Generates the web URL for a Google Drive file or folder."""
    item_id = item.get("id")
    mime_type = item.get("mimeType")

    if not item_id:
        return "" # Cannot generate URL without ID

    if mime_type == "application/vnd.google-apps.folder":
        return f"https://drive.google.com/drive/folders/{item_id}"
    elif mime_type == "application/vnd.google-apps.document":
        return f"https://docs.google.com/document/d/{item_id}/edit"
    elif mime_type == "application/vnd.google-apps.spreadsheet":
        return f"https://docs.google.com/spreadsheets/d/{item_id}/edit"
    elif mime_type == "application/vnd.google-apps.presentation":
        return f"https://docs.google.com/presentation/d/{item_id}/edit"
    # Add more specific types if needed (e.g., forms, drawings)
    else:
        # Default link for other file types viewable in Drive
        return f"https://drive.google.com/file/d/{item_id}/view"

# --- Find Item by Name (using cache) ---
def find_item_by_name(item_name: str, user_id: str) -> dict | None:
    """Searches the cached drive index for an item by exact name."""
    drive_index = load_index(user_id)
    if not drive_index:
        print(f"Warning: Drive index cache not found or empty for user {user_id} during search.")
        return None
    
    for item in drive_index:
        if item.get('name') == item_name:
            print(f"Found item '{item_name}' with ID {item.get('id')}")
            return item # Return the first match
            
    print(f"Item '{item_name}' not found in cache for user {user_id}.")
    return None

# ------------------------------------------------------------
# Breadth-First Crawl to Build Complete Drive Index WITH Paths
# ------------------------------------------------------------
async def crawl_drive_tree(creds: Credentials) -> list[dict]:
    """Breadth-first traversal of *all* non-trashed files & folders.

    Each returned item includes a `path` key representing its
    human-readable location (e.g.  "Work/Specs/DocA").

    Notes:
    • We start at the implicit root folder ID "root".
    • We request `supportsAllDrives=True` + `includeItemsFromAllDrives=True`
      so shared drives and shortcuts are included when permissions allow.
    • API quota: one `files.list` per folder.  Typical personal Drives have
      < a few thousand folders, well under quota limits.
    """
    service = build("drive", "v3", credentials=creds)

    items: list[dict] = []          # Flat list of every file/folder
    queue: list[tuple[str, str]] = [("root", "")]  # (folder_id, current_path)

    while queue:
        folder_id, current_path = queue.pop(0)

        page_token = None
        while True:
            resp = service.files().list(
                q=f"'{folder_id}' in parents and trashed = false",
                fields="nextPageToken, files(id,name,mimeType,parents,modifiedTime)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="user",
            ).execute()

            for f in resp.get("files", []):
                # Build path: root-level children have no leading slash
                path = f"{current_path}/{f['name']}" if current_path else f["name"]
                f["path"] = path
                items.append(f)

                # If folder, enqueue for further traversal
                if f.get("mimeType") == FOLDER_MIME:
                    queue.append((f["id"], path))

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    return items

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
        cache_file = drive_cache.cache_path(user_id)
        try:
            cache_file.unlink(missing_ok=True) # Delete file if it exists, ignore if not
            print(f"Removed old cache file for user {user_id} before refresh.")
        except OSError as e:
            print(f"Error removing old cache file for {user_id}: {e}")
        print(f"Updating Drive index cache for user {user_id} (full BFS)...")
        index = await crawl_drive_tree(creds)
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

async def move_doc_to_folder(file_id: str, current_parent_id: str, target_folder_id: str, creds: Credentials, doc_name: str = "Unknown File") -> str:
    """Moves a Google Drive file to a specified target folder using IDs.

    Args:
        file_id: The ID of the file to move.
        current_parent_id: The ID of the file's current parent folder.
        target_folder_id: The ID of the target folder.
        creds: Google OAuth2 credentials.
        doc_name: The name of the document (for logging/messages).

    Returns:
        A status message indicating success or failure.
    """
    try:
        drive_service = build('drive', 'v3', credentials=creds)
        print(f"Attempting to move file '{doc_name}' (ID: {file_id}) from parent {current_parent_id} to target {target_folder_id}")

        # Move the file by updating its parents field
        # We need to remove the old parent and add the new one.
        file_metadata = drive_service.files().update(
            fileId=file_id,
            addParents=target_folder_id,
            removeParents=current_parent_id,
            fields='id, parents' # Request necessary fields
        ).execute()

        print(f"Successfully moved '{doc_name}' (ID: {file_id}) to folder ID {target_folder_id}. New parents: {file_metadata.get('parents')}")
        return f"✅ Successfully moved '{doc_name}' to the target folder."

    except HttpError as error:
        print(f"An API error occurred while moving '{doc_name}': {error}")
        # Provide more specific error messages based on common issues
        reason = error._get_reason()
        if error.resp.status == 404:
            return f"❌ Failed to move '{doc_name}': File or one of the folders not found. Please check the names/IDs."
        elif error.resp.status == 403:
             return f"❌ Failed to move '{doc_name}': Permission denied. Check if you have edit access to the file and the target folder."
        else:
            return f"❌ Failed to move '{doc_name}': {reason}"
    except Exception as e:
        print(f"An unexpected error occurred while moving '{doc_name}': {e}")
        return f"❌ An unexpected error occurred while trying to move '{doc_name}'."

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

async def update_google_doc(doc_id: str, new_content: str, creds: Credentials):
    """
    Replaces the content of an existing Google Doc with new content.
    """
    service = build('docs', 'v1', credentials=creds)

    try:
        print(f"Clearing and updating doc {doc_id}...")

        # --- First, get the real end index of the doc ---
        document = service.documents().get(documentId=doc_id).execute()
        end_index = document.get('body', {}).get('content', [])[-1].get('endIndex', 1)
        print(f"Real document end index: {end_index}")

        # Now safely delete from index 1 to real end index
        requests = [
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,  # After the title usually
                        "endIndex": end_index - 1  # Careful: endIndex is exclusive
                    }
                }
            },
            {
                "insertText": {
                    "location": {"index": 1},
                    "text": "\n\n" + new_content
                }
            }
        ]
        service.documents().batchUpdate(
            documentId=doc_id,
            body={"requests": requests}
        ).execute()

        print(f"✅ Document {doc_id} updated successfully.")
        return True
    except Exception as e:
        print(f"Error updating document: {e}")
        return False
