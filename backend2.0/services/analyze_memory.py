# services/analyze_memory.py
# Simple in-memory active doc tracker (can move to redis/db later if needed)

active_docs = {}

def set_active_doc(user_id: str, doc_id: str):
    active_docs[user_id] = doc_id

def get_active_doc(user_id: str) -> str | None:
    return active_docs.get(user_id)

def clear_active_doc(user_id: str):
    if user_id in active_docs:
        del active_docs[user_id]
