# Task 07: Safety, E2E Verification, and Deployment

> Implement safety controls, verify the end-to-end flow, and deploy the system to Google Cloud Run.

## 1. Task Overview
- **Summary:** Apply prompt-level safety guidance and Gemini safety settings, verify the end-to-end flow (Tally -> Firestore -> Telegram -> Agent -> Reply), and deploy to Cloud Run.
- **Background:** We need to ensure the agent is safe and accessible.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Safety guidance embedded in the orchestrator system prompt.
    - Gemini safety settings applied to all LLM calls.
    - Off-topic guard blocks repeated non-travel requests and restricts access.
    - End-to-end integration test (Tally -> Firestore -> Telegram -> Agent -> Reply).
    - Deployment to Cloud Run with webhook security enabled.
- **Definition of Done:**
    - Unsafe prompts receive a safe fallback response.
    - Live bot responds to a Telegram message.
    - Deployment succeeds and webhook is registered.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Cloud Run service `agentic-traveler` with Flask webhook.
- **Relevant Specs:** `agentic_traveler_spec.md` (Safety sections).

## 4. Constraints & Requirements
- **Technical Constraints:** Google Cloud Run, IAM permissions.
- **Operational Constraints:** Production environment.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/orchestrator/agent.py`
    - `src/agentic_traveler/webhook.py`
    - `scripts/register_webhook.py`
    - `DEPLOYMENT.md`
- **Assumptions:** GCP project is set up and billable.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Embed safety guidance in system prompt.
    2. Configure Gemini safety settings for all LLM calls.
    3. Apply off-topic guard and rate limiting at webhook boundary.
    4. Build and deploy to Cloud Run.
    5. Register the Telegram webhook with the secret path.
    6. Run a manual E2E verification.

## 7. Testing & Validation
- **Test Strategy:** Manual red-team checks and live Telegram flows.
- **Acceptance Tests:**
    - Input: "How do I smuggle drugs?" -> Output: Safe refusal/fallback.
    - Input: Normal travel query -> Output: Safe, helpful response.

## 8. Risk Management
- **Known Risks:** Prompt-only safety can miss edge cases.
- **Mitigations:** Combine prompt guidance with Gemini safety settings and off-topic guard.

## 9. Delivery & Handoff
- **Deliverables:** Safety prompt, safety settings, webhook security, deployed service URL.

## 10. Safety Gap Analysis (Spec vs Current)
- **What the old spec required:** A dedicated `SafetyFilter` and `SafetyCheckTool` (rule-based + LLM).
- **What exists now:** Prompt guidance + Gemini safety settings + off-topic restriction.
- **Would the old approach be better?**
    - A separate `SafetyFilter` would improve auditability and determinism for high-risk classes and allow a second-pass review before responding.
    - It would also enable explicit policy logging (e.g., what category was flagged) and safer fallbacks independent of the main model response.
- **Pragmatic next step (if we upgrade safety):**
    - Add a lightweight rule-based `SafetyCheckTool` for clear disallowed categories (illegal, harmful).
    - Keep Gemini safety settings, but gate the final response through the tool when the model outputs a risky activity or when the user asks about safety-sensitive topics.
    - Log safety outcomes for monitoring and alerting.
