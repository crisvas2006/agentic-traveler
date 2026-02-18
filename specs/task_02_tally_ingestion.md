# Task 02: Tally Form Ingestion

> Implement the Cloud Function to ingest user profiles from Tally webhooks into Firestore.

## 1. Task Overview
- **Summary:** Create a Google Cloud Function that receives a webhook from Tally, parses the JSON payload, and saves it as a structured user profile in Firestore.
- **Background:** Tally is used for the "Know Thy Damn Self" form. We need to store this data to personalize the agent.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Cloud Function `ingest_tally_response` implemented.
    - Data mapping logic from Tally fields to Firestore schema.
    - Firestore write logic.
    - Unit tests for the ingestion logic.
- **Definition of Done:**
    - `pytest` passes for the ingestion function with sample Tally payloads.
    - Local test run successfully writes to a local/mock Firestore or logs the write.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** HTTP Cloud Function -> Firestore (`users` collection).
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 1.2, 1.6).

## 4. Constraints & Requirements
- **Technical Constraints:** Python, `functions-framework`, `google-cloud-firestore`.
- **Operational Constraints:** Stateless function.

## 5. Inputs & Resources
- **Artifacts:** Sample Tally JSON payload (need to create/mock this).
- **Assumptions:** 
    - Firestore project `agentic-traveler-db` exists (or we mock it for now).
    - users collection exists.
    - user item has the following fields (with example):
event_id: "d4124d56-d88a-4b1d-8db4-46ca9d277b11"
(string) 
event_type: "FORM_RESPONSE"
(string) 
phone_number: "+40745022676"
(string) 
source: "tally"
(string) 
user_name: "Cristian"
(string) 
user_profile
(map) 
absolute_avoidances
(array) 
0: "High‑crime / dangerous areas"
(string) 
1: "Heavy partying, loud hostels"
(string) 
2: "Other: "
(string) 
absolute_avoidances_other: "Garden gnomes"
(string) 
activity_level: "Moderate (sports or exercise 2–4×/week)"
(string) 
age_group: "25-34"
(string) 
budget_priority: "Balance — some comfort, but willing to spend a bit if experience demands it"
(string) 
cultural_spiritual_importance: "Rarely — I care more about fun, comfort or convenience"
(string) 
daily_rhythm: "Mid‑morning riser (9–11 AM)"
(string) 
diet_lifestyle_constraints: "I never eat breakfast"
(string) 
discomfort_tolerance_score: 2
(number) 
disliked_trip_patterns: "Waiting in line 18 days at a festival"
(string) 
dream_trip_style: "Go all in on whale hunting in Norway"
(string) 
extra_notes: "I like pina coladas"
(string) 
favorite_past_trip: "Swimming with the dolphins in Spain"
(string) 
hardest_part_solo_travel: "Too much unstructured time — felt directionless"
(string) 
location: "Romania, Bucharest"
next_trip_outcome_goals
(array) 
0: "Adventure / challenge / adrenaline"
(string) 
1: "Rest & recharge"
(string) 
personality_baseline: "Social — love meeting people, connecting, sharing"
(string) 
solo_travel_comfort: "Not ideal — I like some leads or meetups to avoid being totally alone"
(string) 
solo_travel_experience: "Once or twice"
(string) 
structure_preference: "Loose skeleton: key things planned, rest is freestyle"
(string) 
travel_budget_style: "Flexible spender — I balance cost and comfort, will splurge if it makes the trip"
(string) 
travel_deal_breakers
(array) 
0: "Dirty / unsafe accommodations"
(string) 
1: "Places with no cultural or natural beauty"
(string) 
travel_motivations
(array) 
0: "Chill and relax away from routine"
(string) 
trip_vibe
(array) 
0: "Chill / Relaxation"
(string) 
1: "Spiritual / Inner‑journey "
(string) 
typical_trip_lengths
(array) 
0: "4–7 days (short break)"
(string) 
weekday_energy: "Moderate – a mix of chill and hustle"
(string) 
webhook_created_at: "2025-11-30T16:02:24.263Z"
(string) 
webhook_received_at: November 30, 2025 at 6:02:24.562 PM UTC+2

## 6. Implementation Plan
- **High-Level Steps:**
    1. Create `src/agentic_traveler/ingestion/` module.
    2. Implement `tally_mapper.py` to map JSON to UserProfile object.
    3. Implement `main.py` (or `ingest.py`) with the Cloud Function entry point.
    4. Implement Firestore client wrapper.
    5. Write unit tests with mocked Tally data.

## 7. Testing & Validation
- **Test Strategy:** Unit tests with `pytest`.
- **Acceptance Tests:**
    - Send mock HTTP request to local function -> Verify Firestore write (mocked).

## 8. Risk Management
- **Known Risks:** Tally schema changes.
- **Mitigations:** Flexible mapping or validation layer.

## 9. Delivery & Handoff
- **Deliverables:** Code for ingestion function, tests.
