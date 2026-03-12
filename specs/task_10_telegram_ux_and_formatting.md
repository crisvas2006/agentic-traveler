# Task 10: Telegram UX and Formatting

> Ensure Telegram-safe formatting and improve perceived responsiveness with a loading placeholder.

## 1. Task Overview
- **Summary:** Enforce Telegram Markdown formatting constraints in prompts and add a placeholder message that updates while the LLM is working.
- **Background:** Telegram renders Markdown differently than typical web clients; responses should be readable and safe. A placeholder reduces perceived latency.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Format agent responses for Telegram (Markdown, no headers or code blocks).
    - Chunk responses to respect Telegram's 4096 character limit.
    - Show a "Thinking..." placeholder and edit it with the final response.
- **Definition of Done:**
    - Messages are sent with `parse_mode=Markdown` and fall back to plain text on formatting errors.
    - Long responses are chunked safely.
    - Placeholder is created and replaced by the final response when possible.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Implemented at the Telegram webhook boundary; formatting rules are embedded in prompts.
- **Relevant Specs:** `agentic_traveler_spec.md` (Telegram interface).

## 4. Constraints & Requirements
- **Technical Constraints:** Telegram Markdown quirks; 4096 char limit.
- **Operational Constraints:** Avoid extra API calls when possible, but prioritize user feedback during latency.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/webhook.py`
    - `src/agentic_traveler/orchestrator/agent.py`
    - `src/agentic_traveler/orchestrator/discovery_agent.py`
    - `src/agentic_traveler/orchestrator/planner_agent.py`
    - `src/agentic_traveler/orchestrator/companion_agent.py`
- **Assumptions:** Telegram API tokens are configured.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Add send/edit helpers that use `parse_mode=Markdown` with plain-text fallback.
    2. Enforce formatting guidelines in all LLM prompts (bullets, bold, no headers/code).
    3. Send a placeholder message immediately, then edit it with final content.
    4. If the final response is too long to edit, send remaining chunks as new messages.

## 7. Testing & Validation
- **Test Strategy:** Manual Telegram test flow; verify formatting and chunking.
- **Acceptance Tests:**
    - Response with bullets renders correctly in Telegram.
    - Response longer than 4096 chars arrives in multiple messages.
    - Placeholder is visible and replaced by the final response.

## 8. Risk Management
- **Known Risks:** Markdown parsing failures can drop messages.
- **Mitigations:** Always retry with plain text on Markdown errors.

## 9. Delivery & Handoff
- **Deliverables:** Telegram send/edit utilities and formatting rules in prompts.
