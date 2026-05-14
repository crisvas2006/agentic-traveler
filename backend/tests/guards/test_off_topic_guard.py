"""
Tests for the off-topic guard module.

Tests use plain dicts and mocks — no real Supabase calls.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from agentic_traveler.guards.off_topic_guard import (
    RESET_WINDOW_SECONDS,
    THRESHOLD,
    is_restricted,
    record_off_topic,
    reset,
)


def _user_doc(count=0, last_flagged_ts=None, restricted_until=None):
    """Build a minimal user doc with off_topic fields."""
    off_topic = {}
    if count:
        off_topic["count"] = count
    if last_flagged_ts:
        off_topic["last_flagged_ts"] = last_flagged_ts
    if restricted_until:
        off_topic["restricted_until"] = restricted_until
    return {"name": "Test", "off_topic": off_topic}


# ── is_restricted ──────────────────────────────────────────────────────────────

def test_no_restriction_initially():
    """New user with no off-topic history is not restricted."""
    assert is_restricted({}) is None
    assert is_restricted({"off_topic": {}}) is None


def test_restriction_when_set_and_active():
    """User is restricted if restricted_until is in the future."""
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    doc = _user_doc(restricted_until=future)
    msg = is_restricted(doc)
    assert msg is not None
    assert "restricted" in msg.lower()


def test_restriction_expired():
    """User is NOT restricted if restricted_until is in the past."""
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    doc = _user_doc(restricted_until=past)
    assert is_restricted(doc) is None


def test_restriction_message_includes_time():
    """Restriction message includes the unlock time."""
    future = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
    doc = _user_doc(restricted_until=future)
    msg = is_restricted(doc)
    assert "UTC" in msg
    assert "min remaining" in msg


# ── record_off_topic ──────────────────────────────────────────────────────────

def test_counter_increments():
    """Each off-topic record increments the count."""
    now = datetime.now(timezone.utc).isoformat()
    doc = _user_doc(count=2, last_flagged_ts=now)

    with patch("agentic_traveler.tools.db_client.get_db") as mock_get_db:
        result = record_off_topic(doc, user_id="uuid-123")

    assert result["count"] == 3
    assert result["restricted"] is False
    # Supabase upsert should have been called
    mock_get_db.return_value.table.assert_called_with("off_topic_state")


def test_restriction_after_threshold():
    """User is restricted after THRESHOLD consecutive off-topic messages."""
    now = datetime.now(timezone.utc).isoformat()
    doc = _user_doc(count=THRESHOLD - 1, last_flagged_ts=now)

    with patch("agentic_traveler.tools.db_client.get_db"):
        result = record_off_topic(doc, user_id="uuid-123")

    assert result["count"] == THRESHOLD
    assert result["restricted"] is True
    assert "restricted_until" in result


def test_no_user_id_skips_supabase():
    """record_off_topic with empty user_id skips the Supabase write."""
    doc = _user_doc()
    with patch("agentic_traveler.tools.db_client.get_db") as mock_get_db:
        result = record_off_topic(doc, user_id="")

    assert result["count"] == 1
    mock_get_db.assert_not_called()


def test_auto_reset_after_window():
    """Counter resets if the last flag was more than RESET_WINDOW_SECONDS ago."""
    old_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=RESET_WINDOW_SECONDS + 60)
    ).isoformat()

    doc = _user_doc(count=4, last_flagged_ts=old_ts)
    with patch("agentic_traveler.tools.db_client.get_db"):
        result = record_off_topic(doc, user_id="uuid-1")

    # Count should be 1 (reset to 0, then incremented)
    assert result["count"] == 1
    assert result["restricted"] is False


def test_no_auto_reset_within_window():
    """Counter does NOT reset if the last flag was recent."""
    recent_ts = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    doc = _user_doc(count=3, last_flagged_ts=recent_ts)

    with patch("agentic_traveler.tools.db_client.get_db"):
        result = record_off_topic(doc, user_id="uuid-1")

    assert result["count"] == 4


# ── reset ─────────────────────────────────────────────────────────────────────

def test_reset_clears_counter():
    """reset() calls Supabase update with count=0 and restricted_until=None."""
    with patch("agentic_traveler.tools.db_client.get_db") as mock_get_db:
        reset("uuid-123")

    mock_get_db.return_value.table.assert_called_with("off_topic_state")
    update_call = mock_get_db.return_value.table.return_value.update
    call_args = update_call.call_args[0][0]
    assert call_args["count"] == 0
    assert call_args["restricted_until"] is None


def test_reset_with_no_user_id():
    """reset() is a no-op when user_id is empty."""
    with patch("agentic_traveler.tools.db_client.get_db") as mock_get_db:
        reset("")

    mock_get_db.assert_not_called()
