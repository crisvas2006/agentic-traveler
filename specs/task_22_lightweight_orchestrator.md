# Task 22: Lightweight Orchestrator and Delegation

> Make the orchestrator lighter by using a smaller model for intent and delegating to a single primary agent.

## 1. Task Overview
- **Summary:** Split orchestration into a fast intent step and a single primary agent call to reduce cost and latency.
- **Background:** The current orchestrator does full function-calling; a lighter path may be faster and cheaper.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Use a lighter model to classify intent.
    - Route to exactly one primary agent per request (Discovery, Planner, Companion, or Chat).
    - Keep helper tools (time, weather, preferences) available as needed.
- **Definition of Done:**
    - Reduced token usage per request without quality regression.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Introduces a small intent layer before the main agent call.
- **Relevant Specs:** `task_03_orchestrator_agent.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Must not break current tool calls.
- **Operational Constraints:** Maintain response quality.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/orchestrator/agent.py`
- **Assumptions:** A lighter model is available and acceptable for intent.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Add a lightweight intent classifier step.
    2. Route to a single primary agent based on intent.
    3. Keep helper tools accessible if needed.
    4. Measure cost and latency before/after.

## 7. Testing & Validation
- **Test Strategy:** A/B test with a fixed prompt set.
- **Acceptance Tests:**
    - Intent classification matches current behavior on a test suite.

## 8. Risk Management
- **Known Risks:** Misclassification could reduce quality.
- **Mitigations:** Fallback to full orchestrator on low confidence.

## 9. Delivery & Handoff
- **Deliverables:** Intent classifier, routing logic, measurement results.

