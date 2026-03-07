import os
import functions_framework
from flask import jsonify
from google.cloud import firestore

PROJECT_ID = "graphic-jet-472816-v9"
DATABASE_ID = "agentic-traveler-db"
USERS_COLLECTION = "users"

TALLY_WEBHOOK_TOKEN = os.getenv("TALLY_WEBHOOK_TOKEN")

db = firestore.Client(project=PROJECT_ID, database=DATABASE_ID)

QUESTION_KEY_MAP = {
    "question_WAg4pv": "trip_success_factors",
    "question_aByWrb": "travel_bubble",
    "question_GrgWr2": "cultural_spiritual_importance",
    "question_6d9q1J": "local_immersion",
    "question_OAgvAp": "solo_freedom",
    "question_7deQJR": "morning_vibe",
    "question_blDa2Z": "physical_intensity",
    "question_Al0k6z": "energy_strategy",
    "question_rlp70X": "discomfort_tolerance_score",
    "question_BGgvLK": "unexpected_event_reaction",
    "question_kYpL0e": "splurge_priority",
    "question_vNpR0D": "budget_personality",
    "question_KMgXPV": "deal_breakers",
    "question_Ldg8Ep": "name",
    "question_1rxjbl": "location"
}

def _flatten_tally_fields(fields: list[dict]) -> dict:
    """
    Convert Tally 'fields' into a flat dict.
    """
    result: dict = {}

    for f in fields:
        original_key = f.get("key") or f.get("label") or f.get("id")
        field_key = QUESTION_KEY_MAP.get(original_key, original_key)

        field_type = f.get("type")
        raw_value = f.get("value")
        options = f.get("options", [])

        # Skip per-option checkbox fields with value true/false
        if field_type == "CHECKBOXES" and not isinstance(raw_value, list):
            continue

        # Map ids -> text for choice-like questions
        if field_type in ("MULTIPLE_CHOICE", "MULTI_SELECT", "CHECKBOXES") and isinstance(raw_value, list):
            id_to_text = {opt["id"]: opt["text"] for opt in options}
            texts = [id_to_text.get(v, v) for v in raw_value]

            if field_type == "MULTIPLE_CHOICE":
                value = texts[0] if texts else None
            else:
                value = texts
        else:
            value = raw_value

        if field_key and value is not None:
            result[field_key] = value

    return result


@functions_framework.http
def tally_webhook(request):
    if request.method == "GET":
        return "ok", 200

    if TALLY_WEBHOOK_TOKEN:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {TALLY_WEBHOOK_TOKEN}":
            return "Unauthorized", 401

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return "Invalid JSON", 400

    submission = body.get("data") or body

    response_id = (
        submission.get("responseId")
        or submission.get("submissionId")
        or submission.get("id")
    )
    if not response_id:
        return "Missing responseId", 400

    fields = submission.get("fields", [])
    userFields = _flatten_tally_fields(fields)
    
    flat = {}
    flat["event_id"] = body.get("eventId")
    flat["submissionId"] = submission.get("submissionId")
    flat["event_type"] = body.get("eventType")
    flat["webhook_created_at"] = body.get("createdAt")
    flat["webhook_received_at"] = firestore.SERVER_TIMESTAMP
    flat["source"] = "tally"

    flat["name"] = userFields.pop("name", None)
    #flat["phone_number"] = userFields.pop("phone_number", None)
    flat["location"] = userFields.pop("location", None)
    
    # Everything else goes into user_profile.form_response
    flat["user_profile"] = {
        "form_response": userFields
    }

    db.collection(USERS_COLLECTION).document(response_id).set(flat, merge=True)

    return jsonify({"status": "ok"}), 200
