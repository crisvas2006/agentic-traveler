# Task 17: Preference Extraction from Message Likes

> Extract preferences when a user likes a message and persist them in the profile.

## 1. Task Overview
- **Summary:** When a user reacts positively to a bot message, infer the category of the suggestion and update preferences.
- **Background:** Implicit feedback improves personalization without extra questions.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Capture Telegram "like" reactions.
    - Map the liked message to a preference category.
    - Update the user profile accordingly.
- **Definition of Done:**
    - A like reaction results in a preference update in Firestore.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Requires handling Telegram reaction updates and mapping to suggestion tags.
- **Relevant Specs:** `task_04_profile_agent.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Telegram reaction update payloads must be enabled.
- **Operational Constraints:** Avoid noisy or incorrect preference updates.

## 5. Inputs & Resources
- **Artifacts:**
    - Telegram webhook handling in `src/agentic_traveler/webhook.py`
    - Preference update pipeline in `src/agentic_traveler/orchestrator/preference_learner.py`
- **Assumptions:** Bot is configured to receive reaction updates.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Enable Telegram reaction updates in webhook registration.
    2. Store minimal metadata for bot messages (category tags).
    3. On reaction, map message id to category and update preferences.

## 7. Testing & Validation
- **Test Strategy:** Manual reaction testing in Telegram.
- **Acceptance Tests:**
    - Liking a suggestion updates profile tags or preferences.

## 8. Risk Management
- **Known Risks:** Incorrect mappings from message to category.
- **Mitigations:** Tag messages at send-time and only learn from tagged content.

## 9. Delivery & Handoff
- **Deliverables:** Reaction handling and preference update integration.

