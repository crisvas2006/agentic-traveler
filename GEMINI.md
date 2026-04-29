# Development Guidelines

## How to Think

### 1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
Minimum code that solves the problem. Nothing speculative — but flag what's worth considering.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.
- Prefer a library when it reduces surface area you'd need to test and maintain — not just because it exists.

**Proactive suggestions:** When you spot a meaningful improvement beyond the task scope, surface it — don't silently implement it, but don't silently discard it either.
- **High confidence it's right and valuable** (clear win, low risk): include it in the plan as an intended step. The human will remove it if unwanted.
- **Lower confidence or non-trivial tradeoff**: present it as a proposal and ask before implementing.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

Every changed line should trace directly to the user's request or an explicitly surfaced suggestion.

### 4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:

[Step] → verify: [check]
[Step] → verify: [check]
[Step] → verify: [check]


## Documentation
- When creating or updating significant features, update `README.md` to reflect the changes.
- Documentation should be concise and explain the relevant parts in the code.
- When creating or updating code, add or update comments for methods and classes if the code is not self-explanatory or the cognitive load is high.
- All software should be documented in a way that is easy to understand and deploy by following the instructions in the repository.

## Feature Planning & Task Specs
Create a `task_spec_<feature_name>.md` before writing any code when a task meets either of these conditions:
- **Scope:** touches more than one module, or expected to take more than ~2 hours.
- **Cognitive complexity:** introduces mechanisms that are non-trivial to reason about (e.g. new async patterns, state machines, external integrations, security boundaries, data migrations).

The spec serves two purposes: guiding implementation, and helping humans understand what the task involves and why decisions were made.

A task spec should include:
- **Goal** — what problem this solves and why.
- **Approach** — the chosen solution and key design decisions.
- **Alternatives considered** — what was ruled out and why.
- **Steps** — ordered implementation plan with verification checkpoints.
- **Risks & open questions** — known unknowns, tradeoffs, dependencies.
- **Out of scope** — explicit boundaries to prevent scope creep.

## Code Quality
- Write tests before or alongside implementation for the current task.
- Use logging for meaningful context (user IDs, intent, timing) — but never log sensitive data.
- Run `ruff check` before considering code complete.
- Prioritize integrating libraries and APIs with low code rather than building complex features from scratch.

## Security
- Never hardcode secrets (API keys, tokens, passwords) in source code — always use environment variables.
- Never log secrets or PII (user tokens, phone numbers, full API keys).
- Sanitize user input before passing to LLM prompts (prompt injection risk).
- Verify `.env` is in `.gitignore` — never commit secrets.

## Python & Compatibility
- Target Python 3.13 — must match the version in `Dockerfile`.
- Pin dependency versions in `requirements.txt` for reproducible builds.
- Test syntax-sensitive changes against the Docker Python version.

## Deployment
- Do not commit changes automatically.
- Never auto-deploy to Cloud Run without explicit approval.
- Always verify the container starts (check Cloud Run logs) after deployment.
- Treat the `Dockerfile` Python version as source of truth for compatibility.

## Data & Models
- Do not remove fields of models without approval.

## Cost Awareness
- Prefer lightweight models for non-critical tasks (e.g., `gemini-2.5-flash-lite` for summarization).
- Note Cloud Run billing implications of any config changes (instances, concurrency, memory).

## Project Structure
```
project-root/
    pyproject.toml      # deps, metadata, config for tools
    src/
        agentic_traveler/
            __init__.py
            ...
    tests/
        test_something.py
    specs/               # domain knowledge, form content, etc.
```