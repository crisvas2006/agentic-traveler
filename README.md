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
        
    *   `trips` + child tables (`trip_destinations`, `trip_bookings`, `trip_days`, `trip_day_blocks`, `trip_checklist`): layered trip documents with JSONB sections for loose-shape state and child tables for per-item collections. The `derive_saga_state()` Postgres function derives the canonical saga phase (DREAMING → LIVING); `vw_trips_growth` tracks creation velocity.
        
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
    *   Uses **structured output** (a single JSON response), not function calling: the
        model returns the intent plus any lightweight actions to take — a new preference
        to save, app feedback, or a credit-balance answer — and deterministic Python runs
        the side-effects. (Function calling was dropped here because combining it with
        forced-JSON output on flash-lite caused unstable tool-call loops.)
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

8.  **Booking Input Saga** — unstructured booking parser

    *   Parses pasted flight/hotel confirmations into structured JSON data.
    *   Stateful 2-turn saga: parse -> verify -> upsert to the active trip.

9.  **Mood Check-in & Journal Sagas** — trip lifecycle endpoints (Task 41)

    *   **MoodCheckinSaga** (listener, only while a trip is `LIVING`): captures
        a volunteered mood — free text or the dashboard's mood widget message —
        into `trips.live_state.last_mood` (deterministic fast-path for the
        widget, keyword-gated `flash-lite` for free text), and once per day, if
        none is logged, surfaces a soft mood prompt as a status nudge (never
        interrupts a question). The latest mood is folded into the
        TripAgent/PlannerAgent context so pacing and swap suggestions adapt to
        how the traveler feels.
    *   **JournalSaga** (`REMEMBERING` window, ≤30 days post-trip): offers at
        most one reflection prompt per day on a low-substance turn, and
        otherwise silently captures reflections (entry + highlights/regrets via
        `flash-lite`) into `trips.journal` while the companion answers. Never
        interrogates.

10. **Conversation Manager**

    *   Stores recent messages + compacted summary in Supabase `conversations` table.

11. **Offline LLM Judge**

    *   Samples a share of completed turns and scores reply quality on five dimensions (budget respect, conciseness, personalization subtlety, groundedness, helpfulness).
    *   Runs asynchronously as a fire-and-forget background thread to never block user turns.
    *   Emits `reply_judged` metrics to `analytics_events` for offline evaluation.

12. **Centralized Budget Policy**

    *   `core/budget_policy.py` enforces unified character caps and token limits across all models and agents.
    *   Provides standard profiles (`planner`, `trip`, `chat`, `advisor`, `judge`, `extractor`) to ensure responses fit within web and Telegram UI constraints without individual agents hardcoding limits.

#### Curiosity prompts (Task 42)

What keeps Aletheia from feeling like a TripAdvisor clone is that it sometimes
asks the kind of question a well-read, travel-loving friend would — *"more
'wander till I'm a little lost', or 'know roughly where I'm headed'?"* A small,
human-curated, source-cited library
(`backend/src/agentic_traveler/content/curiosity_prompts.yaml`, grounded in de
Botton, Iyer, Solnit, Steves, Seneca, Pearce, Potts, Chatwin, Macfarlane and
others — see `docs/travel_literature_notes.md`) is selected by a **pure-Python**
`CuriosityPromptInjector` (no LLM) and woven into exploratory / reflective
companion replies during `DREAMING` / `SHAPING` / `REMEMBERING`.

Because a deep question can fall flat *coming from an AI*, three guards counter
the "AI effect": (1) the prompt texts are concrete and low-effort (a light
either/or, answerable in a few words) — the literature lives in the entry's
rationale, not the wording the user sees; (2) the injector frames each prompt as
a strictly **optional aside** the model adds at the end of an already-useful
reply, answerable-or-ignorable, never repeated, dropped if it would feel
intrusive; (3) the more personal prompts only fire once the trip has a
destination (no cold-opening intimate questions), capped at once per day per
trip, and suppressed entirely for high-`structure_preference` planners. Disabled
in one flip via `CURIOSITY_INJECTOR_ENABLED=false`.

#### Advisory turns (Task 45)

The PlanningSaga doesn't just collect slots — for the **timeframe** it composes
an *advisory turn*: one `gemini-3.5-flash` call that answers any question the
traveler asked, offers one grounded insight, and **proposes** a value with
one-tap confirm chips (`[Set September] [Another time] [Skip]`). The insight is
grounded in a **destination brief** — cached "world facts" (best windows by the
weather/crowds/price triad, seasonal character, signature experiences, fit
hooks) captured once when a destination is first set, stored on
`trip.discovery.destination_brief`, never authoritative (a verify-with-official
-sources disclaimer applies). The composer's system prompt distils travel
frameworks (seasonality triad, push/pull, comfort-novelty, state-over-trait,
anticipation) so the advice feels like a knowledgeable friend, not a form.

Key behaviours:
- **Answer, don't march past** (the "September bug" fixed): a question asked
  while a slot is open is answered AND the open decision is re-presented in the
  same reply — never dropped. For the timeframe slot the composer does both;
  for chip slots the companion answers and the chip is re-attached.
- **Propose, then confirm** — proposed values are written ONLY on confirmation
  (tap or an affirmation like "yes"); a counter-proposal ("what about May?")
  re-evaluates and re-proposes instead of moving on. Values the traveller
  *states* decisively ("May, that's fixed") still write immediately via the
  extractor. Pending proposals persist on `trip.discovery.advisor`; a confirm
  tap is re-validated against them server-side before writing (trust-but-verify).
- **DNA-default chip lines** (zero LLM): chip questions lead with a
  personalization when the profile has signal ("Your last trips ran slow —
  same again?").
- Degrades cleanly: no brief → composer runs DNA-only; composer fails → the
  static slot question. The brief and composer are `@traceable`; metrics
  (`brief_captured`, `advisor_turn_composed`, `proposal_made/accepted/rejected`)
  feed the proposal-acceptance KPI.

#### Reading experience (Task 46)

A single canonical markdown profile now governs ALL agent output — chat, trip,
planner, advisor turn — and is the single source of truth for formatting rules:

- **`core/markdown_profile.py`** exposes two surfaces:
  - `CANONICAL_FORMATTING` — a shared instruction block imported by every agent's
    `_SYSTEM_PROMPT`, replacing the former per-agent Telegram-specific formatting
    sections. Agents now emit `**bold**`, `### headings`, `> blockquotes`, and
    `- lists` — the canonical forms that render correctly in both the web
    ReactMarkdown renderer and on Telegram after degradation.
  - `degrade_for_telegram(text)` — converts canonical Markdown → Telegram
    MarkdownV1: `**bold** → *bold*`, `### Title → *Title*`, `> quote → _quote_`,
    `- item → • item`, table rows flattened, code fences stripped (content kept).
    **Deterministic and idempotent** (running twice = running once). Wired in the
    channel layer (`telegram.py`) before `sanitize_telegram_markdown`, so it runs
    once per outbound Telegram message on both the real and mock senders.

- **Warm ivory web theme** — the light-theme CSS variables shift from plain white
  (`#ffffff`) to a warm ivory paper (`#faf8f3`) with a warm ink foreground
  (`#23201a`), warm card/muted/border tones, matching the reading feel of
  physical travel planning materials. The theme is applied **uniformly across
  every surface** — the dashboard (chat, trip library, trip detail, nav, map),
  the auth shell (login / sign-up / forgot / reset) and all marketing/legal
  pages. The components themselves were already token-driven, but the *shells*
  carried cold-mode literals that the token sweep couldn't reach: cold pastel
  `blue-50`/`purple-50` (and `#eef4ff`/`#f5f0ff`) ambient washes, neutral-grey
  grids, `rgba(0,0,0,…)` drop shadows, and a few hardcoded `slate-*` booking
  rows. On the dashboard this matters most through the frosted-glass cards,
  which sample the ambient wash — a cold ground tinted every panel cool. These
  now reuse the warm `.aletheia-card` shadow and the theme-aware `.grid-bg`,
  with every ambient wash mixing the blue→purple accents *into* the paper
  ground so light mode reads as ink on paper everywhere.

- **Bubble-less agent prose** — agent replies in the web chat no longer appear in
  a glass-card bubble. They render full-width with a compact attribution row
  (6px gradient dot + muted timestamp) and `1.65` line-height reading typography.
  User messages keep the gradient-filled bubble.

- **ReactMarkdown component normalisation** — all heading depths (h1–h6) are
  remapped to `h3` (styled at `1em/600` weight); tables are flattened to plain
  text spans; images and `<img>` tags return null; code/pre blocks use plain
  inherited font. This guarantees that forbidden elements never render even if
  the model emits them.

- **Desktop expand mode** — an expand toggle (⤢/⤡) in the ChatPanel header
  (hidden on mobile, `lg:grid` on desktop) overlays the chat as a full-width
  pane with a 720px reading column and hides the map/trip panels. Esc key
  collapses it. Uses an `is-solid` card variant — no `backdrop-filter` cost
  over the map background.

#### Real-time architecture (Task 37)

Three composable layers give the web a live feel, all multiplexed through the
task-35 `EventEmitter` (phases `status` / `delta` / `metric`):

*   **Realtime subscriptions.** A Postgres trigger `touch_trip_updated_at` bumps
    `trips.updated_at` on any child-row write (`trip_destinations`,
    `trip_bookings`, `trip_days`, `trip_day_blocks`, `trip_checklist`), so the
    frontend reflects agent-driven trip mutations through a **single**
    subscription on the parent `trips` row (free-tier discipline: ≤1 WebSocket
    per tab).
*   **SSE streaming.** `POST /chat/stream` returns `text/event-stream` and emits
    `status` events (intermediate progress), `delta` events (the reply), and a
    final `done` carrying the persisted `message_id` (plus the full `text` as a
    reconciliation fallback). The agent reply is written to `messages` **before**
    streaming completes, so a dropped connection still recovers the reply via
    Realtime (de-duplicated by `message_id`). Delta strategy depends on the turn:
    a **tool-less** turn streams **token-by-token** from Gemini
    `generate_content_stream` (fastest first token); a **tool-capable** turn runs
    one reliable **blocking** generation (on Vertex, streaming + automatic
    function calling drops the post-tool synthesis) and then **paces** the
    finished reply to the client as `delta` chunks so it still types in smoothly —
    one generation, no double tool cost. The non-streaming `POST /chat/send`
    stays for compatibility.
*   **Status events.** Rendered from a static `event_text_registry` (no LLM):
    "Understanding what you're asking… / Picking up your trip… / Checking the
    weather… / Searching the web… / Thinking…". Tool status is emitted
    the moment a tool runs, via a contextvar the tool functions read (so it works
    on both web and Telegram). On Telegram, the first real status becomes the
    placeholder message (no generic "Thinking…"); later statuses edit it
    (throttled ≥1 s so each is readable), then one final edit to the complete
    reply — never a partial reply.

On the web, the dashboard chat consumes this via `useChatStream` (renders the
intermediary status lines — no generic typing dots — then the streamed reply,
pacing each status ≥1 s and letting the reply preempt pending statuses),
`useChatRealtime` (merges out-of-band rows
— a recovered turn or a Telegram/other-tab message — de-duplicated against
SSE-finalized ids), and `useTripRealtime` (one parent subscription → refetches
the assembled trip on any change, for the trip panel).

#### Trip Detail Panel (live data, task 40)

The dashboard's trip view is fully live (no mock data on the runtime path):

- **`useTripList`** queries the user's trips through the RLS-protected browser
  client (so a user only ever sees their own — never another user's), maps
  each to a library-card summary, and picks a default focus (an `active` trip,
  else the most recently updated).
- **`useTrip(tripId)`** wraps `useTripRealtime` and runs the raw assembled trip
  (parent JSONB columns + the five child collections) through **`trip-adapter`**
  into the `Trip` + `TripDay[]` view model the panel components consume. A 60s
  poll backstops a dropped Realtime socket.
- **`TripDetailPanel`** renders the ten-section stack (vision banner, header,
  country-intel strip, safety banner, itinerary, logistics rail, budget bar,
  scratchpad, live-state card, journal) under a **progressive-disclosure law**:
  every section is gated on having data (or, for a few, the lifecycle phase),
  so empty sections vanish rather than showing placeholders. The phase is
  derived from `trips.status` + `saga_state`.
- Mutations stay chat-first: saved-idea chips, the mood check-in, journal
  prompts, and "plan a trip" CTAs send a message into the chat thread rather
  than writing directly, so the assistant (and its sagas) owns trip state.
- The Kyoto map is a visual placeholder pending the real MapLibre map (task 49);
  the hand-coded Kyoto trip now lives in `lib/dashboard-fixtures.ts` (tests +
  the map placeholder only), not the runtime data path.

#### Current Model Stack

The system uses a tiered model approach to balance reasoning quality and cost:

| Agent | Model | Rationale |
| :--- | :--- | :--- |
| **Router** | `gemini-3.1-flash-lite` | Ultra-fast, low-cost classification. |
| **Chat** | `gemini-3.1-flash-lite` | Responsive conversational agent. |
| **Search** | `gemini-3.1-flash-lite` | Lightweight grounding proxy. |
| **Profile** | `gemini-3.1-flash-lite` | Renders structured Traveler DNA from Tally onboarding. |
| **Trip** | `gemini-3.5-flash` | Richer reasoning for destination discovery. |
| **Planner** | `gemini-3.5-flash` | Multi-day coherence and structured itinerary building. |

The backend is stateless: each request reconstructs context from Supabase and tools, then responds directly to Telegram.

### Third-party data processors

| Processor | Region | What we send | Retention |
|---|---|---|---|
| Google Vertex AI / Gemini | configurable, EU-pinnable | chat prompts + replies | per Google Gemini terms |
| Supabase | eu-central-1 | user rows, trips, messages | until user deletes account |
| Resend | EU | transactional emails | per Resend retention |
| Telegram | global | message text on the Telegram channel | per Telegram terms |
| LangSmith (LangChain Inc.) | EU (Frankfurt) — `eu.api.smith.langchain.com` | chat prompts + replies + tool calls, tagged with an HMAC-hashed user id only (no email, name, phone, telegram handle, or JWT) | 14-day rolling (free tier) |

Kill switch for LangSmith: set `LANGSMITH_TRACING=false` in the runtime env and redeploy; the app continues to function with zero outbound traffic to LangSmith.

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
*   **Global cost capture (task 51)**: every LLM call funnels through
    `client_factory.gemini_generate` / `gemini_generate_stream`, which append
    token usage (and grounded-search costs) to a per-turn `ContextVar`
    accumulator — so nested tools (e.g. the booking parser) are billed
    correctly without threading usage records through return signatures.
    System-paid calls (conversation compaction) run under
    `suppress_usage_capture()` and never enter the user's deduction; the
    self-billing country-intel background fetch runs outside the request
    context and is likewise unaffected.
*   **Failure visibility**: When an agent produces no usable response (empty
    output or an `ERROR` action), the turn is not charged, a `turn_failed`
    metric is emitted, and the LangSmith run is flagged as errored (it otherwise
    records as successful, since the user still gets a graceful fallback rather
    than an exception).

### The Build

Tools and technologies:

*   **Supabase (PostgreSQL)**
    
    *   Relational storage for users, trips, and feedback
        
    *   JSONB columns for flexible agentic state (profiles, preferences)
        
    *   RPC functions for atomic credit deduction and concurrent safety
        
*   **Web frontend**

    *   Next.js 16 / React 19 / TypeScript / Tailwind CSS v4 on Vercel
    *   Supabase Auth with Google OAuth and email/password (PKCE flow, Cloudflare Turnstile CAPTCHA)
    *   Dashboard: phase-aware live trip view + AI chat panel (live via Realtime); map canvas placeholder pending the real map (task 49)

*   **GCP**
    
    *   Cloud Run for the stateless agent service (FastAPI + Python)
        
    *   Secret Manager for API keys and webhook tokens
        
*   **Backend & agents**
    
    *   Python with the Google GenAI SDK (function calling) to define the agent flow
        
    *   Small, specialized agents:
        
        *   Orchestrator, Router, Chat, Trip, Planner, Search, Profile, Conversation Manager
            
    *   **Saga dispatcher:** after the Router classifies intent, a
        deterministic (no-LLM) `SagaDispatcher` selects the owner *saga* for the
        turn — `PlanningSaga`, `DiscoverySaga`, `ChatSaga`, or `OffTopicSaga`
        (in `orchestrator/sagas/`). The PlanningSaga is a slot-filling skill: it
        resolves the active trip (`resolve_active_trip` over cheap summaries,
        then hydrates one), derives the trip's phase from data
        (`derive_saga_state_local`, mirroring the Postgres `derive_saga_state`),
        and collects the missing essentials one question per turn — categorical
        slots (travelers/pace/structure/budget) as **multiple-choice**
        (`SlotRequest.choices`), free-form slots (destination, timeframe) parsed
        by a small extractor — writing structured patches back to the trip via
        `TripRepository`. The user's message dictates which
        engine answers and which trip is in focus. The Router emits a
        `trip_directive` (`continue` / `new` / `unspecified`): `new` sets the
        current trip aside and starts a fresh one ("Putting **Japan** on hold —
        let's start fresh. Where to?"); a generic plan request on a *completed*
        trip (`unspecified`) is **confirmed** rather than silently regenerated
        ("We're partway through **Japan** — keep refining, or start a new trip?").
        The heavy itinerary **PlannerAgent** runs only when the user is actually
        continuing/refining (`continue`, or a new planning fact this turn); a
        completed trip plus a casual question drifts to the lighter
        **TripAgent** — the trip stays in focus without being force-fed a fresh
        itinerary. State is data, never stored on the saga (the confirmation has
        no persisted flag — the next turn's directive decides), so the shape maps
        1:1 to a future LangGraph migration. Each saga emits
        `saga_entered` / `saga_exited` /
        `slot_filled` metrics by default.

    *   **Tappable slot prompts (web + Telegram):** categorical questions render
        as one self-contained card — the question and its option chips in a single
        agent bubble — on the web chat, and as an inline keyboard on Telegram.
        Most slots are single-select (one tap fires); **travelers** is
        multi-select (e.g. partner + family) with checkboxes, a Confirm button,
        and a mutually-exclusive **Skip**. Tapping a
        choice applies the value **deterministically** — no extraction LLM call:
        the answer rides a structured `selection` (`{slot, values}`) on
        `/chat/send` (or a `slot|<slot>|<value>` `callback_query` on Telegram),
        is re-validated against the slot's legal options server-side
        (trust-but-verify), and is merged into `trips.preferences` via a shared
        `slot_selection_to_side_effect` mapper. A **Skip** option writes a `skip`
        sentinel so the slot is never re-asked. Typing the answer instead still
        works (the free-text extractor is the graceful fallback), and a
        `slot_selected {slot, value, channel}` metric is emitted on every tap.
        The task-44 direction confirmation renders as two **quick-reply** chips
        (web) whose taps send a normal message the Router re-classifies into a
        `trip_directive` — keeping the confirmation stateless.
            
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
    
    *   Input: user profile from Supabase (`user_profiles` table), trip constraints from Telegram chat (rough dates or time window, duration, budget band, desired vibe, energy, willingness for discomfort).
        
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
        
        *   user_profile from Supabase (`user_profiles` table) as long term personalization.
            
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

    *   **Metrics pipeline (Task 35):** `analytics_events` (append-only event log, 7-day rolling window) + `metrics_daily` (daily rollup) + `metrics_rollup_state` (idempotency tracker). A `pg_cron` job (`metrics_daily_rollup`, 03:00 UTC daily) aggregates yesterday's events into `metrics_daily` and deletes events older than 7 days. Six canonical SQL views answer fleet-level queries: `vw_growth_funnel_30d`, `vw_saga_dropoff`, `vw_data_growth_per_user`, `vw_errors_24h`, `vw_capacity_today`, `vw_cost_per_user_30d`. **One-time setup:** enable the `pg_cron` extension (Supabase Dashboard → Database → Extensions → pg_cron), apply the migration, then run `SELECT public.run_metrics_rollup()` once to seed the pipeline. Agent code emits events via `EventEmitter.emit("metric", {...})`; the orchestrator batches and flushes them at end of turn.

    *   `link_tokens`: short-lived single-use tokens for `telegram_link` (10-minute TTL) and `tally_submission` (7-day TTL) flows.

    *   `off_topic_state`, `waitlist`: off-topic restriction state and landing-page sign-ups.

    *   **Trip data model:** `trips` (parent row with JSONB sections: `discovery`, `travelers`, `preferences`, `country_intel`, `budget`, `live_state`, `scratchpad`, `journal`, `cover`) + 5 child tables: `trip_destinations`, `trip_bookings`, `trip_days`, `trip_day_blocks`, `trip_checklist`. Postgres function `derive_saga_state(trip_id)` returns the canonical saga phase (DREAMING | SHAPING | ANCHORING | DETAILING | READY_TO_GO | LIVING | REMEMBERING) from row content — `trips.saga_state` is a cache only. `vw_trips_growth` provides weekly trip-creation counts by status (free-tier capacity KPI). All tables RLS-enabled; frontend subscribes to the parent row; child writes bump `updated_at` (auto-trigger in task 37). Python `TripRepository` in `backend/src/agentic_traveler/tools/trip_repo.py`.

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
- **State-Driven Multi-Agent Orchestrator**: The backend parses incoming messages and determines the correct saga (e.g. Planning, Discovery, Chat, Off-Topic) based on user intent and current trip context.
- **Flexible & Natural Interactions**: The bot adapts to how the user plans. Users can set permanent global rules (e.g., "Never ask me about my budget") via the *hard overrides* system, or gracefully bypass any specific question on the fly by simply telling the bot to skip it or that they will handle it themselves.
- **Real-time Context Awareness**: Weather-aware suggestions and adaptive itineraries based on current mood and energy.
- **Safety & Moderation**: Integrated off-topic guard and multi-layer webhook security.
- **Usage & Metrics Tracking**: Real-time per-user LLM usage and estimated credit cost tracking (where `1 credit = 1 eurocent`) inside the Supabase `usage_tracking` table, alongside weekly global analytics rollups flushed to the `analytics_weekly` table.
- **Latency & Token Instrumentation** (Task 48): Every turn emits two always-on analytics events: `turn_stage_timings` (router_ms, extractor_ms, agent_ms, persist_ms, total_ms, ttft_ms) and per-LLM-call `llm_call_usage` (call_type, model, input/output/thinking tokens, latency_ms). Queryable via `vw_turn_latency_p50_p95` and `vw_llm_cost_by_call_type` views. Router and slot-extractor run in parallel (saving ~200–400 ms per planning turn). All conversational call types use LOW thinking budget; only `itinerary` uses MEDIUM.
- **Profile & Preference Sync** — Extracts hard overrides (e.g. "I'm vegan") and persists them via `ProfileAgent`.
- **Country Intel Saga** — Background fetch of up-to-date entry rules, safety, health, and money facts when a destination is confirmed or requested. Top-ups and promo-code redemption live on the **web** (under Account Settings) — the previous Telegram `/promo <CODE>` command has been removed. When a user runs out of credits, both Telegram and web chat surface a message pointing them back to the web app to redeem or top up.
- **Interactive CLI & Webhook**: Support for both local development (CLI) and production Telegram bot interactions.
- **Feedback Loop**: Integrated tool for capturing user sentiment to refine future suggestions.

## Project Structure

The project is structured as a monorepo containing both the backend agent service and the Next.js web application:

```text
agentic-traveler/
├── backend/                    # Python FastAPI + Google GenAI service
│   ├── src/agentic_traveler/   # Backend core package (modular, layered architecture)
│   │   ├── analytics/          # Metrics buffering + weekly flush to Supabase
│   │   ├── core/               # Foundational logic (sanitization, shared utilities)
│   │   ├── economy/            # User credits & promo code management
│   │   ├── guards/             # Security layers (off-topic guard)
│   │   ├── interfaces/         # Entry points (CLI, Webhook handler)
│   │   ├── orchestrator/       # Multi-agent system (Orchestrator, Chat, Trip, Planner, Profile, Search agents)
│   │   └── tools/              # External tool implementations (Supabase DB client, Weather, Search)
│   ├── tests/                  # Unit and integration tests
│   └── scripts/                # Helper utilities (webhooks, alerts configuration)
├── frontend/                   # Next.js 16 / React 19 web application
│   ├── src/
│   │   ├── app/                # Next.js App Router (dashboard, auth, chat UI)
│   │   ├── components/         # Shared React components
│   │   └── lib/                # Database clients & utility functions
│   └── package.json            # Frontend dependency manager
├── supabase/                   # Supabase schema definitions, RLS policies, and database hooks
└── specs/                      # Markdown specifications for the project features and tasks
```

## Setup

### Backend Setup

#### 1. Create and activate the virtual environment

All python virtual environment setup, dependencies, and execution live in the `backend/` directory of the repository:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate
```

#### 2. Install dependencies

Install pinned runtime and development dependencies inside the activated environment:

```powershell
pip install -r requirements.txt
pip install -e .
```

#### 3. Environment variables

Create a `.env` file in the `backend/` directory:

```env
# Google GenAI / Vertex AI settings
GOOGLE_API_KEY=your-gemini-api-key
GEMINI_REGION=global
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/application_default_credentials.json

# Database settings
SUPABASE_URL=your-supabase-url
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret

# Economy & Channels
DEFAULT_USER_CREDITS=200
LINK_TOKEN_SECRET=your-token-signing-secret
TALLY_WEBHOOK_TOKEN=your-tally-webhook-bearer-token
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_SECRET_TOKEN=your-telegram-webhook-secret-token

# Observability (Optional)
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=your-langsmith-project-name
```

- **`GOOGLE_API_KEY`** — required for Developer API access (used for all Gemini LLM calls).
- **`GEMINI_REGION` & `GOOGLE_PROJECT_ID`** — regional settings if routing Vertex AI API calls.
- **`GOOGLE_APPLICATION_CREDENTIALS`** — path to GCP credentials JSON if utilizing Vertex AI.
- **`SUPABASE_URL` & `SUPABASE_SERVICE_KEY`** — required to connect to the database (service role key is needed to bypass Row Level Security for administration and billing).
- **`LINK_TOKEN_SECRET`** — secret key for signing secure deep-link tokens.

### Frontend Setup

#### 1. Install dependencies

Navigate to the `frontend/` directory and install the required npm packages:

```powershell
cd frontend
npm install
```

#### 2. Environment variables

Create a `.env.local` file in the `frontend/` directory:

```env
# Exposed to browser
NEXT_PUBLIC_SUPABASE_URL=your-supabase-url
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=your-supabase-anon-key
# NEXT_PUBLIC_TURNSTILE_SITE_KEY=your-cloudflare-turnstile-key

# Server-side secrets
RESEND_API_KEY=your-resend-api-key
RESEND_FROM_ADDRESS=noreply@yourdomain.com
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
BACKEND_URL=http://127.0.0.1:8080
LINK_TOKEN_SECRET=your-token-signing-secret
DEFAULT_USER_CREDITS=200
TELEGRAM_BOT_USERNAME=@YourTelegramBot
TALLY_FORM_URL=your-tally-form-endpoint
```

- **`NEXT_PUBLIC_SUPABASE_URL` & `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`** — public database URL and anonymous key for frontend Supabase SDK initialization.
- **`SUPABASE_SERVICE_ROLE_KEY`** — service role key allowing backend API operations to bypass RLS.
- **`BACKEND_URL`** — local or production URL of the Python FastAPI orchestrator backend.

---

## Usage

### Backend: Interactive CLI

Chat with the orchestrator locally by impersonating an existing Supabase user:

```powershell
.\backend\.venv\Scripts\python -m agentic_traveler.interfaces.cli
```

This lists users in Supabase, lets you pick one, then opens an interactive chat loop. You can also pass a Telegram ID directly:

```powershell
.\backend\.venv\Scripts\python -m agentic_traveler.interfaces.cli --telegram-id 12345
```

### Backend: Local FastAPI Server

Start the local Python backend endpoint (runs by default on port `8080`):

```powershell
# Disables Telegram IP whitelist for local development
$env:SKIP_IP_CHECK="1"
.\backend\.venv\Scripts\uvicorn agentic_traveler.interfaces.main:app --reload --port 8080
```

### Frontend: Next.js Web App

Start the local development server for the user dashboard:

```powershell
cd frontend
npm run dev
```

This runs the next dev server, making the visual spatial dashboard available at `http://localhost:3000`.

---

## Testing

### Backend: Unit tests

Unit tests use mocked Supabase and LLM — no credentials needed:

```powershell
.\backend\.venv\Scripts\python -m pytest backend/tests/ --ignore=backend/tests/integration -v
```

### Backend: Integration tests

Integration tests use the **real Gemini API** and **real Supabase** database. They require valid credentials configured in `backend/.env`.

```powershell
$env:_INTEGRATION_TESTS="1"; .\backend\.venv\Scripts\python -m pytest backend/tests/ -m integration -v
```

### Backend: Run all tests together

```powershell
$env:_INTEGRATION_TESTS="1"; .\backend\.venv\Scripts\python -m pytest backend/tests/ -v
```

### Frontend: Validation & Linting

Validate that the frontend builds and lints cleanly without Next.js errors or type mismatches:

```powershell
cd frontend

# Run linting
npm run lint

# Build production bundle
npm run build
```

---

## Deployment

- **Backend**: Deployed to Google Cloud Run. Detailed guide at [DEPLOYMENT.md](backend/DEPLOYMENT.md).
- **Frontend**: Deployed to Vercel (configured with automatic branch preview builds and production deploys).






