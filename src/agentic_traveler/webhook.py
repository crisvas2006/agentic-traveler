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
import time
from collections import defaultdict
from threading import Lock

import requests as http_requests
from dotenv import load_dotenv
from flask import Flask, Request, jsonify, request

from agentic_traveler.logging_config import setup_logging
from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.sanitize import sanitize_user_input
from agentic_traveler.tools.firestore_user import FirestoreUserTool

load_dotenv()
setup_logging(verbose=os.getenv("VERBOSE", "").lower() in ("1", "true"))

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── configuration ──

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "")
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

def send_telegram_message(chat_id: int | str, text: str) -> None:
    """Send a message via the Telegram Bot API."""
    # Telegram limit is 4096 chars per message
    for i in range(0, len(text), 4096):
        chunk = text[i : i + 4096]
        try:
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
        except Exception:
            logger.exception("Failed to send Telegram message to %s", chat_id)


# ── globals (initialized once per container) ──

_user_tool = FirestoreUserTool()
_orchestrator = OrchestratorAgent(firestore_user_tool=_user_tool)


# ── webhook endpoint ──

@app.route("/webhook/<secret>", methods=["POST"])
def telegram_webhook(secret: str):
    """
    Handle incoming Telegram updates.

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

    # ── Handle /start <submissionId> ──
    if text.startswith("/start"):
        _handle_start(chat_id, user_id, from_user, text)
        return jsonify({"ok": True}), 200

    # ── Regular message → orchestrator ──
    logger.info("Message from user %s: %s", user_id, text[:80])
    try:
        response = _orchestrator.process_request(user_id, text)
        reply = response.get("text", "Something went wrong.")
    except Exception:
        logger.exception("Orchestrator error for user %s", user_id)
        reply = "Sorry, I hit an error processing your message. Please try again."

    send_telegram_message(chat_id, reply)
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

    # Try to link Telegram user to Firestore profile
    user_doc = _user_tool.link_telegram_user(submission_id, user_id)
    if user_doc:
        name = user_doc.get("user_name", "Traveler")
        send_telegram_message(
            chat_id,
            f"✅ Welcome, {name}! Your travel profile is linked.\n\n"
            "You can now ask me anything — try:\n"
            "• \"Suggest me a 5-day trip in May\"\n"
            "• \"I want a nature getaway under 800 EUR\"\n"
            "• \"What do you know about me?\"",
        )
    else:
        send_telegram_message(
            chat_id,
            "❌ I couldn't find a profile for that link. "
            "Please make sure you've completed the travel form first:\n"
            "https://tally.so/r/9qN6p4",
        )


# ── health check ──

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({"status": "ok"}), 200


# ── local dev server ──

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
