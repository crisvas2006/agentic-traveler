# Task 05: Discovery Agent

> Implement the Discovery Agent for finding destination candidates.

## 1. Task Overview
- **Summary:** Create the agent that takes user constraints and proposes destinations using web search and weather data.
- **Background:** This is the "Where should I go?" feature.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - `DiscoveryAgent` implemented.
    - `WebSearchTool` integrated (Google Search or similar).
    - `WeatherTool` integrated (OpenWeatherMap or similar).
    - Logic to rank and filter destinations.
- **Definition of Done:**
    - Agent returns 3 valid destination candidates for a given prompt.
    - Weather checks are performed for the requested dates.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Uses external tools heavily.
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 3.5).

## 4. Constraints & Requirements
- **Technical Constraints:** ADK, External API limits.
- **Operational Constraints:** Latency of web search.

## 5. Inputs & Resources
- **Artifacts:** Enriched profile from Task 04.
- **Assumptions:** We have API keys for search/weather.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Implement `DiscoveryAgent` class.
    2. Implement `WebSearchTool` wrapper.
    3. Implement `WeatherTool` wrapper.
    4. Create the prompt for destination discovery (Chain of Thought).
    5. Implement response parsing (JSON output for candidates).

## 7. Testing & Validation
- **Test Strategy:** VCR/Cassette recording for API calls to save costs/time.
- **Acceptance Tests:**
    - Input: "Beach trip in July, cheap". Output: List including Albania, Bulgaria, etc. (depending on current data).

## 8. Risk Management
- **Known Risks:** Hallucinations, outdated pricing.
- **Mitigations:** Prompt engineering to force "estimates only" and "verify" warnings.

## 9. Delivery & Handoff
- **Deliverables:** Discovery agent code, search/weather tools.
