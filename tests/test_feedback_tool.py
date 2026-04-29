"""Tests for FeedbackTool."""

from unittest.mock import MagicMock, patch


def _make_mock_db():
    """Return a MagicMock Firestore client."""
    return MagicMock()


def test_record_appends_document_with_correct_fields():
    """FeedbackTool.record should write a document with all required fields."""
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

    with patch("google.cloud.firestore.Client", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="user123",
            text="That's not what I meant",
            category="confusion",
            user_doc=user_doc,
            _sync=True,
        )

    mock_db.collection.assert_called_with("feedback")
    add_call = mock_db.collection.return_value.add
    assert add_call.called

    doc = add_call.call_args[0][0]
    assert doc["user_id"] == "user123"
    assert doc["text"] == "That's not what I meant"
    assert doc["category"] == "confusion"
    assert "timestamp" in doc
    assert len(doc["conversation_context"]) == 6  # all 6 messages = 3 exchanges


def test_record_truncates_context_to_last_6():
    """Should return at most 6 messages regardless of history length."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    messages = [{"role": "user", "text": f"msg {i}"} for i in range(20)]
    user_doc = {"conversation_history": {"recent_messages": messages}}

    mock_db = _make_mock_db()
    with patch("google.cloud.firestore.Client", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="u1",
            text="test",
            category="other",
            user_doc=user_doc,
            _sync=True,
        )

    doc = mock_db.collection.return_value.add.call_args[0][0]
    assert len(doc["conversation_context"]) == 6


def test_unknown_category_coerced_to_other():
    """Unknown category strings should fall back to 'other'."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    mock_db = _make_mock_db()
    with patch("google.cloud.firestore.Client", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="u1",
            text="weird feedback",
            category="INVALID_CATEGORY",
            _sync=True,
        )

    doc = mock_db.collection.return_value.add.call_args[0][0]
    assert doc["category"] == "other"


def test_record_with_no_user_doc():
    """Feedback without user_doc should store empty conversation_context."""
    from agentic_traveler.tools.feedback_tool import FeedbackTool

    mock_db = _make_mock_db()
    with patch("google.cloud.firestore.Client", return_value=mock_db):
        tool = FeedbackTool()
        tool.record(
            user_id="u1",
            text="I love this bot!",
            category="positive",
            user_doc=None,
            _sync=True,
        )

    doc = mock_db.collection.return_value.add.call_args[0][0]
    assert doc["conversation_context"] == []
