# Task 43 — Multiple-choice slot prompts: web + Telegram rendering + answer round-trip

> Spec lineage: `specs/task_36_trip_saga_orchestrator.md` §4.1 #4 (the
> `SlotRequest.choices` contract), which absorbed the old
> `task_chat_future_extensions.md` §1 multiple-choice wire shape.
> Depends on task 36 (contract, **done**). Benefits from task 37 (realtime +
> SSE + Telegram message-edit plumbing). Soft-blocks nothing.

## 1. Problem Statement

Task 36 gave the PlanningSaga a multiple-choice contract: categorical slots
(`pace`, `structure`, `budget_tier`, plus a `skip` opt-out) are returned as a
`SlotRequest(slot, prompt, choices=[ChoiceOption(id, label, value)],
allow_multi)`. The intent is low-friction slot filling — tap a chip instead of
typing — and a deterministic answer (no extraction LLM call) when the user
picks an option. **But none of that is wired to the channels.** The
orchestrator (`OrchestratorAgent._dispatch_sagas`) computes the `slot_request`
and then *discards* it — `process_request` / `process_request_for_user` return
only `{"text", "action"}`. So today the user just sees the question text and
must answer in free text, which the `slot_extractor` then parses. That works
(no crash) but throws away the entire multiple-choice UX, and the categorical
extraction call we were trying to avoid still runs. This task surfaces
`slot_request` out of the orchestrator and renders it as tappable options on
both the web chat and Telegram, with the selection mapped deterministically
back onto the trip — closing the loop the contract was built for, and making
every future saga's choice prompts (task 38 Country Intel, task 39 Booking,
etc.) render richly for free.

## 2. Goals & Non-Goals

### Goals

- The orchestrator surfaces the owner saga's `slot_request` (slot, prompt,
  choices, allow_multi) in its return value, and `/chat/send` persists it into
  the agent message's `messages.metadata.ui` block.
- **Web:** when the latest agent reply carries a `multi_choice` UI block, the
  chat renders the prompt + option chips (and a Confirm button when
  `allow_multi`). Tapping an option (or confirming a multi-select) sends the
  selection back; the chips then render as disabled/answered. Mobile **and**
  desktop both, per CLAUDE.md §3.
- **Telegram:** the same `slot_request` renders as an inline keyboard; tapping
  a button fires a `callback_query` that the backend handles, edits the
  original message to show the chosen answer, and sends the next prompt.
- A user's **selection** is applied to the trip **deterministically** (no
  `slot_extractor` LLM call): the chosen `value` is written to the trip via a
  shared `slot_selection_to_side_effect` mapper; `skip` writes the literal
  `"skip"` sentinel (key-presence marks the slot satisfied, so the saga moves
  on and never re-asks).
- Free-text answering still works unchanged (graceful fallback): a user who
  types "slow" instead of tapping is still parsed by `slot_extractor`.

### Non-Goals

- New saga types or any change to the slot model / `SlotRequest` shape
  (that's frozen in task 36).
- SSE streaming itself, the realtime parent-row subscription, and the Telegram
  debounced `editMessageText` progress UX — those are **task 37**. This task
  consumes whatever delivery task 37 provides; if task 37 has not shipped, the
  web path still works via the `/chat/send` response body (synchronous), and
  the Telegram path via a normal `sendMessage` with `reply_markup`.
- Rendering choices anywhere outside the chat surface (e.g. the trip panel /
  task 40).
- Persisting per-option analytics beyond the existing `slot_request_emitted`
  metric (a `slot_selected` metric is in-scope; richer funnels are not).

## 3. Acceptance Criteria

AC-1. `OrchestratorAgent.process_request` and `process_request_for_user` return
  a dict that includes `slot_request` — `None` when the turn has no slot
  question, else `{"slot": str, "prompt": str, "choices": [{"id","label",
  "value"}] | None, "allow_multi": bool}`. `_dispatch_sagas` propagates
  `result.slot_request`; the OFF_TOPIC / CHAT-router short-circuits return
  `slot_request=None`.

AC-2. `POST /chat/send` writes the slot_request into the agent message's
  `metadata.ui` as `{"kind": "multi_choice", "slot", "prompt", "options":
  [{"id","label"}], "allow_multi", "submit_label"?}` when (and only when) the
  reply carries choices. Replies without choices leave `metadata.ui` unset.

AC-3. `POST /chat/send` accepts an optional `selection` field
  `{"slot": str, "values": [str]}`. When present, the orchestrator applies the
  values deterministically to the active trip (no `slot_extractor` call), the
  persisted user message body is the human-readable chosen label(s), and the
  reply is the saga's next prompt.

AC-4. Selecting `pace=slow` (web or Telegram) results in
  `trips.preferences.pace == "slow"` and the saga's next reply asks the next
  missing slot (`structure`), not `pace` again.

AC-5. Selecting `skip` on a slot writes `"skip"` to that slot and the saga
  advances past it (never re-asks it for that trip).

AC-6. Telegram: a slot_request with choices is sent with an inline keyboard;
  tapping a button (`callback_query`) applies the selection, answers the
  `callback_query` (no client spinner hang), edits the prompt message to show
  the chosen label, and sends the next prompt.

AC-7. Web chat renders the option chips and (for `allow_multi`) a Confirm
  button at **both** a 375px mobile width and a desktop width; after answering,
  the chips are disabled and the chosen option is visually marked.

AC-8. A `slot_selected` metric row is emitted on selection with
  `{slot, value, channel}`.

AC-9. Free-text fallback unchanged: typing the answer instead of tapping still
  fills the slot via `slot_extractor` (regression check on task 36 behavior).

## 4. Files & Modules Touched

```
backend/src/agentic_traveler/orchestrator/agent.py                   [modify — return slot_request; accept selection]
backend/src/agentic_traveler/orchestrator/sagas/planning.py          [modify — export slot_selection_to_side_effect; selection entrypoint]
backend/src/agentic_traveler/orchestrator/sagas/base.py              [modify — to_wire() helper on SlotRequest, optional]
backend/src/agentic_traveler/interfaces/routers/chat.py              [modify — selection in, metadata.ui out]
backend/src/agentic_traveler/interfaces/routers/telegram.py          [modify — inline keyboard + callback_query handler]
backend/src/agentic_traveler/interfaces/schemas.py                   [modify — ChatSendRequest.selection, ChatSendResponse passthrough]
frontend/src/app/api/chat/route.ts                                   [modify — pass selection; surface reply metadata]
frontend/src/hooks/useChat.ts                                        [modify — expose ui block; sendSelection()]
frontend/src/components/dashboard/ChatPanel.tsx                      [modify — render chips + confirm, answered state]
backend/tests/orchestrator/sagas/test_planning_saga.py              [modify — selection→side_effect mapper tests]
backend/tests/orchestrator/test_orchestrator.py                     [modify — slot_request surfaced; selection path]
backend/tests/interfaces/test_chat_router.py                        [modify/create — metadata.ui + selection]
README.md                                                            [modify — document the multiple-choice UX]
```

No schema migration is required: `messages.metadata` is already a JSONB column
(task 28). No new table, so no new RLS.

## 5. Constraints

- **No new LLM call on selection.** A tapped choice must write deterministically
  via the shared mapper; only free-text answers may invoke `slot_extractor`.
- **`SlotRequest` / `ChoiceOption` shapes are frozen** (task 36). This task only
  serializes them to the wire and back — it must not change the dataclasses'
  fields.
- **Backwards compatible:** clients that ignore `metadata.ui` and never send
  `selection` keep working exactly as today (free-text). The `/chat/send`
  response shape is additive only.
- **`callback_data` ≤ 64 bytes** (Telegram hard limit). Encode as
  `slot|<slot>|<value>`; slot names and values are short enums, so this fits.
  Reject/ignore malformed callback data defensively.
- **Selection is trust-but-verify:** the backend re-validates that the chosen
  `value` is a legal option for that `slot` (and that the slot is one the saga
  actually asked) before writing — never trust the client's value blindly
  (prompt-injection / tampering surface).
- CLAUDE.md §3 mobile-first is non-negotiable: the chip layout ships with the
  `sm:`/`md:` treatment in the same change, not deferred.
- CLAUDE.md §9: no auto-deploy, no Gemini/Telegram calls in unit tests
  (mock the Bot API), no secrets in logs.

## 6. Edge Cases

- **Stale choice tap:** user taps a chip from an old message after the slot is
  already filled (e.g. tapped twice, or the trip advanced). The deterministic
  write is idempotent (upsert); the saga simply recomputes the next missing
  slot. No error. Covered by a test.
- **`allow_multi` with zero selections + Confirm:** treated as `skip` for that
  slot (or a no-op that re-asks) — pick one; spec'd as **skip**.
- **Selection for a slot the saga didn't ask / illegal value:** backend rejects
  (logs a WARN, returns the current prompt unchanged). No write.
- **Telegram `callback_query` for an unknown/expired message:** answer the
  callback (to clear the client spinner) and no-op.
- **Web client offline mid-selection:** the chips remain tappable; the
  `/chat/send` retry is idempotent.
- **No active trip when a selection arrives** (e.g. trip deleted in another
  tab): resolve/create as the normal planning turn does, or no-op with a gentle
  "let's start over" — spec'd as: re-resolve; if none, the PlanningSaga's
  zero-trip path creates one and the selection applies to it.
- **`skip` then later volunteering the value:** user skipped `pace` (wrote
  "skip") then types "actually, slow days" — `slot_extractor` overwrites
  "skip" with "slow". Allowed (presence semantics; last write wins).
- **Free-tier realtime:** the agent reply with `metadata.ui` rides the existing
  single parent-row subscription (task 37); no extra channel.

## 7. Implementation Plan

### Step 1 — Surface `slot_request` from the orchestrator
`SagaResult.slot_request` → `_dispatch_sagas` return dict → `_process_user_doc`
return. Add a serializer (e.g. `SlotRequest.to_wire()` in `base.py`):

```python
def to_wire(self) -> dict:
    return {
        "slot": self.slot,
        "prompt": self.prompt,
        "choices": (
            [{"id": c.id, "label": c.label, "value": c.value} for c in self.choices]
            if self.choices else None
        ),
        "allow_multi": self.allow_multi,
    }
```

`process_request*` return `{... , "slot_request": result.get("slot_request")}`
(None on the OFF_TOPIC / CHAT-router short-circuit paths).
→ verify: unit test asserts the returned dict carries the wire shape for a
PLAN turn that asks `pace`, and `None` for a CHAT turn.

### Step 2 — Deterministic selection mapper (shared)
In `planning.py`, a pure function reused by both channels:

```python
def slot_selection_to_side_effect(trip_id: str, slot: str, value: str) -> SideEffect | None:
    """Map a tapped/selected slot value onto a trip write. Returns None for an
    illegal (slot, value) pair. 'skip' is a legal value for categorical slots."""
    legal = _legal_values(slot)         # from _SLOT_CHOICES + {'skip'}
    if value not in legal:
        return None
    if slot in ("pace", "structure", "budget_tier"):
        return SideEffect(kind="trip_patch", payload={"id": trip_id, "preferences": {slot: value}})
    # destination/timeframe/travelers are free-text, not choice-driven → None
    return None
```

→ verify: unit tests for legal/illegal pairs and `skip`.

### Step 3 — Orchestrator selection entrypoint
`process_request_for_user(..., selection: dict | None = None)` and the Telegram
equivalent. When `selection` is present:
1. resolve/create the active trip (same as a planning turn);
2. `se = slot_selection_to_side_effect(trip_id, slot, value)` for each value;
   reject illegal → return current prompt unchanged;
3. `trip_repo.apply_side_effect(user_id, se)`;
4. emit `slot_selected` metric `{slot, value, channel}`;
5. re-run the PlanningSaga (no `slot_extractor` call needed — the write already
   landed) to produce the next prompt / plan;
6. persist the human-readable label as the user message body.

→ verify: integration-style unit test (mocked repo) asserts `preferences.pace`
written and next prompt is `structure`.

### Step 4 — Web: `/chat/send` in/out (`chat.py`, `schemas.py`)
- `ChatSendRequest` gains `selection: Optional[SelectionIn]`
  (`{slot: str, values: list[str]}`).
- On a normal turn, after the orchestrator returns, if `agent_result["slot_request"]`
  has choices, write `metadata.ui`:

```jsonc
// messages.metadata.ui
{
  "kind": "multi_choice",
  "slot": "pace",
  "prompt": "What pace feels right?",
  "options": [
    {"id": "slow", "label": "Slow — room to breathe"},
    {"id": "medium", "label": "Medium — a good rhythm"},
    {"id": "fast", "label": "Fast — see a lot"},
    {"id": "skip", "label": "Skip for now"}
  ],
  "allow_multi": false,
  "submit_label": "Confirm"   // present only when allow_multi
}
```

- When `selection` is present, call the orchestrator's selection entrypoint and
  persist the chosen label as the user message body.
→ verify: router test asserts `metadata.ui.kind == "multi_choice"` on a pace
turn, and that a `selection` request writes the slot + returns the next prompt.

### Step 5 — Web: `useChat.ts` + `ChatPanel.tsx`
- `useChat`: expose `reply.metadata.ui`; add `sendSelection(slot, values, label)`
  that POSTs `/chat/send` with the `selection` field and optimistically appends
  the label as the user bubble.
- `ChatPanel`: when the last agent message has `metadata.ui.kind ==
  "multi_choice"` and is unanswered, render the prompt + option buttons
  (single-tap fires immediately; `allow_multi` shows checkboxes + Confirm).
  After answering, render the chips disabled with the chosen one marked.
  Tailwind: stack vertically on mobile (`flex-col`), inline-wrap on `sm:`/`md:`.
→ verify: `npm run build`; manual check at 375px and desktop (§8).

### Step 6 — Telegram: inline keyboard + callback (`telegram.py`)
- When the orchestrator reply carries `slot_request.choices`, send the prompt
  with `reply_markup.inline_keyboard` (one button per option; `callback_data =
  f"slot|{slot}|{value}"`).
- Add a `callback_query` branch in the update handler: parse `callback_data`,
  call the orchestrator selection entrypoint, `answerCallbackQuery`,
  `editMessageText` to show the chosen label, then `sendMessage` the next prompt
  (or the plan). Ignore malformed/expired callbacks gracefully.
→ verify: unit test with a mocked Bot API asserts inline keyboard is built and a
simulated callback applies the write + edits the message (no real Telegram call).

### Step 7 — Docs + metric
- README: short paragraph under the saga section describing tappable slot
  prompts on web + Telegram, the `skip` option, and the deterministic write.
- Register `slot_selected` in the metrics catalogue.

## 8. Testing Plan

- **Unit:** `slot_selection_to_side_effect` (legal/illegal/skip); orchestrator
  selection path (mocked `TripRepository` + dispatcher) writes slot + advances;
  `chat.py` metadata.ui shaping; Telegram inline-keyboard build + simulated
  callback (Bot API mocked per TESTING_STRATEGY); regression: free-text answer
  still fills the slot.
- **Integration (`-m integration`, `_INTEGRATION_TESTS=1`):** end-to-end web
  `/chat/send` selection round-trip against real Supabase (self-provisioned
  user per the `integration_user_id` fixture in `test_trip_repo.py`), asserting
  `trips.preferences.pace` persists and the next prompt is `structure`.
- **Manual (UI, both viewports — mobile non-negotiable):**
  - 375px mobile + desktop: chips render, wrap correctly, are tappable, show
    answered state; Telegram inline keyboard renders and the message edits on tap.
- **Sample happy path (web):**
  - Request: `POST /chat/send {"body":"plan a trip to Iceland in late Jan, 2 of us"}`
    → reply prompt "What pace feels right?" with `metadata.ui` (pace options).
  - Request: `POST /chat/send {"selection":{"slot":"pace","values":["slow"]}}`
    → `trips.preferences.pace="slow"`; reply prompt "How structured do you want it?".
- **Sample error path:** `selection` with `{"slot":"pace","values":["zoomy"]}`
  → no write, reply re-asks pace (illegal value rejected, logged WARN).

## 9. Conditional Sections

### 9.2 LLM Considerations
- **No new prompt or model call** is introduced on the selection path — that's
  the whole point (deterministic write). The free-text fallback still uses the
  existing task-36 `slot_extractor` (flash-lite).
- **Prompt-injection / tampering surface:** the `selection.value` and Telegram
  `callback_data` are untrusted. The backend re-validates `(slot, value)`
  against the saga's legal options before writing (§5). No user text from the
  selection enters an LLM prompt.

### 9.3 Observability
- New metric `slot_selected {slot, value, channel}` on every tap/confirm.
- Structured WARN on rejected/illegal selections (with `slot`, not the raw
  value if it could be abusive — log a truncated/escaped form).
- Telegram callback failures logged with `user_id` + `slot`.

### 9.4 Rollback Plan
- Pure additive: revert the diff. `metadata.ui` is ignored by older clients;
  the `selection` field is optional. No schema or data migration to undo.

## 10. Findings & Follow-ups

### 10.1 Improvements observed
- **DONE (post-review):** `travelers` is now a categorical multiple-choice slot
  (Just me / partner / friends / family / skip), since the question literally
  enumerates discrete options — surfaced when a user expected chips there. Its
  values write into `trip.travelers` (not `preferences`) via a `_TRAVELER_PRESETS`
  branch in `slot_selection_to_side_effect`; `_slot_values` now treats a
  composition-only answer (friends/family, no exact count) as satisfying the
  slot. `ui_block_from_wire`'s `multi_choice` discriminator was broadened from
  `_PREFERENCE_SLOTS` to "any slot in `_SLOT_CHOICES`". The free-text extractor
  remains the fallback. The frontend needed no change (chips are slot-agnostic).
- **DONE (post-review #2):** `travelers` is **multi-select** (`allow_multi`,
  e.g. partner + family). The deterministic mapper became
  `slot_values_to_side_effect(trip, slot, values)` (aggregates the chosen presets
  into `travelers.composition`, keeping a `count` only for a single unambiguous
  pick); `slot_selection_to_side_effect` is now a single-value wrapper. ``skip``
  is exclusive (clears the rest). `_MULTI_SELECT_SLOTS` drives `allow_multi` on
  the `SlotRequest`.
- **DONE (post-review #2):** the web rendering is **unitary** — `SlotChoices`
  draws the prompt + chips as one agent bubble (the plain message bubble is
  suppressed when a `ui` block is present), instead of a message followed by
  detached chips.
- Still open: tappable presets for `timeframe` (e.g. date-range chips) would need
  a richer value shape; out of scope.

### 10.2 Spec deviations
- **`slot_selection_to_side_effect` takes the hydrated `trip`, not `trip_id`.**
  `TripRepository.upsert_trip` REPLACES the `preferences` JSONB column, so the
  mapper must merge the chosen value into the trip's existing preferences (like
  `_slots_to_side_effects`) to avoid clobbering sibling slots. Signature is
  `(trip, slot, value)`.
- **`metadata.ui.kind` is decided in the channel layer, not on `SlotRequest`.**
  §5 freezes the `SlotRequest`/`ChoiceOption` dataclasses, so the new
  `multi_choice` vs `quick_reply` discriminator is computed by
  `ui_block_from_wire()` from the slot name (`_PREFERENCE_SLOTS` →
  `multi_choice`, else `quick_reply`) rather than added as a model field.
- **Selection entrypoint is `_process_selection` + `PlanningSaga.run_after_selection`.**
  Rather than re-running the full saga (which would call `slot_extractor`),
  `run_after_selection` skips extraction entirely and runs the post-extraction
  decision with `made_progress=True`, so a now-complete trip proceeds to the
  itinerary and an incomplete one asks the next slot. The orchestrator branches
  to `_process_selection` *before* the Router (no intent classification on a
  deterministic tap).
- **Task-44 confirmation = `quick_reply`, web-only chips.** The "keep refining /
  start new" confirmation renders as two quick-reply chips on web; each tap
  sends a short phrase as a NORMAL message that the Router re-classifies into a
  `trip_directive` (stateless, no persisted "awaiting" flag). On **Telegram**
  the confirmation stays plain text — inline buttons can only send
  `callback_data`, not the free-text a directive re-classification needs, so
  only `multi_choice` preference slots get a Telegram inline keyboard.
- **Open question resolved → structured `selection` field (Option A).** See §12.

### 10.3 Open-question reasoning (selection transport on web)
Chose the structured `selection` field over "send the chosen value as a plain
message". The plain-message route still incurs the `slot_extractor` LLM call
(defeating the multiple-choice contract's zero-extraction goal), is ambiguous
about which slot a bare value answers, and couples the render layer to a fragile
text convention. The structured field is self-describing, deterministic, gives a
clean `(slot, value)` re-validation boundary, and leaves free-text typing intact
as the graceful fallback (AC-9). The plain-message mechanism survives only as
that fallback (the existing `_CHOICE_VALUES` intercept).

## 11. Definition of Done

- [x] AC-1..AC-9 pass (unit tests; AC-7 chips + AC-6 Telegram edit need the
  manual viewport check below).
- [x] §6 edge cases covered (stale tap idempotent; illegal value re-asks;
  malformed/expired callback answered + no-op; zero-select Confirm → skip;
  no-active-trip re-resolves/creates) or deferred in §10.2.
- [x] `ruff check` clean; `pytest` unit suite passes (298 passed, 43 deselected).
  Integration round-trip under `_INTEGRATION_TESTS=1` not run locally (no live
  Supabase in this environment) — deferred to the manual check.
- [x] `npm run build` succeeds. **Manual:** chips at 375px mobile **and** desktop
  + Telegram inline keyboard edit-on-tap still owed (user verification).
- [x] No file outside §4 modified (or §10.2 explains why) — added
  `backend/tests/interfaces/test_chat_router.py` (was "modify/create" in §4) and
  `backend/tests/interfaces/test_webhook.py` (Telegram callback tests, the §4
  `telegram.py` change's test home); frontend `useChatStream.ts` carries the
  `UiBlock` type + `ui` on the SSE `done` event (the streaming counterpart of the
  §4 `/chat/send` metadata.ui).
- [x] README updated (the multiple-choice UX).
- [x] No secrets/PII in logs (rejected selections log the slot, not raw value);
  Bot API mocked in tests.

## 12. Open Questions

- ~~**Selection transport on web:**~~ **RESOLVED → structured `selection` field**
  on `/chat/send` (Option A). Reasoning in §10.3. The plain-message variant is
  retained only as the free-text fallback.
- **Scheduling (see below).** Landed as a standalone task after task 37 (not
  folded in), as recommended.

---

## Recommended scheduling

**Implement immediately after task 37 (realtime + SSE + Telegram message-edit),
as the next task — or fold it into task 37.** Rationale:

- **It depends on task 36 (done)** for the `SlotRequest.choices` contract, and
  **benefits from task 37**, which builds the `messages.metadata` realtime
  propagation (web) and the Telegram message-edit/inline-UX plumbing that this
  task's `multi_choice` block and `callback_query` handling ride on. Doing it
  before 37 means re-doing the delivery wiring.
- **Nothing hard-depends on it.** Every slot prompt already degrades to
  free-text via the task-36 `slot_extractor`, so tasks 38–42 are not blocked if
  this slips. But its value **compounds**: tasks 38 (Country Intel — e.g.
  "refresh intel?" confirm) and 39 (Booking input — e.g. booking-kind picker)
  will emit their own choice prompts, so landing 43 right after 37 means those
  sagas get tappable UI for free instead of each re-inventing it.
- **Net:** schedule `37 → 43 → 38 → 39 → 40 → 41 → 42`. If task 37's scope is
  light, merging 43 into 37 is reasonable since both are "wire `SagaResult` /
  `EventEmitter` out to the web + Telegram channels."
