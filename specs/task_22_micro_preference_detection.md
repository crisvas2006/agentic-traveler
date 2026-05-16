# Task 18: Micro-Preference Detection and Proactive Hints

> Detect recurring user micro-questions and proactively surface related info when relevant.

## 1. Task Overview
- **Summary:** Track recurring questions or phrases and use them to enrich future responses.
- **Background:** Small patterns (e.g., repeatedly asking "who goes there?") signal deeper interests.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Detect repeated intent patterns from user messages.
    - Persist micro-preferences as tags or notes.
    - Inject relevant context proactively when appropriate.
- **Definition of Done:**
    - Repeated user patterns result in a stored preference.
    - Future replies incorporate those preferences naturally.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Works alongside the ProfileAgent and preference updates.
- **Relevant Specs:** `task_04_profile_agent.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Keep detection lightweight.
- **Operational Constraints:** Avoid overfitting to one-off messages.

## 5. Inputs & Resources
- **Artifacts:**
    - Conversation history
    - Preference update pipeline
- **Assumptions:** Conversation history is stored in Firestore.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Add a lightweight pattern detector over recent messages.
    2. Promote repeated patterns to a stored preference/tag.
    3. Surface hints in responses when relevant.

## 7. Testing & Validation
- **Test Strategy:** Simulated conversation histories.
- **Acceptance Tests:**
    - Repeated questions lead to a stored micro-preference and future proactive hints.

## 8. Risk Management
- **Known Risks:** Over-personalization or incorrect inference.
- **Mitigations:** Require multiple occurrences before storing.

## 9. Delivery & Handoff
- **Deliverables:** Pattern detector and profile integration.

