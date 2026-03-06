# Development Guidelines

## Documentation
- When creating or updating significant features, update `README.md` to reflect the changes.
- Documentation should be concise and explain the relevant parts in the code.
- When creating or updating code, add or update comments for methods and classes if the code is not self-explanatory or the cognitive load is high.
- All software should be documented in a way that is easy to understand and deploy by following the instructions in the repository.

## Feature Planning
- When implementing a new significant feature, start by creating a `task_template_<feature_name>.md` in a "feature plan" with the steps planned and the relevant info.

## Code Quality
- Write tests for the current task being developed.
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