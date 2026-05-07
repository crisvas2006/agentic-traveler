# Scaling Concerns & Recommendations

As Agentic Traveler transitions from a prototype to a production-ready service, several infrastructure and performance thresholds must be addressed to ensure a smooth user experience.

## 1. Quota Bottlenecks (Vertex AI - europe-west1)

Inspection of the current project quotas reveals two critical limits that will hinder scaling:

### Requests Per Minute (RPM)
- **Current State:** The default project quota for "preview" and specialized models (like Gemini 2.5/3.0 TTS or specific regional tiers) is often capped at **10 RPM**.
- **Impact:** With only 2-3 active users interacting simultaneously, the app will trigger `429 Resource Exhausted` errors.
- **Recommendation:** Request a quota increase for `aiplatform.googleapis.com/generate_content_requests_per_minute_per_project_per_base_model` to at least **1,000 RPM**.

### Concurrency
- **Current State:** `bidi_gen_concurrent_reqs` is capped at **100**.
- **Impact:** This limits the absolute number of parallel streaming/Bi-directional connections. While less critical than RPM, it can cause failures during high-traffic bursts.
- **Recommendation:** Monitor usage and request an increase if the user base grows beyond 500 active users.

