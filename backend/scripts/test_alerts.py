"""
Integration test script for GCP Cloud Monitoring alerts.

Triggers all 6 alert conditions against the deployed Cloud Run webhook
to verify that log-based metrics fire and email alerts are delivered.

Usage:
    python scripts/test_alerts.py          # alerts 1-3 only
    python scripts/test_alerts.py --all    # all 6 alerts (needs SKIP_IP_CHECK)

Flow:
    1. Run setup_alerts.py first (creates metrics + policies)
    2. For alerts 3-6: temporarily enable SKIP_IP_CHECK on Cloud Run
    3. Run this script
    4. Wait 3-8 min for alerts → check email
    5. Remove SKIP_IP_CHECK

For testing alerts 3-6, you need to enable SKIP_IP_CHECK on Cloud Run:
# 1. Temporarily allow non-Telegram IPs
gcloud run services update agentic-traveler `
  --region europe-west1 `
  --update-env-vars SKIP_IP_CHECK=true

# 2. Run all tests
.\.venv\Scripts\python scripts/test_alerts.py --all

# 3. Wait 3-8 min, check email + GCP Console

# 4. IMPORTANT: Remove SKIP_IP_CHECK
gcloud run services update agentic-traveler `
  --region europe-west1 `
  --remove-env-vars SKIP_IP_CHECK

Prerequisites:
    - .env with TELEGRAM_SECRET_TOKEN, GOOGLE_PROJECT_ID, CLOUD_RUN_URL
    - Alerts set up via setup_alerts.py
"""

import argparse
import os
import sys
import time

import requests as http_requests
from dotenv import load_dotenv

load_dotenv()

SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN", "")
PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", "")
SERVICE_URL = os.getenv("CLOUD_RUN_URL", "")
TEST_USER_ID = os.getenv("TEST_USER_ID", "")

FAKE_USER_ID = 999999999
FAKE_CHAT_ID = 999999999

OFF_TOPIC_MESSAGES = [
    "Can you solve this differential equation: dy/dx = 3x^2 + 2x?",
    "Write me a Python function that implements quicksort",
    "What is your opinion on the latest political elections?",
    "Help me debug this JavaScript error: TypeError undefined",
    "Can you write me an essay about quantum computing?",
    "Explain how neural networks work with backpropagation",
]

TRAVEL_MESSAGES = [
    "I want to go to Japan next spring for 2 weeks",
    "What's the best time to visit Greece?",
    "Plan a 5-day trip to Barcelona for me",
    "I'm in Rome and feeling tired, what should I do?",
    "Suggest me a cheap beach destination in Europe",
    "What are the best restaurants in Lisbon?",
    "Help me plan a road trip through Tuscany",
    "I need a hotel recommendation in Amsterdam",
    "What should I pack for a winter trip to Iceland?",
    "Compare Thailand vs Vietnam for a 2-week backpacking trip",
]


def _make_payload(text: str, user_id: int = FAKE_USER_ID) -> dict:
    """Build a fake Telegram update payload."""
    return {
        "update_id": int(time.time()),
        "message": {
            "message_id": int(time.time()),
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "AlertTest",
            },
            "chat": {"id": FAKE_CHAT_ID, "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }


def send_request(
    text: str,
    *,
    use_valid_secret: bool = True,
    use_valid_header: bool = True,
    user_id: int = FAKE_USER_ID,
) -> int:
    """Send a request to the webhook and return the status code."""
    path_secret = SECRET_TOKEN if use_valid_secret else "wrong_secret_12345"
    url = f"{SERVICE_URL.rstrip('/')}/webhook/{path_secret}"

    headers = (
        {"X-Telegram-Bot-Api-Secret-Token": SECRET_TOKEN}
        if use_valid_header
        else {"X-Telegram-Bot-Api-Secret-Token": "wrong"}
    )

    try:
        resp = http_requests.post(
            url, json=_make_payload(text, user_id), headers=headers, timeout=30,
        )
        return resp.status_code
    except http_requests.exceptions.ConnectionError:
        return -1


def test_non_telegram_ip():
    """Alert 1: Requests from non-Telegram IP (× 6).

    Uses valid secrets so the request passes auth layers 1-2 and
    reaches the IP whitelist check (layer 3), which logs the rejection.
    """
    print("\n🔴 Alert 1: Non-Telegram IP (× 6)")
    for i in range(6):
        code = send_request("test non-telegram IP")
        print(f"  [{i+1}/6] status={code}")
        time.sleep(0.3)
    print("  → Triggers: non_telegram_ip (≥5 in 5min)")


def test_auth_failure():
    """Alert 2: Invalid secret token (× 4)."""
    print("\n🔴 Alert 2: Auth failure (× 4)")
    for i in range(4):
        code = send_request("test", use_valid_header=False)
        print(f"  [{i+1}/4] status={code}")
        time.sleep(0.3)
    print("  → Triggers: auth_failure (≥3 in 5min)")


def test_rate_limit():
    """Alert 3: Rate limit abuse (× 12). Needs SKIP_IP_CHECK."""
    print("\n🟡 Alert 3: Rate limit (× 12)")
    for i in range(12):
        code = send_request(f"rate limit test {i}")
        print(f"  [{i+1}/12] status={code}")
        time.sleep(0.2)
    print("  → Triggers: rate_limit_hit (≥10 in 10min)")


def test_off_topic():
    """Alert 5: Off-topic restriction (× 6). Needs SKIP_IP_CHECK + valid user."""
    print("\n🟠 Alert 5: Off-topic restriction (× 6)")
    if not TEST_USER_ID:
        print("  ⏭  Skipped — TEST_USER_ID not set in .env")
        return
    user_id = int(TEST_USER_ID)
    for i, msg in enumerate(OFF_TOPIC_MESSAGES):
        code = send_request(msg, user_id=user_id)
        print(f"  [{i+1}/6] status={code} — {msg[:50]}...")
        time.sleep(3)
    print("  → Triggers: user_restricted (≥5 in 1h)")


def test_high_token_usage():
    """Alert 6: High token consumption (× 10). Needs SKIP_IP_CHECK + valid user."""
    print("\n🟡 Alert 6: High token usage (× 10)")
    if not TEST_USER_ID:
        print("  ⏭  Skipped — TEST_USER_ID not set in .env")
        return
    user_id = int(TEST_USER_ID)
    print("  ℹ  Run script 5× to reach threshold of 50 events/hour")
    for i, msg in enumerate(TRAVEL_MESSAGES):
        code = send_request(msg, user_id=user_id)
        print(f"  [{i+1}/10] status={code} — {msg[:50]}...")
        time.sleep(3)
    print("  → Contributes to: high_token_usage (≥50 in 1h)")


def main():
    parser = argparse.ArgumentParser(description="Test alert conditions")
    parser.add_argument(
        "--all", action="store_true",
        help="Include LLM-dependent tests (alerts 5-6). Needs SKIP_IP_CHECK.",
    )
    args = parser.parse_args()

    if not SECRET_TOKEN:
        print("ERROR: TELEGRAM_SECRET_TOKEN not set in .env")
        sys.exit(1)
    if not SERVICE_URL:
        print("ERROR: CLOUD_RUN_URL not set in .env")
        sys.exit(1)

    print("=" * 60)
    print("🧪 Alert Integration Test — Cloud Run")
    print(f"   Target:  {SERVICE_URL}")
    print(f"   Project: {PROJECT_ID}")
    print("=" * 60)

    if args.all:
        print("\n⚠  SKIP_IP_CHECK must be ENABLED on Cloud Run for --all")
        print("   Alert 1 (non-Telegram IP) is skipped in this mode because")
        print("   SKIP_IP_CHECK disables the IP check that generates the log.\n")
        print("   To test alert 1, run WITHOUT --all (SKIP_IP_CHECK disabled).")
        test_auth_failure()
        test_rate_limit()
        test_off_topic()
        test_high_token_usage()
    else:
        print("\n   Testing alerts 1-2 (no SKIP_IP_CHECK needed)")
        test_non_telegram_ip()
        test_auth_failure()
        print("\n📝 Alerts 3, 5-6 skipped (use --all with SKIP_IP_CHECK enabled)")

    # Summary
    print("\n" + "=" * 60)
    print("📋 Next steps")
    print("=" * 60)
    print("  ⏰ Wait 3-8 min for alerts to fire, then check:")
    print(f"  • https://console.cloud.google.com/monitoring/alerting?project={PROJECT_ID}")
    print("  • Your email inbox (and spam folder)")
    if args.all:
        print()
        print("  ⚠  IMPORTANT: Remove SKIP_IP_CHECK now:")
        print("  gcloud run services update agentic-traveler \\")
        print("    --region europe-west1 \\")
        print("    --remove-env-vars SKIP_IP_CHECK")


if __name__ == "__main__":
    main()
