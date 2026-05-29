# Task 16: Proactive Engagement and Reflective Journaling

> Add proactive questions to deepen the profile, re-engage inactive users, and prompt post-trip reflection.

## 1. Task Overview
- **Summary:** Ask periodic profile-completing questions, ping inactive users, and run mindful journal prompts at defined trip milestones.
- **Background:** Proactive engagement builds better profiles and improves retention.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Detect missing profile fields and ask targeted questions.
    - Re-engage users after inactivity (e.g., 30 days).
    - Trigger journal prompts at end of trip, 1 week after, and 3 months after.
    - Provide a 3-month reminder for "Current Tide" or similar energy state.
- **Definition of Done:**
    - Scheduler sends a targeted question based on profile gaps.
    - Inactive user receives a thoughtful prompt.
    - Journal prompts are logged and stored.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Requires a scheduling mechanism (Cloud Scheduler + Cloud Run or background job).
- **Relevant Specs:** `task_11_onboarding_profile_enrichment.md`.

## 4. Constraints & Requirements
- **Technical Constraints:** Avoid spamming; respect user opt-out.
- **Operational Constraints:** Scheduling must be reliable and low cost.

## 5. Inputs & Resources
- **Artifacts:**
    - Firestore user profiles and trip state
    - A scheduling mechanism (Cloud Scheduler, Cloud Tasks, or cron)
- **Assumptions:** Trip start/end dates are available or inferred.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Define a list of high-value profile gaps and corresponding questions.
    2. Implement a scheduler job to select eligible users and send prompts.
    3. Store journal entries in a `journals` collection linked to user/trip.
    4. Add opt-in/opt-out preference for proactive messages.
    5. Add a 3-month "Current Tide" reminder template.

## 7. Testing & Validation
- **Test Strategy:** Dry-run scheduler with mock users.
- **Acceptance Tests:**
    - Inactive user receives a re-engagement prompt.
    - Journal prompts are sent at the configured intervals.

## 8. Risk Management
- **Known Risks:** Over-notifying users.
- **Mitigations:** Strict rate limits and user opt-out.

## 9. Delivery & Handoff
- **Deliverables:** Scheduler job, prompt templates, journal storage schema.

