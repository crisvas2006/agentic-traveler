# Task 04: Profile & Memory Agent

> Implement the Profile Agent responsible for interpreting user data into a structured travel personality profile and updating it over time.

## 1. Task Overview
- **Summary:** Convert Tally form data and conversational preferences into a structured profile with personality dimensions, tags, tone preference, additional info, and summary.
- **Background:** Personalization is key. The Profile Agent provides compact, high-signal context to other agents.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - `ProfileAgent` implemented.
    - Initial profile built from Tally form data on `/start <submissionId>`.
    - Preference updates merged asynchronously into the structured profile.
- **Definition of Done:**
    - User profile contains `personality_dimensions_scores`, `tags`, `tone_preference`, `additional_info`, and `summary`.
    - Preference updates adjust the structured profile without overwriting unrelated fields.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Profile agent is called during onboarding and for ongoing preference updates.
- **Relevant Specs:** `travel_personality_dimensions.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Google GenAI SDK (no ADK).
- **Operational Constraints:** Fast response on onboarding; async updates for preference changes.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/orchestrator/profile_agent.py`
    - `src/agentic_traveler/orchestrator/preference_learner.py`
    - `src/agentic_traveler/tools/firestore_user.py`
    - `specs/travel_personality_dimensions.md`
- **Assumptions:** Tally form submissions are stored under `user_profile.form_response`.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Build initial structured profile from Tally form data (with a greeting).
    2. Store the structured profile under `user_profile` in Firestore.
    3. On preference updates, call `ProfileAgent.update_profile()` asynchronously.
    4. Merge updated structured data back into Firestore without deleting other fields.

## 7. Testing & Validation
- **Test Strategy:** Unit tests for profile JSON output; manual onboarding flow test.
- **Acceptance Tests:**
    - On `/start <submissionId>`, profile fields are created and a greeting is sent.
    - Subsequent preference updates modify scores/tags/summary without wiping other data.

## 8. Risk Management
- **Known Risks:** Inconsistent JSON output from the model.
- **Mitigations:** Enforce JSON output with response MIME type and defaults for missing dimensions.

## 9. Delivery & Handoff
- **Deliverables:** Profile agent code, preference update pipeline, Firestore merge logic.
