"""Traveler-DNA question bank — Python mirror of ``frontend/src/lib/profile-questions.ts`` (Task 54).

Single source of truth for the questions the just-in-time elicitation engine
(Task 55) may weave into chat to build the "living" Traveler DNA. The TS registry
is the canonical author surface; this module is a hand-kept mirror (the monorepo
isolation rule means the backend cannot import a frontend file at runtime — the
Cloud Run image ships ``backend/`` only). ``tests/orchestrator/test_profile_questions.py``
guards the two against drift, mirroring the existing ``CAPABILITY_INTENTS`` sync test.

``binding`` is the key axis:
  - ``profile``    — a stable trait. Answered once, persisted to
                     ``user_profiles.profile_data.answered_questions``, reused.
  - ``flow_state`` — a current-state question (the "different I's"): re-asked each
                     time the user (re)enters the flow. Never persisted durably.

This is the SEED set; the nuanced expansion (~30–45 questions) is authored in Task 59.
"""

from __future__ import annotations

from dataclasses import dataclass

PROFILE = "profile"
FLOW_STATE = "flow_state"


@dataclass(frozen=True)
class ProfileChoiceDef:
    id: str
    label: str
    value: str


@dataclass(frozen=True)
class ProfileQuestionDef:
    id: str
    binding: str  # "profile" | "flow_state"
    prompt: str
    choices: tuple[ProfileChoiceDef, ...]
    informs: tuple[str, ...]
    category: str  # "compass" | "pulse" | "strategy" | "identity" | "state"
    cost: str  # "tap" | "flash_lite"
    allow_multi: bool = False
    tally_key: str | None = None
    hard_override_slot: str | None = None


def _c(id: str, label: str, value: str) -> ProfileChoiceDef:
    return ProfileChoiceDef(id=id, label=label, value=value)


PROFILE_QUESTIONS: tuple[ProfileQuestionDef, ...] = (
    # ── profile · compass ──────────────────────────────────────────────────
    ProfileQuestionDef(
        id="travel_company",
        binding=PROFILE,
        prompt="Who's usually in your travel bubble?",
        choices=(
            _c("solo", "Solo — just me", "solo"),
            _c("duo", "My partner", "duo"),
            _c("inner_circle", "Close friends or family", "inner_circle"),
            _c("socialite", "I meet people on the road", "socialite"),
        ),
        informs=("social_energy", "travel_company"),
        category="compass",
        cost="tap",
        tally_key="travel_bubble",
    ),
    ProfileQuestionDef(
        id="trip_success",
        binding=PROFILE,
        prompt="What makes a trip feel like a success?",
        choices=(
            _c("nature", "Nature", "nature"),
            _c("culture", "Culture & history", "culture"),
            _c("taste", "Food & markets", "taste"),
            _c("peace", "Peace & reset", "peace"),
            _c("adventure", "Adventure", "adventure"),
            _c("aesthetics", "Beautiful places", "aesthetics"),
            _c("social", "People & nightlife", "social"),
            _c("growth", "Learning & growth", "growth"),
        ),
        informs=("themes", "motivations"),
        category="compass",
        cost="tap",
        allow_multi=True,
        tally_key="trip_success",
    ),
    ProfileQuestionDef(
        id="meaning_depth",
        binding=PROFILE,
        prompt="How much does the deeper meaning of a place matter to you?",
        choices=(
            _c("seeker", "I seek meaning & connection", "seeker"),
            _c("explorer", "I enjoy it, but I'm here for the experience", "explorer"),
            _c("vacationer", "I care more about the vibe & fun", "vacationer"),
        ),
        informs=("meaning_depth", "spiritual_interest"),
        category="compass",
        cost="tap",
        tally_key="meaning_depth",
    ),
    ProfileQuestionDef(
        id="immersion",
        binding=PROFILE,
        prompt="Where's your sweet spot for local immersion?",
        choices=(
            _c("deep_end", "Eat & stay like a local", "deep_end"),
            _c("best_of_both", "Authentic, but a comfy bed", "best_of_both"),
            _c("curated", "Curated & high-end", "curated"),
        ),
        informs=("immersion", "comfort_preference"),
        category="compass",
        cost="tap",
        tally_key="immersion",
    ),
    # ── profile · pulse ────────────────────────────────────────────────────
    ProfileQuestionDef(
        id="morning_vibe",
        binding=PROFILE,
        prompt="What's your ideal morning on a trip?",
        choices=(
            _c("sunrise", "Up for the sunrise", "sunrise"),
            _c("civilized", "A civilized, slow start", "civilized"),
            _c("night_owl", "Mornings are for sleeping", "night_owl"),
        ),
        informs=("daily_rhythm",),
        category="pulse",
        cost="tap",
        tally_key="ideal_morning",
    ),
    ProfileQuestionDef(
        id="activity_intensity",
        binding=PROFILE,
        prompt="How much sweat equity are you up for?",
        choices=(
            _c("leisurely", "Leisurely", "leisurely"),
            _c("active", "Active", "active"),
            _c("rugged", "Rugged", "rugged"),
        ),
        informs=("activity_intensity",),
        category="pulse",
        cost="tap",
        tally_key="physical_intensity",
    ),
    ProfileQuestionDef(
        id="pace",
        binding=PROFILE,
        prompt="What's your pace when you travel?",
        choices=(
            _c("sprinter", "See it all (fast)", "fast"),
            _c("wanderer", "A bit of both (medium)", "medium"),
            _c("slow_mo", "Slow & deep", "slow"),
        ),
        informs=("pace", "energy_strategy"),
        category="pulse",
        cost="tap",
        tally_key="energy_strategy",
    ),
    # ── profile · strategy ─────────────────────────────────────────────────
    ProfileQuestionDef(
        id="structure_preference",
        binding=PROFILE,
        prompt="How much do you like a plan vs. wandering?",
        choices=(
            _c("total_freedom", "Total freedom", "total_freedom"),
            _c("flexible", "A loose skeleton", "flexible"),
            _c("planned", "Mostly planned", "planned"),
        ),
        informs=("structure_preference", "spontaneity"),
        category="strategy",
        cost="tap",
        tally_key="solo_freedom",
    ),
    ProfileQuestionDef(
        id="risk_appetite",
        binding=PROFILE,
        prompt="How much discomfort are you happy to embrace?",
        choices=(
            _c("comfort_first", "Comfort is the priority", "comfort_first"),
            _c("balanced", "A bit of friction is fine", "balanced"),
            _c("discomfort_ok", "Discomfort is part of the story", "discomfort_ok"),
        ),
        informs=("risk_appetite",),
        category="strategy",
        cost="tap",
        tally_key="uncertainty_scale",
    ),
    ProfileQuestionDef(
        id="adaptability",
        binding=PROFILE,
        prompt="A strike cancels your transport. What's your move?",
        choices=(
            _c("tactician", "Find the workaround", "tactician"),
            _c("alchemist", "Make it the new plan", "alchemist"),
            _c("delegate", "Let me handle it for you", "delegate"),
        ),
        informs=("adaptability",),
        category="strategy",
        cost="tap",
        tally_key="strike_scenario",
    ),
    ProfileQuestionDef(
        id="splurge_priority",
        binding=PROFILE,
        prompt="Where does the treat-yourself money usually go?",
        choices=(
            _c("stay", "The stay", "stay"),
            _c("plate", "The food", "plate"),
            _c("experience", "The experience", "experience"),
            _c("piece", "Local craft or art", "piece"),
        ),
        informs=("splurge_priority",),
        category="strategy",
        cost="tap",
        tally_key="splurge",
    ),
    ProfileQuestionDef(
        id="budget_tier",
        binding=PROFILE,
        prompt="What's your budget personality?",
        choices=(
            _c("negotiator", "The negotiator", "negotiator"),
            _c("balanced", "Balanced", "balanced"),
            _c("high_end", "High-end", "high_end"),
        ),
        informs=("budget_tier",),
        category="strategy",
        cost="tap",
        tally_key="budget_personality",
        hard_override_slot="ask.budget",
    ),
    ProfileQuestionDef(
        id="deal_breakers",
        binding=PROFILE,
        prompt="Any absolute deal-breakers?",
        choices=(
            _c("poor_hygiene", "Poor hygiene", "poor_hygiene"),
            _c("no_wifi", "No Wi-Fi", "no_wifi"),
            _c("crowds", "Overwhelming crowds", "crowds"),
            _c("extreme_heat", "Extreme heat", "extreme_heat"),
            _c("extreme_cold", "Extreme cold", "extreme_cold"),
            _c("poor_transport", "Poor transport", "poor_transport"),
        ),
        informs=("avoids",),
        category="strategy",
        cost="tap",
        allow_multi=True,
        tally_key="deal_breakers",
    ),
    # ── flow_state · the "different I's" (re-asked each flow run) ───────────
    ProfileQuestionDef(
        id="trip_intent_this_time",
        binding=FLOW_STATE,
        prompt="What are you hoping this trip gives you?",
        choices=(
            _c("reset", "Rest & reset", "reset"),
            _c("adventure", "Adventure", "adventure"),
            _c("connection", "Connection", "connection"),
            _c("discovery", "Discovery", "discovery"),
            _c("everything", "A bit of everything", "everything"),
        ),
        informs=("trip_intent",),
        category="state",
        cost="tap",
    ),
    ProfileQuestionDef(
        id="energy_for_this_trip",
        binding=FLOW_STATE,
        prompt="How's your energy for this one?",
        choices=(
            _c("low", "Low — keep it gentle", "low"),
            _c("steady", "Steady", "steady"),
            _c("high", "High — let's go", "high"),
        ),
        informs=("energy_state",),
        category="state",
        cost="tap",
    ),
    ProfileQuestionDef(
        id="current_craving",
        binding=FLOW_STATE,
        prompt="Right now, what sounds best?",
        choices=(
            _c("nature", "Nature", "nature"),
            _c("culture", "Culture", "culture"),
            _c("food", "Food", "food"),
            _c("nightlife", "Nightlife", "nightlife"),
            _c("quiet", "Quiet", "quiet"),
        ),
        informs=("craving",),
        category="state",
        cost="tap",
    ),
)

BY_ID: dict[str, ProfileQuestionDef] = {q.id: q for q in PROFILE_QUESTIONS}


def legal_option_values(qid: str) -> set[str]:
    """Legal ``value`` set for a question — used to re-validate a selection
    server-side (trust-but-verify; the client registry is never trusted)."""
    q = BY_ID.get(qid)
    return {c.value for c in q.choices} if q else set()
