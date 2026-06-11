import logging
import os
import time
from collections import defaultdict
from threading import Lock

import requests as http_requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from agentic_traveler.analytics import metrics_tracker
from agentic_traveler.core.sanitize import sanitize_user_input, sanitize_telegram_markdown
from agentic_traveler.core.markdown_profile import degrade_for_telegram
from agentic_traveler.guards import off_topic_guard
from agentic_traveler.interfaces.dependencies import (
    verify_telegram_ip,
    verify_telegram_secret,
)
from agentic_traveler.interfaces.schemas import TelegramWebhookPayload
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.orchestrator.sagas.planning import (
    _SLOT_CHOICES,
    ui_block_from_wire,
)
from agentic_traveler.tools.chat_repo import ChatRepository
from agentic_traveler.tools.user_repo import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "").strip()
if not FRONTEND_ORIGIN:
    raise RuntimeError("Missing required environment variable: FRONTEND_ORIGIN")

# Base Tally form URL (used for personalized onboarding deep-links sent over
# Telegram). Fail fast at startup if missing so a misconfigured deploy can't
# silently send broken links.
TALLY_FORM_URL = os.getenv("TALLY_FORM_URL", "").strip()
if not TALLY_FORM_URL:
    raise RuntimeError("Missing required environment variable: TALLY_FORM_URL")

# ── rate limiting (in-memory, per-user) ──

RATE_LIMIT_PER_MIN = 10
RATE_LIMIT_PER_HOUR = 60
DISABLE_RATE_LIMIT = os.getenv("DISABLE_RATE_LIMIT", "").lower() in ("1", "true")

_rate_lock = Lock()
_user_timestamps: dict[str, list[float]] = defaultdict(list)

def _is_rate_limited(user_id: str) -> bool:
    """Check if user has exceeded message rate limits. Returns False immediately if rate limiting is disabled."""
    if DISABLE_RATE_LIMIT:
        return False
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
_chat_repo_instance: ChatRepository | None = None

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

def get_chat_repo() -> ChatRepository:
    global _chat_repo_instance
    if _chat_repo_instance is None:
        _chat_repo_instance = ChatRepository()
    return _chat_repo_instance

# ── Telegram helpers (zero-overhead performance testing mocks) ──

MOCK_TELEGRAM = os.getenv("MOCK_TELEGRAM", "").lower() in ("1", "true")

if MOCK_TELEGRAM:
    logger.info("⚡ MOCK_TELEGRAM mode active: Outgoing Telegram API calls will be bypassed")

    def send_telegram_message(
        chat_id: int | str, text: str, reply_markup: dict | None = None,
    ) -> int | None:
        """Mock message sender that bypasses external HTTP requests."""
        text = degrade_for_telegram(text)
        logger.debug("MOCK_TELEGRAM: sent message to %s: %s", chat_id, text[:60])
        return 888888  # Synthetic message ID

    def edit_telegram_message(
        chat_id: int | str, message_id: int, text: str,
        reply_markup: dict | None = None,
    ) -> None:
        """Mock message editor that bypasses external HTTP requests."""
        text = degrade_for_telegram(text)
        logger.debug("MOCK_TELEGRAM: edited message %s to %s", message_id, text[:60])
        return

    def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
        """Mock callback-query acknowledger."""
        logger.debug("MOCK_TELEGRAM: answered callback %s", callback_query_id)
        return
else:
    def send_telegram_message(
        chat_id: int | str, text: str, reply_markup: dict | None = None,
    ) -> int | None:
        """Send a message via the Telegram API with Markdown formatting.

        ``reply_markup`` (e.g. an inline keyboard) is attached only to the final
        chunk so a multi-part message keeps its buttons at the bottom (Task 43)."""
        text = degrade_for_telegram(text)
        text = sanitize_telegram_markdown(text)
        last_message_id = None
        chunk_starts = list(range(0, len(text) or 1, 4096))
        for i in chunk_starts:
            chunk = text[i: i + 4096]
            is_last = i == chunk_starts[-1]
            payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "Markdown"}
            if reply_markup is not None and is_last:
                payload["reply_markup"] = reply_markup
            try:
                resp = http_requests.post(
                    f"{TELEGRAM_API}/sendMessage",
                    json=payload,
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

    def edit_telegram_message(
        chat_id: int | str, message_id: int, text: str,
        reply_markup: dict | None = None,
    ) -> None:
        """Edit an existing Telegram message with new Markdown text.

        ``reply_markup`` attaches/refreshes an inline keyboard (Task 43)."""
        if not text:
            text = "Sorry, I had trouble coming up with a response."

        if len(str(text)) > 4000:
            text = str(text)[:4000] + "\n\n...(message truncated)"
        else:
            text = str(text)

        text = degrade_for_telegram(text)
        text = sanitize_telegram_markdown(text)
        payload: dict = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        try:
            resp = http_requests.post(
                f"{TELEGRAM_API}/editMessageText",
                json=payload,
                timeout=10,
            )
            if not resp.ok:
                logger.warning(
                    "Telegram editMessageText failed (%s): %s. Retrying plain text.",
                    resp.status_code, resp.text,
                )
                retry_payload: dict = {
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                }
                if reply_markup is not None:
                    retry_payload["reply_markup"] = reply_markup
                resp2 = http_requests.post(
                    f"{TELEGRAM_API}/editMessageText",
                    json=retry_payload,
                    timeout=10,
                )
                if not resp2.ok:
                    logger.error(
                        "Telegram editMessageText plain text fallback failed (%s): %s",
                        resp2.status_code, resp2.text,
                    )
        except Exception:
            logger.exception("Failed to edit Telegram message %s", message_id)

    def answer_callback_query(callback_query_id: str, text: str | None = None) -> None:
        """Acknowledge an inline-keyboard tap so the client stops its spinner
        (Task 43). Best-effort — a failed ack never blocks the reply."""
        payload: dict = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        try:
            http_requests.post(
                f"{TELEGRAM_API}/answerCallbackQuery", json=payload, timeout=10,
            )
        except Exception:
            logger.exception("Failed to answer callback query %s", callback_query_id)

# ── inline keyboard (Task 43) ──

def _inline_keyboard(slot_request: dict | None) -> dict | None:
    """Build a one-button-per-option inline keyboard from a slot_request wire
    dict, or None when there's nothing tappable. Only categorical preference
    slots (``multi_choice``) become buttons; the task-44 direction confirmation
    (``quick_reply``) stays plain text on Telegram (inline buttons can't send a
    free-text message, which is what that flow needs)."""
    ui = ui_block_from_wire(slot_request)
    if not ui or ui.get("kind") != "multi_choice" or not slot_request:
        return None
    slot = slot_request["slot"]
    rows = []
    for c in slot_request.get("choices") or []:
        # callback_data hard cap is 64 bytes (Telegram). slot + value are short
        # enums, but guard defensively and drop any option that wouldn't fit.
        cb = f"slot|{slot}|{c['value']}"
        if len(cb.encode("utf-8")) > 64:
            continue
        rows.append([{"text": c["label"], "callback_data": cb}])
    return {"inline_keyboard": rows} if rows else None


def _choice_label(slot: str, value: str) -> str:
    """Human label for a chosen (slot, value), for the edited confirmation text."""
    for c in _SLOT_CHOICES.get(slot, []):
        if str(c.value) == str(value):
            return c.label
    return value


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

    # Status events (Task 37) arrive as dict payloads {"phase","text",...}. The
    # FIRST status becomes the placeholder message (no generic "Thinking…" — we
    # only show real states from the registry); later statuses edit it, throttled
    # to ≥1 s so each state is readable and doesn't flicker. on_delta is never
    # wired for Telegram, so the bot never shows a partial reply — only status,
    # then one final edit to the complete reply (which preempts any pending state).
    _ph = {"id": None}
    _last_status_edit = {"t": 0.0}

    def update_status(payload: dict):
        text = (payload or {}).get("text") or (payload or {}).get("message") or ""
        if not text:
            return
        now = time.time()
        if _ph["id"] is None:
            _ph["id"] = send_telegram_message(chat_id, text)
            _last_status_edit["t"] = now
            return
        if now - _last_status_edit["t"] < 1.0:
            return
        _last_status_edit["t"] = now
        edit_telegram_message(chat_id, _ph["id"], text)

    try:
        response = get_orchestrator().process_request(
            user_id, text, status_callback=update_status
        )
        logger.info("webhook received from orchestrator: %s", response)
        reply = response.get("text", "Something went wrong.")
    except Exception:
        logger.exception("Orchestrator error for user %s", user_id)
        reply = "Sorry, I hit an error processing your message. Please try again."
        response = {"action": "ERROR"}

    # Tappable slot choices (Task 43) → inline keyboard on the reply message.
    keyboard = _inline_keyboard(response.get("slot_request"))

    # Mirror the exchange into the web-visible messages table so Telegram users
    # see their full history when they sign in on the web. Best-effort: never
    # block the Telegram reply on a persistence failure.
    internal_user_id = user_doc.get("id") if user_doc else None
    if internal_user_id:
        try:
            get_chat_repo().append_pair(
                user_id=internal_user_id,
                user_body=text,
                agent_body=reply,
                source="telegram",
                agent_metadata={"action": response.get("action")},
            )
        except Exception:
            logger.exception("chat_repo append failed for telegram user %s", user_id)

    placeholder_msg_id = _ph["id"]
    if placeholder_msg_id:
        logger.info("Editing placeholder %s for chat %s (reply_len=%d)", placeholder_msg_id, chat_id, len(reply))
        edit_telegram_message(chat_id, placeholder_msg_id, reply, reply_markup=keyboard)
        if len(reply) > 4000:
            send_telegram_message(chat_id, reply[4000:])
    else:
        logger.info("No placeholder — sending fresh reply to chat %s", chat_id)
        send_telegram_message(chat_id, reply, reply_markup=keyboard)


def _process_callback_bg(callback_query: dict) -> None:
    """Handle an inline-keyboard tap (Task 43). Parses ``slot|<slot>|<value>``,
    applies the selection deterministically via the orchestrator, edits the
    original prompt to show the chosen answer, and sends the next prompt.

    Always answers the callback first so the client spinner clears even on the
    no-op / malformed paths (AC-6, §6)."""
    cq_id = str(callback_query.get("id") or "")
    if cq_id:
        answer_callback_query(cq_id)

    data = str(callback_query.get("data") or "")
    message = callback_query.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("id") or message.get("message_id")
    from_user = callback_query.get("from") or {}
    user_id = str(from_user.get("id") or "")

    parts = data.split("|")
    if len(parts) != 3 or parts[0] != "slot" or not chat_id or not user_id:
        logger.warning("Ignoring malformed/expired callback_data=%r", data[:64])
        return
    _, slot, value = parts

    user_doc = get_user_tool().get_user_by_telegram_id(user_id)
    if not user_doc:
        logger.warning("Callback from unknown telegram user %s", user_id)
        return

    label = _choice_label(slot, value)

    # Disable the original keyboard and show the chosen answer.
    if message_id:
        orig = (message.get("text") or "").strip()
        edited = f"{orig}\n\n✅ {label}" if orig else f"✅ {label}"
        edit_telegram_message(chat_id, message_id, edited, reply_markup={"inline_keyboard": []})

    try:
        response = get_orchestrator().process_request(
            user_id, label, selection={"slot": slot, "values": [value]},
        )
        reply = response.get("text", "Something went wrong.")
    except Exception:
        logger.exception("Callback selection failed for user %s", user_id)
        reply = "Sorry, I hit an error applying that choice. Please try again."
        response = {"action": "ERROR"}

    keyboard = _inline_keyboard(response.get("slot_request"))
    send_telegram_message(chat_id, reply, reply_markup=keyboard)

    # Mirror the exchange into the web-visible thread (chosen label + next prompt).
    internal_user_id = user_doc.get("id")
    if internal_user_id:
        try:
            get_chat_repo().append_pair(
                user_id=internal_user_id, user_body=label, agent_body=reply,
                source="telegram", agent_metadata={"action": response.get("action")},
            )
        except Exception:
            logger.exception("chat_repo append failed for telegram callback user %s", user_id)


def _handle_telegram_link(chat_id: int, telegram_id: str, token: str) -> None:
    """Handle short UUID link token to associate Telegram account to web user.

    Tokens are stored in public.link_tokens (UUID, 36 chars).
    The full ?start= payload is "link_" + token = 41 bytes — inside Telegram's
    64-byte hard cap for deep-link start parameters.
    """
    import uuid
    from datetime import datetime, timezone, timedelta
    from agentic_traveler.tools.db_client import get_db

    # Validate that the token is a valid UUID to prevent PostgREST/PostgreSQL
    # syntax errors (22P02) when querying link_tokens.
    try:
        uuid.UUID(token)
    except ValueError:
        logger.warning("Invalid UUID link token received in Telegram deep-link: %s", token)
        send_telegram_message(
            chat_id,
            "❌ This link is invalid or has already been used. "
            "Please generate a new one from your Account Settings on the web app.",
        )
        return

    db = get_db()

    # Look up the token (service role bypasses RLS).
    result = (
        db.table("link_tokens")
        .select("user_id, expires_at")
        .eq("token", token)
        .maybe_single()
        .execute()
    )

    if not result.data:
        logger.warning("Telegram link token not found: %s", token)
        send_telegram_message(
            chat_id,
            "❌ This link is invalid or has already been used. "
            "Please generate a new one from your Account Settings on the web.",
        )
        return

    row = result.data
    expires_raw = row["expires_at"]
    # Supabase returns ISO-8601 with timezone; normalise to aware datetime.
    if expires_raw.endswith("Z"):
        expires_raw = expires_raw[:-1] + "+00:00"
    expires_at = datetime.fromisoformat(expires_raw)

    if expires_at < datetime.now(timezone.utc):
        # Clean up the expired row.
        db.table("link_tokens").delete().eq("token", token).execute()
        send_telegram_message(
            chat_id,
            "❌ This link has expired (links are valid for 10 minutes). "
            "Please generate a new one from your Account Settings on the web.",
        )
        return

    web_user_id = row["user_id"]

    # Consume the token — single-use.
    db.table("link_tokens").delete().eq("token", token).execute()

    success, msg = get_user_tool().link_telegram_to_web_user(web_user_id, telegram_id)
    send_telegram_message(chat_id, msg)

    if success:
        metrics_tracker.record_interaction(user_id=telegram_id, is_new_user=False)
        
        # Check if they have completed the form
        try:
            profile_res = db.table("user_profiles").select("form_response").eq("user_id", web_user_id).maybe_single().execute()
            has_completed_form = False
            if profile_res and profile_res.data:
                form_resp = profile_res.data.get("form_response")
                if form_resp and isinstance(form_resp, dict) and len(form_resp) > 0:
                    has_completed_form = True

            if not has_completed_form:
                # Check for active tally_submission token
                token_check = db.table("link_tokens").select("token, expires_at").eq("user_id", web_user_id).eq("kind", "tally_submission").execute()
                has_active_token = False
                id_token = None
                if token_check and token_check.data:
                    for r in token_check.data:
                        exp_raw = r["expires_at"]
                        if exp_raw.endswith("Z"):
                            exp_raw = exp_raw[:-1] + "+00:00"
                        if datetime.fromisoformat(exp_raw) >= datetime.now(timezone.utc):
                            has_active_token = True
                            id_token = r["token"]
                            break

                if not has_active_token:
                    tally_token_expires_at = datetime.now(timezone.utc) + timedelta(days=7)
                    tally_token_res = db.table("link_tokens").insert({
                        "user_id": web_user_id,
                        "kind": "tally_submission",
                        "expires_at": tally_token_expires_at.isoformat()
                    }).execute()
                    if tally_token_res and tally_token_res.data:
                        id_token = tally_token_res.data[0]["token"]

                if id_token:
                    onboarding_url = f"{TALLY_FORM_URL}?idToken={id_token}"
                    invitation_msg = (
                        "💡 *A Thoughtful Recommendation for Your Travels*\n\n"
                        "To help me provide highly personalized recommendations tailored to your traveler style, "
                        "you might enjoy taking 3 minutes to fill out our onboarding questionnaire! It maps out your Traveler DNA.\n\n"
                        "Here is your personalized link (valid for 7 days, and you can always generate a new one in website settings):\n"
                        f"{onboarding_url}"
                    )
                    send_telegram_message(chat_id, invitation_msg)
        except Exception:
            logger.exception("Failed to check or generate onboarding link for newly-linked user %s", web_user_id)


def _handle_start(chat_id: int, user_id: str, text: str) -> None:
    """Handle /start command — link Telegram user to Supabase profile."""
    parts = text.split(maxsplit=1)
    submission_id = parts[1].strip() if len(parts) > 1 else ""

    if submission_id.startswith("link_"):
        token = submission_id[5:]
        _handle_telegram_link(chat_id, user_id, token)
        return

    if not submission_id:
        user_doc = get_user_tool().get_user_by_telegram_id(user_id)
        name = user_doc.get("name", "Traveler") if user_doc else "Traveler"
        send_telegram_message(
            chat_id,
            f"👋 Welcome back to *Aletheia Travel*, {name}!\n\n"
            "How can I help you plan your next adventure today?",
        )
        return

    logger.warning("Unsupported or invalid deep-link start parameter received: %s (telegram_id: %s)", submission_id, user_id)
    send_telegram_message(
        chat_id,
        "⚠️ Invalid link parameter. If you wanted to link your web account, please generate a link from settings inside the web app.",
    )



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

    # Inline-keyboard taps (Task 43) arrive as callback_query, not message.
    callback_query = payload.callback_query
    if callback_query:
        cb_user_id = str((callback_query.get("from") or {}).get("id") or "")
        if cb_user_id and _is_rate_limited(cb_user_id):
            # Still answer so the client spinner clears; just don't process.
            cq_id = str(callback_query.get("id") or "")
            if cq_id:
                background_tasks.add_task(answer_callback_query, cq_id, None)
            return {"ok": True}
        background_tasks.add_task(_process_callback_bg, callback_query)
        return {"ok": True}

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

    # ── Unlinked/unregistered user guard ──
    is_link_flow = False
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        param = parts[1].strip() if len(parts) > 1 else ""
        if param.startswith("link_"):
            is_link_flow = True

    if not is_link_flow:
        user_doc = get_user_tool().get_user_by_telegram_id(user_id)
        if not user_doc:
            msg = (
                "👋 Welcome to Aletheia Travel\n\n"
                "Visit our web app for more information:\n"
                f" {FRONTEND_ORIGIN}\n\n"
                "If you want to chat here please create an account first:\n"
                f" {FRONTEND_ORIGIN}/sign-up\n\n"
                "Then go to settings and find the option to link telegram to your account."
            )
            background_tasks.add_task(send_telegram_message, chat_id, msg)
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
    else:
        logger.info("Dispatching message for user %s: %s", user_id, text[:80])
        background_tasks.add_task(_process_message_bg, chat_id, user_id, text)

    return {"ok": True}
