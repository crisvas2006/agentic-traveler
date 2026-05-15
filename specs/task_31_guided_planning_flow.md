# Task 15: Guided Planning Flow (Progressive Questions)

> Ask clarifying questions before producing a detailed itinerary to match the user's desired structure.

## 1. Task Overview
- **Summary:** Introduce a short question sequence that clarifies trip structure preferences before calling the Planner.
- **Background:** Early conversations rarely contain all planning constraints; asking first improves quality.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Detect when a user asks for a plan but key details are missing.
    - Ask a minimal set of guiding questions (dates, pace, structure, budget).
    - Only call `plan_itinerary` once the user confirms they want a full plan.
- **Definition of Done:**
    - The assistant asks clarifying questions instead of generating a full itinerary immediately.
    - Once answered, a full plan is generated.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Implemented in orchestrator routing and/or prompt rules.
- **Relevant Specs:** `task_06_planner_agent.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Keep the question list short.
- **Operational Constraints:** Do not annoy users who explicitly want a full plan.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/orchestrator/agent.py`
    - `src/agentic_traveler/orchestrator/planner_agent.py`
- **Assumptions:** Orchestrator can track whether the user has confirmed a full plan.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Add a guard rule: ask a short set of questions before planning.
    2. Track conversation state to avoid repeating questions.
    3. Trigger `plan_itinerary` only after confirmation.

## 7. Testing & Validation
- **Test Strategy:** Conversation simulations.
- **Acceptance Tests:**
    - "Plan my trip" -> clarifying questions first.
    - User answers -> full itinerary generated.

## 8. Risk Management
- **Known Risks:** Extra friction could reduce satisfaction.
- **Mitigations:** Keep questions minimal and allow opt-out.

## 9. Delivery & Handoff
- **Deliverables:** Updated orchestration logic and prompt rules.

