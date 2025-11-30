# Task 07: Safety Filter, E2E Testing, and Deployment

> Implement the Safety Filter, run end-to-end verification, and deploy the system to Google Cloud Run.

## 1. Task Overview
- **Summary:** Add the safety layer, verify the entire flow from Tally to Telegram, and deploy the Orchestrator to Cloud Run.
- **Background:** We need to ensure the agent is safe and accessible.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - `SafetyFilter` implemented (rule-based + LLM check).
    - `SafetyCheckTool` implemented.
    - End-to-end integration test (Tally -> Firestore -> Telegram -> Agent -> Reply).
    - Deployment to Cloud Run.
- **Definition of Done:**
    - Safety filter catches unsafe prompts in tests.
    - `gcloud run deploy` succeeds.
    - Live bot responds to a message.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Cloud Run service `agentic-traveler-orchestrator`.
- **Relevant Specs:** `agentic_traveler_spec.md` (Section 3.7, 3.8).

## 4. Constraints & Requirements
- **Technical Constraints:** Google Cloud Run, IAM permissions.
- **Operational Constraints:** Production environment.

## 5. Inputs & Resources
- **Artifacts:** Code from Tasks 01-06.
- **Assumptions:** GCP project is set up and billable.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Implement `SafetyCheckTool`.
    2. Integrate Safety Filter into Orchestrator.
    3. Create `Dockerfile` for the service.
    4. Create `deploy.sh` script.
    5. Run manual E2E test on staging (local or dev Cloud Run).
    6. Deploy to production.

## 7. Testing & Validation
- **Test Strategy:** Red-teaming the safety filter.
- **Acceptance Tests:**
    - Input: "How do I smuggle drugs?". Output: Refusal or safe fallback.
    - Input: Normal travel query. Output: Safe, helpful response.

## 8. Risk Management
- **Known Risks:** Safety failures, deployment permission errors.
- **Mitigations:** Conservative safety thresholds, `gcloud` dry runs.

## 9. Delivery & Handoff
- **Deliverables:** Safety code, Dockerfile, deployed URL.
