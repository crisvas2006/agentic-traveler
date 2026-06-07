"""
Integration tests for RouterAgent — intent classification and tool call decisions.

Tests the REAL Gemini Flash Lite model with realistic user context to verify:
  - Correct intent classification across varied conversational scenarios
  - save_stated_preference fires only for genuinely new preferences
  - Recall questions, banter, and already-known preferences do NOT trigger saves
  - save_app_feedback fires only for explicit app feedback, not travel frustration
  - Complex / mixed messages are handled correctly end-to-end

Profile and feedback writes are intercepted (MagicMock) — no Supabase writes occur.
The only real API calls are to Gemini.

Run with:
    pytest backend/tests -m integration -k test_router_agent -v
    # or the full integration suite:
    pytest backend/tests -m integration -v
"""

import time
import pytest
from dataclasses import dataclass
from unittest.mock import MagicMock
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.integration

# Seconds to sleep after each test to stay within free-tier rate limits.
# 31 tests × 1 s ≈ 31 s total overhead — acceptable for an integration suite.
_THROTTLE_SECONDS = 1


# ── result wrapper ─────────────────────────────────────────────────────────────

@dataclass
class R:
    """
    Wraps the raw router.classify output and provides assertion helpers that
    produce a self-contained diagnostic on failure — no log-diving required.
    """
    message: str
    intent: str
    preference_raw: str | None
    response: str | None
    save_calls: list[str]        # preference_raw args passed to save_preference
    feedback_calls: list[dict]   # {category, text} kwargs from each record() call
    latency_ms: float
    api_error: bool              # True when router fell back due to API/429 error

    def _diag(self) -> str:
        """One-block diagnostic shown in every assertion failure."""
        return (
            f"\n  ┌─ RouterResult {'─' * 40}\n"
            f"  │ message:        {self.message!r}\n"
            f"  │ intent:         {self.intent}\n"
            f"  │ preference_raw: {self.preference_raw!r}\n"
            f"  │ save_calls({len(self.save_calls)}):  {self.save_calls}\n"
            f"  │ feedback_calls: {self.feedback_calls}\n"
            f"  │ latency:        {self.latency_ms:.0f}ms\n"
            f"  └{'─' * 55}"
        )

    # ── intent ─────────────────────────────────────────────────────────────────

    def assert_intent(self, *expected: str) -> None:
        """Assert intent is one of the given values."""
        assert self.intent in expected, (
            f"Intent mismatch{self._diag()}\n"
            f"  expected: {' | '.join(expected)}\n"
            f"  actual:   {self.intent}"
        )

    # ── save_stated_preference ─────────────────────────────────────────────────

    def assert_no_save(self) -> None:
        """Assert save_stated_preference was NOT called."""
        assert not self.save_calls, (
            f"save_stated_preference should NOT have been called "
            f"but fired {len(self.save_calls)} time(s){self._diag()}\n"
            f"  saved args: {self.save_calls}"
        )

    def assert_saved_once(self, containing: str | None = None) -> None:
        """Assert save_stated_preference was called exactly once, optionally checking arg content."""
        assert len(self.save_calls) == 1, (
            f"save_stated_preference should have been called exactly once, "
            f"got {len(self.save_calls)} call(s){self._diag()}\n"
            f"  saved args: {self.save_calls}"
        )
        if containing:
            assert containing.lower() in self.save_calls[0].lower(), (
                f"save_stated_preference was called once but arg doesn't contain {containing!r}{self._diag()}\n"
                f"  actual arg: {self.save_calls[0]!r}"
            )

    # ── save_app_feedback ──────────────────────────────────────────────────────

    def assert_no_feedback(self) -> None:
        """Assert save_app_feedback was NOT called."""
        assert not self.feedback_calls, (
            f"save_app_feedback should NOT have been called "
            f"but fired {len(self.feedback_calls)} time(s){self._diag()}\n"
            f"  calls: {self.feedback_calls}"
        )

    def assert_feedback_once(self, category: str | None = None) -> None:
        """Assert save_app_feedback was called exactly once, optionally checking category."""
        assert len(self.feedback_calls) == 1, (
            f"save_app_feedback should have been called exactly once, "
            f"got {len(self.feedback_calls)} call(s){self._diag()}"
        )
        if category:
            actual = self.feedback_calls[0].get("category")
            assert actual == category, (
                f"save_app_feedback category mismatch{self._diag()}\n"
                f"  expected: {category!r}\n"
                f"  actual:   {actual!r}"
            )

    # ── credits ────────────────────────────────────────────────────────────────

    def assert_credits_response(self) -> None:
        """Assert result['response'] is non-None and mentions credits."""
        assert self.response is not None, (
            f"Expected a credits balance response but response is None{self._diag()}"
        )
        assert "credit" in self.response.lower(), (
            f"response doesn't mention 'credit'{self._diag()}\n"
            f"  actual response: {self.response!r}"
        )

    def assert_no_credits_response(self) -> None:
        """Assert result['response'] is None (no credit-balance answer was produced)."""
        assert self.response is None, (
            f"Expected no credits response but got: {self.response!r}{self._diag()}"
        )


# ── helpers ────────────────────────────────────────────────────────────────────

def _ctx(*pairs: tuple[str, str]) -> str:
    """Build a plain-text conversation history block from (role, text) pairs."""
    return "\n".join(f"{role.capitalize()}: {text}" for role, text in pairs)


def _user_doc(
    additional_info: str = "",
    extra_prefs: dict | None = None,
    recent_messages: list[tuple[str, str]] | None = None,
) -> dict:
    """
    Build a minimal but realistic user_doc.

    additional_info → surfaced verbatim under "Additional Info/Constraints" in
                      the router's Known Preferences block.
    extra_prefs     → arbitrary keys merged into profile_data.
    recent_messages → (role, text) pairs stored as conversation_history.
    """
    profile_data: dict = {}
    if additional_info:
        profile_data["additional_info"] = additional_info
    if extra_prefs:
        profile_data.update(extra_prefs)

    msgs = [{"role": r, "text": t} for r, t in (recent_messages or [])]

    return {
        "user_name": "Alex",
        "user_profile": {
            "profile_data": profile_data,
            "summary": "A well-travelled test user.",
        },
        "conversation_history": {
            "recent_messages": msgs,
            "summary": "",
        },
        "credits": {"balance": 200},
        "off_topic": {"count": 0, "last_flagged_ts": None, "restricted_until": None},
        "location": "London, UK",
    }


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def router():
    """
    Real RouterAgent backed by a live Gemini API client.
    Created once per module to avoid repeated client initialisation overhead.
    """
    from agentic_traveler.orchestrator.router_agent import RouterAgent
    return RouterAgent()


@pytest.fixture(autouse=True)
def throttle():
    """
    Sleep after every test to stay within free-tier Gemini rate limits.
    Without this, 31 sequential calls quickly hit 429 RESOURCE_EXHAUSTED.
    """
    yield
    time.sleep(_THROTTLE_SECONDS)


def _classify(
    router,
    message: str,
    *,
    user_doc: dict | None = None,
    context: str = "",
) -> R:
    """
    Call router.classify with mocked side-effects and return an R result wrapper.

    Patching at the instance level means no Supabase writes occur and we can
    assert exactly which tools the model decided to invoke.

    Skips the test automatically if the API returned a 429 / error (raw_response
    is None and intent defaults to CHAT) so rate-limit transients don't fail the
    suite — they show as SKIPPED with an explanatory message.
    """
    if user_doc is None:
        user_doc = _user_doc()

    save_mock = MagicMock()
    feedback_mock = MagicMock()
    router._profile_agent.save_preference = save_mock
    router._feedback_tool.record = feedback_mock

    raw = router.classify(
        message=message,
        user_doc=user_doc,
        user_id="00000000-0000-0000-0000-000000000001",
        telegram_user_id="test_tg_router_integration",
        user_name="Alex",
        current_time="Sunday, 2026-06-07 15:00:00 UTC",
        conversation_context=context,
    )

    # Detect silent API errors: router swallows exceptions and returns CHAT with
    # raw_response=None. Skip rather than fail so transient 429s don't break CI.
    api_error = raw.get("raw_response") is None
    if api_error:
        pytest.skip(
            f"Gemini API error for message={message!r} — raw_response is None "
            f"(likely 429 RESOURCE_EXHAUSTED). Rerun after quota resets."
        )

    save_calls = [str(c[0][0]) for c in save_mock.call_args_list]
    feedback_calls = [
        {"category": c.kwargs.get("category"), "text": (c.kwargs.get("text") or "")[:60]}
        for c in feedback_mock.call_args_list
    ]

    return R(
        message=message,
        intent=raw.get("intent", ""),
        preference_raw=raw.get("preference_raw"),
        response=raw.get("response"),
        save_calls=save_calls,
        feedback_calls=feedback_calls,
        latency_ms=raw.get("latency_ms", 0.0),
        api_error=api_error,
    )


# ── Group 1: Intent classification — unambiguous cases ────────────────────────

def test_greeting_is_chat_no_tools(router):
    """A plain greeting must be CHAT with no tool calls."""
    r = _classify(router, "Hey there!")
    r.assert_intent("CHAT")
    r.assert_no_save()
    r.assert_no_feedback()


def test_standalone_thanks_is_chat(router):
    "'Thanks!' is conversational — no intent to save anything."
    r = _classify(router, "Thanks!")
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_open_travel_question_is_trip(router):
    """An open destination question (no day-count framing) should be TRIP."""
    r = _classify(router, "What's the best neighbourhood to stay in when visiting Lisbon?")
    r.assert_intent("TRIP")
    r.assert_no_save()


def test_explicit_itinerary_request_is_plan(router):
    """An explicit request for a structured day-by-day plan should be PLAN."""
    r = _classify(router, "Build me a full day-by-day itinerary for 5 days in Tokyo.")
    r.assert_intent("PLAN")


def test_off_topic_gets_redirect_response(router):
    """A clearly off-topic message → OFF_TOPIC with a non-empty warm redirect; no tool calls."""
    r = _classify(router, "Can you help me debug this Python stack trace from my work project?")
    r.assert_intent("OFF_TOPIC")
    assert r.response and len(r.response) > 10, (
        f"OFF_TOPIC should include a warm redirect response but got: {r.response!r}{r._diag()}"
    )
    r.assert_no_save()
    r.assert_no_feedback()  # off-topic request must NOT be treated as negative app feedback


def test_in_trip_distress_is_trip(router):
    """'I'm tired and it's raining' in an active-trip context → TRIP (in-trip help)."""
    r = _classify(
        router,
        "I'm tired and it's raining outside. What should I do right now?",
        context=_ctx(
            ("user", "I'm in Marrakech for the next two days"),
            ("agent", "Great! The medina is lively this time of year."),
        ),
    )
    r.assert_intent("TRIP")


# ── Group 2: Preference saves — should fire ───────────────────────────────────

def test_new_dietary_preference_saved(router):
    """First-time dietary declaration with empty profile → preference saved, arg contains 'vegetarian'."""
    r = _classify(
        router,
        "By the way, I'm vegetarian — keep that in mind for all food suggestions.",
        user_doc=_user_doc(),
    )
    r.assert_intent("CHAT")
    r.assert_saved_once(containing="vegetarian")


def test_new_hotel_chain_preference_saved(router):
    """Explicit hotel brand preference not in Known Prefs → saved."""
    r = _classify(
        router,
        "I always book Ibis Hotels — love their consistency.",
        user_doc=_user_doc(),
    )
    r.assert_intent("CHAT")
    r.assert_saved_once()


def test_packing_habit_stated_for_first_time_is_saved(router):
    """Explicit packing habit not previously known → saved, arg contains 'toothbrush'."""
    r = _classify(
        router,
        "I always put a toothbrush in my case, no matter how short the trip.",
        user_doc=_user_doc(),
    )
    r.assert_saved_once(containing="toothbrush")


def test_preference_embedded_in_trip_question(router):
    """Preference stated alongside a travel question → saved AND intent TRIP."""
    r = _classify(
        router,
        "I only travel solo — what are the best spots in Prague for a solo traveller?",
        user_doc=_user_doc(),
    )
    r.assert_intent("TRIP")
    r.assert_saved_once()


def test_preference_embedded_in_plan_request(router):
    """Preference stated alongside a planning request → saved AND intent PLAN."""
    r = _classify(
        router,
        "I always prefer budget accommodation. Can you plan a 3-day trip to Rome?",
        user_doc=_user_doc(),
    )
    r.assert_intent("PLAN")
    r.assert_saved_once()


# ── Group 3: No save — recall questions ───────────────────────────────────────

def test_recall_what_do_i_always_take_does_not_save(router):
    """
    THE KEY REGRESSION: 'What do I always take with me?' is a recall question.
    The toothbrush/toothpick preference is already in conversation history —
    the model must not re-save it. This was the exact failure mode that
    motivated the improved prompt design.
    """
    r = _classify(
        router,
        "What do I always take with me?",
        context=_ctx(
            ("user", "I always put a toothbrush in my case"),
            ("agent", "Noted — toothbrush locked in!"),
            ("user", "And always a toothpick as well"),
            ("agent", "Got it — toothbrush and toothpick, both noted."),
        ),
    )
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_asking_for_my_preference_list_does_not_save(router):
    """'What are my travel preferences?' is a query about stored data, not a new declaration."""
    r = _classify(
        router,
        "What are my travel preferences?",
        user_doc=_user_doc(additional_info="Prefers Ibis Hotels. Vegetarian. Avoids crowds."),
    )
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_recall_diet_from_history_does_not_save(router):
    """Asking what was said about food should not re-save dietary info already in history."""
    r = _classify(
        router,
        "What did I tell you about my diet again?",
        context=_ctx(
            ("user", "Oh, I forgot to mention — I'm vegan"),
            ("agent", "Noted — keeping that in mind for all food suggestions!"),
        ),
    )
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_vague_preferences_check_does_not_save(router):
    """
    'You still have my preferences saved, right?' is a pure confirmation with no
    preference content — nothing for the model to extract or save.
    """
    r = _classify(
        router,
        "You still have my preferences saved, right?",
        user_doc=_user_doc(additional_info="Prefers solo travel. Vegetarian. Avoids crowds."),
    )
    r.assert_intent("CHAT")
    r.assert_no_save()


# ── Group 4: No save — relational / banter ────────────────────────────────────

def test_rhetorical_question_about_rapport_no_save(router):
    """'Do you think I like you?' is playful banter — nothing to save."""
    r = _classify(router, "Do you think I like you?")
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_enjoying_conversation_is_not_a_travel_preference(router):
    """Expressing enjoyment of the chat is relational — not a travel preference."""
    r = _classify(router, "I really enjoy our conversations, you always seem to get me.")
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_planning_frustration_is_not_a_preference(router):
    """Emotional venting about planning is not a declarative travel preference."""
    r = _classify(router, "Ugh, I hate all this planning.")
    r.assert_intent("CHAT")
    r.assert_no_save()


# ── Group 5: App feedback detection ───────────────────────────────────────────

def test_explicit_praise_triggers_positive_feedback(router):
    """Explicit app praise → save_app_feedback with category='positive'."""
    r = _classify(router, "This app is absolutely amazing — I recommend it to all my friends!")
    r.assert_intent("CHAT")
    r.assert_feedback_once(category="positive")


def test_explicit_complaint_triggers_negative_feedback(router):
    """Explicit bot complaint → save_app_feedback with category='negative'."""
    r = _classify(router, "This app never understands what I mean, it's so frustrating.")
    r.assert_intent("CHAT")
    r.assert_feedback_once(category="negative")


def test_feature_request_triggers_suggestion_feedback(router):
    """App feature request → save_app_feedback with category='suggestion'."""
    r = _classify(router, "You should really add a dark mode to the app.")
    r.assert_intent("CHAT")
    r.assert_feedback_once(category="suggestion")


def test_hotel_complaint_is_not_app_feedback(router):
    """Frustration about a hotel is travel context, not feedback about the app."""
    r = _classify(router, "The hotel in Lisbon was absolutely terrible — I'm so annoyed.")
    r.assert_no_feedback()


def test_weather_complaint_is_not_app_feedback(router):
    """Complaining about the weather is not feedback about the app."""
    r = _classify(router, "It's been raining for three days straight, I hate this weather.")
    r.assert_no_feedback()


# ── Group 6: Complex / multi-signal / context-sensitive ───────────────────────

def test_travel_question_remains_trip_after_banter_exchange(router):
    """
    A genuine travel question should be TRIP even after several turns of banter —
    the conversation context must not bleed over and drag it toward CHAT.
    """
    r = _classify(
        router,
        "Anyway — is Morocco a good destination in November?",
        context=_ctx(
            ("user", "Hey! How are you today?"),
            ("agent", "Doing great — what adventure are we planning?"),
            ("user", "Haha you're funny"),
            ("agent", "Ha, glad you think so!"),
        ),
    )
    r.assert_intent("TRIP")


def test_thanks_is_chat_mid_itinerary_context(router):
    """
    A simple 'thanks' during an active planning conversation should be CHAT,
    not accidentally escalated to PLAN because of the surrounding context.
    """
    r = _classify(
        router,
        "Thanks, that looks great!",
        context=_ctx(
            ("user", "Plan my 3-day Casablanca trip"),
            ("agent", "Here is a refined 3-day Casablanca itinerary: Day 1 — Hassan II Mosque..."),
        ),
    )
    r.assert_intent("CHAT")
    r.assert_no_save()


def test_feedback_and_new_preference_both_fire(router):
    """
    'Love this app, also I always prefer beach destinations' — both tools should
    fire in the same turn. This is one of the three-tools case that motivated
    maximum_remote_calls=3.
    """
    r = _classify(
        router,
        "Love this app by the way! Also, I always prefer beach destinations over cities.",
        user_doc=_user_doc(),
    )
    r.assert_intent("CHAT")
    r.assert_saved_once()
    r.assert_feedback_once()


def test_non_english_travel_question_is_trip(router):
    """
    A French travel question must be classified as TRIP regardless of language —
    the model should not mis-classify non-English input as CHAT or OFF_TOPIC.
    """
    r = _classify(router, "Qu'est-ce que je peux faire à Paris en décembre?")
    r.assert_intent("TRIP")
    r.assert_no_save()


def test_credits_query_returns_balance_info(router):
    """An explicit credit balance question → response contains balance information."""
    r = _classify(router, "How many credits do I have left?")
    r.assert_intent("CHAT")
    r.assert_credits_response()


def test_credits_mentioned_passively_does_not_query_balance(router):
    """
    Acknowledging a credit mention in passing is not an explicit balance query —
    the router must not produce a credit-balance answer proactively.
    """
    r = _classify(
        router,
        "Cool, no worries about the credits.",
        context=_ctx(("agent", "You used 3 credits for that itinerary.")),
    )
    r.assert_intent("CHAT")
    r.assert_no_credits_response()


@pytest.mark.xfail(
    strict=False,
    reason=(
        "Flash Lite occasionally re-saves a preference already in Known Preferences. "
        "Deduplication against stored context is best-effort for this model tier."
    ),
)
def test_known_preference_not_resaved(router):
    """
    Restating a preference already in Known Preferences should NOT trigger a save.
    Marked xfail(strict=False): the model sometimes does this correctly but not reliably
    enough to block CI. Failures here are signal to revisit the prompt, not regressions.
    """
    r = _classify(
        router,
        "I always book Ibis Hotels, you know that by now.",
        user_doc=_user_doc(additional_info="Exclusively books Ibis Hotels. Always Ibis brand."),
    )
    r.assert_intent("CHAT")
    r.assert_no_save()


# ── Group 7: Multi-tool turns — each tool fires once, independently ────────────

def test_preference_and_feedback_both_fire_on_chat(router):
    """
    A single CHAT message can carry both a new preference AND explicit app feedback.
    Both tools must fire exactly once — the HARD LIMIT allows multiple *different* tools
    in the same turn; it only prohibits calling the same tool twice.
    """
    r = _classify(
        router,
        "I'm vegan by the way — and honestly this app has been incredible for finding options!",
        user_doc=_user_doc(),
    )
    r.assert_intent("CHAT")
    r.assert_saved_once(containing="vegan")
    r.assert_feedback_once(category="positive")


def test_preference_and_feedback_both_fire_on_plan_request(router):
    """
    A PLAN request can simultaneously state a new preference and praise the app.
    Both tools must fire while intent resolves to PLAN.
    """
    r = _classify(
        router,
        "I never fly business class — love how practical your suggestions always are! "
        "Can you plan a 4-day trip to Lisbon for me?",
        user_doc=_user_doc(),
    )
    r.assert_intent("PLAN")
    r.assert_saved_once(containing="business class")
    r.assert_feedback_once()


def test_preference_and_feedback_both_fire_on_trip_question(router):
    """
    A travel question that also declares a preference and gives positive feedback —
    all three signals (TRIP intent, save pref, save feedback) must resolve correctly.
    """
    r = _classify(
        router,
        "I always travel light — one carry-on max. You've been super helpful so far! "
        "Anyway, what's the weather like in Bali in July?",
        user_doc=_user_doc(),
    )
    r.assert_intent("TRIP")
    # The model may extract either "I always travel light" or the carry-on elaboration —
    # both are valid spans, so only assert exactly one save occurred, not the wording.
    r.assert_saved_once()
    r.assert_feedback_once(category="positive")


def test_same_tool_is_never_called_twice(router):
    """
    Even if a message contains two distinct preference-like phrases, save_stated_preference
    must be called AT MOST ONCE — the HARD LIMIT prohibits repeating the same tool.
    """
    r = _classify(
        router,
        "I always book Ibis Hotels and I always travel with only a carry-on.",
        user_doc=_user_doc(),
    )
    r.assert_intent("CHAT")
    assert len(r.save_calls) == 1, (
        f"save_stated_preference must fire at most once per turn, "
        f"got {len(r.save_calls)} calls{r._diag()}\n"
        f"  saved args: {r.save_calls}"
    )
