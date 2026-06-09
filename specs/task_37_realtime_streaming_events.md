# Task 37 — Realtime subscriptions + SSE streaming + status events

> Spec lineage: `specs/proposal_trip_model_and_planning_saga.md` §11, §10.6.
> Depends on tasks 34, 35, 36 (schema, EventEmitter, saga interface in place).

## 1. Problem Statement

The proposal commits to three composable real-time UX layers: (1) Supabase
Realtime subscriptions so the dashboard reflects agent-driven trip mutations
without a refresh; (2) Server-Sent Events streaming the final agent reply
token-by-token to the web; (3) intermediate status events ("Understanding
your question… checking the weather… composing reply…") so users see what
the agent is doing during a 3–5 second turn. All three flow through the
same `EventEmitter` from task 35, multiplexed by phase
(`status` / `delta` / `metric`). This task lands the Postgres touch
triggers that make per-trip child writes reflect through a single parent
subscription, the FastAPI `/chat/stream` SSE endpoint, the Gemini
streaming switch on the heavy agents, the message-edit pattern for
Telegram (deliberately simpler than web — status only, then full final
message), and the SSE/Realtime de-duplication that prevents the message
from rendering twice in the web chat.

## 2. Goals & Non-Goals

### Goals

- When the agent writes to a trip (or any of its child rows), every open
  web client on that trip sees the change within ~1 second, without a
  refresh.
- When the user sends a chat message via the web, the reply streams
  word-by-word into the chat bubble within ~500 ms of the first delta.
- During the same web turn, the user sees status updates ("Looking up
  Iceland visa rules…") before the reply starts streaming.
- On Telegram, the user sees the current status text as the bot's
  placeholder message, then **one** final edit to the complete reply
  (no half-message intermediate state — per the user's UX call).
- A turn whose SSE connection drops mid-stream still ends with the user
  seeing the final message (via the Realtime fallback), exactly once,
  with no flicker.
- Free-tier discipline: at most one WebSocket per active dashboard tab,
  ≤4 multiplexed channels (`messages`, `trips`, `user_profiles`, and one
  reserve).

### Non-Goals

- The `credits` table in realtime — explicitly NOT subscribed (per user
  decision §11.2). One-shot SELECT on dropdown / settings open.
- A user-facing "what is the bot doing" timeline UI beyond a single rotating
  status line.
- Backpressure controls — the SSE stream is unidirectional and we accept
  burst traffic.

## 3. Acceptance Criteria

AC-1. A Postgres trigger `touch_trip_updated_at` bumps `trips.updated_at`
  on INSERT/UPDATE/DELETE of any of `trip_destinations`, `trip_bookings`,
  `trip_days`, `trip_day_blocks`, `trip_checklist`. Verified by writing a
  child row and reading the parent's `updated_at`.

AC-2. A frontend `useTripRealtime(tripId)` hook subscribes to
  `postgres_changes` events on `trips` filtered by `id`, refetches affected
  child collections on UPDATE, and exposes the assembled `Trip` shape to
  React. **One** WebSocket per active tab, verified via `chrome://net-export`.

AC-3. A `useChatRealtime(threadId)` hook subscribes to `postgres_changes`
  on `messages` filtered by `thread_id`, and merges incoming rows into the
  chat state. Rows whose `id` matches one already finalized from the SSE
  stream are dropped (de-duplication, AC-6).

AC-4. `POST /chat/stream` returns `Content-Type: text/event-stream` and
  emits at least these event types over the connection: `status`, `delta`,
  `done`. The `done` event payload includes `message_id`.

AC-5. The heavy agents (`TripAgent`, `PlannerAgent`, `ChatAgent`) use
  Gemini `generate_content_stream` and yield deltas through a per-turn
  `asyncio.Queue` that the SSE endpoint drains.

AC-6. The web chat reducer deduplicates: a `messages` row arriving via
  Realtime is dropped if a `done` event already arrived for the same
  `message_id`. If the SSE connection drops before `done`, the Realtime
  row IS rendered (recovery path).

AC-7. The Telegram bot, on a streaming turn, sends a placeholder message
  ("Working on it…"), edits to the current status text on each `status`
  event (debounced ≥500 ms), and **once** at the end edits to the full
  final reply text. **No** mid-stream delta edits.

AC-8. The orchestrator wires concrete sinks into the `EventEmitter`:
  `on_status` → the web SSE writer or the Telegram editor; `on_delta` →
  the web SSE writer only (Telegram drops); `metric` continues to
  `analytics_events` (task 35).

AC-9. A streamed turn against `/chat/stream` produces exactly five
  expected SSE events in the happy path: `status:router`, `status:saga_selected`,
  `status:tool` (if a tool ran), `delta×N`, `done`.

## 4. Files & Modules Touched

```
supabase/schema_public.sql                                            [modify]
backend/src/agentic_traveler/interfaces/routers/chat.py               [modify — add /stream endpoint]
backend/src/agentic_traveler/orchestrator/agent.py                    [modify — async streaming dispatch]
backend/src/agentic_traveler/orchestrator/event_emitter.py            [modify — async-friendly]
backend/src/agentic_traveler/orchestrator/trip_agent.py               [modify — stream variant]
backend/src/agentic_traveler/orchestrator/planner_agent.py            [modify — stream variant]
backend/src/agentic_traveler/orchestrator/chat_agent.py               [modify — stream variant]
backend/src/agentic_traveler/orchestrator/event_text_registry.py      [create]
backend/src/agentic_traveler/interfaces/telegram_handler.py           [modify — placeholder-edit pattern]
frontend/src/hooks/useTripRealtime.ts                                 [create]
frontend/src/hooks/useChatRealtime.ts                                 [create]
frontend/src/hooks/useChatStream.ts                                   [create]
frontend/src/components/dashboard/ChatPanel.tsx                       [modify — wire streaming]
backend/tests/test_chat_stream.py                                     [create]
backend/tests/test_event_emitter_sinks.py                             [create]
README.md                                                             [modify]
```

## 5. Constraints

- Must not break the existing `POST /chat` non-streaming endpoint — it
  stays for backward compatibility with any client that doesn't speak SSE.
- Telegram MUST NOT receive partial replies (per user UX decision). Only
  status edits and one final edit.
- The SSE stream MUST close cleanly on `done`, not be left dangling.
- A failed SSE connection MUST NOT prevent the final reply from being
  persisted to `messages`.
- The touch trigger MUST NOT cause recursive updates (a parent's own
  UPDATE does not re-fire — we only touch from child triggers, and the
  parent's `updated_at` is a column UPDATE, not an INSERT or other-column
  UPDATE).
- All hooks must clean up subscriptions on unmount to avoid leaking sockets.

## 6. Edge Cases

- **User sends two messages in rapid succession on the web** → two
  parallel SSE turns. Frontend handles two concurrent streams (each in
  its own AbortController).
- **Cloud Run instance restarts mid-stream** → SSE connection drops;
  client falls back to Realtime push of the persisted message. User sees
  the final reply, ~1–2 s late, never sees half.
- **Telegram rate-limit hit on edit** → debounce queue holds events;
  the final edit still occurs.
- **No realtime activity for 2 hours** → Supabase Realtime sends
  heartbeat; connection stays. Browser tab in background may close socket
  — hook reconnects on visibility change.
- **Trip in another tab updated** → that tab's hook receives the parent
  UPDATE, refetches; only the affected child collection is fetched, not
  the whole tree.
- **User sends a streaming request but the model raises mid-stream** →
  emit `status:error` with a short user-visible message; close stream
  cleanly; do not write a half-message to `messages`.
- **Race: SSE `done` arrives before the Realtime push** → reducer marks
  the message as finalized; Realtime push for same `message_id` dropped.
- **Race: Realtime push arrives before SSE `done`** → reducer renders
  the full message immediately; subsequent SSE deltas are ignored;
  `done` event is treated as confirmation.

## 7. Implementation Plan

### Step 1 — Touch trigger

```sql
CREATE OR REPLACE FUNCTION public.touch_trip_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.trips
  SET updated_at = now()
  WHERE id = COALESCE(NEW.trip_id, OLD.trip_id);
  RETURN COALESCE(NEW, OLD);
END;
$$;

DO $$
DECLARE child_table text;
BEGIN
  FOR child_table IN
    SELECT unnest(ARRAY['trip_destinations','trip_bookings','trip_days',
                        'trip_day_blocks','trip_checklist'])
  LOOP
    EXECUTE format($f$
      DROP TRIGGER IF EXISTS touch_on_%I ON public.%I;
      CREATE TRIGGER touch_on_%I
        AFTER INSERT OR UPDATE OR DELETE ON public.%I
        FOR EACH ROW EXECUTE FUNCTION public.touch_trip_updated_at();
    $f$, child_table, child_table, child_table, child_table);
  END LOOP;
END $$;
```

**Verify:** `INSERT INTO trip_bookings ...` then `SELECT updated_at FROM
trips WHERE id = ...` shows a recent timestamp.

### Step 2 — Event-text registry

`backend/src/agentic_traveler/orchestrator/event_text_registry.py`:

```python
"""Static map: (phase, key) -> user-visible status string. Used by the
orchestrator to render status events without calling an LLM.
"""

STATUS_TEXT = {
    ("router", None):              "Understanding what you're asking…",
    ("saga_selected", "PlanningSaga"):  "Picking up your trip…",
    ("saga_selected", "DiscoverySaga"): "Searching for places…",
    ("saga_selected", "CountryIntelSaga"): "Looking up the destination…",
    ("saga_selected", "BookingInputSaga"): "Reading your booking…",
    ("saga_selected", "ChatSaga"): None,   # silent
    ("tool", "check_weather"):     "Checking the weather…",
    ("tool", "search_web"):        "Searching the web…",
    ("tool", "country_intel_fetch"): "Looking up entry rules…",
    ("composing", None):           "Writing the reply…",
}

def text_for(phase: str, key: str | None) -> str | None:
    return STATUS_TEXT.get((phase, key), STATUS_TEXT.get((phase, None)))
```

### Step 3 — Streaming agent variants

For each of `TripAgent`, `PlannerAgent`, `ChatAgent`: add a
`process_request_stream(...)` async generator that wraps
`client.models.generate_content_stream(...)` and yields `(delta_text,
final_metadata)` tuples. Keep the existing non-streaming `process_request`
unchanged for the Telegram path and tests.

```python
async def process_request_stream(self, ...):
    stream = await asyncio.to_thread(
        self._client.models.generate_content_stream, ...
    )
    final = []
    async for chunk in self._iter_chunks(stream):
        text = chunk.text or ""
        if text:
            final.append(text)
            yield ("delta", text)
    yield ("done", {"text": "".join(final), "raw": stream.last})
```

### Step 4 — `/chat/stream` SSE endpoint

```python
# interfaces/routers/chat.py
from fastapi.responses import StreamingResponse
from fastapi import APIRouter
import asyncio, json

router = APIRouter()

@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, user_id: str = Depends(authed_user)):
    queue: asyncio.Queue = asyncio.Queue()

    async def driver():
        try:
            await orchestrator.process_streaming(user_id, payload.text, queue)
        except Exception:
            await queue.put(("status", {"phase": "error", "text": "Something glitched."}))
        await queue.put(("done", {}))

    asyncio.create_task(driver())

    async def gen():
        while True:
            phase, data = await queue.get()
            yield f"event: {phase}\ndata: {json.dumps(data)}\n\n"
            if phase == "done":
                break

    return StreamingResponse(gen(), media_type="text/event-stream")
```

### Step 5 — Orchestrator streaming variant

Add `process_streaming(user_id, text, queue)` to the orchestrator:

- Build the EventEmitter with `on_status = lambda d: queue.put_nowait(("status", d))`
  and `on_delta = lambda d: queue.put_nowait(("delta", d))`.
- Run the saga (owner + listeners) on a background task.
- When the owner's text is built (or its stream completes), persist
  the `messages` row, emit `done` with `{message_id}` to the queue.

### Step 6 — Frontend hooks

`useTripRealtime(tripId)`:

```ts
export function useTripRealtime(tripId: string) {
  const [trip, setTrip] = useState<Trip | null>(null);
  useEffect(() => {
    if (!tripId) return;
    refetchTrip(tripId).then(setTrip);
    const ch = supabase.channel(`trip:${tripId}`)
      .on("postgres_changes",
          { event: "UPDATE", schema: "public", table: "trips",
            filter: `id=eq.${tripId}` },
          () => refetchTrip(tripId).then(setTrip))
      .subscribe();
    return () => { supabase.removeChannel(ch); };
  }, [tripId]);
  return trip;
}
```

`useChatRealtime(threadId)` similar pattern on `messages`.

`useChatStream`:

```ts
export function useChatStream(threadId: string) {
  // returns: { send(text), pending, current } where:
  //   pending = "router" | "saga_selected:Planning" | "tool:weather" | "composing" | null
  //   current = string (incremental delta-accumulator)
  // on receiving 'done', the hook marks the message_id as finalized in a Set
  // that useChatRealtime checks before applying inserts.
}
```

A small `FinalizedMessageIds` context bridges the two hooks.

### Step 7 — Telegram handler

In `telegram_handler.py`, when handling a webhook update for a chat
message:

1. Send placeholder via `sendMessage` → save `placeholder_id`.
2. Hand the `EventEmitter` an `on_status` that calls
   `editMessageText(placeholder_id, status_text)` debounced ≥500 ms.
3. `on_delta` is a no-op for Telegram.
4. When the orchestrator's `done` arrives, call
   `editMessageText(placeholder_id, final_text)` once.

### Step 8 — Wire the orchestrator's `events` sinks

`OrchestratorAgent.process_streaming` constructs the `EventEmitter` with
the right sinks for the channel (web vs Telegram). The non-streaming
`process_request_for_user` and `process_request` continue to work — they
just pass `on_status=None, on_delta=None`, so emit-status is a no-op
and only `metric` writes happen.

### Step 9 — Tests

`test_chat_stream.py`: spin up FastAPI TestClient, hit `/chat/stream`,
collect SSE events, assert the expected order.

`test_event_emitter_sinks.py`: verify each phase routes to the right
sink; `metric` is always batched; `status`/`delta` failures are caught
and don't break the turn.

## 8. Testing Plan

- **Unit:** emitter routing, event-text-registry lookups, dedup logic
  in the chat reducer.
- **Integration (`-m integration`):** real SSE turn against the
  dev backend; assert latency-to-first-delta < 2 s.
- **Manual desktop:** Chrome DevTools → Network → EventStream view shows
  the expected event timeline. Trip detail panel updates within 1 s of
  a backend trip mutation (use `curl` to mutate via TripRepository).
- **Manual mobile:** Safari iOS, dashboard responsive, chat panel
  receives streamed deltas smoothly.
- **Manual Telegram:** send a chat → placeholder appears → status text
  updates → final message replaces placeholder. **Never** a half-reply.

Sample SSE wire output (happy path):

```
event: status
data: {"phase":"router","text":"Understanding what you're asking…"}

event: status
data: {"phase":"saga_selected","saga":"PlanningSaga","text":"Picking up your trip…"}

event: status
data: {"phase":"tool","tool":"check_weather","text":"Checking the weather…"}

event: delta
data: {"text":"Iceland in late January is "}

event: delta
data: {"text":"magical but bracing — "}

event: done
data: {"message_id":9912,"latency_ms":4120,"credits_spent":4}
```

## 9. Conditional Sections

### 9.1 Data Model & RLS

Touch trigger function created; no schema changes; RLS unaffected.
The trigger runs as `SECURITY DEFINER` (function defaults are fine —
the `UPDATE` it does is against the same row's owner).

### 9.2 LLM Considerations

- Switching to `generate_content_stream` does not change token costs.
- The status-text registry is **not** an LLM call — pure Python.
- The orchestrator does not invoke any extra LLM for streaming.

### 9.3 Observability

- Each `status` and `delta` event is also emitted as a `metric` event
  (sampled to avoid bloat: `status` 100% in dev, 10% in prod; `delta`
  never — too high cardinality).
- New metric: `sse_connection_dropped` when the client disconnects
  mid-stream.

### 9.4 Rollback Plan

- Frontend: remove the `useChatStream` hook; chat panel reverts to using
  the existing non-streaming `POST /chat`.
- Backend: `/chat/stream` is additive; leave deployed but unused if
  needed.
- Touch trigger: `DROP TRIGGER touch_on_<table>` per child table; `DROP
  FUNCTION touch_trip_updated_at`.

## 10. Findings & Follow-ups

### 10.1 Improvements observed (not done in this task)

- **Status display pacing is enforced client-side (phase 2).** The "show each
  status ≥1 s, but let the final result preempt any pending statuses" rule is a
  rendering concern for the web `useChatStream` hook. The backend already emits
  the events in order (status… → delta… → done); the web client paces them. For
  Telegram it's enforced server-side via the ≥1 s edit throttle + the final edit
  always landing last.
- **`TripRepository._touch_parent` can be removed** once the new DB trigger is
  confirmed live in all environments (kept now as belt-and-suspenders).

### 10.2 Spec deviations

- **True token streaming implemented (Option A reversed per user request).** The
  three content agents (`trip_agent`/`planner_agent`/`chat_agent`) now take an
  optional `events` and route through `client_factory.generate_maybe_stream`,
  which uses Gemini `generate_content_stream` (synchronous; runs AFC inline) and
  emits real token `delta`s through `events.on_delta` when the turn is streaming
  (`events.is_streaming`, i.e. a delta sink is wired). Non-streaming turns
  (Telegram, `/chat/send`, tests) take the original single-call path unchanged.
  AC-5 and AC-9 (`delta×N`) are now met with real tokens; the SSE endpoint no
  longer synthesises chunks.
- **Tool-level status (`status:tool`) implemented.** `orchestrator/tool_events.py`
  holds the active `EventEmitter` in a **contextvar** that `generate_maybe_stream`
  binds for the duration of the call; `check_weather` and the `search_web` tool
  closure call `emit_tool_status(...)` the moment the SDK invokes them, so
  "Checking the weather…" / "Searching the web…" fire mid-turn on **both** web
  and Telegram. A contextvar (not a global) keeps concurrent turns isolated.
- **No `orchestrator.process_streaming` async method.** The `/chat/stream`
  endpoint runs the sync `process_request_for_user` in a worker thread
  (`asyncio.to_thread`) and marshals status/delta events back via
  `loop.call_soon_threadsafe`; because `generate_content_stream` is synchronous,
  real token streaming needed **no** async refactor of the agents, sagas, or
  orchestrator. (§4's `agent.py [modify — async streaming dispatch]` became
  "thread an optional `events`/`delta_callback` through + emit phase status".)
- **EventEmitter sink signature changed** from `Callable[[str], None]` to
  `Callable[[dict], None]`; status payloads carry `{"phase","text",…}` and delta
  payloads `{"text"}`, so SSE events match the wire format and Telegram extracts
  what it needs (AC-8). Added `EventEmitter.is_streaming`. Updated the three
  emitter assertion tests.
- **Telegram handler file** is `interfaces/routers/telegram.py` (spec §4 said
  `interfaces/telegram_handler.py`). The placeholder-edit pattern (AC-7) existed;
  this task removed the generic "⏳ Thinking…" placeholder so the **first real
  status** becomes the placeholder, throttled status edits to ≥1 s, and kept the
  single final edit (preempts any pending status). `on_delta` stays unwired for
  Telegram, so it never shows a partial reply.
- **`done` carries `text`** in addition to `message_id` — a fallback for turns
  that don't stream deltas (slot questions, off-topic redirects, error path) and
  a reconciliation value for the client.
- **`/chat/stream` reuses `ChatSendRequest`** — no `schemas.py` change.
- **`TripRepository._touch_parent` kept** — coexists with the new trigger; both
  set `updated_at = now()`, so double-bumping is harmless (see §10.1).
- **Frontend (phase 2 — implemented):** `useChatStream`, `useChatRealtime`,
  `useTripRealtime`, the `/api/chat/stream` SSE proxy route, and `ChatPanel`
  wiring all landed. Deviations from §6/§7's sketch:
  - The **de-dup bridge** (the spec's "`FinalizedMessageIds` context") is kept
    **internal to `useChat`** rather than a separate React context — `useChat`
    already owns the message list, the `threadId`, and the finalized-id `Set`,
    and composes both `useChatStream` and `useChatRealtime`, so no cross-tree
    context is needed.
  - `useTripRealtime` reads the trip + children directly through the **RLS
    browser client** (the intended Supabase pattern) rather than a backend
    route — there is no GET-trip API endpoint, and RLS scopes the read to the
    owner. It's the data primitive for the task-40 trip panel.
  - One `react-hooks/set-state-in-effect` suppression in `useTripRealtime` for
    the standard fetch-in-effect loading flag (the new lint rule misfires on it;
    the pre-existing `ChatPanel` theme effect trips the same rule).
  - `done` carries `user_message_id` + `thread_id` (added to the backend) so the
    client finalizes its optimistic user bubble and learns the thread id for the
    Realtime subscription on a first-ever message.

### 10.3 Post-ship fixes (observed in live testing)

- **Double-rendered user bubble (~1 s).** While an SSE turn is in flight the
  backend persists the user (and agent) rows mid-stream, so Realtime echoed them
  back before `onDone` could mark their ids finalized — briefly showing the
  just-sent message twice. Fix: `useChat.onRealtimeInsert` ignores **web-origin**
  rows while `inflightRef` is set (`onDone` reconciles the canonical pair);
  Telegram / other-tab rows still merge live.
- **Empty synthesis after a tool call → "I had trouble…" crash.** A weather query
  routed to the PlannerAgent; AFC fired `search_web` (grounding ran) but the
  streamed synthesis turn came back with **empty text** (a streaming-AFC edge),
  which the orchestrator mapped to `action=ERROR`. Fix: `generate_maybe_stream`
  now falls back to a single blocking `gemini_generate` when the streamed text is
  empty (nothing was sent to the client yet) and pushes the recovered answer as
  one delta; `gemini_generate_stream` also guards `chunk.text` so a non-text part
  can't abort the stream. Covered by `tests/test_client_factory_stream.py`.
- **Failures invisible in LangSmith.** Because the orchestrator returns a graceful
  fallback (never raises), the run recorded as successful. Added
  `observability.record_run_error()` (sets the run-tree `error`, best-effort) +
  a `turn_failed` metric, both fired on `is_error_response` before the metrics
  flush. Covered in `tests/test_observability.py`.
- **Weather tool preference.** Nudged the PlannerAgent prompt so a direct weather
  question calls `check_weather` (authoritative, no grounding fee) instead of
  `search_web` — also avoids the streaming-AFC-after-grounding path most prone to
  the empty-synthesis edge above.

### 10.4 Streaming reliability + routing (second pass)

The empty-synthesis fallback above was correct but slow: on Vertex, streaming +
automatic function calling reliably drops the post-tool synthesis, so EVERY
tool-using turn wasted a streamed attempt and then re-ran a full blocking
generation (re-executing every search → ~43 s turns, and the answer appeared as
one block, "not streamed").

- **`generate_maybe_stream` split by tool-capability.** Tool-less turns keep real
  token-by-token streaming (fastest first token). **Tool-capable** turns now go
  straight to a single **blocking** generation (AFC runs tools reliably, returns
  the full answer) and then **pace** the reply to the client as `delta` chunks
  (`_emit_paced`, exact word-boundary slices, ≤2.5 s total) so it still types in.
  One generation, no double tool cost, no wasted stream. Tool-status events still
  fire during the blocking call via the bound-emitter contextvar.
  `tests/test_client_factory_stream.py` covers both branches.
- **Routing: the user's message dictates the engine (not slot-fullness).**
  `PlanningSaga.run` previously sent EVERY `TRIP` turn on a fully-slotted trip to
  the heavy `PlannerAgent` (so "how's the weather?" rebuilt an itinerary and hit
  the slow tool path). Now, with all essentials known, the planner runs only when
  `intent == "PLAN"` or the user just supplied a new planning fact
  (`made_progress`); otherwise the turn drifts to the lighter `TripAgent`. The
  slot-fill structure is unchanged — the trip stays in focus, but a complete trip
  no longer forces the planner. `tests/orchestrator/sagas/test_planning_saga.py`
  adds the casual-question-drifts and modification-rebuilds cases.
- **Web UI: only intermediary states, no typing dots.** `ChatPanel` dropped the
  generic three-dot "typing" placeholder; it now shows the real status line until
  the reply streams in.

## 11. Definition of Done

**Backend core (this session):**
- [x] AC-1 touch trigger SQL added to `schema_public.sql` (verified live — user applied the migration).
- [x] AC-4 `/chat/stream` emits `status`/`delta`/`done` (tested in `test_chat_stream.py`).
- [x] AC-5 agents use `generate_content_stream` (real token deltas via `generate_maybe_stream`).
- [x] AC-7 Telegram: first-status placeholder + throttled status edits + one final edit (no partial reply).
- [x] AC-8 EventEmitter sinks wired (status → SSE/Telegram, delta → SSE, metric → analytics_events).
- [x] AC-9 SSE ordering `status…` → `delta×N` → `done`, **including `status:tool`** (weather/search).
- [x] `ruff` clean; `pytest` passes (250 unit tests).
- [x] README updated with a "Real-time architecture" subsection.

**Frontend (phase 2 — this session):**
- [x] AC-2 `useTripRealtime(tripId)` — one parent `trips` subscription, refetches
  the assembled trip (parent + 5 child collections) via the RLS browser client.
- [x] AC-3 `useChatRealtime(threadId)` — `messages` INSERT subscription, merges
  rows, drops those already finalized via SSE (de-dup bridge in `useChat`).
- [x] AC-6 de-dup / recovery: reply persisted before the stream ends; `done`
  carries `message_id` + `user_message_id` + `thread_id`; `useChat` finalizes
  those ids so the Realtime echo is dropped, and renders the Realtime row when
  SSE drops before `done`.
- [x] `useChatStream` + `/api/chat/stream` SSE proxy + `ChatPanel` wiring
  (status line → token-streamed reply); status paced ≥1 s with reply preemption.
- [x] `npm run build` succeeds; `npm run lint` clean for the new files.

**Manual verification still owed (UI, both viewports):**
- [ ] Live desktop + 375px mobile check of the streaming reply, the status
  line, and the recovery path (per §8). Build + types pass; runtime/visual
  confirmation is the remaining step.

## Manual operations (user, post-implementation) — done

1. **Realtime enabled** on `public.trips`, `public.messages`,
   `public.user_profiles` via **Database → Publications → `supabase_realtime`**
   (the older "Database → Replication" location in earlier docs is deprecated).
   ✅ done by the user.
2. **Touch-trigger migration applied** in Supabase. ✅ done by the user.
3. **Cloud Run concurrency = 100** (perf tests show degradation only past
   ~150 req/s; streaming holds a worker per turn). ✅ user's call.
4. Verify in LangSmith that streamed turns appear like non-streamed turns —
   both wrap through the same traced `gemini.generate_content[_stream]` call.
