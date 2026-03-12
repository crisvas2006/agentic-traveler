# Task 08: Input Sanitization and Off-Topic Guard

> Sanitize user input before any LLM prompt and add a persistent off-topic guard with temporary restrictions.

## 1. Task Overview
- **Summary:** Strip control characters from user messages at the webhook boundary and enforce an off-topic policy that gently redirects users and temporarily restricts access after repeated non-travel attempts.
- **Background:** The assistant should minimize prompt injection risks and reduce wasted LLM calls for irrelevant content.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Sanitize inbound Telegram text before any LLM prompt.
    - Track consecutive off-topic messages per user.
    - Restrict the user for 1 hour after 5 consecutive off-topic messages.
    - Persist counters in Firestore so restrictions survive restarts.
- **Definition of Done:**
    - Sanitized input is used by the webhook before calling the orchestrator.
    - Off-topic counter resets on a travel-related message.
    - Restricted users receive a clear restriction message and no LLM call is made.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Enforcement happens at the webhook boundary and inside the orchestrator tool call flow.
- **Relevant Specs:** `agentic_traveler_spec.md` (Safety and uncertainty handling).

## 4. Constraints & Requirements
- **Technical Constraints:** Must be stateless at the service layer; persistence uses Firestore user doc.
- **Operational Constraints:** Fast execution; avoid unnecessary LLM calls.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/sanitize.py`
    - `src/agentic_traveler/off_topic_guard.py`
    - `src/agentic_traveler/webhook.py`
    - `src/agentic_traveler/orchestrator/agent.py`
- **Assumptions:** Firestore `users` documents exist for active Telegram users.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Add `sanitize_user_input()` to strip control characters and whitespace.
    2. Apply sanitization in the webhook before any command handling.
    3. Implement `off_topic_guard` to track counts and restriction windows.
    4. Expose a `flag_off_topic` tool to the LLM that triggers the counter.
    5. Check `is_restricted()` in the webhook to short-circuit requests.

## 7. Testing & Validation
- **Test Strategy:** Unit tests for sanitization and off-topic counter logic.
- **Acceptance Tests:**
    - Send 5 consecutive off-topic messages -> user receives restriction message and further messages are blocked for 1 hour.
    - Send a travel query after off-topic messages -> counter resets.

## 8. Risk Management
- **Known Risks:** Over-aggressive off-topic detection could block legitimate travel chat.
- **Mitigations:** The LLM prompt instructs lenient off-topic classification and allows banter.

## 9. Delivery & Handoff
- **Deliverables:** Sanitization utility, off-topic guard utilities, webhook enforcement.
