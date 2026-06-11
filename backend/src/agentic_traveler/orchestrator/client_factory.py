import contextvars
import os
import logging
import time
from contextlib import contextmanager
from typing import Optional
from google import genai
from agentic_traveler.core.observability import traceable
from agentic_traveler.orchestrator.tool_events import (
    get_current_emitter,
    reset_current_emitter,
    set_current_emitter,
)

logger = logging.getLogger(__name__)

# ── Per-turn usage capture (task 51) ─────────────────────────────────────────
# Every Gemini call funnels through gemini_generate / gemini_generate_stream,
# so token usage is captured HERE and accumulated into a per-turn ContextVar —
# nested tools (booking parser, slot extractor, …) get billed without having
# to thread usage records back up through every return signature.
#
# Default None = no active turn (scripts, webhooks, self-billing background
# work like the country-intel fetcher): capture is a silent no-op.
#
# Threading: ContextVars do NOT propagate into raw ThreadPoolExecutor.submit.
# Work that must stay billable on a worker thread has to be submitted via
# contextvars.copy_context().run(...) — the copied context references the
# SAME list object, so appends land in the turn's records (task 48 note).
current_turn_usage: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar(
    "current_turn_usage", default=None
)


def begin_usage_capture() -> list:
    """Start a fresh usage list for this turn and return it. Always called at
    turn start, which also clears any stale list left on a reused thread."""
    records: list = []
    current_turn_usage.set(records)
    return records


@contextmanager
def suppress_usage_capture():
    """Exclude a block's LLM calls from the user's turn billing — for system
    work that pays its own way or is platform overhead (conversation
    compaction today; the offline judge in task 47)."""
    token = current_turn_usage.set(None)
    try:
        yield
    finally:
        current_turn_usage.reset(token)


def _capture_usage(
    model: str, response, *, latency_ms: Optional[float] = None, call_type: Optional[str] = None
) -> None:
    """Append `response`'s token usage (and any grounding cost) to the active
    turn's records, and emit a per-call llm_call_usage metric (AC-2).
    No active turn or no usage metadata → no-op. Never raises."""
    records = current_turn_usage.get()
    if records is None or response is None:
        return
    try:
        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        thinking_tokens = int(getattr(usage, "thoughts_token_count", 0) or 0) if usage else 0
        if input_tokens or output_tokens:
            records.append({
                "model_name": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
                "thinking_tokens": thinking_tokens,
            })
            logger.info(
                "📊 LLM usage | model=%s input_tokens=%d output_tokens=%d thinking_tokens=%d",
                model, input_tokens, output_tokens, thinking_tokens,
            )
            # AC-2: emit per-call usage metric via current EventEmitter.
            emitter = get_current_emitter()
            if emitter is not None:
                try:
                    emitter.emit("metric", {
                        "name": "llm_call_usage",
                        "call_type": call_type or "unknown",
                        "model": model,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "thinking_tokens": thinking_tokens,
                        "latency_ms": int(latency_ms) if latency_ms is not None else None,
                    })
                except Exception:
                    logger.debug("llm_call_usage emit failed.", exc_info=True)
        # Grounded calls carry a per-prompt cost on top of tokens. Lazy imports:
        # utils pulls in the weather tool, economy pulls Supabase — neither
        # belongs in this module's import graph at startup.
        from agentic_traveler.orchestrator.utils import has_grounding
        if has_grounding(response):
            from agentic_traveler.economy import credit_manager
            records.append({
                "model_name": "grounding",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "grounding_count": 1,
                "grounding_cost_credits": credit_manager.calculate_grounding_cost(1),
            })
    except Exception:
        logger.warning("Usage capture failed for model=%s.", model, exc_info=True)

class MockGenAIClient:
    class MockModels:
        def generate_content(self, model, contents, config=None):
            import json
            
            class MockUsageMetadata:
                prompt_token_count = 120
                candidates_token_count = 60
                
            class MockCandidate:
                class MockContent:
                    parts = []
                content = MockContent()
                grounding_metadata = None

            class MockResponse:
                usage_metadata = MockUsageMetadata()
                candidates = [MockCandidate()]

            # Distinguish router intent queries using response_mime_type
            is_json = False
            if config and getattr(config, "response_mime_type", None) == "application/json":
                is_json = True

            if is_json:
                MockResponse.text = json.dumps({
                    "intent": "CHAT",
                    "request_summary": "Simulated performance testing query",
                    "preference_raw": None,
                    "response": None
                })
            else:
                MockResponse.text = "*Mocked travel suggestion!* You should visit Rome and enjoy the local culinary scenes."
                
            return MockResponse()

        def generate_content_stream(self, model, contents, config=None):
            # Single-chunk stream for perf testing: reuse the non-streaming mock.
            yield self.generate_content(model, contents, config)

    def __init__(self, **kwargs):
        self.models = self.MockModels()


def get_client() -> Optional[genai.Client]:
    """
    Returns a configured genai.Client based on environment variables.
    
    If GEMINI_REGION is set, initializes the Vertex AI client to route requests
    to that specific Google Cloud region (e.g. 'europe-west1').
    
    Otherwise, falls back to the global Developer API using GOOGLE_API_KEY.
    """
    if os.getenv("MOCK_LLM", "").lower() in ("1", "true"):
        logger.info("Initializing Mock GenAI Client for performance testing")
        return MockGenAIClient()

    region = os.getenv("GEMINI_REGION")
    project = os.getenv("GOOGLE_PROJECT_ID")
    api_key = os.getenv("GOOGLE_API_KEY")

    try:
        if region and project:
            logger.info("Initializing Vertex AI Client in region %s for project %s", region, project)
            return genai.Client(vertexai=True, location=region, project=project)
        elif api_key:
            logger.info("Initializing Developer API Client (global) using GOOGLE_API_KEY")
            return genai.Client(api_key=api_key)
        else:
            logger.warning("No GEMINI_REGION+GOOGLE_PROJECT_ID or GOOGLE_API_KEY found — LLM features disabled.")
            return None
    except Exception as e:
        logger.exception("Failed to initialize genai.Client: %s", e)
        return None




def _summarize_config(config) -> Optional[dict]:
    """Render a GenerateContentConfig into a JSON-serializable summary.

    LangSmith cannot serialize a config that carries Python function tools
    (``tools=[check_weather, ...]``) — Pydantic raises on the raw function
    objects and drops the entire input from the trace. We keep the useful,
    serializable bits and reduce tools to their names.
    """
    if config is None:
        return None
    summary: dict = {}
    for attr in ("max_output_tokens", "response_mime_type", "temperature"):
        val = getattr(config, attr, None)
        if val is not None:
            summary[attr] = val
    thinking = getattr(config, "thinking_config", None)
    if thinking is not None:
        budget = getattr(thinking, "thinking_budget", None)
        if budget is not None:
            summary["thinking_budget"] = budget
    tools = getattr(config, "tools", None)
    if tools:
        summary["tools"] = [
            getattr(t, "__name__", None) or type(t).__name__ for t in tools
        ]
    return summary


def _trace_inputs(inputs: dict) -> dict:
    """process_inputs hook for the traced wrapper: drop the unserializable
    client, summarize the config, and keep model + contents (the prompt)."""
    safe = {k: v for k, v in inputs.items() if k != "client"}
    if "config" in safe:
        safe["config"] = _summarize_config(safe["config"])
    return safe


@traceable(name="gemini.generate_content", process_inputs=_trace_inputs)
def gemini_generate(client, *, model: str, contents, config, call_type: Optional[str] = None):
    """Single traced wrapper around `client.models.generate_content` — every
    Gemini call goes through here so prompts appear in LangSmith traces and
    token usage lands in the turn's billing records (task 51).
    ``call_type`` is forwarded to the llm_call_usage metric (AC-2)."""
    t = time.time()
    response = client.models.generate_content(model=model, contents=contents, config=config)
    _capture_usage(model, response, latency_ms=(time.time() - t) * 1000, call_type=call_type)
    return response


@traceable(name="gemini.generate_content_stream", process_inputs=_trace_inputs)
def gemini_generate_stream(client, *, model: str, contents, config, on_delta=None, call_type: Optional[str] = None):
    """Synchronous streaming wrapper around `client.models.generate_content_stream`
    (Task 37). Calls ``on_delta(text)`` for each non-empty text chunk and returns
    ``(last_chunk, full_text)``. The SDK's stream is synchronous and runs
    automatic function calling inline, so tool calls fire (and emit their status)
    during iteration. The last chunk carries cumulative ``usage_metadata`` for
    the orchestrator's existing token logging.
    ``call_type`` is forwarded to the llm_call_usage metric (AC-2)."""
    t = time.time()
    full: list[str] = []
    last = None
    for chunk in client.models.generate_content_stream(
        model=model, contents=contents, config=config
    ):
        last = chunk
        # `.text` is a property that can raise (or warn → None) when a chunk
        # carries a non-text part (e.g. a function_call during AFC). Never let
        # that abort the stream — skip the chunk and keep iterating.
        try:
            text = getattr(chunk, "text", None)
        except Exception:
            text = None
        if text:
            full.append(text)
            if on_delta is not None:
                on_delta(text)
    # The final chunk carries the cumulative usage for the whole stream.
    _capture_usage(model, last, latency_ms=(time.time() - t) * 1000, call_type=call_type)
    return last, "".join(full)


def _config_has_tools(config) -> bool:
    """True when the generation config declares callable tools (so the turn may
    trigger automatic function calling)."""
    return bool(getattr(config, "tools", None))


def _slice_at_word_boundaries(text: str, target: int):
    """Yield successive slices of *text* of ~``target`` chars, each ending at a
    word boundary. Concatenating the yielded slices reproduces *text* exactly
    (whitespace and markdown preserved), so it's safe for paced re-emission."""
    i, n = 0, len(text)
    while i < n:
        j = min(i + target, n)
        while j < n and not text[j].isspace():
            j += 1
        while j < n and text[j].isspace():
            j += 1
        yield text[i:j]
        i = j


def _emit_paced(
    events, text: str, *, chunk_chars: int = 24,
    delay_s: float = 0.03, max_total_s: float = 2.5,
) -> None:
    """Emit an already-computed reply to the client as a sequence of ``delta``
    events that type in smoothly. Used for tool-capable turns, where we generate
    in one blocking call (reliable) but still want the streamed-in feel. Runs in
    the orchestrator's worker thread, so the small sleeps don't block the loop;
    the per-chunk delay shrinks so a long reply never paces longer than
    ``max_total_s``."""
    chunks = list(_slice_at_word_boundaries(text, chunk_chars))
    if not chunks:
        return
    delay = min(delay_s, max_total_s / len(chunks))
    for idx, chunk in enumerate(chunks):
        events.emit("delta", {"text": chunk})
        if delay > 0 and idx < len(chunks) - 1:
            time.sleep(delay)


def generate_maybe_stream(client, model: str, contents, config, events=None, call_type: Optional[str] = None):
    """Run a Gemini generation, streaming token deltas through ``events`` when
    the turn is streaming (web SSE), else a single synchronous call. In ALL
    paths the active EventEmitter is bound for the duration so tool functions
    can emit their status (Telegram shows tool status too). Returns
    ``(response, text)`` with the same shape callers already expect.

    ``call_type`` identifies the budget type for llm_call_usage metrics (AC-2).

    Streaming strategy:
      * **No tools** → real token-by-token streaming (fastest first token).
      * **Tool-capable** → a single BLOCKING call, then the answer is paced to
        the client. On Vertex, streaming + automatic function calling reliably
        drops the post-tool synthesis (the model calls a tool, then streams no
        answer back), which previously forced an expensive blocking re-run of
        every tool. Going straight to blocking is reliable and avoids the double
        tool cost; pacing keeps the typed-in feel.
    """
    streaming = events is not None and getattr(events, "is_streaming", False)
    token = set_current_emitter(events)
    try:
        if not streaming:
            resp = gemini_generate(client, model=model, contents=contents, config=config, call_type=call_type)
            return resp, (getattr(resp, "text", None) or "")

        if _config_has_tools(config):
            resp = gemini_generate(client, model=model, contents=contents, config=config, call_type=call_type)
            text = getattr(resp, "text", None) or ""
            if text:
                _emit_paced(events, text)
            return resp, text

        resp, text = gemini_generate_stream(
            client, model=model, contents=contents, config=config,
            on_delta=lambda txt: events.emit("delta", {"text": txt}),
            call_type=call_type,
        )
        if text.strip():
            return resp, text
        # Defensive: a tool-less stream returning nothing shouldn't happen, but
        # recover with one blocking call so the user still gets a reply.
        logger.warning(
            "Streaming returned empty text (model=%s); one blocking retry.", model,
        )
        resp = gemini_generate(client, model=model, contents=contents, config=config, call_type=call_type)
        text = getattr(resp, "text", None) or ""
        if text:
            events.emit("delta", {"text": text})
        return resp, text
    finally:
        reset_current_emitter(token)

