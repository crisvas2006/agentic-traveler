# Task 11: Onboarding Profile Enrichment and Welcome Summary

> Map Tally form submissions into a structured travel personality profile and greet new users with a "welcome home" summary.

## 1. Task Overview
- **Summary:** Ingest the Tally form into `user_profile.form_response`, link a Telegram user via `/start <submissionId>`, and build a structured personality profile with a greeting.
- **Background:** The system needs a stable, compact representation of traveler preferences that can evolve over time.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Tally webhook stores a stable `form_response` object in the user profile.
    - `/start <submissionId>` links Telegram user to the Tally profile.
    - ProfileAgent produces personality dimension scores, tags, tone preference, additional info, and summary.
    - Send a welcome greeting after profile mapping is complete.
- **Definition of Done:**
    - New user completes form, runs `/start <submissionId>`, receives a greeting and example prompts.
    - User profile contains the structured profile fields and persists across sessions.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Tally webhook writes to Firestore; Telegram `/start` triggers profile enrichment; profile updates are merged back into Firestore.
- **Relevant Specs:** `travel_personality_dimensions.md`, `task_02_tally_ingestion.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Firestore writes must merge without deleting unrelated user data.
- **Operational Constraints:** Profile mapping should be quick enough to run during onboarding.

## 5. Inputs & Resources
- **Artifacts:**
    - `tally_webhook_v2/main.py`
    - `src/agentic_traveler/tools/firestore_user.py`
    - `src/agentic_traveler/orchestrator/profile_agent.py`
    - `src/agentic_traveler/orchestrator/preference_learner.py`
    - `src/agentic_traveler/webhook.py`
    - `specs/travel_personality_dimensions.md`
- **Assumptions:** The Tally form submission id is passed into `/start <submissionId>`.

## 6. Implementation Plan
- **High-Level Steps:**
    1. In the Tally webhook, map question keys to stable field names and store them under `user_profile.form_response`.
    2. Merge writes into Firestore to avoid overwriting unrelated fields.
    3. On `/start <submissionId>`, link Telegram user to the submission record.
    4. Call `ProfileAgent.build_initial_profile()` to derive a structured profile.
    5. Save the structured profile into `user_profile` and send a welcome greeting.
    6. On later preference updates, call `ProfileAgent.update_profile()` asynchronously and merge the updated structure back.

## 7. Testing & Validation
- **Test Strategy:** Manual test with a real Tally submission and Telegram `/start`.
- **Acceptance Tests:**
    - New form submission -> Firestore user doc contains `user_profile.form_response`.
    - `/start <submissionId>` links Telegram id and adds structured profile fields.
    - Greeting message is sent after successful profile mapping.

## 8. Risk Management
- **Known Risks:** Schema drift in Tally question ids.
- **Mitigations:** Centralized question-id map and merge-based Firestore writes.

## 9. Delivery & Handoff
- **Deliverables:** Tally v2 webhook, onboarding flow, structured profile schema, greeting message.
