# Task 21: Secret Management

> **Status: ✅ COMPLETED** (2026-05-14)

> Centralize secrets using a managed secret store instead of .env in production.

## 1. Task Overview
- **Summary:** Move API keys and tokens to a secret manager and load them at runtime.
- **Background:** Production credentials should not live in files or environment variables checked into source control.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Store secrets in GCP Secret Manager.
    - Load secrets at startup and cache them safely.
- **Definition of Done:**
    - ✅ Production deploy uses GCP Secret Manager for keys (injected via Cloud Run env).
    - ✅ Local development continues to use `.env`.
    - ✅ Deployment command in `DEPLOYMENT.md` includes secret mappings.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Secrets are stored in GCP Secret Manager and injected as environment variables into the Cloud Run container at runtime.
- **Relevant Specs:** `task_07_safety_and_deployment.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Requires IAM roles for Secret Manager access (Service Account needs `Secret Manager Secret Accessor`).
- **Operational Constraints:** Fail-safe behavior if secrets are missing.

## 5. Inputs & Resources
- **Artifacts:**
    - `backend/DEPLOYMENT.md`
    - `backend/src/agentic_traveler/interfaces/webhook.py` (loads env vars)
- **Assumptions:** GCP project available and IAM permissions configured.

## 6. Implementation Plan
- **High-Level Steps:**
    1. ✅ Create secrets in GCP Secret Manager.
    2. ✅ Update deployment command to map secrets to environment variables.
    3. ✅ Verify app loads secrets correctly in production.

## 7. Testing & Validation
- **Test Strategy:** Deploy to production with Secret Manager and verify functionality.
- **Acceptance Tests:**
    - ✅ App boots and can call Telegram and Gemini using secrets.
    - ✅ All mandatory secrets (TALLY, GOOGLE, TELEGRAM) are verified as working.

## 8. Risk Management
- **Known Risks:** Permission errors (Secret Accessor role).
- **Mitigations:** Use explicit deployment flags to grant permissions if needed.

## 9. Delivery & Handoff
- **Deliverables:** Working production deployment and updated `DEPLOYMENT.md`.
