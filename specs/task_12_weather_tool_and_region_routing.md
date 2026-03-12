# Task 12: Weather Tool and Region-Aware LLM Routing

> Provide weather lookup via Open-Meteo and route Gemini calls to the closest region for lower latency.

## 1. Task Overview
- **Summary:** Implement a weather tool using Open-Meteo (geocoding + forecast) and configure the GenAI client to use a regional Vertex AI endpoint when available.
- **Background:** Weather context improves destination and itinerary quality; region-aware LLM routing reduces latency.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Weather tool converts location names to coordinates and retrieves forecasts.
    - Orchestrator can call `check_weather` and inject data into downstream prompts.
    - GenAI client uses `GEMINI_REGION` and `GOOGLE_PROJECT_ID` when provided.
- **Definition of Done:**
    - Weather data is retrieved for a city and summarized in suggestions.
    - LLM calls route to regional Vertex AI when env vars are set.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Weather service is a local utility used by the orchestrator; client routing is centralized.
- **Relevant Specs:** `task_05_discovery_agent.md` (weather integration).

## 4. Constraints & Requirements
- **Technical Constraints:** Open-Meteo APIs; fallback to global API key if no region is configured.
- **Operational Constraints:** Keep requests under 10 seconds to avoid webhook timeouts.

## 5. Inputs & Resources
- **Artifacts:**
    - `src/agentic_traveler/tools/weather.py`
    - `src/agentic_traveler/orchestrator/agent.py`
    - `src/agentic_traveler/orchestrator/client_factory.py`
- **Assumptions:** Network egress from Cloud Run is allowed for Open-Meteo.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Implement `WeatherService.get_coordinates()` using Open-Meteo geocoding.
    2. Implement `WeatherService.get_weather()` for daily forecasts.
    3. Provide `format_weather_summary()` for raw data injection into prompts.
    4. Add a `check_weather` tool in the orchestrator that calls the service.
    5. Create a GenAI client factory that selects Vertex AI when `GEMINI_REGION` is set.

## 7. Testing & Validation
- **Test Strategy:** Manual calls for known locations; unit tests for geocoding and formatting.
- **Acceptance Tests:**
    - Request weather for a city and receive a valid summary block.
    - LLM client logs indicate regional initialization when configured.

## 8. Risk Management
- **Known Risks:** Ambiguous location names and geocoding mismatches.
- **Mitigations:** Fuzzy matching on admin regions and fallback to best match.

## 9. Delivery & Handoff
- **Deliverables:** Weather service module, orchestrator tool, region-aware client factory.
