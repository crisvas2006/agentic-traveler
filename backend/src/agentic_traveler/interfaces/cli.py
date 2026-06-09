"""
Interactive CLI for chatting with the Agentic Traveler orchestrator.

Usage:
    python -m agentic_traveler.cli                  # lists users, lets you pick
    python -m agentic_traveler.cli --telegram-id 12345  # use a specific user
    python -m agentic_traveler.cli -v               # verbose logging
"""

import argparse
from dotenv import load_dotenv

load_dotenv()

from agentic_traveler.core.logging_config import setup_logging  # noqa: E402
from agentic_traveler.orchestrator.agent import OrchestratorAgent  # noqa: E402
# get_db is safe to import here: db_client reads SUPABASE_URL lazily inside
# get_db(), not at module load time, so load_dotenv() above always runs first.
from agentic_traveler.tools.db_client import get_db  # noqa: E402
from agentic_traveler.tools.user_repo import UserRepository  # noqa: E402


def list_users(tool: UserRepository, limit: int = 10):
    """Fetch up to `limit` users and display them for selection."""
    resp = get_db().table("users").select("name, telegram_id").limit(limit).execute()
    users = resp.data or []
    for idx, row in enumerate(users, 1):
        name = row.get("name", "Unknown")
        tg_id = row.get("telegram_id", "N/A")
        print(f"  [{idx}] {name}  (telegram_id: {tg_id})")
    return users


def main():
    parser = argparse.ArgumentParser(description="Chat with Agentic Traveler")
    parser.add_argument("--telegram-id", help="Telegram user ID to impersonate")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="Enable verbose (DEBUG) logging to see agent routing & timing",
    )
    args = parser.parse_args()

    setup_logging(verbose=args.verbose)

    tool = UserRepository()
    telegram_id = args.telegram_id

    if not telegram_id:
        print("\n🌍  Agentic Traveler — pick a user to impersonate:\n")
        users = list_users(tool)
        if not users:
            print("  No users found in Supabase.")
            return
        choice = input("\nEnter number (or telegram ID): ").strip()
        if choice.isdigit() and int(choice) <= len(users):
            telegram_id = users[int(choice) - 1].get("telegram_id")
        else:
            telegram_id = choice

    # Show the selected user profile
    profile = tool.get_user_by_telegram_id(telegram_id)
    if profile:
        print(f"\n✅  Logged in as: {profile.get('name', 'Unknown')}")
        prefs = profile.get("user_profile", {})
        if prefs:
            vibes = prefs.get("trip_vibe", [])
            location = profile.get("location", "")
            print(f"   Location: {location}")
            print(f"   Vibes: {', '.join(vibes) if isinstance(vibes, list) else vibes}")
    else:
        print(f"\n⚠️  No profile found for telegram_id={telegram_id}")
        print("   You'll get the onboarding flow.\n")

    agent = OrchestratorAgent(user_repo=tool)

    print("\n💬  Type your messages below (Ctrl+C or 'quit' to exit)")
    print(f"   {'Verbose logging ON — check stderr for agent details' if args.verbose else 'Tip: use -v for verbose logging'}")
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
