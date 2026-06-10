"""CuriosityPromptInjector unit tests (task 42).

Covers library validity, the selection rules (structure-preference gate,
once-per-day session gate, force bypass, determinism), the AI-effect guards
(requires-destination gate + optional-aside delivery framing), and the env
rollback switch. Pure Python — no LLM.
"""

from agentic_traveler.orchestrator.curiosity_injector import (
    CuriosityPrompt,
    CuriosityPromptInjector,
    LIBRARY_PATH,
    frame_curiosity_prompt,
    load_library,
)

# All 7 saga states the library must cover (AC-7).
_STATES = {
    "DREAMING", "SHAPING", "ANCHORING", "DETAILING",
    "READY_TO_GO", "LIVING", "REMEMBERING",
}


def _user(structure=0.4, **scores):
    scores["structure_preference"] = structure
    return {
        "user_profile": {
            "profile_data": {
                "personality_dimensions_scores": scores,
                "travel_motivations": ["rest", "aesthetic"],
            }
        }
    }


def _trip(destinations=None, scratchpad=None, motivations=None):
    return {
        "id": "trip-1",
        "destinations": destinations if destinations is not None else [],
        "discovery": {"motivations": motivations or []},
        "scratchpad": scratchpad or {},
    }


def _entry(id="e", states=("DREAMING",), text="Sea or city?", **trigger):
    return CuriosityPrompt(
        id=id,
        source={"author": "Test", "title": "Test"},
        trigger={"states": list(states), **trigger},
        text=text,
        rationale="test",
    )


# ── library validity (AC-1, AC-7, AC-8) ──────────────────────────────────────

def test_real_library_loads_and_parses():
    lib = load_library(LIBRARY_PATH)
    assert len(lib) >= 30
    assert all(isinstance(p, CuriosityPrompt) for p in lib)


def test_every_text_within_200_chars():
    for p in load_library(LIBRARY_PATH):
        assert len(p.text) <= 200, f"{p.id} too long: {len(p.text)}"


def test_library_covers_all_seven_states():
    covered = set()
    for p in load_library(LIBRARY_PATH):
        covered.update(p.trigger.states)
    assert _STATES <= covered, f"missing: {_STATES - covered}"


def test_every_entry_cites_a_real_source():
    for p in load_library(LIBRARY_PATH):
        assert p.source.author and p.source.title


# ── selection rules (AC-3, AC-5, AC-6) ───────────────────────────────────────

def test_high_structure_preference_returns_none():
    inj = CuriosityPromptInjector(library=[_entry()])
    assert inj.select("DREAMING", _user(structure=0.85), {}) is None


def test_once_per_session_returns_none():
    inj = CuriosityPromptInjector(library=[_entry()])
    used = {"curiosity_used_this_session": True}
    assert inj.select("DREAMING", _user(), used) is None


def test_returns_prompt_when_eligible():
    inj = CuriosityPromptInjector(library=[_entry(id="anticipation")])
    got = inj.select("DREAMING", _user(), {})
    assert isinstance(got, CuriosityPrompt)
    assert got.id == "anticipation"


def test_force_bypasses_both_gates():
    inj = CuriosityPromptInjector(library=[_entry()])
    used = {"curiosity_used_this_session": True}
    assert inj.select("DREAMING", _user(structure=0.95), used, force=True) is not None


def test_no_candidate_for_state_returns_none():
    inj = CuriosityPromptInjector(library=[_entry(states=("DREAMING",))])
    assert inj.select("LIVING", _user(), {}) is None


def test_deterministic_for_same_inputs():
    lib = [_entry(id=f"e{i}", text=f"q{i}") for i in range(5)]
    inj = CuriosityPromptInjector(library=lib)
    u = _user()
    u["id"] = "user-xyz"
    a = inj.select("DREAMING", u, {})
    b = inj.select("DREAMING", u, {})
    assert a is not None and a.id == b.id


# ── AI-effect guards (this task's emphasis) ──────────────────────────────────

def test_requires_destination_gate_blocks_cold_open():
    # A more personal prompt only fires once there's a destination on the trip,
    # so the AI never cold-opens an intimate question.
    inj = CuriosityPromptInjector(library=[_entry(id="deep", requires_destination=True)])
    no_dest = inj.select("DREAMING", _user(), {}, trip=_trip(destinations=[]))
    with_dest = inj.select("DREAMING", _user(), {}, trip=_trip(destinations=[{"name": "Kyoto"}]))
    assert no_dest is None
    assert with_dest is not None and with_dest.id == "deep"


def test_motivation_gate_matches_profile_or_trip():
    inj = CuriosityPromptInjector(library=[_entry(id="rest", motivation_any=["rest"])])
    # Profile lists "rest" → matches.
    assert inj.select("DREAMING", _user(), {}) is not None
    # Profile without the motivation and no trip motivation → no match.
    u = _user()
    u["user_profile"]["profile_data"]["travel_motivations"] = ["adventure"]
    assert inj.select("DREAMING", u, {}, trip=_trip(motivations=[])) is None


def test_framing_makes_prompt_an_optional_aside():
    framed = frame_curiosity_prompt("Sea or city?")
    low = framed.lower()
    assert "Sea or city?" in framed
    assert "<curiosity_prompt>" in framed
    # The framing must instruct optionality / non-insistence — the AI-effect counter.
    assert "optional" in low
    assert "ignore" in low or "ignored" in low
    assert "never repeat" in low or "do not repeat" in low


# ── env rollback (§9.4) ──────────────────────────────────────────────────────

def test_env_disabled_returns_none(monkeypatch):
    monkeypatch.setenv("CURIOSITY_INJECTOR_ENABLED", "false")
    inj = CuriosityPromptInjector(library=[_entry()])
    assert inj.select("DREAMING", _user(), {}, force=True) is None


# ── wiring into PlanningSaga (AC-4) ──────────────────────────────────────────

def _planning_saga():
    from unittest.mock import MagicMock
    from agentic_traveler.orchestrator.sagas.planning import PlanningSaga
    return PlanningSaga(client=MagicMock())


def test_planning_curiosity_suffix_injects_marks_and_emits():
    from agentic_traveler.orchestrator.event_emitter import EventEmitter
    saga = _planning_saga()
    events = EventEmitter(user_id="u1", trip_id="t1")
    trip = {"id": "trip-1", "destinations": [{"name": "Kyoto"}], "scratchpad": {}, "discovery": {}}
    side_effects = []
    suffix = saga._curiosity_suffix(trip, _user(), "DREAMING", side_effects, events)
    assert "<curiosity_prompt>" in suffix
    assert side_effects[0].payload["scratchpad"]["curiosity_last_at"]
    assert any(r["event_name"] == "curiosity_prompt_injected" for r in events._metric_buffer)


def test_planning_curiosity_suffix_skips_non_companion_phase():
    from agentic_traveler.orchestrator.event_emitter import EventEmitter
    saga = _planning_saga()
    side_effects = []
    suffix = saga._curiosity_suffix(
        {"id": "t", "scratchpad": {}}, _user(), "DETAILING", side_effects,
        EventEmitter(user_id="u1", trip_id="t1"),
    )
    assert suffix == ""
    assert side_effects == []


def test_planning_curiosity_suffix_once_per_day():
    from datetime import date
    from agentic_traveler.orchestrator.event_emitter import EventEmitter
    saga = _planning_saga()
    side_effects = []
    trip = {"id": "t", "destinations": [{"name": "Kyoto"}],
            "scratchpad": {"curiosity_last_at": date.today().isoformat()}, "discovery": {}}
    suffix = saga._curiosity_suffix(trip, _user(), "DREAMING", side_effects,
                                    EventEmitter(user_id="u1", trip_id="t1"))
    assert suffix == ""
    assert side_effects == []
