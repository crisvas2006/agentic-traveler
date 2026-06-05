# Agentic Traveler — Gemini Instructions

This is the instructional guide for Gemini coding agents working in this repository.

> [!IMPORTANT]
> **CLAUDE.md is the central instruction file and single source of truth** for repository layout, build/test/run commands, development guidelines, security rules, and project-specific invariants.
> 
> You MUST read and follow [CLAUDE.md](CLAUDE.md) before writing any code or proposing plans. Do not duplicate its content here.

---

## 1. Slash Commands

This repository includes custom slash commands defined in the `.claude/commands/` directory. Gemini agents should recommend these commands to the user or mimic their workflows to verify code quality:

- **`/spec <description>`** — Creates a task spec under `specs/` following `task_template_v2.md`. Highly recommended before implementing tasks that touch multiple modules or take >2 hours. (See [.claude/commands/spec.md](.claude/commands/spec.md))
- **`/review [spec path]`** — Audits the current git diff against the hard blocks and guidelines in `CLAUDE.md` and the spec (if provided). (See [.claude/commands/review.md](.claude/commands/review.md))
- **`/ship [spec path]`** — Pre-commit gate that runs linting, tests, builds, and checks spec DoD before the user commits. (See [.claude/commands/ship.md](.claude/commands/ship.md))

---

## 2. Gemini 3.5 Agentic Development Guidelines

When modifying, designing, or adding agents, tools, or prompts in the `backend/src/agentic_traveler/orchestrator/` or `backend/src/agentic_traveler/tools/` layers, adhere to the following Gemini-specific best practices:

### 1. Model Selection & Cost Control
- **Lightweight Tasks:** Use `gemini-3.1-flash-lite` for intent routing, simple chat, summary tasks, and classification.
- **Reasoning/Synthesis:** Use `gemini-3.5-flash` for complex destination discovery (`TripAgent`) and itinerary planning (`PlannerAgent`).
- **Thinking Budget:** For reasoning-heavy sub-agents, enable `thinking_config` with a sensible budget (e.g., `512` tokens) to ensure high-quality output before synthesis.

### 2. Google GenAI SDK Integration
- **Always use the new `google-genai` SDK** (e.g., `from google import genai`). Do NOT use the legacy, deprecated `google-generativeai` package.
- All GenAI client instances must be obtained via the client factory:
  ```python
  from agentic_traveler.orchestrator.client_factory import get_client
  client = get_client()
  ```

### 3. Structured Output (JSON Mode & Schema Enforcement)
- To guarantee the structure of the returned JSON, always use a Pydantic model with `response_schema` in the `GenerateContentConfig`:
  ```python
  from pydantic import BaseModel, Field

  class RouteResponse(BaseModel):
      intent: str = Field(description="Must be exactly one of: CHAT, TRIP, PLAN, OFF_TOPIC")
      request_summary: str = Field(description="One-sentence description of the user request")
      preference_updated: Optional[dict] = Field(default=None, description="Updated preference metadata")
      response: Optional[str] = Field(default=None, description="Redirection or credit info response")

  config = types.GenerateContentConfig(
      response_mime_type="application/json",
      response_schema=RouteResponse,
      system_instruction=system_prompt,
  )
  ```
- This forces the LLM to output valid JSON matching the exact schema structure, minimizing prompt engineering complexity.
- Always parse the response using Pydantic validation (e.g. `RouteResponse.model_validate_json(response.text)`) wrapped in a `try...except` block, providing a sensible fallback (e.g., default to `CHAT` intent) if the validation or parsing fails.

### 4. Automatic Function Calling (AFC) & Tools
- Pass tools as standard Python functions in the `tools` list of `GenerateContentConfig`.
- Leverage AFC by setting `automatic_function_calling` with a strict `maximum_remote_calls` limit:
  - **Router Agent:** `maximum_remote_calls=4` (credit checks, updates).
  - **Trip Agent:** `maximum_remote_calls=6` (weather checks, search).
  - **Planner Agent:** `maximum_remote_calls=8` (multi-day planning requiring multiple weather and search calls).
- Avoid enabling Google Search grounding directly in specialized agents. Instead, proxy grounding queries through `SearchAgent` using the `search_web` tool to capture grounding logs and handle token/credit billing correctly.

### 5. Error Isolation & Safety
- **Wrap Generate Content Calls:** Always catch exceptions around `generate_content` calls. Log the traceback via `logger.exception()` but return a friendly, generic fallback message to the user (e.g., `"I hit a snag. Please try again."`) with an `action: "ERROR"` response.
- **Credit Billing Guard:** If an LLM call fails or raises an error, do not deduct credits from the user's balance. Pass `token_records=[]` to `_save_and_finish` under error conditions.
- **Safety Blocks:** Explicitly set safety thresholds to `BLOCK_ONLY_HIGH` to prevent false-positive blocks from returning empty responses:
  ```python
  safety_settings=[
      types.SafetySetting(
          category=c,
          threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
      ) for c in [...]
  ]
  ```

---

## 3. Git Operations & Safe Sandbox Guidelines
- **Strict Read-Only Git Policy:** Gemini agents must never run modifying git commands (including `git add`, `git commit`, `git restore`, `git reset`, `git checkout`). You are limited strictly to read-only git operations (e.g. `git status`, `git diff`, `git log`, `git show`). Any staging, unstaging, or committing of files must be left entirely to the user.