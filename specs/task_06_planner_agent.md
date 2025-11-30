# Task 06: Planner & Companion Agent

> Implement the Planner and Companion Agent for itinerary generation and in-trip assistance.

## 1. Task Overview
- **Summary:** Create the agent that generates day-by-day itineraries and provides live suggestions during the trip.
- **Background:** This covers "What do I do there?" and "What now?".
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - `PlannerAgent` implemented.
    - Itinerary generation logic (Structure vs Freedom).
    - In-trip suggestion logic (Mood/Weather based).
    - `FirestoreTripTool` for reading/writing trip state.
- **Definition of Done:**
    - Agent generates a 3-day itinerary for a given destination.
    - Agent provides a valid "next activity" suggestion based on mock context.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** heavily relies on `WebSearchTool` and `MapsAndPoiTool` (or search approximation).
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 3.6).

## 4. Constraints & Requirements
- **Technical Constraints:** ADK.
- **Operational Constraints:** None.

## 5. Inputs & Resources
- **Artifacts:** Trip details, User profile.
- **Assumptions:** Destination is already chosen.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Implement `PlannerAgent` class.
    2. Implement `FirestoreTripTool` (create_trip, update_trip).
    3. Implement itinerary generation prompt.
    4. Implement in-trip suggestion prompt.
    5. Integrate `FirestoreEventTool` for logging suggestions.

## 7. Testing & Validation
- **Test Strategy:** Offline simulation of a trip flow.
- **Acceptance Tests:**
    - Input: "I'm in Rome, it's raining". Output: Suggests Pantheon or Museum (Indoor).

## 8. Risk Management
- **Known Risks:** Over-scheduling, impossible logistics.
- **Mitigations:** "Loose skeleton" default mode.

## 9. Delivery & Handoff
- **Deliverables:** Planner agent code, trip tools.
