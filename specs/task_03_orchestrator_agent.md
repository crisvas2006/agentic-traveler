# Task 03: Orchestrator Agent & Telegram Integration

> Implement the main Orchestrator Agent and the Telegram webhook entry point.

## 1. Task Overview
- **Summary:** Build the entry point Cloud Function that receives Telegram messages (via Make), initializes the ADK agent graph, and routes requests to the Orchestrator Agent.
- **Background:** The Orchestrator is the "front desk" of the system.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - HTTP entry point `/telegram-webhook`.
    - Orchestrator Agent implemented using ADK.
    - Basic routing logic (New Trip vs In-Trip vs Chat).
    - Integration with Firestore to fetch User context.
    - Basic security (API Key/Token validation) for the HTTP endpoint.
- **Definition of Done:**
    - Unit tests for the Orchestrator's routing logic.
    - Local simulation of a Telegram message flow.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Telegram -> Make -> Cloud Run (Orchestrator) -> Other Agents.
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 3.3).

## 4. Constraints & Requirements
- **Technical Constraints:** ADK for agent orchestration.
- **Operational Constraints:** Low latency response (Telegram timeout).

## 5. Inputs & Resources
- **Artifacts:** None.
- **Assumptions:** We will mock the other agents (Profile, Discovery, Planner) for now.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Define `OrchestratorAgent` class using ADK.
    2. Implement `determine_intent` logic (LLM based or heuristic).
    3. Create the HTTP handler for the webhook.
    4. Implement `FirestoreUserTool` (read-only for now) to get user context.
    5. Wire up the agent graph (Orchestrator only for now).

## 7. Testing & Validation
- **Test Strategy:** Unit tests, ADK offline simulation.
- **Acceptance Tests:**
    - Input: "I want to go to Italy" -> Output: Orchestrator routes to "New Trip" flow (mocked response).

## 8. Risk Management
- **Known Risks:** Latency with LLM calls.
- **Mitigations:** Keep Orchestrator prompt simple.

## 9. Delivery & Handoff
- **Deliverables:** Orchestrator agent code, webhook handler.
