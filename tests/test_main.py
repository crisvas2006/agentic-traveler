import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, Request
from agentic_traveler.main import telegram_webhook

@pytest.fixture
def app():
    app = Flask(__name__)
    return app

@pytest.fixture
def mock_request():
    req = MagicMock()
    req.headers = {}
    req.get_json.return_value = {"telegramUserId": "123", "messageText": "Hi"}
    return req

def test_webhook_missing_token_env_var(app, mock_request):
    with app.app_context():
        with patch("os.environ.get", return_value=None):
            with patch("agentic_traveler.main.orchestrator_agent.process_request") as mock_process:
                mock_process.return_value = {"text": "ok"}
                resp = telegram_webhook(mock_request)
                # Response is (json, status) tuple
                assert resp[1] == 200

def test_webhook_valid_token(app, mock_request):
    mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "secret"}
    with app.app_context():
        with patch("os.environ.get", return_value="secret"):
            with patch("agentic_traveler.main.orchestrator_agent.process_request") as mock_process:
                mock_process.return_value = {"text": "ok"}
                resp = telegram_webhook(mock_request)
                assert resp[1] == 200

def test_webhook_invalid_token(app, mock_request):
    mock_request.headers = {"X-Telegram-Bot-Api-Secret-Token": "wrong"}
    with app.app_context():
        with patch("os.environ.get", return_value="secret"):
            resp = telegram_webhook(mock_request)
            assert resp[1] == 403
