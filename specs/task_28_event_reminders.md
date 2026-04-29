# Task Spec: Trip Event Reminders

## Goal
Proactively notify users of important, time-sensitive trip events via Telegram push messages. This ensures the traveler stays on track without having to constantly check their itinerary, acting as a true "travel companion" that taps them on the shoulder when it's time to check in for a flight, catch a boat, or head to a dinner reservation.

## Approach
To build a reliable reminder system on serverless architecture (Cloud Run scales to zero), we cannot use long-running sleep threads. We will build an asynchronous polling architecture:

1. **Cloud Scheduler (The Pulse):** A Google Cloud Scheduler cron job will trigger a secure HTTP endpoint on our Cloud Run service every 5–10 minutes.
2. **Firestore `reminders` Collection:** A dedicated collection (or subcollection under the trip) to store reminders decoupled from the complex trip structure. Fields: `user_id`, `trip_id`, `activity_title`, `scheduled_time` (UTC), `message`, and `sent_status` (boolean).
3. **The Processor:** The triggered endpoint queries Firestore for `sent_status == False` AND `scheduled_time <= NOW()`, pushes the `message` via the Telegram Bot API, and updates the `sent_status` to True.
4. **Agent Integration:** We will provide the AI Orchestrator/Planner with an `add_reminder` tool so it can autonomously determine when a reminder is appropriate (e.g., automatically scheduling a check-in reminder 24 hours before a flight the user just told it about).

## Alternatives Considered
- **Cloud Tasks (Push Queue):** *Rejected.* Using Cloud Tasks allows exact, down-to-the-second scheduling. However, if a user changes their flight time, we would have to hunt down the exact Cloud Task ID and cancel/recreate it. A polling database architecture is vastly simple for handling user edits and cancellations.
- **In-Memory Timers / Asyncio.sleep:** *Rejected.* Cloud Run kills idle containers, meaning all in-memory scheduled timers would be wiped out.
- **`.ics` Calendar Invites:** *Rejected for now.* Having the bot send an `.ics` file so it creates a native phone alarm is a neat future feature, but getting reliable push notifications via Telegram first is the priority.

## Steps

[Step] Define the Firestore schema for Reminders (ensuring all timestamps are strictly UTC).
→ verify: Schema logic handles edge cases (e.g., past due but unsent).

[Step] Create the processing function and a highly secured FastAPI endpoint (`/internal/process-reminders`) that requires a specific header secret.
→ verify: Endpoint rejects unauthorized requests; successfully queries due reminders.

[Step] Implement batch Telegram messaging logic and Firestore commit batching so the endpoint operates safely even if 50 reminders trigger at the same minute.
→ verify: Telegram webhook receives the push and marks the DB doc as sent.

[Step] Add the `add_reminder` function to the LLM's toolkit. Guide the LLM in the system prompt to automatically calculate appropriate offsets (e.g., "Schedule flight check-in reminders exactly 24 hours before").
→ verify: The agent correctly infers timezone math and creates a valid database entry from a natural language prompt ("Remind me 2 hours before my train to Kyoto").

[Step] Document the `gcloud scheduler jobs create http` command in `README.md` to run the cron job targeting the endpoint.
→ verify: Cron job deploys and successfully pings Cloud Run.

## Risks & Open Questions
- **Timezones (CRITICAL RISK):** A user traveling from London to Tokyo may provide a time in JST, but their phone/bot might communicate differently. All times must be converted to absolute UTC before storage. We must provide the LLM with the user's current destination timezone context so it can do the math properly.
- **Spamming the User:** If a cron job fails to mark a notification as `sent=true` due to a DB error, the next cron tick might send the notification again. *Mitigation:* Ensure strict idempotency and use Firestore transactions. 

## Out of Scope
- Voice call reminders.
- Native device alarms (Apple/Google Calendar integrations).
- Push notifications via native mobile apps (handled strictly via Telegram).
