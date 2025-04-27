import json, os, datetime, pathlib


CACHE_DIR = pathlib.Path("drive_cache")
CACHE_DIR.mkdir(exist_ok=True)

def cache_path(user_id: str) -> pathlib.Path:
    return CACHE_DIR / f"{user_id}.json"

def load_index(user_id: str) -> list[dict] | None:
    p = cache_path(user_id)
    return json.loads(p.read_text()) if p.exists() else None

def save_index(user_id: str, index: list[dict]):
    cache_path(user_id).write_text(json.dumps(index, indent=2))

def updated_at(user_id: str) -> datetime.datetime | None:
    """Returns the last modification time of the cache file, or None if it doesn't exist."""
    p = cache_path(user_id)
    try:
        if p.exists():
            # Get modification time and convert to UTC datetime object
            mtime = p.stat().st_mtime
            return datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
    except OSError as e:
        print(f"Error accessing cache file stats for {user_id}: {e}")
    return None