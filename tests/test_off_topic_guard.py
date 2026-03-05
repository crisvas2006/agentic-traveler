"""
Tests for the off-topic guard module.

Tests use plain dicts and mocks — no real Firestore calls.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from agentic_traveler.off_topic_guard import (
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
    return {"user_name": "Test", "off_topic": off_topic}


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


def test_counter_increments():
    """Each off-topic record increments the count."""
    ref = MagicMock()
    now = datetime.now(timezone.utc).isoformat()

    doc = _user_doc(count=2, last_flagged_ts=now)
    result = record_off_topic(doc, ref)
    assert result["count"] == 3
    assert result["restricted"] is False
    ref.update.assert_called_once()


def test_restriction_after_threshold():
    """User is restricted after THRESHOLD consecutive off-topic messages."""
    ref = MagicMock()
    now = datetime.now(timezone.utc).isoformat()

    doc = _user_doc(count=THRESHOLD - 1, last_flagged_ts=now)
    result = record_off_topic(doc, ref)
    assert result["count"] == THRESHOLD
    assert result["restricted"] is True
    assert "restricted_until" in result

    # Verify Firestore was called with restriction
    call_args = ref.update.call_args[0][0]
    assert "off_topic.restricted_until" in call_args


def test_reset_clears_counter():
    """reset() writes count=0 and restricted_until=None to Firestore."""
    ref = MagicMock()
    reset(ref)
    ref.update.assert_called_once()
    call_args = ref.update.call_args[0][0]
    assert call_args["off_topic.count"] == 0
    assert call_args["off_topic.restricted_until"] is None


def test_auto_reset_after_window():
    """Counter resets if the last flag was more than RESET_WINDOW_SECONDS ago."""
    ref = MagicMock()
    old_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=RESET_WINDOW_SECONDS + 60)
    ).isoformat()

    # User had 4 off-topic messages, but last flag was >1h ago
    doc = _user_doc(count=4, last_flagged_ts=old_ts)
    result = record_off_topic(doc, ref)
    # Count should be 1 (reset to 0, then incremented)
    assert result["count"] == 1
    assert result["restricted"] is False


def test_no_auto_reset_within_window():
    """Counter does NOT reset if the last flag was recent."""
    ref = MagicMock()
    recent_ts = (
        datetime.now(timezone.utc) - timedelta(seconds=30)
    ).isoformat()

    doc = _user_doc(count=3, last_flagged_ts=recent_ts)
    result = record_off_topic(doc, ref)
    assert result["count"] == 4


def test_restriction_message_includes_time():
    """Restriction message includes the unlock time."""
    future = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
    doc = _user_doc(restricted_until=future)
    msg = is_restricted(doc)
    assert "UTC" in msg
    assert "min remaining" in msg


def test_record_with_no_ref():
    """record_off_topic works without crashing when ref is None."""
    doc = _user_doc()
    result = record_off_topic(doc, None)
    assert result["count"] == 1
    assert result["restricted"] is False


def test_reset_with_no_ref():
    """reset() is a no-op when ref is None."""
    reset(None)  # should not raise
