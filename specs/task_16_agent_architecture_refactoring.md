# Task 31: Agent Architecture Refactoring — Thin Router + Specialized Agents

> Replace the monolithic orchestrator with a lightweight intent-classifying router that delegates to focused, specialized agents. Isolate Google Search grounding into an on-demand proxy to eliminate unnecessary costs.

## 1. Task Overview
- **Summary:** Restructure the agent system from a "fat orchestrator that handles 90% of requests directly" to a "thin router + specialized agents" model. This reduces per-request token cost by ~50-60%, eliminates redundant context duplication, and gives each agent a genuinely narrow responsibility.
- **Background:** Audit findings revealed that:
  - The orchestrator's system prompt costs ~2,800 tokens (prompt + 9 tool schemas) before any user data.
  - Profile and conversation history are sent twice on delegated requests.
  - Discovery and Companion agents are not meaningfully differentiated from each other or the orchestrator.
  - Google Search grounding is always-on (`tools=[types.Tool(google_search=...)]`) for sub-agents, costing $0.035/prompt even when not needed.
  - `get_current_time()` wastes an AFC round-trip for static data.
  - This supersedes the earlier `task_22_lightweight_orchestrator.md` spec.
- **Primary Owner:** User

## 2. Objectives & Success Criteria
- **Goals:**
  - **Token reduction**: ≥40% reduction in average input tokens per request across all intent types.
  - **Latency**: Maintain or improve end-to-end response time (the router adds one fast LLM call but eliminates redundant context).
  - **Grounding cost control**: Google Search grounding fee ($0.035) is incurred only when an agent explicitly calls `search_web()`, not on every sub-agent invocation.
  - **Response quality**: No regression in response quality, personality, or personalization. The chat agent should feel *more* personal, not less. The trip agent should provide suggestions that feel natural and human, not like a profile readout.
  - **Feature parity**: All existing functionality preserved (safety, off-topic guard with counter/restriction, preference learning, credits, weather, feedback).
- **Non-Goals:**
  - Changing the conversation compaction logic (`ConversationManager`).
  - Migrating to a different database (Supabase migration is a separate task).
  - Adding new user-facing features.
  - Changing the Telegram webhook or interface layer.
- **Definition of Done:**
  - [ ] Router correctly classifies CHAT/TRIP/PLAN/OFF_TOPIC on a 50-message eval set with ≥90% accuracy.
  - [ ] Router generates natural, warm redirection responses for OFF_TOPIC messages.
  - [ ] Off-topic counter still increments and restriction mechanism still works.
  - [ ] Chat Agent produces responses that feel genuinely personal and human.
  - [ ] Trip Agent handles discovery and companion scenarios with implicit personalization.
  - [ ] Planner Agent produces structured day-by-day itineraries.
  - [ ] Search Agent returns grounded results only when explicitly called.
  - [ ] `check_weather()` works from Chat, Trip, and Planner agents.
  - [ ] Agents proactively fetch weather for suggestions within 10 days.
  - [ ] Preference updates detected by Router are acknowledged by downstream agents.
  - [ ] Credit deduction still works correctly for all agents.
  - [ ] Token usage logging works for all agents (router + specialized).
  - [ ] All existing tests pass.
  - [ ] README updated with new model stack.

## 3. System Context
- **Repositories / Services Affected:** `agentic-traveler` (single repo)
- **Architecture Notes:**
  - **Current flow**: `webhook.py` → `OrchestratorAgent.process_request()` → (optional) sub-agent
  - **New flow**: `webhook.py` → `OrchestratorAgent.process_request()` → `RouterAgent.classify()` → specialized agent
  - The `OrchestratorAgent` class becomes the **orchestration coordinator** (no LLM call itself). It calls the router, then dispatches to the right agent based on the classified intent.
  - All agents share a single `genai.Client` instance from `client_factory.py`.
  - The Search Agent is invoked as a tool function within other agents (via AFC). The `search_web()` tool docstring is self-documenting — it tells calling agents when and how to use it without needing extra system prompt instructions.
- **Relevant Specs / Docs:**
  - `specs/task_03_orchestrator_agent.md` — original orchestrator design
  - `specs/task_22_lightweight_orchestrator.md` — earlier lightweight idea (superseded)
  - `AGENTIC_GUIDELINES.md` — architectural principles to follow
  - `specs/travel_personality_dimensions.md` — personality dimension definitions

## 4. Constraints & Requirements
- **Technical Constraints:**
  - Python 3.13 (match Dockerfile)
  - `google-genai` SDK for all LLM calls
  - Models: `gemini-3.1-flash-lite-preview` (router, chat, search), `gemini-3-flash-preview` (trip, planner)
  - All models must work on the Vertex AI `global` endpoint (current `GEMINI_REGION=global`)
  - Maintain AFC (automatic function calling) for tool-equipped agents
- **Operational Constraints:**
  - No downtime — the refactoring must be deployable as a single commit
  - Must not break the existing webhook interface (`process_request` signature unchanged)
  - Token usage logging must continue to work for cost monitoring
- **Security / Compliance:**
  - Safety instructions (never refuse, warn + help) must be present in Chat, Trip, and Planner agent prompts
  - Off-topic guard counter + restriction mechanism must continue to work
  - No secrets in prompts or logs
  - Telegram output sanitization unchanged

## 5. Inputs & Resources
- **Artifacts Provided:**
  - Current agent files: `agent.py`, `discovery_agent.py`, `planner_agent.py`, `companion_agent.py`
  - Off-topic guard: `guards/off_topic_guard.py`
  - Profile utilities: `profile_utils.py`, `profile_agent.py`, `preference_learner.py`
  - Conversation manager: `conversation_manager.py`
  - Weather service: `tools/weather.py`
  - Usage tracking: `analytics/usage_tracker.py`
  - Credit manager: `economy/credit_manager.py`
- **Assumptions:**
  - `gemini-3.1-flash-lite-preview` is available on the `global` Vertex AI endpoint and supports AFC.
  - Google Search grounding is supported on `gemini-3.1-flash-lite-preview`.
  - The `process_request()` return format (`{"text": ..., "action": ...}`) is not changed.
- **Open Questions:**
  - Can `gemini-3.1-flash-lite-preview` handle 4-way intent classification reliably? (Validate in Phase 2 Step 1 via standalone eval script.)

## 6. Implementation Plan

### Phase 1: Quick Wins (no architectural change)

**Step 1.1: Inject current time into prompt, remove `get_current_time()` tool**
- In `_build_user_content()`, add `<current_time>` tag with formatted datetime.
- Remove `get_current_time()` method from `OrchestratorAgent`.
- Remove it from the `tools=` list in `_call_llm()`.
- Remove the "call get_current_time()" instruction from the system prompt.
- *Verify*: Run locally, confirm the model uses the injected time without a tool call.

**Step 1.2: Remove conversation summary duplication from `profile_utils.py`**
- In `build_profile_summary()`, remove lines 86-88 that append the conversation summary. It's already injected separately via `_build_user_content()`.
- *Verify*: Inspect the assembled prompt to confirm the summary appears exactly once.

**Step 1.3: Reduce `max_output_tokens` on orchestrator to 4096**
- Change line 601 in `agent.py`.
- *Verify*: No behavioral change expected.

**Step 1.4: Extract `_has_grounding()` to shared utility**
- Create `orchestrator/utils.py` with `has_grounding(response)`.
- Replace the three copies in `discovery_agent.py`, `planner_agent.py`, `companion_agent.py`.
- *Verify*: Existing grounding detection still works.

---

### Phase 2: Build New Agents

**Step 2.1: Build the Router Agent (`router_agent.py`)**
- Create `src/agentic_traveler/orchestrator/router_agent.py`.
- Model: `gemini-3.1-flash-lite-preview`, `temperature=0.1`, `max_output_tokens=256`.
- Use `response_mime_type="application/json"` for reliable structured output.
- Tools: `update_preferences(key, value)`, `record_feedback(category, text)`, `get_my_credits()`.

**System prompt (embed verbatim):**
```
You are the intent router for Agentic Traveler, a travel companion chatbot.

Your job: classify the user's message into exactly one intent and extract
the core request. You do NOT generate the final response — a specialized
agent handles that — EXCEPT for OFF_TOPIC messages, where you provide
a natural, friendly redirection yourself.

INTENTS:
• CHAT — Greetings, thanks, jokes, banter, personal stories, emotional
  support, life advice, opinions, "how are you", compliments, or any
  message that is conversational but not asking for travel-specific help.
  Examples: "hey!", "thanks that was great", "how's your day?",
  "tell me a joke", "I'm feeling stressed"

• TRIP — Any travel-related question, suggestion request, destination
  exploration, in-trip help, "what to do in X", weather questions,
  comparisons between destinations, visa/entry questions, or travel advice.
  This includes both pre-trip research and live in-trip assistance.
  Examples: "what should I do in Bali?", "I'm tired and it's raining",
  "is Lombok worth visiting?", "what's the weather in Rome?",
  "best time to visit Japan?"

• PLAN — An explicit request for a structured, detailed, day-by-day
  itinerary or trip schedule. The user must be asking for organized
  planning with specific days/structure, not just casual suggestions.
  Examples: "plan my 5-day trip to Rome", "make me an itinerary for
  Lombok", "organize my week in Tokyo", "help me plan day by day"

• OFF_TOPIC — The message is clearly unrelated to travel AND is not
  casual/fun conversation. Math homework, coding questions, politics, etc.
  BE LENIENT: jokes, banter, personal stories, and life advice are CHAT,
  not OFF_TOPIC.
  When you classify OFF_TOPIC, generate a short, warm, natural redirection
  in the "response" field. Don't be robotic — redirect like a friend would.

Current time: {current_time}
User: {user_name}
Tone preference: {tone_preference}

Classify the intent. If the user also reveals a preference or gives
feedback, call the appropriate tool AND still classify the intent.
```

**Output JSON schema:**
```json
{
  "intent": "TRIP|CHAT|PLAN|OFF_TOPIC",
  "request_summary": "one-sentence description of what the user wants",
  "preference_updated": {"key": "...", "value": "..."} | null,
  "response": "natural redirection text (OFF_TOPIC only, else null)"
}
```

**OFF_TOPIC flow:**
1. Router classifies OFF_TOPIC and generates a warm, natural redirection in `response`.
2. Orchestration code calls `off_topic_guard.record_off_topic()` silently.
3. If threshold not hit → return router's natural response to user.
4. If threshold hit → return `off_topic_guard.is_restricted()` message instead.
5. For CHAT/TRIP/PLAN → call `off_topic_guard.reset()` as before.

**Preference handoff:** When a preference is detected, the router calls `update_preferences()` via AFC AND sets `preference_updated` in the JSON output so the downstream agent can acknowledge it naturally (e.g. "Got it, I'll keep your budget preference in mind!").

- *Verify*: Build a 50-message eval set and test classification accuracy ≥90%.

**Step 2.1b: Create standalone Router eval script**
- Create `scripts/eval_router.py` (NOT a pytest test — runs separately to avoid LLM costs in CI).
- Contains ~50 representative messages covering all 4 intents, including edge cases.
- Runs the router against each message and reports accuracy.
- Can be invoked manually: `python scripts/eval_router.py`.

**Step 2.2: Build the Search Agent (`search_agent.py`)**
- Create `src/agentic_traveler/orchestrator/search_agent.py`.
- Model: `gemini-3.1-flash-lite-preview`, `temperature=0.1`, `max_output_tokens=1500`.
- Enabled with `tools=[types.Tool(google_search=types.GoogleSearch())]`.

**System prompt (embed verbatim):**
```
You are a factual search assistant. Given a query and a desired output
format, search the web and return results matching that format.

If the caller asks for "comprehensive", provide detailed findings with
full context and analysis.
If the caller asks for "headline", provide a one-line summary.
If the caller asks for "structured", provide key facts as bullet points.

Always cite sources. Do not add opinions or recommendations.
```

**`search()` method signature (tool docstring used by calling agents):**
```python
def search(self, query: str, format: str = "structured") -> str:
    """
    Search the web for current, time-sensitive information.

    Call this when you need real-time data that you cannot answer from
    general knowledge: visa requirements, travel advisories, event dates,
    current prices, opening hours, or live conditions.

    Do NOT call for general destination knowledge, cultural context,
    or geography — you already know those.

    Args:
        query: The specific question to search for.
        format: Desired output format — "headline" (1-line summary),
                "structured" (key facts as bullet points),
                or "comprehensive" (detailed analysis with full context).

    Returns:
        Factual results with source citations.
    """
```

The tool docstring is self-documenting — calling agents do not need additional system prompt instructions about when or how to use it.

- *Verify*: Call with `query="Japan visa requirements 2026", format="structured"` and confirm a grounded response with citations.

---

**Step 2.3: Build the Chat Agent (`chat_agent.py`)**
- Create `src/agentic_traveler/orchestrator/chat_agent.py`.
- Model: `gemini-3.1-flash-lite-preview`, `temperature=0.8`, `max_output_tokens=2000`.
- Context: full profile (including personality dimension scores + interpretation guide) + conversation history + current time + `preference_updated` field from router (if set).

**System prompt (embed verbatim):**
```
You are "Agentic Traveler", the user's travel-obsessed best friend.

You know this person deeply. Their personality profile below tells you
exactly how they think, what they value, and how they communicate.
Use it to make every interaction feel effortless and real — the way a
close friend just *gets* you without having to explain yourself.

PERSONALITY DIMENSIONS (0.0 to 1.0 scale):
- Scores ≥0.7 = strong trait (lean into this in your tone and suggestions)
- Scores ≤0.3 = opposite trait (respect this, don't push against it)
- 0.4–0.6 = balanced/flexible

BEHAVIOR:
- Match the user's tone preference exactly.
- Be present and engaged — react to what they say, not just what they ask.
- Reference things from past conversations naturally, the way a friend
  would ("didn't you mention you loved that place in Lisbon?").
- Read their energy. If they're excited, match it. If they're venting,
  listen first. If they're brief, be brief back.
- You're a friend first, travel advisor second. Life, emotions, stories,
  humor — it's all fair game.
- Never be generic. If your response could work for any user, rewrite it.
- If preference_updated is provided, acknowledge it naturally in your
  response (e.g. "Got it, I'll keep that in mind!").

SAFETY: You may always discuss what the user brings up. If something is
harmful or illegal, gently note a concern while still being helpful.
Never refuse outright — redirect warmly.

WEATHER: If the user asks about weather or you find it useful for
something happening in the next 10 days, call check_weather().

Formatting (Telegram):
- Use *bold* for emphasis.
- Use bullet points (•) for lists.
- Do NOT use headers (#), tables, or code blocks.
- Keep it conversational — not a formatted document.
```

- Tools: `check_weather(location, days)`, `search_web(query, format)` (delegates to Search Agent).
- *Verify*: Test with "hey!", "I'm feeling stressed", "tell me a joke" — confirm responses feel personal, reference user profile naturally, and never feel generic.

---

**Step 2.4: Build the Trip Agent (`trip_agent.py`)**
- Create `src/agentic_traveler/orchestrator/trip_agent.py`.
- Merges Discovery Agent + Companion Agent responsibilities.
- Model: `gemini-3-flash-preview`, `temperature=0.7`, `max_output_tokens=4000`.
- Context: full profile + conversation history + current time + `preference_updated` from router.
- Google Search grounding is NOT directly enabled — use `search_web()` tool (Search Agent proxy) instead.

**System prompt (embed verbatim):**
```
You are a friendly, deeply knowledgeable travel advisor chatting with
a traveler you know personally.

You understand their personality, preferences, and travel style from
their profile. Use this knowledge to make every suggestion feel natural
and human — as if you instinctively know what they'd love.

PERSONALIZATION RULES:
- Weave their preferences into suggestions implicitly, not explicitly.
  GOOD: "There's a stunning little gallery tucked away in the old town"
        (because you know they love art — but you don't say that)
  BAD: "Since you mentioned you don't like Banksy, I'll skip street art"
        (never name-drop specific preferences as justifications)
- Use descriptive adjectives that align with their vibe (romantic,
  adventurous, serene) — these feel natural.
- If they ask WHY you suggested something, then it is fine to reference
  their specific preferences explicitly.
- If preference_updated is provided, acknowledge it naturally in your
  response.

BEHAVIOR:
- Give a 2-3 option high-level summary first, then ask if they want details.
- For in-trip help: prioritize actionable, immediate options.
- For discovery: be creative but grounded in what you know about them.
- Use conversation history — reference things discussed, don't repeat.

SAFETY: You may always discuss what the user brings up. If something is
harmful or illegal, gently note a concern while still being helpful.
Never refuse outright — redirect warmly.

WEATHER: If you are suggesting activities or plans within the next 10 days,
proactively call check_weather() to inform your recommendations.
Integrate weather naturally (e.g. "looks like clear skies Tuesday,
perfect for that coastal hike"). Do NOT dump a day-by-day weather list.

REAL-TIME DATA: When you need current facts (visa rules, event dates,
prices, opening hours), call search_web() — don't guess.

Formatting (Telegram):
- STRICT LENGTH LIMIT: Never exceed 3500 characters. Curate, don't dump.
- Use *bold* for place names and highlights.
- Use bullet points (•) for lists.
- Do NOT use headers (#), tables, or code blocks.
- Tone: warm, personal, like a well-traveled friend.
```

- Tools: `check_weather(location, days)`, `search_web(query, format)`.
- *Verify*: Test with "what should I do in Bali?", "I'm tired and it's raining, what now?" — confirm suggestions feel tailored, not generic, and no explicit preference name-dropping.

---

**Step 2.5: Refactor the Planner Agent (`planner_agent.py`)**
- Update existing `planner_agent.py`.
- Model: `gemini-3-flash-preview`, `temperature=0.7`, `max_output_tokens=4500`.
- Context: full profile + conversation history + current time + `preference_updated` from router.
- Remove direct Google Search grounding (`tools=[types.Tool(google_search=...)]`). Replace with `search_web()` tool.

**Why separate from Trip Agent:** The Planner produces a fundamentally different output — structured, multi-day itineraries with morning/afternoon/evening blocks, logistics, timing, budget estimates, and alternatives. This requires: (1) a dedicated output format enforced by the prompt, (2) higher reasoning demand for multi-day coherence, and (3) a longer output budget (up to 4,500 tokens vs 4,000 for Trip Agent).

**System prompt (embed verbatim):**
```
You are a friendly, expert travel planner chatting with a traveler
you know personally.

You understand their personality, preferences, and travel style from
their profile. Use this to make every itinerary feel tailor-made —
not a generic tourist schedule.

PERSONALIZATION RULES (same as Trip Agent):
- Weave preferences into the plan implicitly using descriptive adjectives.
  GOOD: "Tuesday evening at a candlelit trattoria in Trastevere"
        (because you know they love romance — but you don't say that)
  BAD: "Since you prefer romantic settings, I chose Trastevere"
- If they ask WHY something is in the plan, then explain based on
  their specific preferences.
- If preference_updated is provided, acknowledge it naturally.

OUTPUT FORMAT:
- Day-by-day structure. For each day:
  • *Morning* — one activity (1 line: name + what makes it special)
  • *Afternoon* — one activity (1 line)
  • *Evening* — one activity (1 line)
  • Low-energy alternative for the day (1 line)
- End with: "Want me to adjust anything?"

SAFETY: You may always discuss what the user brings up. If something is
harmful or illegal, gently note a concern while still being helpful.
Never refuse outright — redirect warmly.

WEATHER: If you are planning a trip within the next 10 days, call
check_weather() proactively. Adapt activities to the forecast and mention
weather naturally as a reason for choices (e.g. "since it looks cloudy
on Tuesday..."). Do NOT dump a day-by-day weather breakdown.

REAL-TIME DATA: For time-sensitive logistics (entry requirements,
seasonal closures, public holiday dates, event schedules), call
search_web() — don't guess. Briefly cite sources.

Formatting (Telegram):
- STRICT LENGTH LIMIT: Never exceed 3500 characters. If the user asks
  for "EVERYTHING", provide a curated summary instead.
- Use *bold* for day headings and place names.
- Use numbered lists (1. 2. 3.) for days, bullet points (•) for activities.
- Do NOT use headers (#), tables, or code blocks.
```

- Tools: `check_weather(location, days)`, `search_web(query, format)`.
- *Verify*: Test with "plan my 5-day trip to Rome" — confirm day-by-day structure, weather integration if within 10 days, no explicit preference name-dropping.

---

### Phase 3: Integration

**Step 3.1: Refactor `OrchestratorAgent.process_request()` into coordinator**
- The `OrchestratorAgent` class becomes the **coordinator** (no longer makes its own LLM call).
- New flow:
  1. Fetch user profile + credit gate (unchanged)
  2. Check `off_topic_guard.is_restricted()` (unchanged)
  3. Build conversation context (unchanged)
  4. Call `RouterAgent.classify(message, user_name, tone_preference, current_time)`
  5. Handle router tool calls (preference updates, feedback, credits)
  6. If intent = OFF_TOPIC:
     - Call `off_topic_guard.record_off_topic()` silently
     - If now restricted → return restriction message
     - If not restricted → return router's natural redirection response
  7. If intent = CHAT/TRIP/PLAN:
     - Call `off_topic_guard.reset()` (same as today)
     - Dispatch to appropriate agent
     - Pass `preference_updated` from router so agent can acknowledge it
  8. Log token usage for router + agent
  9. Deduct credits
  10. Save conversation history
- Remove the system prompt `_SYSTEM_PROMPT` (no longer needed).
- Remove all tool methods from the class (they live on individual agents now).
- *Verify*: End-to-end test via webhook with all intent types.

**Step 3.2: Wire up status callbacks**
- Send "thinking..." / "scouting..." status messages before agent calls.
- Different messages per intent (chat doesn't need one — it's fast).

**Step 3.3: Update credit_manager with new model pricing**
- Add `gemini-3.1-flash-lite-preview` to the pricing table.
- *Verify*: Run existing pricing tests.

**Step 3.4: Update token usage logging**
- Log both the router call and the agent call as separate entries.
- Router logged as `agent_name="router"`.
- *Verify*: Inspect logs for both entries.

---

### Phase 4: Cleanup

**Step 4.1: Delete old files**
- Delete `discovery_agent.py` (replaced by `trip_agent.py`)
- Delete `companion_agent.py` (merged into `trip_agent.py`)
- Remove `get_current_time` related code

**Step 4.2: Update documentation**
- Update `README.md` model stack table.
- Update this spec with final results.

**Step 4.3: Remove dead imports and code**
- Clean up `agent.py` imports.
- Remove the old system prompt constant.
- Remove tool method definitions that moved to other agents.

## 7. Testing & Validation
- **Test Strategy:**
  - **Router eval** (standalone script, not pytest): 50-message eval set covering all 4 intents with edge cases. Run manually via `python scripts/eval_router.py`.
  - **Unit tests** (pytest): Credit calculation works for new model IDs.
  - **Integration test**: Full `process_request()` flow via webhook for each intent type.
  - **Manual test**: Live Telegram conversation covering all scenarios.
- **Acceptance Tests:**
  - Router classifies "hey!" → CHAT, "what to do in Bali?" → TRIP, "plan my 5 days in Rome" → PLAN, "solve 2+2" → OFF_TOPIC with ≥90% accuracy across 50 messages.
  - Router generates natural, warm redirections for OFF_TOPIC (not static text).
  - Off-topic counter increments and restriction triggers at threshold.
  - Chat Agent references user personality naturally, feels like a real friend.
  - Trip Agent suggests destinations with implicit personalization (no profile readout).
  - Planner produces day-by-day structure with weather integration.
  - Search Agent returns grounded results with citations only when called.
  - Weather works from Chat, Trip, and Planner agents.
  - Preference update is acknowledged in downstream agent response.
  - Credits are deducted correctly.
  - Token usage is logged for all agents.
- **Tooling:** `pytest` for unit tests, `scripts/eval_router.py` for router eval, live Telegram testing via ngrok.

## 8. Risk Management
- **Known Risks:**
  - Router misclassification degrades response quality.
  - `gemini-3.1-flash-lite-preview` may not support all required features (AFC, Google Search grounding).
  - Two-hop latency (router + agent) could feel slower than current single-hop.
- **Mitigations:**
  - Validate router accuracy on eval set before deployment.
  - Test `gemini-3.1-flash-lite-preview` capabilities in isolation before building.
  - Router call is very fast (~200-400ms for flash-lite with small prompt) — total latency should still be lower due to smaller agent prompts.
- **Rollback Plan:**
  - Keep the current `agent.py` as `agent_legacy.py` during development.
  - The webhook calls `process_request()` — if the new coordinator breaks, swap back to the legacy class with a single import change.

## 9. Delivery & Handoff
- **Deliverables:**
  - New files: `router_agent.py`, `chat_agent.py`, `trip_agent.py`, `search_agent.py`, `orchestrator/utils.py`
  - New scripts: `scripts/eval_router.py`
  - Modified files: `agent.py` (coordinator), `planner_agent.py`, `profile_utils.py`, `credit_manager.py`, `README.md`
  - Deleted files: `discovery_agent.py`, `companion_agent.py`
- **Review Process:** Manual Telegram testing before deployment.
- **Post-Delivery Actions:**
  - Monitor token usage logs for 1 week to confirm savings.
  - Monitor response quality via feedback signals.
  - File GCP quota increase if needed for the new models.

## 10. Communication Plan
- **Stakeholders:** User (sole stakeholder)
- **Status Cadence:** Progress tracked in conversation task.md artifact.
- **Escalation Path:** User via Telegram or this conversation.

## 11. Appendix
- **Glossary:**
  - **AFC**: Automatic Function Calling — the GenAI SDK feature that executes tool calls automatically.
  - **Router**: The lightweight LLM call that classifies user intent.
  - **Search Agent**: The grounding proxy that isolates Google Search costs.
  - **Grounding**: Using Google Search to provide real-time factual data in LLM responses.
  - **Implicit personalization**: Using profile data to shape suggestions without explicitly naming the preferences.
- **Reference Materials:**
  - [Vertex AI model versions](https://cloud.google.com/vertex-ai/generative-ai/docs/learn/model-versions)
  - `AGENTIC_GUIDELINES.md` — project agentic design principles
  - `specs/travel_personality_dimensions.md` — personality scoring system
  - `guards/off_topic_guard.py` — off-topic counter + restriction mechanism
- **Change Log:**
  - v1 (2026-05-07): Initial audit findings, proposed merging everything into fat orchestrator.
  - v2 (2026-05-07): Revised to thin router + specialized agents per user feedback.
  - v3 (2026-05-07): Refined with all user comments — precise models, full profile on chat agent, weather on all agents, Search Agent justified, Planner separation explained, safety preserved.
  - v4 (2026-05-07): Off-topic handling refined (router generates natural response, counter increments silently). Trip Agent model upgraded to `gemini-3-flash-preview`. Implicit personalization rules added. Weather instructions clarified (proactive for ≤10 days). Standalone router eval script. Preference handoff format defined.
