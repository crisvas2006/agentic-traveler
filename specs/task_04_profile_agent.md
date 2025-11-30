# Task 04: Profile & Memory Agent

> Implement the Profile and Memory Agent responsible for managing user context and preferences.

## 1. Task Overview
- **Summary:** Create the agent that interfaces with Firestore to retrieve and enrich user profiles, and manage learned preferences.
- **Background:** Personalization is key. This agent provides the "brain" about the user to other agents.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - `ProfileAgent` implemented.
    - `FirestoreUserTool` enhanced with `get_enriched_profile`.
    - Logic to merge static Tally data with dynamic `preferenceSignals`.
- **Definition of Done:**
    - Unit tests: Agent correctly returns a merged profile object.
    - Integration: Can read from a (mocked) Firestore user record.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Called by Orchestrator, Discovery, and Planner agents.
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 3.4).

## 4. Constraints & Requirements
- **Technical Constraints:** ADK.
- **Operational Constraints:** Fast reads.

## 5. Inputs & Resources
- **Artifacts:** Firestore schema from Task 02.
- **Assumptions:** User data exists.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Implement `ProfileAgent` class.
    2. Implement `get_enriched_profile` method in `FirestoreUserTool`.
    3. Implement logic to interpret `preferenceSignals` (e.g., boosting certain vibe words).
    4. Implement `update_preferences` for the feedback loop.

## 7. Testing & Validation
- **Test Strategy:** Unit tests with mock Firestore data.
- **Acceptance Tests:**
    - Input: User with "likes hiking" signal. Output: Enriched profile includes "hiking" in high priority interests.

## 8. Risk Management
- **Known Risks:** Complex preference logic.
- **Mitigations:** Start with simple counters (likes/dislikes).

## 9. Delivery & Handoff
- **Deliverables:** Profile agent code, preference logic.
