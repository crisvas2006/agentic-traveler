# Agentic Traveler

An agentic travel planner and companion powered by Google Gen AI.

## High level description

### Problem Statement

When I want to travel, I usually have fuzzy desires and constraints but no clear destination. I bounce between flight sites, booking platforms, blogs, and maps, trying to answer three questions at once:

*   Where should I go that genuinely fits my budget, personality, energy, and constraints
    
*   What concrete itinerary and activities would make this trip feel meaningful, not generic
    
*   How do I adapt plans when reality changes, for example bad weather, low energy, or a different mood than expected
    

Even after hours of research, I can still end up with:

*   Destinations chosen for price or hype, not personal fit
    
*   Overcrowded or under planned itineraries
    
*   Frustration during the trip when plans do not match energy, weather, or local reality
    

Existing tools are either deal engines or rigid planners. They barely model who you are as a traveler: lifestyle, energy, risk tolerance, deeper motivations like self discovery or connection. They also do not behave like a companion that adapts day by day.

I focus the MVP on the solo traveler (who may sometimes bring a partner or friend) who wants trips that align with their personality and current life phase, not just “cheap and popular”.

### Why agents?

The problem is not a single query but an ongoing process:

*   Build a rich, structured profile of the traveler
    
*   Interpret vague requests like “5–7 days in late spring, I’m tired, want nature and some culture, from Bucharest”
    
*   Discover plausible destinations, filter by constraints, and justify why they fit
    
*   Turn a chosen destination into a flexible itinerary
    
*   During the trip, adapt suggestions to mood, weather, and what actually happened
    

This requires:

*   Long term memory (profile and learned preferences)
    
*   Session state per interaction
    
*   Tool use (datastore, search, weather, maps)
    
*   Safety and uncertainty handling
    

Agents fit well because they allow:

*   Small, specialized components (discovery, planning, memory, safety) instead of one giant prompt
    
*   Tight control over what context each agent sees, which improves cost and reduces hallucinations
    
*   A planning-before-acting pattern with explicit tool calls and checks
    
*   Clear separation between runtime (stateless Cloud Run) and state (Supabase + logs)
    

The user does not need “one big model answer” but a persistent, evolving travel companion. Agentic design matches that need.

### What I created

High level, the system has three layers.

#### 1\. Personalization intake

A Tally form, “The Odyssey Onboarding” collects a deep but structured profile:

*   Context: home base, budget style
    
*   Lifestyle & energy: daily rhythm, physical activity, typical tempo
    
*   Travel style: preferred trip vibes (nature, culture, party, etc), structure preference, solo comfort
    
*   Personality & values: spontaneous vs reflective, social vs independent, motivations to travel, risk tolerance, spiritual interest
    
*   Past travel: what worked, what did not, solo challenges
    
*   Practical constraints: vacation days, diet/lifestyle, climate/logistics avoidances
    
*   Goals & dreams: what they want from their next trip, dream trip style, This form sends data directly to the backend's `/tally-webhook` endpoint, which persists it into Supabase.

To support seamless linking of onboarding profiles for existing web users, the system uses a secure token handshake:
*   **Table: `link_tokens`**: Manages secure random UUID tokens (avoiding exposure of database user IDs) of two kinds:
    *   `telegram_link` (10-minute TTL): Connects a Telegram account to a web profile via `/settings`.
    *   `tally_submission` (7-day TTL): Connects Tally onboarding form submissions to an existing web profile.
*   **Personalized Onboarding**: If a linked Telegram user or Web Chat user has not yet completed the form, they receive a thoughtful recommendation with a personalized deep-link using the base URL configured in the `TALLY_FORM_URL` environment variable: `<TALLY_FORM_URL>?idToken=<token>`.
*   **Webhook Merging**: If the webhook receives a submission with a valid `idToken`, it resolves the existing user record, updates it gracefully (mapping `submission_id`, and optionally `location` if provided in the submission), deletes the single-use token, verifies that the user has remaining credits, and then triggers background traveler DNA profiling (`ProfileAgent`) with full LLM cost-tracking and credit deduction, or logs a warning and returns early if no credits remain.

#### 2\. Automation and messaging

*   Telegram is a major communication interface.
    
*   The Telegram Bot webhook calls the Cloud Run endpoint directly (`/webhook/<secret>`).
    
*   The backend sends replies back to Telegram via the Bot API.
    

This keeps the backend focused on agent logic and state, with Telegram handling the channel plumbing.

#### 3\. Agentic backend on Cloud Run

*   Service: agentic-traveler-orchestrator (Python + Google GenAI SDK)
    
*   Data: Supabase (PostgreSQL) as source of truth
    
    *   `users`: long-term profile, `preference_signals` (JSONB), and `credits`
        
    *   `trips`: constraints, candidates, chosen destination, itinerary summary, and status
        
    *   `feedback`: user sentiment logs for lightweight learning
        
    *   `analytics_weekly`: aggregated usage metrics and token accounting
        
Core agents (tool-calling architecture):

1.  **Coordinator** (entry point — no LLM call)

    *   Receives every Telegram message.
    *   Loads user context from Supabase via `UserRepository`.
    *   Calls the **Router Agent** for intent classification.
    *   Dispatches to the appropriate specialized agent.
    *   Handles off-topic restriction and atomic credit deduction via Supabase RPC.

2.  **Router Agent** — intent classifier

    *   Classifies user messages: CHAT | TRIP | PLAN | OFF_TOPIC.
    *   Handles lightweight tools directly: `update_preferences()`, `record_feedback()`, `get_my_credits()`.
    *   For OFF_TOPIC: generates a warm, natural redirection response.

3.  **Chat Agent** — conversational companion

    *   Handles greetings, banter, emotional support, life advice, casual Q&A.
    *   Full personality profile + dimension scores injected.

4.  **Trip Agent** — travel discovery and in-trip help

    *   Merges the former Discovery Agent + Companion Agent.
    *   Handles destination exploration, travel advice, in-trip assistance.
    *   Implicit personalization (adjectives, not preference name-dropping).

5.  **Planner Agent** — structured itinerary builder

    *   Produces day-by-day itineraries with morning/afternoon/evening blocks.
    *   Separate from Trip Agent due to distinct output format + longer token budget.

6.  **Search Agent** — grounding proxy

    *   Isolated Google Search grounding — only invoked by other agents when needed.
    *   Eliminates the always-on $0.035/prompt grounding fee.

7.  **Profile Agent**

    *   Converts raw Tally form responses into a structured "Traveler DNA" profile.

8.  **Conversation Manager**

    *   Stores recent messages + compacted summary in Supabase `conversations` table.

#### Current Model Stack

The system uses a tiered model approach to balance reasoning quality and cost:

| Agent | Model | Rationale |
| :--- | :--- | :--- |
| **Router** | `gemini-3.1-flash-lite-preview` | Ultra-fast, low-cost classification. |
| **Chat** | `gemini-3.1-flash-lite-preview` | Responsive conversational agent. |
| **Search** | `gemini-3.1-flash-lite-preview` | Lightweight grounding proxy. |
| **Trip** | `gemini-3-flash-preview` | Richer reasoning for travel advice. |
| **Planner** | `gemini-3-flash-preview` | Multi-day coherence and structured output. |
| **Analytics** | `gemini-2.5-flash-lite` | Extremely low-cost summarization of logs. |

The backend is stateless: each request reconstructs context from Supabase and tools, then responds directly to Telegram.

### Security & Safety

The system implements defense-in-depth for the Telegram webhook:
1.  **Secret URL Path**: Webhook receives updates at `/webhook/<secret_token>`.
2.  **Secret Token Validation**: Verifies the `X-Telegram-Bot-Api-Secret-Token` header.
3.  **IP Whitelisting**: Only accepts requests from official Telegram CIDR ranges.
4.  **Rate Limiting**: Per-user distributed limits backed by Supabase.
5.  **Payload Validation**: Ensures only valid text messages are processed.
6.  **Infrastructure Limits**: Cloud Run configured with max-instances and concurrency limits to prevent cost spikes or DDoS.

### Analytics & Observability

The orchestrator includes a custom metrics system designed for Cloud Run:
*   **In-Memory Buffering**: Captures interactions and token usage without blocking requests.
*   **Threshold-based Flush**: Weekly metrics are written to Supabase (`analytics_weekly` table) every 50 events or on process shutdown.
*   **Deduplicated Tracking**: Monitors active users per ISO week.
*   **Token Accounting**: Tracks input/output tokens per model and per agent call.

### The Build

Tools and technologies:

*   **Supabase (PostgreSQL)**
    
    *   Relational storage for users, trips, and feedback
        
    *   JSONB columns for flexible agentic state (profiles, preferences)
        
    *   RPC functions for atomic credit deduction and concurrent safety
        
*   **Web frontend**

    *   Next.js 16 / React 19 / TypeScript / Tailwind CSS v4 on Vercel
    *   Supabase Auth with Google OAuth and email/password (PKCE flow, Cloudflare Turnstile CAPTCHA)
    *   Dashboard: phase-aware trip view, map canvas, AI chat panel (in design/build)

*   **GCP**
    
    *   Cloud Run for the stateless agent service (FastAPI + Python)
        
    *   Secret Manager for API keys and webhook tokens
        
*   **Backend & agents**
    
    *   Python with the Google GenAI SDK (function calling) to define the agent flow
        
    *   Small, specialized agents:
        
        *   Orchestrator, Router, Chat, Trip, Planner, Search, Profile, Conversation Manager
            
    *   Planning before acting:
        
        *   For complex tasks (itinerary building), agents first sketch a plan then execute tool calls
            
    *   Lightweight learning:
        
        *   Preferences are learned incrementally from chat feedback and updated in Supabase
            
*   **Automation and chat**
    
    *   Tally form for user personalization
        
    *   Integrated `/tally-webhook` mapping raw form data into structured profiles
        
    *   Telegram bot as primary interface
        
    *   Direct Telegram webhook to Cloud Run (with IP whitelisting and secret validation)
        
*   **Safety and monitoring**
    
    *   Safety guidance in prompts and model safety settings
        
    *   Logging of:
        
        *   Incoming message metadata
            
        *   Tool calls and outcomes
            
        *   Errors and basic latencies
            
    *   Versioned prompts and tools, so changes can be tracked and rolled back
        

The build emphasizes clear responsibilities per agent, stateless runtime with externalized state, and a realistic but contained scope that still demonstrates agentic behavior, memory, and robustness.

### If I had more time, this is what I’d do

If I had more time, I would extend in these directions:

1.  **Richer behavior modeling**
    
    *   Add a vector store for user embeddings and trip summaries
        
    *   Use similarity search to adapt plans based on past successful trips
        
    *   Move beyond simple counters toward richer “travel archetypes” for each user
        
2.  **Group and relationship aware travel**
    
    *   Support multiple traveler profiles and a group plan
        
    *   Add an agent that mediates between different budgets, vibes, and avoidances
        
    *   Support group chats where the agent helps converge on “good enough for everyone” plans
        
3.  **Deeper travel integrations**
    
    *   Integrate a real flight or accommodation API for realistic price ranges and routes
        
    *   Generate prefilled links or filters for popular booking sites
        
4.  **Proactive companion mode**
    
    *   Optional daily check ins during trips, based on weather and preferences
        
    *   Simple triggers to propose alternatives when key activities fall through
        
5.  **Evaluation and observability**
    
    *   Build a small eval set of scenarios and expected behaviors
        
    *   Use it to test changes in prompts, tools, and logic before deployment
        
    *   Improve tracing to quickly understand “bad” suggestions and fix root causes
        
6.  **User experience surfaces**
    
    *   Add a minimal web UI for visualizing trips and editing profiles
        
    *   Expose the system as an API that other products or agencies could integrate
        

These steps would deepen the technical sophistication and make the project an even stronger showcase of agentic AI, architecture, and product thinking.

## Technical Design Documentation

### 1.1 Problem and product description

Solo travelers with vague desires and constraints spend a lot of time jumping between sites to decide where to go, when to go, and what to do. The process of choosing a destination, creating an itinerary, and adapting on the fly is mentally heavy and fragmented across tools. Existing platforms are either generic deal aggregators or rigid planners, they do not understand the traveler as a person and do not adapt during the trip.

This project is an AI agentic travel companion that:

*   Builds a deep but structured profile of the traveler, including personality, energy, risk tolerance, travel style, and constraints.
    
*   Proposes destinations and itineraries that match this profile and the current life and emotional context.
    
*   Acts as a live companion during trips: answering questions, adapting plans to weather and energy, and learning from behavior over time.
    

The primary interaction channel is Telegram chat. A web frontend is under active development (see §1.7).

### 1.2 Personalization and data intake

User personalization is collected through a Tally form (https://tally.so/r/ODPGak):

*   Form: "The Odyssey Onboarding"

*   Fields cover:

    *   Quick context: age band, base city, budget style.

    *   Lifestyle and energy: daily rhythm, physical activity.

    *   Travel style: desired trip vibe, structure preference, solo comfort.

    *   Personality and values: spontaneity, social vs independent, motivation to travel, spiritual interest, risk tolerance.

    *   Past travel: best trip, bad trip patterns, solo travel experience and pain points.

    *   Practical constraints: vacation days, budget approach, dietary and lifestyle preferences, hard avoidances.

    *   Goals and dreams: what they want from next trip, dream trip style, extra notes.

Technical intake:

*   Tally form → `/tally-webhook` endpoint on the Cloud Run backend (no separate Cloud Function).

*   The webhook handler authenticates the request via the `TALLY_WEBHOOK_TOKEN` bearer header and persists the raw submission to Supabase.

*   The **`ProfileAgent`** then maps the raw responses into a structured **Traveler DNA** (tags, personality-dimension scores, tone preference) and sends the user a message acknowledging that onboarding succeeded.

*   **Linking flow:** If the submission carries an `idToken` query parameter (issued via the `link_tokens` table as a single-use `tally_submission` token), the handler merges into the existing user record instead of creating a duplicate, then runs the same Traveler DNA pass without an intrusive chat alert.

The resulting Traveler DNA is the main personalization source for the agents.

### 1.3 MVP capabilities

Must have features for the first version:

1.  **Destination discovery**
    
    *   Input: user profile from Firestore, trip constraints from Telegram chat (rough dates or time window, duration, budget band, desired vibe, energy, willingness for discomfort).
        
    *   Output:
        
        *   A short list of three to five destination candidates.
            
        *   For each destination:
            
            *   Why it matches the user\_profile (vibe words, personality, risk tolerance, energy, budget style, avoidances).
                
            *   Rough budget band.
                
            *   Best periods within the requested window, based on seasonality and cost.
                
            *   Short notes on travel effort (distance, estimated travel time, complexity).
                
2.  **Trip planning**
    
    *   Input: chosen destination, user\_profile, trip window and duration.
        
    *   Output:
        
        *   A rough day level itinerary:
            
            *   Day structure that reflects structure preference (highly planned, loose skeleton, or free form).
                
            *   Activity sets per day, with alternatives for different energy levels.
                
            *   Hints on what to book later: example neighborhoods to stay in, typical local transport patterns, key bookings to secure early.
                
        *   No direct bookings; suggestions are grounded in real world information and current knowledge but the user executes bookings on their usual platforms.
            
3.  **Live companion during the trip**
    
    *   Input: user messages from Telegram:
        
        *   Current mood and energy: tired, social, introspective, bored, restless.
            
        *   Constraints: weather, time of day, physical limitation, budget for the day.
            
    *   Output:
        
        *   Two to three actionable suggestions for what to do next, linked to:
            
            *   Current mood and energy.
                
            *   Current location and time.
                
            *   Known preferences and avoidances.
                
        *   The agent logs what types of suggestions were accepted or rejected and biases future suggestions.
            
4.  **Personalization and learning**
    
    *   The system uses:
        
        *   user\_profile from Firestore as long term personalization.
            
        *   An event log per user and trip (suggestion offered, accepted, rejected), which is used for lightweight preference learning.
            
    *   Behavioral learning is lightweight:
        
        *   Track counts of accepted or rejected categories (for example: hikes, nightlife, long structured tours, spiritual events).
            
        *   Adjust the probability of suggesting these categories in future trips.
            
5.  **Safety and uncertainty handling**
    
    *   The system avoids suggesting illegal or obviously unsafe activities.
        
    *   For any recommendation that touches safety, local laws, or where the system is not confident, it always adds a note such as:“Please verify details and safety before booking or acting on this suggestion.”
        

### 1.4 Not in scope for MVP

*   Automatic group negotiation and group chat.
    
*   Rich web or mobile frontend. Telegram is the primary interface.
    
*   Direct booking flows or payment handling.
    
*   Heavy behavior modeling or complex life phase models.
    
*   Direct integration with specific travel APIs such as Skyscanner or Amadeus in the first version. Use general web search and basic tools instead.
    

### 1.7 Web Frontend

A Next.js web application complements the Telegram interface with a visual, spatial layer.

**Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4, Supabase Auth (`@supabase/ssr`), Vercel.

**Auth flows implemented:**
- Email/password sign-up and login (with Cloudflare Turnstile CAPTCHA)
- Google OAuth (PKCE flow via Supabase)
- Password reset via branded email links routed through `/auth/confirm`
- Consent recording (`consents` table) on sign-up for GDPR accountability - [TO BE IMPLEMENTED - GDPR COMPLIANCE]

**Dashboard vision (in design/build):**

The dashboard is the *cockpit* to the AI agent — it makes trips spatial and tangible. It is phase-aware: a new user sees an onboarding canvas guiding them to plan a first trip; a user with an upcoming trip sees it in planning focus; a user currently on a trip sees live companion mode with today's itinerary highlighted.

Core layout paradigm: **map as canvas, panels as overlays.**

- **Left sidebar / swipe-right (mobile):** Trip library — all trips (Exploring → Planning → Active → Complete), Traveler DNA teaser at the bottom.
- **Center / default pane (mobile):** Trip detail — day-by-day itinerary accordion, destination candidate cards, budget overview, key bookings checklist. Selecting a day updates the map in real time.
- **Map canvas (always present):** World map with candidate destination pins during discovery; zoomed destination map with POI pins and day route during planning; live location dot during active trip. Map tile style tracks the light/dark theme.
- **Chat (floating bubble on mobile, right sidebar on desktop):** The AI agent is always one tap away. Chat is the primary way to trigger changes; the panels reflect the results.

Visual identity: extends the auth pages (blue → purple gradient, glassmorphic panels, Geist font, dark/light theming) in a bolder, more spatial direction. Map tile style adapts to the active theme.

Full design specification: [`specs/frontend_dashboard_design.md`](specs/frontend_dashboard_design.md).

---

### 1.5 Key user stories

Profile and setup:

*   As a solo traveler, I want to fill a single, deep profile form once so that the system can understand my energy, style, constraints, and motivations without asking every time.
    

Destination discovery:

*   As a user, I want to say things like “five to seven days in May or June, I want nature and some culture, medium budget, leaving from Bucharest” and get a small set of destinations that clearly match my travel personality and constraints.
    

Trip planning:

*   As a user who picked a destination, I want a structured but flexible itinerary, with a few alternatives and clear explanations, so I feel guided but not constrained.
    

Live companion:

*   As a user during the trip, I want to tell the agent my mood, energy, and weather situation and get two or three adapted suggestions, so I can salvage bad days and improve good ones without replanning from scratch.
    

Learning:

*   As a repeat user, I want the system to quietly learn that I avoid certain activities and love others, so later trips feel more tailored with less configuration.
    

### 1.6 High level system architecture

Main components:

*   **Tally form**

    *   Collects user personalization data.

    *   Sends responses directly to the Cloud Run backend (`/tally-webhook`).

*   **Tally webhook handler** (part of the Cloud Run service — not a separate Cloud Function)

    *   FastAPI route under `backend/src/agentic_traveler/interfaces/routers/`.

    *   Authenticates each request via the `Authorization: Bearer <TALLY_WEBHOOK_TOKEN>` header.

    *   Persists the raw submission to Supabase, then hands off to the `ProfileAgent` to build the Traveler DNA and acknowledge the user.

    *   If the submission carries a valid `idToken` (issued via `link_tokens` as a `tally_submission` token), the handler merges into the existing user record instead of creating a duplicate.

*   **Supabase (PostgreSQL)** — source of truth for all state. See `supabase/schema_public.sql` for the authoritative schema. Core tables:

    *   `users`: identity record — `id` (UUID), `telegram_id`, `submission_id`, `name`, `location`, `source`, timestamps.

    *   `user_profiles`: AI-generated Traveler DNA — `profile_data` (JSONB: `tags`, `personality_dimensions_scores`, `tone_preference`, `additional_info`), `form_response` (raw Tally answers), `summary`.

    *   `credits`: per-user credit balance and spend history (`1 credit ≈ 1 eurocent`).

    *   `conversations`: rolling, compacted conversation window owned by the Conversation Manager (agent context — not user-visible).

    *   `chat_threads` + `messages`: append-only message log that is the source of truth for the web chat UI. `messages.source` is `'web'` or `'telegram'`.

    *   `usage_tracking`: per-user / per-model LLM token counts and credit cost.

    *   `feedback`: user-submitted feedback captured from the chat.

    *   `analytics_weekly`: aggregated weekly metrics flushed in batches from the in-memory analytics buffer.

    *   `link_tokens`: short-lived single-use tokens for `telegram_link` (10-minute TTL) and `tally_submission` (7-day TTL) flows.

    *   `off_topic_state`, `waitlist`: off-topic restriction state and landing-page sign-ups.

    *   **RLS is enforced** on user-scoped tables; atomic credit operations use Supabase RPCs (`deduct_credits`, `accumulate_user_usage`) invoked with the service key.

*   **Web app (Next.js on Vercel)** — primary interface

    *   Authenticated dashboard, chat, settings, and onboarding entry points (see §1.7).

    *   Calls the Cloud Run backend for chat, credits, and account operations.

*   **Telegram Bot** — optional secondary channel

    *   Linked from `/settings` in the web app via a `telegram_link` token; a user can chat with the same agent from Telegram once linked.

    *   Sends webhook updates directly to the Cloud Run service at `/webhook/<secret>`.

*   **Cloud Run service "agentic-traveler-orchestrator"**

    *   Stateless HTTP service in Python (FastAPI + Google GenAI SDK).

    *   Hosts the multi-agent system (Coordinator + Router + Chat/Trip/Planner/Search/Profile + Conversation Manager — see §1 *Agentic backend on Cloud Run* above).

    *   Entry-point endpoints: `/webhook/<secret>` (Telegram), `/tally-webhook` (Tally), plus authenticated web routes for chat and credits.

    *   Uses Supabase as the single source of truth for profiles, conversations, messages, feedback, credits, and analytics.

    *   Uses external tools (web search via Search Agent, weather, maps) only when an agent decides they're needed.

    *   Applies safety guidance and model safety settings before responding.


##
### Common workflow to eliminate 80% of stylistic mistakes in python code:
black .
ruff check .
mypy .
pytest
isort .

## Features

- **AI-Powered Travel Personalization**: Uses a deep onboarding questionnaire (Tally) and localized mapping to create a unique "Traveler DNA".
- **Multi-Agent Orchestration**: Specialised agents for Discovery, Planning, and in-trip Companionship.
- **Real-time Context Awareness**: Weather-aware suggestions and adaptive itineraries based on current mood and energy.
- **Safety & Moderation**: Integrated off-topic guard and multi-layer webhook security.
- **Usage & Metrics Tracking**: Real-time per-user LLM usage and estimated credit cost tracking (where `1 credit = 1 eurocent`) inside the Supabase `usage_tracking` table, alongside weekly global analytics rollups flushed to the `analytics_weekly` table.
- **Credits & Promo Codes**: Each new user is granted an initial credit balance. Top-ups and promo-code redemption live on the **web** (under Account Settings) — the previous Telegram `/promo <CODE>` command has been removed. When a user runs out of credits, both Telegram and web chat surface a message pointing them back to the web app to redeem or top up.
- **Interactive CLI & Webhook**: Support for both local development (CLI) and production Telegram bot interactions.
- **Feedback Loop**: Integrated tool for capturing user sentiment to refine future suggestions.

## Project Structure

The project follows a modular, domain-driven architecture:

```text
src/agentic_traveler/
├── analytics/         # Metrics tracking & usage logging (flushed to Firestore)
├── core/              # Foundational logic (sanitization, shared utilities)
├── economy/           # User credits & promo code management
├── guards/            # Security layers (off-topic guard)
├── interfaces/        # Entry points (CLI, Webhook handler)
├── orchestrator/      # Multi-agent system (Orchestrator, Discovery, Planner, Companion)
└── tools/             # External tool implementations (Firestore, Weather, Search)
```

## Setup

### 1. Create and activate the virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate
```

### 2. Install dependencies

```powershell
pip install -e ".[dev]"
```

### 3. Environment variables

Create a `.env` file in the project root:

```env
GOOGLE_API_KEY=your-gemini-api-key
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/application_default_credentials.json
```

- **`GOOGLE_API_KEY`** — required for all Gemini LLM calls (orchestrator + sub-agents).
- **`GOOGLE_PROJECT_ID`** — your GCP project ID (used by the Firestore client).
- **`GOOGLE_APPLICATION_CREDENTIALS`** — path to the Application Default Credentials JSON file.
  To generate it, run `gcloud auth application-default login` and copy the path it prints.

> **Note (Microsoft Store Python):** If you use the Microsoft Store version of Python,
> `gcloud` saves credentials under a sandboxed `AppData` path. You **must** set
> `GOOGLE_APPLICATION_CREDENTIALS` explicitly — see the path printed by the gcloud command.

## Usage

### Interactive CLI

Chat with the orchestrator locally by impersonating an existing Firestore user:

```powershell
.\.venv\Scripts\python -m agentic_traveler.interfaces.cli
```

This lists all users in Firestore, lets you pick one, then opens an interactive chat loop. You can also pass a Telegram ID directly:

```powershell
.\.venv\Scripts\python -m agentic_traveler.interfaces.cli --telegram-id 12345
```

## Testing

### Unit tests

Unit tests use mocked Firestore and LLM — no credentials needed:

```powershell
.\.venv\Scripts\python -m pytest tests/ --ignore=tests/integration -v
```

### Integration tests

Integration tests use the **real Gemini API** and **real Firestore** database. They require:
- `GOOGLE_API_KEY` set in `.env`
- `GOOGLE_APPLICATION_CREDENTIALS` set in `.env`
- A working GCP project with Firestore enabled

Test data is created with a `_test: True` marker and automatically cleaned up after each test.

```powershell
$env:_INTEGRATION_TESTS="1"; .\.venv\Scripts\python -m pytest -m integration -v
```

> The `_INTEGRATION_TESTS=1` env var tells the test framework to use the real
> Firestore library instead of the mock used by unit tests.

### Run all tests together

```powershell
$env:_INTEGRATION_TESTS="1"; .\.venv\Scripts\python -m pytest -v
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for instructions on deploying to Google Cloud.




