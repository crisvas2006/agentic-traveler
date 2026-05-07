# Testing Strategy

This document outlines the testing policies for the Agentic Traveler project to ensure stability, particularly when introducing new LLM features or refactoring core orchestration logic.

## 1. Automated Regression Testing

### Pytest Suite
All core logic components, utils, and non-LLM boundaries must have automated tests located in the `tests/` directory.

**Running Tests Locally:**
```powershell
# Run the full suite
.\.venv\Scripts\pytest

# Run a specific test file
.\.venv\Scripts\pytest tests/test_credit_manager.py
```

### When to Write Tests
- **New Features:** Any new tool, guardrail, or database interaction must include unit tests.
- **Bug Fixes:** Before fixing a bug, write a failing test that reproduces it. The fix is considered complete when the test passes.
- **Refactoring:** Do not modify existing core logic without ensuring the relevant test suite passes.

### Mocking LLMs and External APIs
Tests should execute quickly and without incurring API costs. 
- Use `unittest.mock` to mock Firestore interactions (`FirestoreUserTool`).
- Use mock responses for `genai.Client` to simulate LLM function calling and text generation.
- Never make real calls to the Gemini API or Telegram API within the automated test suite.

## 2. Pre-Deployment Checklist

Before merging major features or deploying to Google Cloud Run, developers must complete a full regression test:

1. **Static Analysis:**
   Run `ruff check .` to ensure no linting errors.

2. **Automated Suite:**
   Run the full pytest suite and ensure a 100% pass rate.
   ```powershell
   .\.venv\Scripts\pytest
   ```

3. **Manual Flow Validation:**
   For any changes affecting the Orchestrator or Telegram Webhook, you MUST perform a manual staging test.
   - Start the local Flask server (`python -m agentic_traveler.interfaces.webhook`).
   - Run `ngrok http 8080`.
   - Complete the structured manual test flow defined in `tests/manual_test_flow.md` using your Telegram client.

## 3. Continuous Integration (Future)

To guarantee regression tests are always up to date:
- Future iterations will introduce a `.github/workflows/test.yml` or `cloudbuild.yaml` step that automatically runs the pytest suite on every commit to the `main` branch.
- Deployments will be blocked if the automated test suite fails.
