"""
One-shot script to register (or update) the Telegram Bot webhook.

Usage:
    python scripts/register_webhook.py --url https://your-app.run.app/webhook

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_SECRET_TOKEN from .env.
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Register Telegram webhook")
    parser.add_argument(
        "--url",
        required=True,
        help="Public HTTPS base URL (e.g. https://your-app.run.app)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete the webhook instead of setting it",
    )
    args = parser.parse_args()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    secret_token = os.getenv("TELEGRAM_SECRET_TOKEN")

    if not bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    api_base = f"https://api.telegram.org/bot{bot_token}"

    if args.delete:
        resp = requests.post(f"{api_base}/deleteWebhook", timeout=10)
        print(f"deleteWebhook: {resp.json()}")
        return

    if not secret_token:
        print("WARNING: TELEGRAM_SECRET_TOKEN not set — webhook will have no secret header validation")

    # Build webhook URL with secret path segment
    webhook_url = f"{args.url.rstrip('/')}/webhook/{secret_token}" if secret_token else f"{args.url.rstrip('/')}/webhook/nosecret"

    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],  # Only receive message updates
    }
    if secret_token:
        payload["secret_token"] = secret_token

    print(f"Setting webhook to: {webhook_url}")
    resp = requests.post(f"{api_base}/setWebhook", json=payload, timeout=10)
    result = resp.json()

    if result.get("ok"):
        print(f"✅ Webhook registered successfully!")
        print(f"   URL: {webhook_url}")
        print(f"   Secret token: {'set' if secret_token else 'NOT SET'}")
    else:
        print(f"❌ Failed: {result}")
        sys.exit(1)

    # Verify
    resp = requests.get(f"{api_base}/getWebhookInfo", timeout=10)
    info = resp.json().get("result", {})
    print(f"\n📋 Webhook info:")
    print(f"   URL: {info.get('url')}")
    print(f"   Has secret: {info.get('has_custom_certificate', False)}")
    print(f"   Pending updates: {info.get('pending_update_count', 0)}")
    print(f"   Last error: {info.get('last_error_message', 'none')}")


if __name__ == "__main__":
    main()
