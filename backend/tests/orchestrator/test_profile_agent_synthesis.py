"""Task 54 — ProfileAgent.synthesize_from_answers (DNA re-synthesis from chat answers)."""

from agentic_traveler.orchestrator.profile_agent import ProfileAgent


def test_synthesize_builds_prompt_and_returns(monkeypatch):
    agent = ProfileAgent(client=object())  # truthy client; no real Gemini call
    captured: dict = {}

    def fake_call_llm(prompt, fallback_profile=None):
        captured["prompt"] = prompt
        return (
            {"tags": ["couples_travel"], "personality_dimensions_scores": {}, "summary": "X"},
            object(),
            12.0,
        )

    monkeypatch.setattr(agent, "_call_llm", fake_call_llm)
    answered = {
        "travel_company": {"value": "duo"},
        "pace": {"value": "slow"},
        "deal_breakers": {"value": ["no_wifi", "crowds"]},
        "ignored_skip": {"value": "__skip__"},
    }
    structured, resp, lat = agent.synthesize_from_answers("u1", answered, persist=False)

    assert structured["tags"] == ["couples_travel"]
    # Stored values are rendered to their human labels in the prompt, not raw codes.
    assert "My partner" in captured["prompt"]
    assert "Slow & deep" in captured["prompt"]
    assert "No Wi-Fi, Overwhelming crowds" in captured["prompt"]
    assert "__skip__" not in captured["prompt"]


def test_synthesize_empty_answers_returns_fallback_no_llm():
    agent = ProfileAgent(client=object())
    called = {"n": 0}
    agent._call_llm = lambda *a, **k: called.__setitem__("n", called["n"] + 1)  # type: ignore[method-assign]

    structured, resp, lat = agent.synthesize_from_answers("u1", {}, persist=False)

    assert resp is None
    assert structured.get("tags")  # fallback structure
    assert called["n"] == 0  # the LLM is never called when there are no usable answers
