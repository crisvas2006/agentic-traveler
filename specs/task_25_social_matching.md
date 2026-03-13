# Task 25: Social Matching and Group Travel Feature

> Let travelers discover compatible peers, connect, and optionally use AI in group chats.

## 1. Task Overview
- **Summary:** Match users with similar travel profiles and offer opt-in social features (profiles, chat, friends list).
- **Background:** Meeting compatible travelers increases engagement and provides value in popular destinations.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
    - Identify compatible users based on profile similarity and trip overlap.
    - Provide opt-in profile visibility and chat.
    - Allow invoking the AI assistant in group chats via mention.
- **Definition of Done:**
    - Users can opt in, view matches, and chat with a peer.

## 3. System Context
- **Repositories:** `agentic-traveler`.
- **Architecture Notes:** Requires a new user-facing UI and chat backend.
- **Relevant Specs:** `task_16_proactive_engagement_and_journaling.md` (engagement).

## 4. Constraints & Requirements
- **Technical Constraints:** Privacy controls and consent are mandatory.
- **Operational Constraints:** Must throttle and moderate to avoid abuse.

## 5. Inputs & Resources
- **Artifacts:**
    - User profile embeddings or similarity scoring
    - A chat service (Firestore-based or external)
- **Assumptions:** Sufficient user base for matching.

## 6. Implementation Plan
- **High-Level Steps:**
    1. Define matching criteria and opt-in flow.
    2. Build user profile cards and privacy settings.
    3. Implement a chat backend and friends list.
    4. Add AI invocation in group chat (e.g., @genie).

## 7. Testing & Validation
- **Test Strategy:** Closed beta with limited users.
- **Acceptance Tests:**
    - Two users match and exchange messages.
    - AI can answer a group chat question when invoked.

## 8. Risk Management
- **Known Risks:** Privacy, moderation, and harassment risks.
- **Mitigations:** Strong reporting tools, opt-in only, and minimal exposure by default.

## 9. Delivery & Handoff
- **Deliverables:** Matching service, profile UI, chat system, moderation tools.

