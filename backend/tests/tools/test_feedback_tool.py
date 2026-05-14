"""Tests for FeedbackTool — patches Supabase get_db, no real network calls."""

from unittest.mock import MagicMock, patch


def _make_mock_db():
    """Return a MagicMock Supabase client."""
    mock = MagicMock()
    # Ensure chained calls return a consistent mock
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "fb-uuid"}])
    return mock


def _captured_payload(mock_db):
    """Extract the dict passed to .insert() from the mock chain."""
    return mock_db.table.return_value.insert.call_args[0][0]


def test_record_appends_document_with_correct_fields():
    """FeedbackTool.record should write a row with all required fields."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    user_doc = {
        "conversation_history": {
            "recent_messages": [
                {"role": "user", "text": "I want to go to Rome"},
                {"role": "agent", "text": "Great choice!"},
                {"role": "user", "text": "Suggest me hotels"},
                {"role": "agent", "text": "Here are some hotels..."},
                {"role": "user", "text": "That's not what I meant"},
                {"role": "agent", "text": "Sorry, let me try again"},
            ]
        }
    }

    mock_db = _make_mock_db()
    with patch("agentic_traveler.tools.db_client.get_db", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="user123",
            text="That's not what I meant",
            category="confusion",
            user_doc=user_doc,
            _sync=True,
        )

    mock_db.table.assert_called_with("feedback")
    payload = _captured_payload(mock_db)
    assert payload["user_id"] == "user123"
    assert payload["text"] == "That's not what I meant"
    assert payload["category"] == "confusion"
    assert len(payload["conversation_context"]) == 6


def test_record_truncates_context_to_last_6():
    """Should include at most 6 messages regardless of history length."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    messages = [{"role": "user", "text": f"msg {i}"} for i in range(20)]
    user_doc = {"conversation_history": {"recent_messages": messages}}

    mock_db = _make_mock_db()
    with patch("agentic_traveler.tools.db_client.get_db", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="u1",
            text="test",
            category="other",
            user_doc=user_doc,
            _sync=True,
        )

    payload = _captured_payload(mock_db)
    assert len(payload["conversation_context"]) == 6


def test_unknown_category_coerced_to_other():
    """Unknown category strings should fall back to 'other'."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    mock_db = _make_mock_db()
    with patch("agentic_traveler.tools.db_client.get_db", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="u1",
            text="weird feedback",
            category="INVALID_CATEGORY",
            _sync=True,
        )

    payload = _captured_payload(mock_db)
    assert payload["category"] == "other"


def test_record_with_no_user_doc():
    """Feedback without user_doc should store empty conversation_context."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    mock_db = _make_mock_db()
    with patch("agentic_traveler.tools.db_client.get_db", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="u1",
            text="I love this bot!",
            category="positive",
            user_doc=None,
            _sync=True,
        )

    payload = _captured_payload(mock_db)
    assert payload["conversation_context"] == []
