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
    "question_kEDXAd": "age_group",
    "question_vY7VBX": "location",
    "question_K17Aoz": "travel_budget_style",
    "question_Za4p2V": "budget_priority",
    "question_RPX1ep": "weekday_energy",
    "question_oGrYNX": "daily_rhythm",
    "question_GlNaE2": "activity_level",
    "question_OGpKqp": "trip_vibe",
    "question_VJRXWE": "structure_preference",
    "question_POMLZd": "solo_travel_comfort",
    "question_EWjeoq": "travel_deal_breakers",
    "question_OGpW7a": "personality_baseline",
    "question_VJRkzj": "travel_motivations",
    "question_POMaz1": "cultural_spiritual_importance",
    "question_EWj4xl": "discomfort_tolerance_score",
    "question_rPNxoo": "favorite_past_trip",
    "question_4rWgKr": "disliked_trip_patterns",
    "question_jPdOlQ": "solo_travel_experience",
    "question_2PqMKe": "hardest_part_solo_travel",
    "question_xYkeJd": "typical_trip_lengths",
    "question_NoKe70": "diet_lifestyle_constraints",
    "question_qVx2RO": "absolute_avoidances",
    "question_QVg67Y": "absolute_avoidances_other",
    "question_9QLz7E": "next_trip_outcome_goals",
    "question_gGyRXJ": "dream_trip_style",
    "question_yYKWrd": "extra_notes",
    "question_X0VKdz": "name",
    "question_8xv0Vr": "phone_number",
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

    flat["user_name"] = userFields.pop("name", None)
    flat["phone_number"] = userFields.pop("phone_number", None)
    flat["user_profile"] = userFields

    db.collection(USERS_COLLECTION).document(response_id).set(flat, merge=True)

    return jsonify({"status": "ok"}), 200
