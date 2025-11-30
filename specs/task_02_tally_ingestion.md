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
- **Assumptions:** Firestore project `agentic-traveler-db` exists (or we mock it for now).

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
