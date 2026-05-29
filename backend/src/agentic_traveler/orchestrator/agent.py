"""
Orchestrator Coordinator — the single entry point for user messages.

Architecture (v2 — Thin Router + Specialized Agents):
    1. Fetch user profile + credit gate.
    2. Check off-topic restriction.
    3. Build conversation context.
    4. RouterAgent classifies intent (CHAT | TRIP | PLAN | OFF_TOPIC)
       and handles lightweight tools (preferences, feedback, credits).
    5. Dispatch to the appropriate specialized agent:
       - CHAT      → ChatAgent   (gemini-3.1-flash-lite)
       - TRIP      → TripAgent   (gemini-3.5-flash)
       - PLAN      → PlannerAgent (gemini-3.5-flash)
       - OFF_TOPIC → router's natural redirection; off_topic_guard
                     increments counter silently.
    6. Log token usage for router + agent separately.
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
from agentic_traveler.orchestrator.conversation_manager import ConversationManager
from agentic_traveler.orchestrator.router_agent import RouterAgent
from agentic_traveler.orchestrator.chat_agent import ChatAgent
from agentic_traveler.orchestrator.trip_agent import TripAgent
from agentic_traveler.orchestrator.planner_agent import PlannerAgent
from agentic_traveler.tools.user_repo import UserRepository

logger = logging.getLogger(__name__)


def _elapsed(t0: float) -> str:
    """Return formatted elapsed time since *t0*."""
    return f"{(time.time() - t0) * 1000:.0f}ms"


def _current_time_str() -> str:
    """Return a human-readable current datetime string."""
    now = datetime.datetime.now().astimezone()
    return now.strftime("%A, %Y-%m-%d %H:%M:%S %Z")


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
        self._chat_agent = ChatAgent(client=self._client)
        self._trip_agent = TripAgent(client=self._client)
        self._planner_agent = PlannerAgent(client=self._client)

    def process_request(
        self,
        telegram_user_id: str,
        message_text: str,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Telegram entry point. Resolves the user by Telegram ID, then dispatches.

        Returns {"text": str, "action": str}.
        """
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
        return self._process_user_doc(
            user_doc=user_doc,
            user_id=user_id,
            telegram_user_id=telegram_user_id,
            message_text=message_text,
            status_callback=status_callback,
        )

    def process_request_for_user(
        self,
        user_id: str,
        message_text: str,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Web entry point. The user is already resolved by Supabase JWT → users.id;
        we fetch the assembled user_doc and dispatch.

        Returns {"text": str, "action": str}.
        """
        user_doc = self.user_tool.get_user_by_id(user_id)
        if not user_doc:
            logger.warning("process_request_for_user: no user row for id=%s", user_id)
            return {
                "text": "Your profile is missing. Please complete the travel profile to continue.",
                "action": "ONBOARDING_REQUIRED",
            }
        # For web users we don't have a Telegram ID; use the internal user_id as the
        # analytics/logging key. usage_tracker just needs a stable string identifier.
        return self._process_user_doc(
            user_doc=user_doc,
            user_id=user_id,
            telegram_user_id=user_id,
            message_text=message_text,
            status_callback=status_callback,
        )

    def _process_user_doc(
        self,
        user_doc: Dict[str, Any],
        user_id: str,
        telegram_user_id: str,
        message_text: str,
        status_callback: Optional[Callable[[str], None]] = None,
    ) -> Dict[str, Any]:
        """
        Shared post-lookup pipeline. Used by both the Telegram and web entry
        points so credit gating, off-topic enforcement, dispatch, and history
        save behave identically across channels.
        """
        t_total = time.time()
        token_records: list[Dict[str, Any]] = []

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
        t = time.time()
        conv_context = self.conversation_manager.build_context_block(user_doc)
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
            conversation_context=conv_context,
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
        preference_updated = router_result.get("preference_updated")
        router_response = router_result.get("response")

        logger.info("Intent: %s | Preference update: %s", intent, preference_updated)

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
                telegram_user_id, token_records, t_total,
            )
            return {"text": response_text, "action": "RESPONSE"}

        # If the router provided a direct response (e.g., for get_my_credits)
        # Only short-circuit for CHAT intent — TRIP and PLAN must always reach
        # their specialized agents (router_response for those is a bug side-effect).
        elif intent == "CHAT" and router_response:
            if user_id:
                off_topic_guard.reset(user_id)
            _save_and_finish(
                self, user_doc, user_id, message_text, router_response,
                telegram_user_id, token_records, t_total,
            )
            return {"text": router_response, "action": "RESPONSE"}

        # ── 5b. Travel intents — reset off-topic counter ────────────────────
        if user_id:
            off_topic_guard.reset(user_id)

        # ── 5c. Dispatch to specialized agent ───────────────────────────────
        agent_result = _dispatch(
            self, intent, user_doc, message_text, conv_context,
            current_time, preference_updated, status_callback,
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

        # ── 6. Save history + metrics + deduct credits ──────────────────────
        # Skip credit deduction when the agent failed to produce a useful response
        # (AFC limit hit, empty response, or explicit ERROR action). The LLM calls
        # still happened, but charging the user for a broken response is wrong.
        _save_and_finish(
            self, user_doc, user_id, message_text, response_text,
            telegram_user_id, token_records if not is_error_response else [],
            t_total,
        )

        if is_error_response:
            logger.error(
                "Agent failed to produce a response (action=%s, text=%r). Credits NOT deducted.",
                agent_result.get("action"), response_text[:120],
            )
        logger.info("\n=== FINAL OUTPUT ===\n%s\n===================", response_text)
        return {"text": response_text, "action": "RESPONSE"}


# ── private helpers ──────────────────────────────────────────────────────────

def _dispatch(
    coordinator: OrchestratorAgent,
    intent: str,
    user_doc: Dict[str, Any],
    message: str,
    conv_context: str,
    current_time: str,
    preference_updated: Optional[Dict[str, str]],
    status_callback: Optional[Callable[[str], None]],
) -> Dict[str, Any]:
    """Dispatch to the correct specialized agent based on intent."""
    if intent == "TRIP":
        if status_callback:
            status_callback("I'm scouting the globe for the perfect spots for you! Just a moment... 🌍")
        return coordinator._trip_agent.process_request(
            user_doc=user_doc,
            message=message,
            conversation_context=conv_context,
            current_time=current_time,
            preference_updated=preference_updated,
        )
    elif intent == "PLAN":
        if status_callback:
            status_callback("I'm putting together a detailed day-by-day plan for you! Give me a few seconds... 🗺️")
        return coordinator._planner_agent.process_request(
            user_doc=user_doc,
            message=message,
            conversation_context=conv_context,
            current_time=current_time,
            preference_updated=preference_updated,
        )
    else:  # CHAT (default)
        return coordinator._chat_agent.process_request(
            user_doc=user_doc,
            message=message,
            conversation_context=conv_context,
            current_time=current_time,
            preference_updated=preference_updated,
        )


def _save_and_finish(
    coordinator: OrchestratorAgent,
    user_doc: Dict[str, Any],
    user_id: Optional[str],
    message_text: str,
    response_text: str,
    telegram_user_id: str,
    token_records: list,
    t_total: float,
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

    if token_records and user_id:
        cost = credit_manager.calculate_cost(token_records)
        if cost > 0:
            credit_manager.deduct_credits_async(user_id, cost)

        # Group token records by model_name to aggregate tokens & grounding
        by_model = {}
        for rec in token_records:
            model = rec.get("model_name")
            if not model:
                continue
            if model not in by_model:
                by_model[model] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "grounding_used": False,
                    "grounding_count": 0,
                    "grounding_cost_credits": 0,
                }
            by_model[model]["input_tokens"] += rec.get("input_tokens", 0)
            by_model[model]["output_tokens"] += rec.get("output_tokens", 0)
            if rec.get("grounding_used"):
                by_model[model]["grounding_used"] = True
                by_model[model]["grounding_count"] += rec.get("grounding_count", 1)
                by_model[model]["grounding_cost_credits"] += rec.get("grounding_cost_credits", 0)

        # For each model, calculate the exact aggregated cost for the turn and record it
        for model_name, usage in by_model.items():
            # Build list of records for this model to pass to calculate_cost
            recs = [{
                "model_name": model_name,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            }]
            if usage["grounding_used"]:
                recs.append({
                    "model_name": "grounding",
                    "grounding_count": usage["grounding_count"],
                    "grounding_cost_credits": usage["grounding_cost_credits"]
                })
            
            # Calculate exact turn-level aggregated cost for this model
            model_cost = credit_manager.calculate_cost(recs)
            
            # 1. Record in weekly global metrics_tracker
            try:
                metrics_tracker.record_token_usage(
                    agent_name="orchestrator",
                    model_name=model_name,
                    input_tokens=usage["input_tokens"],
                    output_tokens=usage["output_tokens"],
                    total_cost_credits=model_cost,
                )
            except Exception:
                logger.exception("Failed to record aggregated token usage in metrics_tracker.")

            # Record grounding used globally if any
            if usage["grounding_used"]:
                try:
                    metrics_tracker.record_grounding_used()
                except Exception:
                    logger.exception("Failed to record grounding metric in metrics_tracker.")

            # 2. Record in per-user usage_tracking table
            resolved_uuid = usage_tracker._resolve_user_uuid(telegram_user_id)
            if resolved_uuid:
                try:
                    from agentic_traveler.tools.db_client import get_db
                    get_db().rpc("accumulate_user_usage", {
                        "p_user_id": resolved_uuid,
                        "p_model_name": model_name,
                        "p_input_tokens": usage["input_tokens"],
                        "p_output_tokens": usage["output_tokens"],
                        "p_is_grounded": 1 if usage["grounding_used"] else 0,
                        "p_cost_credits": model_cost
                    }).execute()
                except Exception:
                    logger.warning(
                        "Telemetry warning: Failed to accumulate usage in usage_tracking table "
                        "for user_id=%s model=%s. Bypassing.",
                        resolved_uuid, model_name, exc_info=True
                    )

    logger.info("⏱ TOTAL: %s", _elapsed(t_total))
