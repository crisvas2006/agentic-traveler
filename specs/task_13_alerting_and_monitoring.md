# Task 13: Alerting and Monitoring Setup

> Set up Cloud Monitoring alerts for suspicious traffic and Cloud Run resource health.

## 1. Task Overview
- **Summary:** Create log-based metrics and alert policies for suspicious webhook traffic and high token usage, plus resource alerts for CPU, memory, and latency.
- **Background:** The bot requires guardrails against abuse and early warnings for performance issues.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Create log-based metrics for suspicious events (non-Telegram IPs, auth failures, rate limits, restrictions, high token usage).
    - Create alert policies that notify a configured email address.
    - Add resource alerts for CPU, memory, and request latency.
- **Definition of Done:**
    - Script runs idempotently and creates metrics/policies when missing.
    - Alerts appear in the Cloud Monitoring console.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Uses Cloud Logging filters and Cloud Monitoring alert policies.
- **Relevant Specs:** `DEPLOYMENT.md` (Monitoring section).

## 4. Constraints & Requirements
- **Technical Constraints:** Requires `gcloud` CLI and project permissions.
- **Operational Constraints:** Must not fail if resources already exist.

## 5. Inputs & Resources
- **Artifacts:**
    - `scripts/setup_alerts.py`
- **Assumptions:** `ALERTING_EMAIL` and `GOOGLE_PROJECT_ID` are configured in `.env`.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Create or reuse an email notification channel.
    2. Create log-based metrics for suspicious traffic and high token usage.
    3. Create alert policies for each log-based metric.
    4. Create resource-based alert policies for CPU, memory, and latency.

## 7. Testing & Validation
- **Test Strategy:** Manual verification in Cloud Monitoring; simulate an event to trigger an alert.
- **Acceptance Tests:**
    - Metrics are visible in Cloud Logging.
    - Alerts are visible in Cloud Monitoring.

## 8. Risk Management
- **Known Risks:** Missing IAM permissions for Monitoring API calls.
- **Mitigations:** Document required roles and keep the script idempotent.

## 9. Delivery & Handoff
- **Deliverables:** Alert setup script and documented thresholds.
