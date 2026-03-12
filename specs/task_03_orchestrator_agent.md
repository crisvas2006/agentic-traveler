# Task 03: Orchestrator Agent & Telegram Integration

> Implement the main Orchestrator Agent and the Telegram webhook entry point.

## 1. Task Overview
- **Summary:** Build the Cloud Run Flask webhook that receives Telegram updates directly, initializes the Orchestrator, and routes requests through GenAI function calling.
- **Background:** The Orchestrator is the "front desk" of the system.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - HTTP entry point `/webhook/<secret>`.
    - Orchestrator Agent implemented with Google GenAI SDK automatic function calling.
    - Routing logic for Discovery, Planner, Companion, Preferences, and Off-topic handling.
    - Firestore integration to fetch user context and save conversation history.
    - Webhook security: secret URL path + secret token header + Telegram IP allowlist + rate limiting.
- **Definition of Done:**
    - Webhook receives a Telegram message and returns a response end-to-end.
    - Orchestrator routes to the correct tool function for a travel request.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Telegram -> Cloud Run (Flask webhook) -> Orchestrator -> Sub-agents/tools -> Telegram.
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 3.3).

## 4. Constraints & Requirements
- **Technical Constraints:** Google GenAI SDK function calling (no ADK).
- **Operational Constraints:** Low latency response (Telegram timeouts).

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/webhook.py`
    - `src/agentic_traveler/orchestrator/agent.py`
    - `src/agentic_traveler/tools/firestore_user.py`
- **Assumptions:** Telegram webhook is registered with the secret path and token.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Define `OrchestratorAgent` with GenAI function calling.
    2. Implement tool functions: discovery, planning, companion, preference updates, off-topic flag.
    3. Create the Flask webhook handler and security checks.
    4. Load user context from Firestore and save conversation history.
    5. Send Telegram responses with Markdown formatting and chunking.

## 7. Testing & Validation
- **Test Strategy:** Manual webhook tests + unit tests for routing and tool invocation.
- **Acceptance Tests:**
    - Input: "I want to go to Italy" -> Output: Discovery response with options and a follow-up question.

## 8. Risk Management
- **Known Risks:** Latency with LLM calls.
- **Mitigations:** Keep prompts concise; use regional Gemini routing when configured.

## 9. Delivery & Handoff
- **Deliverables:** Orchestrator agent code, Flask webhook handler, Telegram integration.
