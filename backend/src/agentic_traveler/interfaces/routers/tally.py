import logging

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

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
    "question_1rxjbl": "location"
}

def _flatten_tally_fields(fields: list[dict]) -> dict:
    """Convert Tally 'fields' into a flat dict."""
    result: dict = {}

    for f in fields:
        original_key = f.get("key") or f.get("label") or f.get("id")
        field_key = QUESTION_KEY_MAP.get(original_key, original_key)
        
        # Intercept idToken hidden field
        if f.get("label") == "idToken" or (original_key and original_key.startswith("question_dPyN4N")):
            field_key = "idToken"

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

def _process_background_profiling(user_uuid: str, form_response: dict) -> None:
    """Run ProfileAgent in the background to build the Traveler DNA profile."""
    import json
    from agentic_traveler.orchestrator.profile_agent import ProfileAgent
    from agentic_traveler.tools.user_repo import UserRepository
    from agentic_traveler.tools.db_client import get_db

    logger.info("Executing background traveler DNA profiling for user %s", user_uuid)
    
    # Check credit balance before executing profiling LLM call
    try:
        credits_res = get_db().table("credits").select("balance").eq("user_id", user_uuid).maybe_single().execute()
        balance = credits_res.data.get("balance", 0) if credits_res and credits_res.data else 0
        if balance <= 0:
            logger.warning("Dropped background traveler DNA profiling for user %s: No credits remaining (balance=%d).", user_uuid, balance)
            return
    except Exception:
        logger.exception("Failed to check credits before running ProfileAgent for user %s", user_uuid)
        return

    try:
        token_records = []
        profile_agent = ProfileAgent()

        def _safe_serialize(obj):
            if isinstance(obj, dict):
                return {k: _safe_serialize(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_safe_serialize(v) for v in obj]
            try:
                json.dumps(obj)
                return obj
            except (TypeError, ValueError):
                return str(obj)

        safe_form_data = _safe_serialize(form_response)
        structured_data, response, latency_ms = profile_agent.build_initial_profile(
            {"form_response": safe_form_data},
            user_uuid=user_uuid,
            token_records=token_records
        )

        if response:
            from agentic_traveler.analytics import usage_tracker
            usage = usage_tracker.log_and_accumulate(
                agent_name="profile_agent",
                model_name=profile_agent._model_name,
                user_id=user_uuid,
                response=response,
                latency_ms=latency_ms,
            )
            if token_records is not None:
                token_records.append({
                    "model_name": profile_agent._model_name,
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "agent_name": "profile_agent",
                })

        UserRepository().upsert_structured_profile(user_uuid, structured_data)
        logger.info("Background profiling successfully completed for user %s", user_uuid)

        # Append a personalized acknowledgment message to the web chat thread
        condensed_heart = structured_data.get("short_summary") or structured_data.get("summary", "No summary available.")
        try:
            from agentic_traveler.tools.chat_repo import ChatRepository

            chat_repo = ChatRepository()
            tags = structured_data.get("tags", [])
            tags_str = ", ".join(tags) if tags else "None"
            
            acknowledgment_body = (
                f"🧠 **Your Traveler DNA Has Been Mapped!**\n\n"
                f"I have successfully analyzed your onboarding responses and mapped out your unique travel style! Here is the heart of your Traveler DNA:\n\n"
                f"🏷️ **Traveler Style Tags:**\n"
                f"_{tags_str}_\n\n"
                f"📋 **Traveler DNA Summary:**\n"
                f"{condensed_heart}\n\n"
                f"I will now tailor all our future planning sessions, itineraries, and recommendations to match this profile! What would you like to explore next?"
            )
            
            chat_repo.append_agent_message(
                user_id=user_uuid,
                body=acknowledgment_body,
                source="web"
            )
            logger.info("Successfully appended Tally acknowledgment message for user %s", user_uuid)
        except Exception:
            logger.exception("Failed to append Tally acknowledgment message for user %s", user_uuid)

    except Exception:
        logger.exception("Failed to build background profile for user %s", user_uuid)

    # 3. Combined Credit Deduction, Global Metrics, and Telemetry
    # This runs regardless of whether the second LLM call succeeded, using whatever records we gathered.
    if token_records:
        try:
            from agentic_traveler.economy import credit_manager
            credit_manager.record_usage_and_bill(
                user_id=user_uuid,
                token_records=token_records,
                default_agent_name="profile_agent",
                run_async=False,
            )
        except Exception:
            logger.exception("Failed to deduct combined credits or record metrics for background onboarding profiling.")

@router.post("/tally-webhook", dependencies=[Depends(verify_tally_token)])
async def tally_webhook(payload: TallyWebhookPayload, background_tasks: BackgroundTasks):
    """
    Handle incoming Tally form submissions.
    Updates an existing linked user in Supabase.
    """
    body = payload.model_dump()
    
    # In case the JSON payload is totally empty (FastAPI will probably reject but just in case)
    if not body:
        raise HTTPException(status_code=400, detail="Invalid JSON")

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
    
    location = user_fields.pop("location", None)
    id_token = user_fields.pop("idToken", None)
    
    try:
        db = get_db()
        web_user_id = None
        
        if not id_token:
            logger.warning("Dropped Tally submission %s: Missing idToken", response_id)
            return {"status": "dropped", "reason": "Missing idToken"}

        # Check if token exists in link_tokens under tally_submission kind
        token_res = (
            db.table("link_tokens")
            .select("user_id, expires_at")
            .eq("token", id_token)
            .eq("kind", "tally_submission")
            .maybe_single()
            .execute()
        )
        if token_res and token_res.data:
            from datetime import datetime, timezone
            expires_raw = token_res.data["expires_at"]
            if expires_raw.endswith("Z"):
                expires_raw = expires_raw[:-1] + "+00:00"
            expires_at = datetime.fromisoformat(expires_raw)
            
            if expires_at >= datetime.now(timezone.utc):
                web_user_id = token_res.data["user_id"]
                logger.info("Found matching tally_submission idToken resolving to user_id=%s", web_user_id)
            else:
                logger.warning("Tally idToken expired: %s", id_token)
            
            # Consume single-use token
            db.table("link_tokens").delete().eq("token", id_token).execute()
        else:
            logger.warning("Tally idToken not found: %s", id_token)

        if not web_user_id:
            logger.warning("Dropped Tally submission %s: Invalid or expired idToken %s", response_id, id_token)
            return {"status": "dropped", "reason": "Invalid or expired idToken"}

        update_data = {
            "submission_id": response_id,
        }
        if location is not None:
            update_data["location"] = location

        resp = db.table("users").update(update_data).eq("id", web_user_id).execute()
        
        if not resp.data:
            logger.error("Failed to update existing web user %s for tally submission %s", web_user_id, response_id)
            raise HTTPException(status_code=500, detail="Database update failed")
        
        user_id = web_user_id
        
        # 2. Upsert into user_profiles table
        db.table("user_profiles").upsert({
            "user_id": user_id,
            "form_response": user_fields,
        }).execute()
        
        # Trigger background Traveler DNA profiling
        background_tasks.add_task(_process_background_profiling, user_id, user_fields)
        
        logger.info("Successfully processed Tally webhook for submission %s", response_id)
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception:
        logger.exception("Error processing Tally webhook")
        raise HTTPException(status_code=500, detail="Internal server error")
