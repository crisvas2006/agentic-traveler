# Agentic Traveler: Manual Test Flow

This document provides a step-by-step script for manually validating the Telegram Bot's end-to-end functionality. Run this flow via a local `ngrok` tunnel or on a staging deployment before a major production release.

## Prerequisites
1. Ensure your local server is running (`python -m agentic_traveler.interfaces.webhook`).
2. Ensure your webhook is registered to your ngrok or staging URL.
3. Open Telegram and navigate to your bot.

---

## Phase 1: Smoke Tests (Core Functionality & Routing)
*These tests ensure the bot is alive, can onboard users, and handles basic conversational routing without crashing.*

**Step 1.1: Initial Contact**
- **Action:** Send `/start`
- **Expected:** The bot should reply with an onboarding message and a link to the Tally form (`https://tally.so/r/ODPGak`).

**Step 1.2: Profile Linkage (ProfileAgent)**
- **Action:** Complete the Tally form with dummy data. When redirected to Telegram, click the deep link (which sends a message like `/start <submissionId>`).
- **Expected:**
  - The bot sends a temporary "⏳ Mapping your travel DNA..." placeholder.
  - The placeholder updates to a success message.
  - The bot sends a personalized welcome greeting confirming your profile is linked.

**Step 1.3: General Knowledge (No Tool routing)**
- **Action:** Send "What is the capital of Japan?"
- **Expected:** The bot should respond directly with "Tokyo" (or similar conversational answer) without triggering any sub-agents.

**Step 1.4: Credit Check (get_my_credits)**
- **Action:** Send "How many credits do I have left?"
- **Expected:** The bot should check your balance and respond with your remaining credits.

---

## Phase 2: Feature Tests (Sub-Agent Capabilities)
*These tests ensure the Orchestrator successfully routes complex intents to the specialized sub-agents and returns the formatted response.*

**Step 2.1: Weather Checking (check_weather)**
- **Action:** Send "What is the weather like in London right now?"
- **Expected:** The bot triggers the weather service and responds with a natural-sounding summary of the London forecast.

**Step 2.2: Destination Discovery (discover_destinations)**
- **Action:** Send "I want to go to a warm beach destination in Europe for 3 days."
- **Expected:** 
  - The bot sends a "⏳ I'm scouting the globe..." placeholder.
  - Returns a high-level summary of 2-3 beach destination options.

**Step 2.3: Itinerary Planning (plan_itinerary)**
- **Action:** Send "Let's go with the first option you suggested. Please plan a detailed day-by-day itinerary for those 3 days."
- **Expected:**
  - The bot sends a "⏳ I'm putting together a detailed day-by-day plan..." placeholder.
  - Returns a structured, day-by-day itinerary.

**Step 2.4: In-Trip Assistance (get_companion_help)**
- **Action:** Send "I'm currently at the destination. I'm feeling really tired, do you have any suggestions for a chill afternoon?"
- **Expected:** The bot responds with low-energy, relaxing activities suitable for someone currently on a trip.

---

## Phase 3: Delicate & State-Dependent Tests
*These tests ensure the agent correctly remembers context, updates long-term Firestore state, and handles economy/security features.*

**Step 3.1: Preference Learning (update_preferences)**
- **Action:** Send "By the way, I am highly allergic to peanuts."
- **Expected:** The bot acknowledges this and explicitly mentions that it has noted/remembered this allergy.
- **Verification:** Send a follow-up message: "Can you recommend a snack for me?" The bot's recommendation MUST explicitly exclude peanuts or mention your allergy.

**Step 3.2: Off-Topic Guardrail (flag_off_topic)**
- **Action:** Send "Can you write a python script to sort a binary tree?"
- **Expected:** The bot should politely decline and redirect the conversation back to travel.
- **Action:** Send another off-topic message: "What is the history of the French Revolution?"
- **Expected:** The bot should again redirect to travel. (Note: Continuous abuse should eventually trigger the restriction warning).

**Step 3.3: Feedback Recording (record_feedback)**
- **Action:** Send "This itinerary is terrible, I hate it."
- **Expected:** The bot should apologize and offer alternatives. Behind the scenes (check console logs), the `record_feedback` tool should have been called asynchronously with a `negative` category.

**Step 3.4: Promo Code Redemption (credit_manager)**
- **Action:** Send `/promo TEST_CODE` (Replace `TEST_CODE` with a valid mock promo code if available in your DB).
- **Expected:** The bot should confirm that the credits have been successfully added to your account. Send "Check my balance" to verify the total has increased.
