import json
import logging
import os
import time
from collections import defaultdict
from threading import Lock

import requests as http_requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from agentic_traveler.analytics import metrics_tracker
from agentic_traveler.core.sanitize import sanitize_user_input
from agentic_traveler.economy import credit_manager
from agentic_traveler.guards import off_topic_guard
from agentic_traveler.interfaces.dependencies import (
    SECRET_TOKEN,
    verify_telegram_ip,
    verify_telegram_secret,
)
from agentic_traveler.interfaces.schemas import TelegramWebhookPayload
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.tools.user_repo import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── rate limiting (in-memory, per-user) ──

RATE_LIMIT_PER_MIN = 10
RATE_LIMIT_PER_HOUR = 60

_rate_lock = Lock()
_user_timestamps: dict[str, list[float]] = defaultdict(list)

def _is_rate_limited(user_id: str) -> bool:
    """Check if user has exceeded message rate limits."""
    now = time.time()
    with _rate_lock:
        timestamps = _user_timestamps[user_id]
        timestamps[:] = [t for t in timestamps if now - t < 3600]

        last_minute = sum(1 for t in timestamps if now - t < 60)
        if last_minute >= RATE_LIMIT_PER_MIN:
            logger.warning("Rate limit (per-min) hit for user %s", user_id)
            return True
        if len(timestamps) >= RATE_LIMIT_PER_HOUR:
            logger.warning("Rate limit (per-hour) hit for user %s", user_id)
            return True

        timestamps.append(now)
        return False

# ── lazy-loaded globals (initialized on first request) ──

_user_tool_instance: UserRepository | None = None
_orchestrator_instance: OrchestratorAgent | None = None

def get_user_tool() -> UserRepository:
    global _user_tool_instance
    if _user_tool_instance is None:
        logger.info("Initializing lazy UserRepository...")
        _user_tool_instance = UserRepository()
    return _user_tool_instance

def get_orchestrator() -> OrchestratorAgent:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        logger.info("Initializing lazy OrchestratorAgent...")
        _orchestrator_instance = OrchestratorAgent(user_repo=get_user_tool())
    return _orchestrator_instance

# ── Telegram helpers ──

def send_telegram_message(chat_id: int | str, text: str) -> int | None:
    """Send a message via the Telegram API with Markdown formatting."""
    last_message_id = None
    for i in range(0, len(text), 4096):
        chunk = text[i: i + 4096]
        try:
            resp = http_requests.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if not resp.ok:
                logger.warning(
                    "Telegram Markdown send failed (%s), retrying plain text.",
                    resp.status_code,
                )
                resp = http_requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                    timeout=10,
                )
                if not resp.ok:
                    logger.error(
                        "Telegram sendMessage failed: %s %s",
                        resp.status_code, resp.text,
                    )
                    continue

            result = resp.json()
            if result.get("ok"):
                last_message_id = result["result"].get("message_id")

        except Exception:
            logger.exception("Failed to send Telegram message to %s", chat_id)

    return last_message_id

def edit_telegram_message(chat_id: int | str, message_id: int, text: str) -> None:
    """Edit an existing Telegram message with new Markdown text."""
    if not text:
        text = "Sorry, I had trouble coming up with a response."

    if len(str(text)) > 4000:
        text = str(text)[:4000] + "\n\n...(message truncated)"
    else:
        text = str(text)
    try:
        resp = http_requests.post(
            f"{TELEGRAM_API}/editMessageText",
            json={
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
        if not resp.ok:
            logger.warning(
                "Telegram editMessageText failed (%s): %s. Retrying plain text.",
                resp.status_code, resp.text,
            )
            resp2 = http_requests.post(
                f"{TELEGRAM_API}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                },
                timeout=10,
            )
            if not resp2.ok:
                logger.error(
                    "Telegram editMessageText plain text fallback failed (%s): %s",
                    resp2.status_code, resp2.text,
                )
    except Exception:
        logger.exception("Failed to edit Telegram message %s", message_id)

# ── background processing functions ──

def _process_message_bg(chat_id: int, user_id: str, text: str) -> None:
    """Process a regular user message in a background task."""
    # Quick restriction pre-check
    user_doc = get_user_tool().get_user_by_telegram_id(user_id)
    if user_doc:
        restriction_msg = off_topic_guard.is_restricted(user_doc)
        if restriction_msg:
            send_telegram_message(chat_id, restriction_msg)
            return

    placeholder_msg_id = send_telegram_message(chat_id, "⏳ Thinking...")

    def update_status(msg: str):
        if placeholder_msg_id:
            edit_telegram_message(chat_id, placeholder_msg_id, msg)

    try:
        response = get_orchestrator().process_request(
            user_id, text, status_callback=update_status
        )
        logger.info("webhook received from orchestrator: %s", response)
        reply = response.get("text", "Something went wrong.")
    except Exception:
        logger.exception("Orchestrator error for user %s", user_id)
        reply = "Sorry, I hit an error processing your message. Please try again."

    if placeholder_msg_id:
        logger.info("Editing placeholder %s for chat %s (reply_len=%d)", placeholder_msg_id, chat_id, len(reply))
        edit_telegram_message(chat_id, placeholder_msg_id, reply)
        if len(reply) > 4000:
            send_telegram_message(chat_id, reply[4000:])
    else:
        logger.info("No placeholder — sending fresh reply to chat %s", chat_id)
        send_telegram_message(chat_id, reply)


def _handle_start(chat_id: int, user_id: str, text: str) -> None:
    """Handle /start command — link Telegram user to Supabase profile."""
    parts = text.split(maxsplit=1)
    submission_id = parts[1].strip() if len(parts) > 1 else ""

    if not submission_id:
        send_telegram_message(
            chat_id,
            "👋 Welcome to TripGenie! To get started, please fill out "
            "your travel profile:\nhttps://tally.so/r/ODPGak",
        )
        return

    logger.debug("Submission ID: %s, User ID: %s", submission_id, user_id)
    user_doc, is_update = get_user_tool().link_telegram_user(submission_id, user_id)
    if user_doc:
        name = user_doc.get("name", user_doc.get("user_name", "Traveler"))

        placeholder_msg_id = send_telegram_message(chat_id, "⏳ Mapping your travel DNA...")

        try:
            from agentic_traveler.orchestrator.profile_agent import ProfileAgent
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

            form_response = user_doc.get("user_profile", {}).get("form_response", {})
            if not form_response:
                logger.warning(
                    "user_profile.form_response is empty for user %s — profile may be incomplete.",
                    user_id,
                )

            safe_form_data = _safe_serialize(form_response)
            logger.info("Building profile from form_response with %d keys.", len(safe_form_data))

            structured_data = profile_agent.build_initial_profile(
                {"form_response": safe_form_data}
            )
            greeting = structured_data.pop("greeting", None)

            user_uuid = user_doc.get("id")
            if user_uuid:
                get_user_tool().upsert_structured_profile(user_uuid, structured_data)

            if not greeting:
                greeting = f"Great to meet you, {name}! Your profile is mapped out and ready to go."

            examples = (
                "You can now ask me anything — try:\n"
                "• \"Suggest me a 5-day trip in May\"\n"
                "• \"I want a nature getaway under 800 EUR\"\n"
                "• \"What do you know about me?\""
            )

            if is_update:
                edit_telegram_message(
                    chat_id, placeholder_msg_id,
                    f"✅ Welcome back, {name}! Your profile was updated.",
                )
            else:
                edit_telegram_message(
                    chat_id, placeholder_msg_id,
                    f"✅ Welcome, {name}! Your travel profile is linked.",
                )

            send_telegram_message(chat_id, f"_{greeting}_\n\n{examples}")

            metrics_tracker.record_interaction(user_id=user_id, is_new_user=not is_update)

            # Initialize credits for new users (user_uuid is the credits FK)
            if not is_update and user_uuid:
                credit_manager.initialize_credits(user_uuid)

        except Exception:
            logger.exception("Failed to build initial profile.")
            if placeholder_msg_id:
                edit_telegram_message(chat_id, placeholder_msg_id, "✅ Linked! Ready to chat.")
            else:
                send_telegram_message(chat_id, "✅ Linked! Ready to chat.")
    else:
        send_telegram_message(
            chat_id,
            "❌ I couldn't find a profile for that link. "
            "Please make sure you've completed the travel form first:\n"
            "https://tally.so/r/ODPGak",
        )


def _handle_promo(chat_id: int, user_id: str, text: str) -> None:
    """Handle /promo <CODE> command — redeem a promo code via Telegram."""
    parts = text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) > 1 else ""

    if not code:
        send_telegram_message(
            chat_id,
            "🎫 To redeem a promo code, send:\n/promo YOUR_CODE",
        )
        return

    user_doc, user_uuid = get_user_tool().get_user_with_ref(user_id)
    if not user_doc or not user_uuid:
        send_telegram_message(
            chat_id,
            "❌ You need to complete your travel profile first before using a promo code.",
        )
        return

    success, message, credits_added = credit_manager.redeem_promo(user_doc, user_uuid, code)
    send_telegram_message(chat_id, message)


# ── Webhook Route ──

@router.post(
    "/webhook/{secret}",
    dependencies=[
        Depends(verify_telegram_ip),
        Depends(verify_telegram_secret)
    ]
)
async def telegram_webhook(
    secret: str,
    payload: TelegramWebhookPayload,
    background_tasks: BackgroundTasks
):
    """
    Handle incoming Telegram updates.
    All processing is dispatched to a background task so
    that Telegram receives a 200 immediately, preventing retries.
    """
    if secret != os.getenv("TELEGRAM_SECRET_TOKEN", ""):
        logger.warning("Rejected: wrong URL path secret")
        raise HTTPException(status_code=403, detail="Forbidden")

    # FastAPI handles empty JSON gracefully with BaseModel, but let's check message
    message = payload.message
    if not message:
        return {"ok": True}

    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", ""))
    text = sanitize_user_input(message.get("text") or "")

    if not chat_id or not user_id or not text:
        return {"ok": True}

    if _is_rate_limited(user_id):
        send_telegram_message(
            chat_id,
            "⏳ You're sending messages too fast — please wait a moment.",
        )
        return {"ok": True}

    if text.startswith("/start"):
        logger.info("Dispatching /start for user %s", user_id)
        background_tasks.add_task(_handle_start, chat_id, user_id, text)
    elif text.startswith("/promo"):
        logger.info("Dispatching /promo for user %s", user_id)
        background_tasks.add_task(_handle_promo, chat_id, user_id, text)
    else:
        logger.info("Dispatching message for user %s: %s", user_id, text[:80])
        background_tasks.add_task(_process_message_bg, chat_id, user_id, text)

    return {"ok": True}
