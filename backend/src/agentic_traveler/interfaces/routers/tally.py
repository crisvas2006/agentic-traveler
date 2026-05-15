import logging

from fastapi import APIRouter, Depends, HTTPException

from agentic_traveler.interfaces.dependencies import verify_tally_token
from agentic_traveler.interfaces.schemas import TallyWebhookPayload
from agentic_traveler.tools.db_client import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

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
    """Convert Tally 'fields' into a flat dict."""
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

@router.post("/tally-webhook", dependencies=[Depends(verify_tally_token)])
async def tally_webhook(payload: TallyWebhookPayload):
    """
    Handle incoming Tally form submissions.
    Creates a new user and user_profile in Supabase.
    """
    body = payload.model_dump()
    
    # In case the JSON payload is totally empty (FastAPI will probably reject but just in case)
    if not body:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # If the payload was purely a dictionary with extra fields, we can access them
    # Because TallyWebhookPayload allows extra fields, model_dump() includes them.
    submission = body.get("data") or body
    response_id = (
        submission.get("responseId")
        or submission.get("submissionId")
        or submission.get("id")
    )
    if not response_id:
        raise HTTPException(status_code=400, detail="Missing responseId")

    fields = submission.get("fields", [])
    user_fields = _flatten_tally_fields(fields)
    
    name = user_fields.pop("name", None)
    location = user_fields.pop("location", None)
    
    try:
        db = get_db()
        
        # 1. Upsert into users table
        resp = db.table("users").upsert(
            {
                "submission_id": response_id,
                "name": name,
                "location": location,
                "source": "tally",
            },
            on_conflict="submission_id"
        ).execute()
        
        if not resp.data:
            logger.error("Failed to insert user into Supabase for tally submission %s", response_id)
            raise HTTPException(status_code=500, detail="Database error")
            
        user_id = resp.data[0]["id"]
        
        # 2. Upsert into user_profiles table
        db.table("user_profiles").upsert({
            "user_id": user_id,
            "form_response": user_fields,
        }).execute()
        
        logger.info("Successfully processed Tally webhook for submission %s", response_id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error processing Tally webhook")
        raise HTTPException(status_code=500, detail="Internal server error")
