"""Unit tests for v2 Task 9: Generation history."""
import time


def test_add_and_get_history():
    """Can add an entry and retrieve it by session ID."""
    from app.history import add_history_entry, get_history

    session_id = "test-session-1"
    add_history_entry(session_id, "file-abc", "Attention Paper")

    history = get_history(session_id)
    assert len(history) == 1
    assert history[0]["file_id"] == "file-abc"
    assert history[0]["title"] == "Attention Paper"
    assert "timestamp" in history[0]


def test_history_ordered_newest_first():
    """History entries are returned newest first."""
    from app.history import add_history_entry, get_history, _store

    session_id = "test-session-order"
    _store.pop(session_id, None)

    add_history_entry(session_id, "file-1", "Paper 1")
    add_history_entry(session_id, "file-2", "Paper 2")

    history = get_history(session_id)
    assert len(history) == 2
    assert history[0]["file_id"] == "file-2"
    assert history[1]["file_id"] == "file-1"


def test_empty_history():
    """Unknown session returns empty list."""
    from app.history import get_history

    assert get_history("nonexistent-session") == []


def test_history_isolated_between_sessions():
    """Different sessions have independent histories."""
    from app.history import add_history_entry, get_history

    add_history_entry("session-a", "file-a", "Paper A")
    add_history_entry("session-b", "file-b", "Paper B")

    assert len(get_history("session-a")) >= 1
    assert all(e["file_id"] != "file-b" for e in get_history("session-a"))


def test_history_max_entries():
    """History is capped to prevent memory abuse."""
    from app.history import add_history_entry, get_history, MAX_HISTORY_PER_SESSION, _store

    session_id = "test-session-cap"
    _store.pop(session_id, None)

    for i in range(MAX_HISTORY_PER_SESSION + 5):
        add_history_entry(session_id, f"file-{i}", f"Paper {i}")

    history = get_history(session_id)
    assert len(history) <= MAX_HISTORY_PER_SESSION
