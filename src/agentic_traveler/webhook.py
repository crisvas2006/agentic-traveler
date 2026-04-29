"""
Flask webhook handler for Telegram Bot updates.

Security layers (defense-in-depth):
1. Secret token validation (X-Telegram-Bot-Api-Secret-Token header)
2. Secret URL path (/webhook/<secret>)
3. Telegram IP whitelist (149.154.160.0/20, 91.108.4.0/22)
4. Per-user rate limiting (10/min, 60/hour)
5. Payload validation
6. Cloud Run limits (max-instances, concurrency, timeout)
"""

import ipaddress
import logging
import os
import signal
import sys
import threading
import time
from collections import defaultdict
from threading import Lock

import requests as http_requests
from dotenv import load_dotenv
from flask import Flask, Request, jsonify, request

from agentic_traveler import credit_manager
from agentic_traveler import off_topic_guard
from agentic_traveler import metrics_tracker
from agentic_traveler.logging_config import setup_logging
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.sanitize import sanitize_user_input
from agentic_traveler.tools.firestore_user import FirestoreUserTool

load_dotenv()
setup_logging(verbose=os.getenv("VERBOSE", "").lower() in ("1", "true"))

logger = logging.getLogger(__name__)

# Suppress the WinError 10038 ("not a socket") OSError that Werkzeug's
# serve_forever thread throws during hot-reload on Windows.  It fires because
# the dev-server socket is closed by the reloader while Thread-2 is still
# mid-select().  The reload completes successfully; the traceback is purely
# cosmetic.  threading.excepthook (Python 3.8+) lets us intercept it cleanly
# without touching Werkzeug's internals.
_orig_thread_excepthook = threading.excepthook

def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
    winerror = getattr(args.exc_value, "winerror", None)
    if isinstance(args.exc_value, OSError) and winerror == 10038:
        return  # silently drop — Werkzeug socket closed during hot-reload
    _orig_thread_excepthook(args)

threading.excepthook = _thread_excepthook

app = Flask(__name__)

# ── configuration ──

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Telegram webhook IP ranges (may change — check @BotNews)
TELEGRAM_CIDRS = [
    ipaddress.ip_network("149.154.160.0/20"),
    ipaddress.ip_network("91.108.4.0/22"),
]

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
        # Prune entries older than 1 hour
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


# ── Graceful Shutdown ──

def handle_sigterm(signum, frame):
    """Graceful shutdown for Cloud Run (SIGTERM)."""
    logger.info("Received SIGTERM. Starting graceful shutdown...")
    # Flush metrics synchronously before exiting.
    # os._exit(0) is used instead of sys.exit(0) to terminate immediately
    # at the OS level without raising SystemExit, which would propagate
    # through background threads (e.g. Werkzeug's serve_forever) and cause
    # WinError 10038 / EBADF as those threads try to use now-closed sockets.
    metrics_tracker.flush(sync=True)
    logger.info("Graceful shutdown complete. Exiting.")
    os._exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


# ── IP whitelist ──

def _is_telegram_ip(req: Request) -> bool:
    """Check if the request originates from a known Telegram IP range."""
    # Cloud Run sets X-Forwarded-For; fall back to remote_addr
    forwarded = req.headers.get("X-Forwarded-For", "")
    raw_ip = forwarded.split(",")[0].strip() if forwarded else req.remote_addr
    if not raw_ip:
        return False
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        logger.warning("Invalid IP address: %s", raw_ip)
        return False
    allowed = any(ip in cidr for cidr in TELEGRAM_CIDRS)
    if not allowed:
        logger.warning("Rejected request from non-Telegram IP: %s", raw_ip)
    return allowed


# ── Telegram helpers ──

def send_telegram_message(chat_id: int | str, text: str) -> int | None:
    """Send a message via the Telegram API with Markdown formatting.
    
    Returns the message_id of the sent message (or the last message if
    chunked), or None on failure.
    """
    last_message_id = None
    # Telegram limit is 4096 chars per message
    for i in range(0, len(text), 4096):
        chunk = text[i : i + 4096]
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
                # Markdown parsing can fail on unclosed tags — retry as
                # plain text so the user always gets a response.
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
        
    # Note: If text > 4000, we truncate safely below 4096 UTF-16 code units.
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
            logger.warning("Telegram editMessageText failed (%s): %s. Retrying plain text.", resp.status_code, resp.text)
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
                logger.error("Telegram editMessageText plain text fallback failed (%s): %s", resp2.status_code, resp2.text)
    except Exception:
        logger.exception("Failed to edit Telegram message %s", message_id)





# ── lazy-loaded globals (initialized on first request) ──

_user_tool_instance = None
_orchestrator_instance = None


def get_user_tool() -> FirestoreUserTool:
    global _user_tool_instance
    if _user_tool_instance is None:
        logger.info("Initializing lazy FirestoreUserTool...")
        _user_tool_instance = FirestoreUserTool()
    return _user_tool_instance


def get_orchestrator() -> OrchestratorAgent:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        logger.info("Initializing lazy OrchestratorAgent...")
        _orchestrator_instance = OrchestratorAgent(firestore_user_tool=get_user_tool())
    return _orchestrator_instance


# ── background processing functions ──

def _process_message_bg(chat_id: int, user_id: str, text: str) -> None:
    """Process a regular user message in a background thread."""
    # Off-topic restriction check (blocks before LLM call to save costs)
    user_doc = get_user_tool().get_user_by_telegram_id(user_id)
    if user_doc:
        restriction_msg = off_topic_guard.is_restricted(user_doc)
        if restriction_msg:
            send_telegram_message(chat_id, restriction_msg)
            return

    # Show inline placeholder while LLM processes
    placeholder_msg_id = send_telegram_message(chat_id, "⏳ Thinking...")

    def update_status(msg: str):
        if placeholder_msg_id:
            edit_telegram_message(chat_id, placeholder_msg_id, msg)

    try:
        response = get_orchestrator().process_request(user_id, text, status_callback=update_status)
        logger.info("webhook received from orchestrator: %s", response)
        reply = response.get("text", "Something went wrong.")
    except Exception:
        logger.exception("Orchestrator error for user %s", user_id)
        reply = "Sorry, I hit an error processing your message. Please try again."

    if placeholder_msg_id:
        edit_telegram_message(chat_id, placeholder_msg_id, reply)
        # Send remaining chunks if response was too large to edit
        if len(reply) > 4000:
            send_telegram_message(chat_id, reply[4000:])
    else:
        # Fallback if placeholder failed to send (this already chunks internally)
        send_telegram_message(chat_id, reply)


def _dispatch(target, *args) -> None:
    """Spawn a daemon thread for background processing."""
    t = threading.Thread(target=target, args=args, daemon=True)
    t.start()


# ── webhook endpoint ──

@app.route("/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    """
    Handle incoming Telegram updates.

    Validation (secret, IP, rate limit) is synchronous and fast.
    All processing is dispatched to a background daemon thread so
    that Telegram receives a 200 immediately, preventing retries.

    URL: POST /webhook/<TELEGRAM_SECRET_TOKEN>
    The <secret> path segment acts as Layer 2 (secret URL path).
    """
    # Layer 2: Secret URL path
    if secret != SECRET_TOKEN:
        logger.warning("Rejected: wrong URL path secret")
        return jsonify({"ok": False}), 403

    # Layer 1: Secret token header
    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_token != SECRET_TOKEN:
        logger.warning("Rejected: wrong secret token header")
        return jsonify({"ok": False}), 403

    # Layer 3: IP whitelist (skip in local dev / ngrok)
    skip_ip_check = os.getenv("SKIP_IP_CHECK", "").lower() in ("1", "true")
    if not skip_ip_check and not _is_telegram_ip(request):
        return jsonify({"ok": False}), 403

    # Parse update payload
    update = request.get_json(silent=True)
    if not update:
        return jsonify({"ok": False}), 400

    logger.debug("Webhook received update: %s", update)

    # Layer 5: Payload validation — only handle text messages
    message = update.get("message")
    if not message:
        # Silently ignore non-message updates (edited, channel, inline, etc.)
        return jsonify({"ok": True}), 200

    chat_id = message.get("chat", {}).get("id")
    from_user = message.get("from", {})
    user_id = str(from_user.get("id", ""))
    text = sanitize_user_input(message.get("text") or "")

    if not chat_id or not user_id or not text:
        return jsonify({"ok": True}), 200

    # Layer 4: Rate limiting
    if _is_rate_limited(user_id):
        send_telegram_message(
            chat_id,
            "⏳ You're sending messages too fast — please wait a moment.",
        )
        return jsonify({"ok": True}), 200

    # ── Dispatch to background thread & return 200 immediately ──
    if text.startswith("/start"):
        logger.info("Dispatching /start for user %s", user_id)
        _dispatch(_handle_start, chat_id, user_id, from_user, text)
    elif text.startswith("/promo"):
        logger.info("Dispatching /promo for user %s", user_id)
        _dispatch(_handle_promo, chat_id, user_id, text)
    else:
        logger.info("Dispatching message for user %s: %s", user_id, text[:80])
        _dispatch(_process_message_bg, chat_id, user_id, text)

    return jsonify({"ok": True}), 200


def _handle_start(
    chat_id: int, user_id: str, from_user: dict, text: str
) -> None:
    """Handle /start command — link Telegram user to Tally profile."""
    parts = text.split(maxsplit=1)
    submission_id = parts[1].strip() if len(parts) > 1 else ""

    if not submission_id:
        send_telegram_message(
            chat_id,
            "👋 Welcome to TripGenie! To get started, please fill out "
            "your travel profile:\nhttps://tally.so/r/9qN6p4",
        )
        return

    logger.debug("Submission ID: %s, User ID: %s", submission_id, user_id)
    # Try to link Telegram user to Firestore profile
    user_doc, is_update = get_user_tool().link_telegram_user(submission_id, user_id)
    if user_doc:
        name = user_doc.get("name", user_doc.get("user_name", "Traveler"))
        
        # Send a placeholder
        placeholder_msg_id = send_telegram_message(chat_id, "⏳ Mapping your travel DNA...")
        
        try:
            from agentic_traveler.orchestrator.profile_agent import ProfileAgent
            profile_agent = ProfileAgent()
            
            # Extract only the safely serializable form response data to avoid Firestore Datetime JSON errors
            form_data = user_doc.get("user_profile", {}).get("form_response", {})
            if not form_data:
                # Fallback if someone sends raw user_doc without form_response 
                # (We stringify it to be safe)
                form_data = {str(k): str(v) for k, v in user_doc.get("user_profile", {}).items()}
                
            structured_data = profile_agent.build_initial_profile({"form_response": form_data})
            
            greeting = structured_data.pop("greeting", None)
            
            # Save the new structured keys
            get_user_tool().update_user_fields(user_id, {
                "user_profile": structured_data
            })
            
            if not greeting:
                greeting = f"Great to meet you, {name}! Your profile is mapped out and ready to go."
                
            examples = (
                "You can now ask me anything — try:\n"
                "• \"Suggest me a 5-day trip in May\"\n"
                "• \"I want a nature getaway under 800 EUR\"\n"
                "• \"What do you know about me?\""
            )
            
            # 1. Edit the placeholder to show success
            if is_update:
                edit_telegram_message(chat_id, placeholder_msg_id, f"✅ Welcome back, {name}! Your profile was updated.")
            else:
                edit_telegram_message(chat_id, placeholder_msg_id, f"✅ Welcome, {name}! Your travel profile is linked.")

            # 2. Send the personalized greeting as a brand new separate message
            send_telegram_message(chat_id, f"_{greeting}_\n\n{examples}")

            # Record new-user metric (app-level, fire-and-forget)
            metrics_tracker.record_interaction(user_id=user_id, is_new_user=not is_update)

            # Initialize credits for new users
            if not is_update:
                user_ref = get_user_tool().get_user_ref_by_telegram_id(user_id)
                if user_ref:
                    credit_manager.initialize_credits(user_ref)

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


def _handle_promo(chat_id: int, user_id: str, text: str) -> int:
    """Handle /promo <CODE> command — redeem a promo code via Telegram.

    Returns:
        Number of credits added (0 on failure).
    """
    parts = text.split(maxsplit=1)
    code = parts[1].strip() if len(parts) > 1 else ""

    if not code:
        send_telegram_message(
            chat_id,
            "🎫 To redeem a promo code, send:\n/promo YOUR_CODE",
        )
        return 0

    user_doc, user_ref = get_user_tool().get_user_with_ref(user_id)
    if not user_doc or not user_ref:
        send_telegram_message(
            chat_id,
            "❌ You need to complete your travel profile first before using a promo code.",
        )
        return 0

    success, message, credits_added = credit_manager.redeem_promo(user_doc, user_ref, code)
    send_telegram_message(chat_id, message)
    return credits_added


# ── health check ──

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "ok"}), 200


# ── admin endpoints ──

@app.route("/admin/add-credits", methods=["POST"])
def admin_add_credits():
    """Add credits to a user. Requires X-Admin-Key header."""
    if not ADMIN_API_KEY:
        return jsonify({"ok": False, "error": "Admin API not configured"}), 500

    if request.headers.get("X-Admin-Key") != ADMIN_API_KEY:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", ""))
    amount = int(data.get("amount", 0))

    if not user_id or amount <= 0:
        return jsonify({"ok": False, "error": "user_id and positive amount required"}), 400

    user_ref = get_user_tool().get_user_ref_by_telegram_id(user_id)
    if not user_ref:
        return jsonify({"ok": False, "error": f"User {user_id} not found"}), 404

    credit_manager.add_credits(user_ref, amount)
    return jsonify({"ok": True, "added": amount, "user_id": user_id}), 200


@app.route("/promo/redeem", methods=["POST"])
def promo_redeem():
    """Redeem a promo code via HTTP. No special auth required."""
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", ""))
    code = str(data.get("code", "")).strip()

    if not user_id or not code:
        return jsonify({"ok": False, "error": "user_id and code required"}), 400

    user_doc, user_ref = get_user_tool().get_user_with_ref(user_id)
    if not user_doc or not user_ref:
        return jsonify({"ok": False, "error": f"User {user_id} not found"}), 404

    success, message, credits_added = credit_manager.redeem_promo(user_doc, user_ref, code)
    status = 200 if success else 400
    return jsonify({"ok": success, "message": message, "credits_added": credits_added}), status


# ── local dev server ──

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
