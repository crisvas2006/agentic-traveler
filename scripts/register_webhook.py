"""
One-shot utility script to register or update the Telegram Bot webhook.

PURPOSE:
    This script tells Telegram where to send incoming user messages. Without this,
    the bot will not receive any updates from Telegram.

HOW IT WORKS:
    1. It reads your BOT_TOKEN and SECRET_TOKEN from the .env file.
    2. It constructs a secure webhook URL that includes the secret token as a 
       URL path segment (Layer 1 security).
    3. It calls the Telegram 'setWebhook' API method, passing:
       - The target URL.
       - The secret token in the 'secret_token' parameter (Layer 2 security - 
         this shows up in the 'X-Telegram-Bot-Api-Secret-Token' header).
    4. It verifies the registration by calling 'getWebhookInfo'.

USAGE:
    # For local development (using ngrok):
    python scripts/register_webhook.py --url https://your-ngrok-id.ngrok-free.app

    # For production (Cloud Run):
    python scripts/register_webhook.py --url https://agentic-traveler-xyz.a.run.app
"""

import argparse
import os
import sys

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def main():
    # Setup command line arguments
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

    # Authentication tokens retrieved from environment
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    secret_token = os.getenv("TELEGRAM_SECRET_TOKEN")

    if not bot_token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set in .env")
        sys.exit(1)

    # Base URL for all Telegram Bot API requests
    api_base = f"https://api.telegram.org/bot{bot_token}"

    # Handle webhook deletion if requested
    if args.delete:
        resp = requests.post(f"{api_base}/deleteWebhook", timeout=10)
        print(f"deleteWebhook: {resp.json()}")
        return

    if not secret_token:
        print("WARNING: TELEGRAM_SECRET_TOKEN not set — webhook will have no secret header validation")

    # Construct the Webhook URL. 
    # SECURITY LAYER 1: The secret token is appended to the URL path.
    # This prevents anyone from guessing your webhook endpoint and sending fake messages.
    base_url = args.url.rstrip('/')
    webhook_url = f"{base_url}/webhook/{secret_token}" if secret_token else f"{base_url}/webhook/nosecret"

    # Prepare the payload for the setWebhook request
    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"],  # Performance optimization: only receive message updates
    }
    
    # SECURITY LAYER 2: Provide the secret_token to Telegram.
    # Telegram will include this in the 'X-Telegram-Bot-Api-Secret-Token' header 
    # of every request it sends to our server.
    if secret_token:
        payload["secret_token"] = secret_token

    print(f"Setting webhook to: {webhook_url}")
    
    # Make the actual API call to Telegram
    try:
        resp = requests.post(f"{api_base}/setWebhook", json=payload, timeout=10)
        resp.raise_for_status()
        result = resp.json()
    except Exception as e:
        print(f"❌ Network error contacting Telegram: {e}")
        sys.exit(1)

    if result.get("ok"):
        print(f"✅ Webhook registered successfully!")
        print(f"   URL: {webhook_url}")
        print(f"   Secret token: {'set' if secret_token else 'NOT SET'}")
    else:
        print(f"❌ Telegram API Error: {result}")
        sys.exit(1)

    # VERIFICATION: Immediately fetch the current webhook status from Telegram
    # to confirm it's actually configured correctly.
    try:
        resp = requests.get(f"{api_base}/getWebhookInfo", timeout=10)
        info = resp.json().get("result", {})
        print(f"\n📋 Webhook info from Telegram:")
        print(f"   URL: {info.get('url')}")
        print(f"   Has secret: {info.get('has_custom_certificate', False)}")
        print(f"   Pending updates: {info.get('pending_update_count', 0)}")
        print(f"   Last error: {info.get('last_error_message', 'none')}")
    except Exception as e:
        print(f"⚠️ Could not verify webhook info: {e}")


if __name__ == "__main__":
    main()
