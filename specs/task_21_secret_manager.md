# Task 21: Secret Management

> Centralize secrets using a managed secret store instead of .env in production.

## 1. Task Overview
- **Summary:** Move API keys and tokens to a secret manager and load them at runtime.
- **Background:** Production credentials should not live in files or environment variables checked into source control.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Store secrets in GCP Secret Manager (or equivalent).
    - Load secrets at startup and cache them safely.
- **Definition of Done:**
    - Production deploy uses Secret Manager for keys.
    - Local development continues to use `.env`.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Centralized secret access; minimal code changes.
- **Relevant Specs:** `task_07_safety_and_deployment.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Requires IAM roles for Secret Manager access.
- **Operational Constraints:** Fail-safe behavior if secrets are missing.

## 5. Inputs & Resources
- **Artifacts:**
    - `DEPLOYMENT.md`
    - App configuration module
- **Assumptions:** GCP project available and IAM permissions configured.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Create secrets in Secret Manager (Telegram token, Gemini keys, etc.).
    2. Add a secret loader module with caching.
    3. Fallback to `.env` in local dev.

## 7. Testing & Validation
- **Test Strategy:** Deploy to staging with Secret Manager.
- **Acceptance Tests:**
    - App boots and can call Telegram and Gemini using secrets.

## 8. Risk Management
- **Known Risks:** Secret access failures at startup.
- **Mitigations:** Clear error messages and fallback to .env in dev.

## 9. Delivery & Handoff
- **Deliverables:** Secret manager integration and updated deployment docs.

