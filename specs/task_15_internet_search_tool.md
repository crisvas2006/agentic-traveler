# Task 20: Internet Search Tool Integration

> Add a web search tool for discovery and planning when fresh information is required.

## 1. Task Overview
- **Summary:** Implement a `WebSearchTool` that retrieves current information and integrates it into discovery/planning prompts.
- **Background:** Travel suggestions improve with current data (seasonality, events, closures).
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Provide a tool that returns concise, reliable web search results.
    - Use it selectively for time-sensitive or local information.
- **Definition of Done:**
    - Discovery/Planner can call web search when needed.
    - Results are summarized and cited internally for traceability.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Tool should be optional and gated to avoid cost blowups.
- **Relevant Specs:** `task_05_discovery_agent.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Must use a stable search provider API.
- **Operational Constraints:** Rate limits and cost control.

## 5. Inputs & Resources
- **Artifacts:**
    - Orchestrator tool interface
- **Assumptions:** Search API key is available.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Implement a `WebSearchTool` wrapper.
    2. Add a policy for when to call it (fresh data only).
    3. Inject summaries into prompts, not raw results.

## 7. Testing & Validation
- **Test Strategy:** Manual tests on time-sensitive queries.
- **Acceptance Tests:**
    - Asking about seasonal events triggers a search.

## 8. Risk Management
- **Known Risks:** Hallucinations or over-reliance on stale data.
- **Mitigations:** Require the tool for unstable info; prompt caution.

## 9. Delivery & Handoff
- **Deliverables:** Search tool, routing rules, updated prompts.

