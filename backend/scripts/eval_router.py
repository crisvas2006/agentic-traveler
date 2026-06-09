"""
Router intent classification eval script.

Run manually to validate router accuracy on a representative message set.
NOT a pytest test — runs real LLM calls and costs credits.

Usage:
    python scripts/eval_router.py

Requires environment variables: GOOGLE_PROJECT_ID, GEMINI_REGION, etc.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from agentic_traveler.orchestrator.router_agent import RouterAgent  # noqa: E402

# ── eval set (message, expected_intent) ─────────────────────────────────────

EVAL_SET = [
    # CHAT — greetings and banter
    ("hey!", "CHAT"),
    ("hi there", "CHAT"),
    ("hello", "CHAT"),
    ("thanks, that was really helpful!", "CHAT"),
    ("you're awesome", "CHAT"),
    ("how are you?", "CHAT"),
    ("how's your day going?", "CHAT"),
    ("tell me a joke", "CHAT"),
    ("make me laugh", "CHAT"),
    ("I'm feeling stressed today", "CHAT"),
    ("I had the worst day", "CHAT"),
    ("what do you think about life?", "CHAT"),
    ("do you have feelings?", "CHAT"),
    ("what's your favorite country?", "CHAT"),

    # TRIP — travel questions and discovery
    ("what should I do in Bali?", "TRIP"),
    ("I'm in Rome and bored, what now?", "TRIP"),
    ("is Lombok worth visiting?", "TRIP"),
    ("best time to visit Japan?", "TRIP"),
    ("what's the weather like in Barcelona?", "TRIP"),
    ("compare Lisbon and Porto for a weekend", "TRIP"),
    ("I'm tired and it's raining, suggest something", "TRIP"),
    ("what are good restaurants in Paris?", "TRIP"),
    ("visa requirements for Indonesia", "TRIP"),
    ("how safe is Morocco for solo travel?", "TRIP"),
    ("hidden gems in Southeast Asia", "TRIP"),
    ("I need a beach with no tourists", "TRIP"),
    ("what's the nightlife like in Ibiza?", "TRIP"),
    ("good hiking destinations in Europe?", "TRIP"),

    # PLAN — explicit structured planning requests
    ("plan my 5-day trip to Rome", "PLAN"),
    ("make me an itinerary for Lombok", "PLAN"),
    ("organize my week in Tokyo", "PLAN"),
    ("help me plan day by day in Bali", "PLAN"),
    ("create a detailed schedule for 3 days in Amsterdam", "PLAN"),
    ("I want a full itinerary for Portugal", "PLAN"),
    ("plan a 10-day Southeast Asia trip", "PLAN"),
    ("give me a day-by-day plan for my Paris trip", "PLAN"),

    # OFF_TOPIC — clearly unrelated to travel
    ("what is 2+2?", "OFF_TOPIC"),
    ("help me with my Python code", "OFF_TOPIC"),
    ("who won the Champions League?", "OFF_TOPIC"),
    ("write me an essay on climate change", "OFF_TOPIC"),
    ("what's the best programming language?", "OFF_TOPIC"),
    ("explain quantum physics", "OFF_TOPIC"),
    ("help me with my taxes", "OFF_TOPIC"),
    ("what should I cook for dinner?", "OFF_TOPIC"),

    # EDGE CASES — banter vs off-topic (should be CHAT, not OFF_TOPIC)
    ("haha you're funny", "CHAT"),
    ("ok but seriously, what should I pack for Bali?", "TRIP"),
    ("I just got back from Tokyo, it was amazing!", "CHAT"),
]


def run_eval():
    """Run router against the eval set and report accuracy."""
    # Minimal stub user_doc — router doesn't need Firestore for classification
    fake_user_doc = {"user_profile": {"tone_preference": "casual"}}

    # Stateless router initialized once
    router = RouterAgent()

    correct = 0
    total = len(EVAL_SET)
    failures = []

    print(f"\n{'='*60}")
    print(f"Router Eval — {total} messages")
    print(f"{'='*60}\n")

    for i, (message, expected) in enumerate(EVAL_SET, 1):
        # Pass context into classify()
        result = router.classify(
            message=message,
            user_doc=fake_user_doc,
            user_doc_ref=None,
            user_id="eval_script",
            user_name="EvalUser",
            tone_preference="casual",
            current_time="Wednesday, 2026-05-07 12:00:00 UTC",
        )
        actual = result.get("intent", "UNKNOWN")
        ok = actual == expected

        if ok:
            correct += 1
            status = "✅"
        else:
            failures.append((message, expected, actual))
            status = "❌"

        print(f"{status} [{i:02d}] {message[:55]:<55} → {actual} (expected {expected})")

        # Small delay to avoid rate limiting
        time.sleep(0.3)

    accuracy = correct / total * 100
    print(f"\n{'='*60}")
    print(f"Result: {correct}/{total} correct ({accuracy:.1f}%)")

    if failures:
        print(f"\nFailures ({len(failures)}):")
        for msg, exp, act in failures:
            print(f"  • \"{msg}\" → got {act}, expected {exp}")

    passed = accuracy >= 90.0
    print(f"\n{'PASS ✅' if passed else 'FAIL ❌'} — target: ≥90%")
    print(f"{'='*60}\n")
    return passed


if __name__ == "__main__":
    success = run_eval()
    sys.exit(0 if success else 1)
