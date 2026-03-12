# Task 09: Usage Logging and Cost Tracking

> Log LLM usage per agent and accumulate per-user token totals in Firestore.

## 1. Task Overview
- **Summary:** Emit structured log lines for each LLM call and store per-model token counts in the user document.
- **Background:** We need visibility into cost drivers per user and per model, and logs that can feed Cloud Monitoring.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Log input/output/total token counts and latency for each LLM call.
    - Record per-model token totals and call counts in Firestore.
    - Keep logs readable and usable for alerting.
- **Definition of Done:**
    - Orchestrator and sub-agents log usage data when responses include usage metadata.
    - Firestore user docs show `usage.<model>.total_input_tokens`, `total_output_tokens`, `call_count`.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Logging happens in-process and is picked up by Cloud Logging on Cloud Run.
- **Relevant Specs:** `agentic_traveler_spec.md` (Monitoring section).

## 4. Constraints & Requirements
- **Technical Constraints:** Firestore updates must be atomic and cheap.
- **Operational Constraints:** Logging must not significantly increase latency.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/usage_tracker.py`
    - `src/agentic_traveler/orchestrator/agent.py`
    - `src/agentic_traveler/orchestrator/discovery_agent.py`
    - `src/agentic_traveler/orchestrator/planner_agent.py`
    - `src/agentic_traveler/orchestrator/companion_agent.py`
- **Assumptions:** GenAI responses include `usage_metadata` in most cases.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Create `usage_tracker.log_and_accumulate()` to parse token usage and emit structured logs.
    2. Add Firestore atomic increments under `usage.<model>` in the user doc.
    3. Call usage tracking from the orchestrator and sub-agents after LLM responses.
    4. Log prompt length (chars) for sub-agent prompts as a quick size proxy.

## 7. Testing & Validation
- **Test Strategy:** Unit tests for usage parsing and Firestore field updates; integration test with a real GenAI response object.
- **Acceptance Tests:**
    - After a request, user doc includes updated token totals for the model used.
    - Cloud Logging shows a line with agent name, model name, and token counts.

## 8. Risk Management
- **Known Risks:** Model usage metadata may be missing for some responses.
- **Mitigations:** Treat missing metadata as zero and avoid Firestore updates in that case.

## 9. Delivery & Handoff
- **Deliverables:** Usage tracker module, orchestrator/sub-agent logging integration.
