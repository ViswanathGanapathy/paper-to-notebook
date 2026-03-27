"""In-memory generation history, keyed by session ID.

Stores notebook metadata (file_id, title, timestamp) per browser session.
Lost on server restart — acceptable for v2. Persistent DB in v3.
"""
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

MAX_HISTORY_PER_SESSION = 50

# In-memory store: {session_id: [{"file_id": ..., "title": ..., "timestamp": ...}, ...]}
_store: dict[str, list[dict[str, Any]]] = {}


def add_history_entry(session_id: str, file_id: str, title: str) -> None:
    """Add a generation to the session's history."""
    if session_id not in _store:
        _store[session_id] = []

    _store[session_id].append({
        "file_id": file_id,
        "title": title,
        "timestamp": time.time(),
    })

    # Cap to prevent memory abuse
    if len(_store[session_id]) > MAX_HISTORY_PER_SESSION:
        _store[session_id] = _store[session_id][-MAX_HISTORY_PER_SESSION:]


def get_history(session_id: str) -> list[dict[str, Any]]:
    """Get generation history for a session, newest first."""
    entries = _store.get(session_id, [])
    return list(reversed(entries))
