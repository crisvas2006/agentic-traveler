import functions_framework
from flask import Request, jsonify
import os
from agentic_traveler.orchestrator.agent import OrchestratorAgent

# Initialize the agent globally to reuse connections (like Firestore client)
orchestrator_agent = OrchestratorAgent()

@functions_framework.http
def telegram_webhook(request: Request):
    """
    HTTP Cloud Function that receives Telegram updates via Make.
    """
    
    # 1. Security Check
    secret_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    expected_token = os.environ.get("TELEGRAM_SECRET_TOKEN")
    
    if expected_token and secret_token != expected_token:
        return jsonify({"error": "Unauthorized"}), 403

    # 2. Parse Payload
    request_json = request.get_json(silent=True)
    if not request_json:
        return jsonify({"error": "Invalid JSON"}), 400

    # Expected payload structure from Make:
    # {
    #   "telegramUserId": "123456",
    #   "messageText": "Hello",
    #   ...
    # }
    
    telegram_user_id = str(request_json.get("telegramUserId", ""))
    message_text = request_json.get("messageText", "")

    if not telegram_user_id:
        return jsonify({"error": "Missing telegramUserId"}), 400

    # 3. Process with Agent
    response = orchestrator_agent.process_request(telegram_user_id, message_text)

    # 4. Return Response
    return jsonify(response), 200
