"""
Interactive CLI for chatting with the Agentic Traveler orchestrator.

Usage:
    python -m agentic_traveler.cli                  # lists users, lets you pick
    python -m agentic_traveler.cli --telegram-id 12345  # use a specific user
"""

import argparse
import os
from dotenv import load_dotenv

load_dotenv()

from agentic_traveler.orchestrator.agent import OrchestratorAgent
from agentic_traveler.tools.firestore_user import FirestoreUserTool


def list_users(tool: FirestoreUserTool, limit: int = 10):
    """Fetch up to `limit` users and display them for selection."""
    docs = tool.db.collection("users").limit(limit).stream()
    users = []
    for doc in docs:
        data = doc.to_dict()
        users.append(data)
        idx = len(users)
        name = data.get("user_name", "Unknown")
        tg_id = data.get("telegramUserId", "N/A")
        print(f"  [{idx}] {name}  (telegramUserId: {tg_id})")
    return users


def main():
    parser = argparse.ArgumentParser(description="Chat with Agentic Traveler")
    parser.add_argument("--telegram-id", help="Telegram user ID to impersonate")
    args = parser.parse_args()

    tool = FirestoreUserTool()
    telegram_id = args.telegram_id

    if not telegram_id:
        print("\n🌍  Agentic Traveler — pick a user to impersonate:\n")
        users = list_users(tool)
        if not users:
            print("  No users found in Firestore.")
            return
        choice = input("\nEnter number (or telegram ID): ").strip()
        if choice.isdigit() and int(choice) <= len(users):
            telegram_id = users[int(choice) - 1].get("telegramUserId")
        else:
            telegram_id = choice

    # Show the selected user profile
    profile = tool.get_user_by_telegram_id(telegram_id)
    if profile:
        print(f"\n✅  Logged in as: {profile.get('user_name', 'Unknown')}")
        prefs = profile.get("user_profile", {})
        if prefs:
            vibes = prefs.get("trip_vibe", [])
            location = prefs.get("location", "")
            print(f"   Location: {location}")
            print(f"   Vibes: {', '.join(vibes) if isinstance(vibes, list) else vibes}")
    else:
        print(f"\n⚠️  No profile found for telegramUserId={telegram_id}")
        print("   You'll get the onboarding flow.\n")

    agent = OrchestratorAgent(firestore_user_tool=tool)

    print("\n💬  Type your messages below (Ctrl+C or 'quit' to exit)\n")
    print("-" * 60)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input or user_input.lower() in ("quit", "exit", "q"):
                print("\n👋  Bye!")
                break

            response = agent.process_request(telegram_id, user_input)
            action = response.get("action", "UNKNOWN")
            text = response.get("text", "")

            print(f"\n🤖  [{action}]\n{text}")

        except KeyboardInterrupt:
            print("\n\n👋  Bye!")
            break


if __name__ == "__main__":
    main()
