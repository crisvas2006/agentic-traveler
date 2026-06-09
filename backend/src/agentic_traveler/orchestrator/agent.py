"""
Orchestrator Coordinator — the single entry point for user messages.

Architecture (v2 — Thin Router + Specialized Agents):
    1. Fetch user profile + credit gate.
    2. Check off-topic restriction.
    3. Build conversation context.
    4. RouterAgent classifies intent (CHAT | TRIP | PLAN | OFF_TOPIC),
       extracts trip entities, and handles lightweight tools (preferences,
       feedback, credits).
    5. Resolve the active trip, then the SagaDispatcher (Task 36 — deterministic,
       no LLM) selects the owner saga for the turn and runs it:
       - PLAN / TRIP(with trip) → PlanningSaga (slot-fill → PlannerAgent/TripAgent)
       - TRIP(no trip)          → DiscoverySaga (→ TripAgent)
       - CHAT                   → ChatSaga (→ ChatAgent)
       - OFF_TOPIC              → handled inline; off_topic_guard increments
                                  the counter silently (OffTopicSaga mirrors it).
       Saga side-effects are persisted via TripRepository.
    6. Log token usage for router + delegated agent separately.
    7. Deduct credits asynchronously.
    8. Save conversation history.

Token savings vs v1:
    - Simple chat: ~51% fewer input tokens
    - Discovery/trip: ~54% fewer input tokens
    - Planning: ~56% fewer input tokens
    - Off-topic: ~84% fewer input tokens (router only, no sub-agent)
"""

import datetime
import logging
import time
from typing import Any, Callable, Dict, Optional

from agentic_traveler.economy import credit_manager
from agentic_traveler.guards import off_topic_guard
from agentic_traveler.analytics import usage_tracker
from agentic_traveler.analytics import metrics_tracker
from agentic_traveler.orchestrator.client_factory import get_client
from agentic_traveler.core.observability import (
    traceable,
    attach_run_metadata,
    hash_user_id,
    record_run_error,
)
from agentic_traveler.orchestrator.conversation_manager import ConversationManager
from agentic_traveler.orchestrator.router_agent import RouterAgent
from agentic_traveler.orchestrator.event_emitter import EventEmitter
from agentic_traveler.orchestrator.event_text_registry import text_for
from agentic_traveler.orchestrator.sagas import SagaDispatcher, SagaState
from agentic_traveler.orchestrator.sagas.planning import slot_values_to_side_effect
from agentic_traveler.orchestrator.sagas.trip_resolver import (
    resolve_active_trip,
    resolve_trip_focus,
)
from agentic_traveler.tools.user_repo import UserRepository
from agentic_traveler.tools.trip_repo import TripRepository

logger = logging.getLogger(__name__)


def _elapsed(t0: float) -> str:
    """Return formatted elapsed time since *t0*."""
    return f"{(time.time() - t0) * 1000:.0f}ms"


def _current_time_str() -> str:
    """Return a human-readable current datetime string."""
    now = datetime.datetime.now().astimezone()
    return now.strftime("%A, %Y-%m-%d %H:%M:%S %Z")


def _emit_status(events: "EventEmitter", phase: str, key: Optional[str] = None) -> None:
    """Emit a user-facing status event from the static registry (Task 37 — no
    LLM). No-op when the phase/key maps to None (silent phases like ChatSaga),
    and a no-op overall when no status sink is wired (e.g. the non-streaming
    web path passes on_status=None)."""
    text = text_for(phase, key)
    if not text:
        return
    payload: Dict[str, Any] = {"phase": phase, "text": text}
    if phase == "saga_selected" and key:
        payload["saga"] = key
    events.emit("status", payload)


class OrchestratorAgent:
    """
    Orchestration coordinator — routes messages to specialized agents.

    Delegates to RouterAgent for intent classification, then dispatches to
    ChatAgent, TripAgent, or PlannerAgent. All agent instances are reused
    across requests for efficiency.
    """

    def __init__(self, user_repo: Optional[UserRepository] = None):
        self._client = get_client()
        self.user_tool = user_repo or UserRepository()
        self.conversation_manager = ConversationManager(client=self._client)

        # Specialized agents (stateless, shared instances)
        self._router_agent = RouterAgent(client=self._client)
        # The saga dispatcher owns the Chat/Trip/Planner content engines and
        # selects which saga handles each turn (Task 36 — replaces _dispatch).
        self._dispatcher = SagaDispatcher(client=self._client)
        self._trip_repo = TripRepository()

    @traceable(name="orchestrator.process_request")
    def process_request(
        self,
        telegram_user_id: str,
        message_text: str,
        status_callback: Optional[Callable[[dict], None]] = None,
        delta_callback: Optional[Callable[[dict], None]] = None,
        selection: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Telegram entry point. Resolves the user by Telegram ID, then dispatches.

        When ``selection`` is present (a tapped inline-keyboard choice, Task 43)
        the deterministic selection pipeline runs instead of the router.

        Returns {"text": str, "action": str, "slot_request": dict | None}.
        """
        attach_run_metadata(
            user_id_hash=hash_user_id(telegram_user_id), surface="telegram"
        )
        user_doc, user_id = self.user_tool.get_user_with_ref(telegram_user_id)
        if not user_doc:
            logger.info("New user detected: %s", telegram_user_id)
            return {
                "text": (
                    "Welcome! I'm Agentic Traveler, your AI travel companion. 🌍\n\n"
                    "Since it's our first time meeting, I need to know a bit about "
                    "your travel style to give you the best advice.\n\n"
                    "Please take 1 minute to fill out this quick profile:\n"
                    "https://tally.so/r/ODPGak"
                ),
                "action": "ONBOARDING_REQUIRED",
            }
        if selection is not None:
            return self._process_selection(
                user_doc=user_doc, user_id=user_id,
                telegram_user_id=telegram_user_id, selection=selection,
                channel="telegram",
                status_callback=status_callback, delta_callback=delta_callback,
            )
        return self._process_user_doc(
            user_doc=user_doc,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            message_text=message_text,
            status_callback=status_callback,
            delta_callback=delta_callback,
        )

    @traceable(name="orchestrator.process_request_for_user")
    def process_request_for_user(
        self,
        user_id: str,
        message_text: str,
        status_callback: Optional[Callable[[dict], None]] = None,
        delta_callback: Optional[Callable[[dict], None]] = None,
        selection: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Web entry point. The user is already resolved by Supabase JWT → users.id;
        we fetch the assembled user_doc and dispatch.

        When ``selection`` is present (a tapped multiple-choice chip, Task 43)
        the deterministic selection pipeline runs instead of the router.

        Returns {"text": str, "action": str, "slot_request": dict | None}.
        """
        attach_run_metadata(user_id_hash=hash_user_id(user_id), surface="web")
        user_doc = self.user_tool.get_user_by_id(user_id)
        if not user_doc:
            logger.warning("process_request_for_user: no user row for id=%s", user_id)
            return {
                "text": "Your profile is missing. Please complete the travel profile to continue.",
                "action": "ONBOARDING_REQUIRED",
            }
        # For web users we don't have a Telegram ID; use the internal user_id as the
        # analytics/logging key. usage_tracker just needs a stable string identifier.
        if selection is not None:
            return self._process_selection(
                user_doc=user_doc, user_id=user_id,
                telegram_user_id=user_id, selection=selection, channel="web",
                status_callback=status_callback, delta_callback=delta_callback,
            )
        return self._process_user_doc(
            user_doc=user_doc,
            user_id=user_id,
            telegram_user_id=user_id,
            message_text=message_text,
            status_callback=status_callback,
            delta_callback=delta_callback,
        )

    def _process_user_doc(
        self,
        user_doc: Dict[str, Any],
        user_id: str,
        telegram_user_id: str,
        message_text: str,
        status_callback: Optional[Callable[[dict], None]] = None,
        delta_callback: Optional[Callable[[dict], None]] = None,
    ) -> Dict[str, Any]:
        """
        Shared post-lookup pipeline. Used by both the Telegram and web entry
        points so credit gating, off-topic enforcement, dispatch, and history
        save behave identically across channels.
        """
        t_total = time.time()
        token_records: list[Dict[str, Any]] = []
        events = EventEmitter(
            user_id=user_id, trip_id=None,
            on_status=status_callback, on_delta=delta_callback,
        )

        # ── 1b. Credit gate ─────────────────────────────────────────────────
        if not credit_manager.has_credits(user_doc):
            logger.info("User %s has no credits.", telegram_user_id)
            return {"text": credit_manager.CREDITS_EXHAUSTED_MSG, "action": "NO_CREDITS"}

        # ── 2. Restriction check ────────────────────────────────────────────
        restriction_msg = off_topic_guard.is_restricted(user_doc)
        if restriction_msg:
            logger.info("User %s is restricted.", telegram_user_id)
            return {"text": restriction_msg, "action": "RESTRICTED"}

        # ── 3. Build conversation context ───────────────────────────────────
        # Full context (summary + all recent messages) for specialized agents.
        # Slim context (last 4 entries = 2 exchanges, no summary) for the router:
        # the router only needs recent turns for intent classification and passing
        # the full history increases token cost and can cause confusion (e.g. the
        # router extracting preferences from old messages instead of the current one).
        t = time.time()
        conv_context = self.conversation_manager.build_context_block(user_doc)
        router_context = self.conversation_manager.build_context_block(
            user_doc, max_messages=4
        )
        logger.debug("⏱ Context build: %s", _elapsed(t))

        current_time = _current_time_str()
        user_name = user_doc.get("user_name", "Traveler")

        # ── 4. Router — classify intent ─────────────────────────────────────
        t = time.time()
        router_result = self._router_agent.classify(
            message=message_text,
            user_doc=user_doc,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            user_name=user_name,
            current_time=current_time,
            conversation_context=router_context,
            token_records=token_records,
        )
        logger.info("⏱ Router: %s", _elapsed(t))

        # Log router token usage
        raw_router = router_result.get("raw_response")
        if raw_router and hasattr(raw_router, "usage_metadata"):
            router_usage = usage_tracker.log_and_accumulate(
                agent_name="router",
                model_name="gemini-3.1-flash-lite",
                user_id=telegram_user_id,
                response=raw_router,
                latency_ms=router_result.get("latency_ms", 0),
            )
            if router_usage.get("total_tokens", 0) > 0:
                token_records.append(router_usage)

        intent = router_result.get("intent", "CHAT")
        preference_raw = router_result.get("preference_raw")
        router_response = router_result.get("response")

        logger.info("Intent: %s | Preference raw: %s", intent, preference_raw)

        # Status event: the router has classified the turn (Task 37).
        _emit_status(events, "router")

        # ── 5. Handle intent ────────────────────────────────────────────────

        # ── 5a. OFF_TOPIC or direct router response ─────────────────────────
        if intent == "OFF_TOPIC":
            guard_result = off_topic_guard.record_off_topic(user_doc, user_id)
            if guard_result.get("restricted"):
                restriction_msg = off_topic_guard.is_restricted(
                    {**user_doc, "off_topic": {
                        "restricted_until": guard_result.get("restricted_until")
                    }}
                )
                response_text = restriction_msg or "You're temporarily restricted due to off-topic messages."
            else:
                response_text = router_response or (
                    "I'm really only good at travel stuff! 😄 "
                    "Got any trips on your mind?"
                )
            _save_and_finish(
                self, user_doc, user_id, message_text, response_text,
                telegram_user_id, token_records, t_total, events, intent,
                owner_saga="OffTopicSaga",
            )
            return {"text": response_text, "action": "RESPONSE", "slot_request": None}

        # If the router provided a direct response (e.g., a credit-balance answer)
        # Only short-circuit for CHAT intent — TRIP and PLAN must always reach
        # their specialized agents (router_response for those is a bug side-effect).
        elif intent == "CHAT" and router_response:
            if user_id:
                off_topic_guard.reset(user_id)
            _save_and_finish(
                self, user_doc, user_id, message_text, router_response,
                telegram_user_id, token_records, t_total, events, intent,
                owner_saga="ChatSaga",
            )
            return {"text": router_response, "action": "RESPONSE", "slot_request": None}

        # ── 5b. Travel intents — reset off-topic counter ────────────────────
        if user_id:
            off_topic_guard.reset(user_id)

        # ── 5c. Resolve the active trip + dispatch via the saga dispatcher ──
        agent_result = self._dispatch_sagas(
            intent=intent,
            user_doc=user_doc,
            user_id=user_id,
            message_text=message_text,
            conv_context=conv_context,
            current_time=current_time,
            preference_raw=preference_raw,
            router_response=router_response,
            entities=router_result.get("entities", {}) or {},
            trip_directive=router_result.get("trip_directive", "unspecified"),
            events=events,
        )

        response_text = agent_result.get("text", "")

        # Detect AFC-limit failures: the model returns this specific message when
        # it hits maximum_remote_calls and can't synthesise a proper response.
        _ERROR_FALLBACK = "I had trouble coming up with a response just now. Please try again."
        is_error_response = (
            not response_text
            or agent_result.get("action") == "ERROR"
            or response_text.strip() == _ERROR_FALLBACK
        )

        if not response_text:
            response_text = _ERROR_FALLBACK

        # Log specialized agent usage
        raw_agent = agent_result.get("_raw_response")
        if raw_agent and hasattr(raw_agent, "usage_metadata"):
            agent_name = {"CHAT": "chat", "TRIP": "trip", "PLAN": "planner"}.get(intent, "agent")
            model_name = {
                "CHAT": "gemini-3.1-flash-lite",
                "TRIP": "gemini-3.5-flash",
                "PLAN": "gemini-3.5-flash",
            }.get(intent, "gemini-3.5-flash")
            agent_usage = usage_tracker.log_and_accumulate(
                agent_name=agent_name,
                model_name=model_name,
                user_id=telegram_user_id,
                response=raw_agent,
                latency_ms=agent_result.get("_latency_ms", 0),
            )
            if agent_usage.get("total_tokens", 0) > 0:
                token_records.append(agent_usage)

        # Log SearchAgent usage (including grounding)
        search_responses = agent_result.get("_search_responses", [])
        for sr in search_responses:
            raw_search = sr.get("raw")
            if raw_search and hasattr(raw_search, "usage_metadata"):
                search_usage = usage_tracker.log_and_accumulate(
                    agent_name="search",
                    model_name="gemini-3.1-flash-lite",
                    user_id=telegram_user_id,
                    response=raw_search,
                    latency_ms=sr.get("lat", 0),
                )
                if search_usage.get("total_tokens", 0) > 0:
                    token_records.append(search_usage)

                grounding_credits = search_usage.get("grounding_cost_credits", 0)
                if grounding_credits > 0:
                    token_records.append({
                        "model_name": "grounding",
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "grounding_cost_credits": grounding_credits,
                    })

        # Surface agent failures before the metrics flush below: flag the run in
        # LangSmith (otherwise recorded as successful, since we return a graceful
        # fallback and never raise) and emit a queryable metric.
        if is_error_response:
            record_run_error(
                f"agent produced no usable response "
                f"(intent={intent}, action={agent_result.get('action')})"
            )
            events.emit("metric", {
                "name": "turn_failed",
                "intent": intent,
                "owner_saga": agent_result.get("owner_saga"),
                "action": agent_result.get("action"),
            })

        # ── 6. Save history + metrics + deduct credits ──────────────────────
        # Skip credit deduction when the agent failed to produce a useful response
        # (AFC limit hit, empty response, or explicit ERROR action). The LLM calls
        # still happened, but charging the user for a broken response is wrong.
        _save_and_finish(
            self, user_doc, user_id, message_text, response_text,
            telegram_user_id, token_records if not is_error_response else [],
            t_total, events, intent,
            owner_saga=agent_result.get("owner_saga"),
        )

        if is_error_response:
            logger.error(
                "Agent failed to produce a response (action=%s, text=%r). Credits NOT deducted.",
                agent_result.get("action"), response_text[:120],
            )
        logger.info("\n=== FINAL OUTPUT ===\n%s\n===================", response_text)
        # Surface the owner saga's slot question to the channels (Task 43) so they
        # can render tappable choices. Wire form (or None for a free-text/no-slot
        # turn); error turns never carry a usable slot prompt.
        slot_request = agent_result.get("slot_request")
        slot_wire = (
            slot_request.to_wire()
            if slot_request is not None and not is_error_response
            else None
        )
        return {"text": response_text, "action": "RESPONSE", "slot_request": slot_wire}

    # ── selection (Task 43 — deterministic tapped choice, no router/LLM) ─────

    def _planning_saga(self):
        """The registered PlanningSaga instance (owns slot routing). The
        dispatcher always registers exactly one."""
        for saga in self._dispatcher.sagas:
            if getattr(saga, "name", "") == "PlanningSaga":
                return saga
        raise RuntimeError("PlanningSaga not registered in the dispatcher.")

    def _process_selection(
        self,
        *,
        user_doc: Dict[str, Any],
        user_id: str,
        telegram_user_id: str,
        selection: Dict[str, Any],
        channel: str,
        status_callback: Optional[Callable[[dict], None]] = None,
        delta_callback: Optional[Callable[[dict], None]] = None,
    ) -> Dict[str, Any]:
        """Apply a tapped multiple-choice value to the active trip
        deterministically (no router, no slot_extractor — Task 43), then ask the
        next missing slot (or build the plan when the trip is complete).

        The chosen ``value`` is re-validated against the slot's legal options
        before any write (trust-but-verify, §5): an illegal/free-text/unknown
        slot is ignored (logged WARN) and the same slot is simply re-asked."""
        t_total = time.time()
        token_records: list[Dict[str, Any]] = []
        events = EventEmitter(
            user_id=user_id, trip_id=None,
            on_status=status_callback, on_delta=delta_callback,
        )

        if not credit_manager.has_credits(user_doc):
            return {"text": credit_manager.CREDITS_EXHAUSTED_MSG,
                    "action": "NO_CREDITS", "slot_request": None}
        restriction_msg = off_topic_guard.is_restricted(user_doc)
        if restriction_msg:
            return {"text": restriction_msg, "action": "RESTRICTED", "slot_request": None}

        slot = str(selection.get("slot") or "")
        values = [str(v) for v in (selection.get("values") or [])]

        # 1. Resolve (or create) the trip this slot-fill belongs to.
        trip: Optional[Dict[str, Any]] = None
        if user_id:
            try:
                summaries = [
                    s.model_dump() for s in self._trip_repo.list_trip_summaries(user_id)
                ]
            except Exception:
                logger.exception("Selection: failed to list trip summaries for %s", user_id)
                summaries = []
            chosen = resolve_active_trip(summaries, "", {})
            if chosen:
                try:
                    trip_model = self._trip_repo.get_trip(chosen["id"])
                    trip = trip_model.model_dump() if trip_model else None
                except Exception:
                    logger.exception("Selection: failed to hydrate trip %s", chosen.get("id"))
            if trip is None:
                # No trip to attach to (deleted in another tab, fresh user). The
                # PlanningSaga's zero-trip path expects a row to exist.
                try:
                    trip = self._trip_repo.upsert_trip(user_id, {}).model_dump()
                except Exception:
                    logger.exception("Selection: failed to create trip for %s", user_id)

        events.trip_id = trip.get("id") if trip else None

        # 2. Validate + apply the chosen value(s) deterministically as one write
        #    (multi-select slots like travelers aggregate; 'skip' is exclusive).
        se = slot_values_to_side_effect(trip, slot, values)
        if se is None:
            logger.warning(
                "Selection rejected (illegal/free-text/no-trip) slot=%s channel=%s",
                slot, channel,
            )
        else:
            self._apply_side_effects(user_id, [se])
            events.emit("metric", {
                "name": "slot_selected", "slot": slot,
                "value": ",".join(values), "channel": channel,
            })
            # Merge locally so the next-step decision sees the write without a
            # re-read. The side-effect payload already holds the fully-merged
            # JSONB section (preferences / travelers), so copy those sections.
            if trip is not None:
                for key, val in se.payload.items():
                    if key != "id":
                        trip[key] = val

        # 3. Decide the next step (no extraction). A label string is passed only
        #    for trace readability; the saga never parses it on this path.
        conv_context = self.conversation_manager.build_context_block(user_doc)
        state: SagaState = {
            "intent": "PLAN",
            "entities": {},
            "current_time": _current_time_str(),
            "trip_id": trip.get("id") if trip else None,
            "message_text": "",
            "trip_directive": "continue",
        }
        label = " / ".join(values) if values else slot
        try:
            result = self._planning_saga().run_after_selection(
                label, user_doc, trip, state, conv_context, events,
            )
            self._apply_side_effects(user_id, result.side_effects)
        except Exception:
            logger.exception("Selection: planning continuation failed for %s", user_id)
            result = None

        response_text = (result.text if result else "") or (
            "I had trouble continuing just now. Please try again."
        )

        # Log delegated-agent usage (a completed trip may have run the planner).
        if result is not None and getattr(result, "_raw_response", None) is not None:
            raw_agent = result._raw_response
            if hasattr(raw_agent, "usage_metadata"):
                agent_usage = usage_tracker.log_and_accumulate(
                    agent_name="planner", model_name="gemini-3.5-flash",
                    user_id=telegram_user_id, response=raw_agent,
                    latency_ms=getattr(result, "_latency_ms", 0),
                )
                if agent_usage.get("total_tokens", 0) > 0:
                    token_records.append(agent_usage)

        _save_and_finish(
            self, user_doc, user_id, label, response_text,
            telegram_user_id, token_records, t_total, events, "PLAN",
            owner_saga="PlanningSaga",
        )

        slot_wire = (
            result.slot_request.to_wire()
            if result is not None and result.slot_request is not None
            else None
        )
        return {"text": response_text, "action": "RESPONSE", "slot_request": slot_wire}

    # ── saga dispatch ───────────────────────────────────────────────────────

    def _dispatch_sagas(
        self,
        *,
        intent: str,
        user_doc: Dict[str, Any],
        user_id: Optional[str],
        message_text: str,
        conv_context: str,
        current_time: str,
        preference_raw: Optional[str],
        router_response: Optional[str],
        entities: Dict[str, Any],
        trip_directive: str,
        events: EventEmitter,
    ) -> Dict[str, Any]:
        """Resolve the active trip, select the owner saga (+ listeners), run
        them, apply their side effects, and return an agent_result dict shaped
        like the old `_dispatch` so downstream token logging is unchanged."""
        # 1. Resolve which trip this turn is about, honouring the Router's
        #    trip_directive (task 44): "new" ignores existing trips (a fresh one
        #    is created below) and reports which trip, if any, was set aside.
        trip: Optional[Dict[str, Any]] = None
        superseded_title: Optional[str] = None
        if user_id:
            try:
                summaries = [
                    s.model_dump() for s in self._trip_repo.list_trip_summaries(user_id)
                ]
            except Exception:
                logger.exception("Failed to list trip summaries for user %s", user_id)
                summaries = []
            chosen, superseded_title, _create_new = resolve_trip_focus(
                summaries, message_text, entities, trip_directive
            )
            if chosen:
                try:
                    trip_model = self._trip_repo.get_trip(chosen["id"])
                    trip = trip_model.model_dump() if trip_model else None
                except Exception:
                    logger.exception("Failed to hydrate trip %s", chosen.get("id"))

        # 2. Per-turn state (NOT persisted — task 36 §4.1 #2).
        state: SagaState = {
            "intent": intent,
            "entities": entities,
            "current_time": current_time,
            "preference_raw": preference_raw,
            "router_response": router_response,
            "trip_id": trip.get("id") if trip else None,
            "message_text": message_text,
            "trip_directive": trip_directive,
            "superseded_trip_title": superseded_title,
        }

        # 3. Select owner + listeners (deterministic, no LLM).
        owner, listeners = self._dispatcher.select(intent, entities, trip, state)
        _emit_status(events, "saga_selected", getattr(owner, "name", None))

        # 4. Create a fresh DREAMING trip when there's no trip in focus and the
        #    owner needs one — either the zero-trip path, or a "new" directive
        #    that deliberately set the existing trip aside (task 44).
        if trip is None and user_id and getattr(owner, "name", "") in (
            "PlanningSaga", "DiscoverySaga"
        ):
            try:
                trip = self._trip_repo.upsert_trip(user_id, {}).model_dump()
                state["trip_id"] = trip.get("id")
            except Exception:
                logger.exception("Failed to create initial trip for user %s", user_id)

        # 5. Bind trip_id so every metric row this turn carries it.
        events.trip_id = state.get("trip_id")

        # 6. Listeners first (idempotent side effects), then the owner.
        for saga in listeners:
            try:
                listener_result = saga.run(
                    message_text, user_doc, trip, state, conv_context, events
                )
                self._apply_side_effects(user_id, listener_result.side_effects)
            except Exception:
                logger.exception(
                    "Listener saga %s failed.", getattr(saga, "name", "?")
                )

        _emit_status(events, "composing")
        result = owner.run(message_text, user_doc, trip, state, conv_context, events)
        self._apply_side_effects(user_id, result.side_effects)

        return {
            "text": result.text or "",
            "action": "RESPONSE" if result.text else "ERROR",
            "_raw_response": result._raw_response,
            "_latency_ms": result._latency_ms,
            "_search_responses": result._search_responses,
            "owner_saga": getattr(owner, "name", ""),
            "slot_request": result.slot_request,
        }

    def _apply_side_effects(self, user_id: Optional[str], side_effects: list) -> None:
        """Persist a saga's side effects via the TripRepository. Best-effort:
        one failed write never aborts the turn."""
        if not user_id:
            return
        for se in side_effects:
            try:
                self._trip_repo.apply_side_effect(user_id, se)
            except Exception:
                logger.exception(
                    "apply_side_effect failed for kind=%s",
                    getattr(se, "kind", "?"),
                )


# ── private helpers ──────────────────────────────────────────────────────────

def _save_and_finish(
    coordinator: OrchestratorAgent,
    user_doc: Dict[str, Any],
    user_id: Optional[str],
    message_text: str,
    response_text: str,
    telegram_user_id: str,
    token_records: list,
    t_total: float,
    events: EventEmitter,
    intent: str,
    owner_saga: Optional[str] = None,
) -> None:
    """Save history, record metrics, and deduct credits."""
    if user_id:
        coordinator.conversation_manager.append_and_save(
            user_doc, user_id, message_text, response_text
        )

    metrics_tracker.record_interaction(
        user_id=telegram_user_id,
        is_new_user=False,
    )

    total_cost_credits = 0.0
    if token_records and user_id:
        try:
            usage = credit_manager.record_usage_and_bill(
                user_id=user_id,
                token_records=token_records,
                default_agent_name="orchestrator",
                run_async=True,
            )
            if hasattr(usage, "total_cost_credits"):
                total_cost_credits = usage.total_cost_credits
        except Exception:
            logger.exception("Failed to bill and record metrics for turn.")

    latency_ms = int((time.time() - t_total) * 1000)
    events.emit("metric", {
        "name": "turn_completed",
        "intent": intent,
        "owner_saga": owner_saga,
        "latency_ms": latency_ms,
        "credits": total_cost_credits,
        "tokens": sum(r.get("total_tokens", 0) for r in token_records),
    })
    events.flush_metrics()

    logger.info("⏱ TOTAL: %s", _elapsed(t_total))

