# Task Spec: FastAPI Migration

> **Status: ✅ COMPLETED** (2026-05-15)

## Goal
Migrate the existing Aletheia Travel backend web layer from Flask to **FastAPI**. 
This migration aims to modernize the API layer to natively support asynchronous execution (critical for I/O-bound LLM tasks), leverage automatic data validation via Pydantic, and generate interactive API documentation out of the box.

## Why FastAPI? (Advantages)
1. **Asynchronous by Default (`async/await`)**: Agentic workflows and LLM API calls are highly I/O bound. FastAPI is built on an asynchronous ASGI foundation (Starlette), allowing it to handle thousands of concurrent connections efficiently without blocking the main thread.
2. **Built-in Background Tasks**: Replaces our manual `threading.Thread` usage in `webhook.py` with FastAPI's native `BackgroundTasks`, which is safer, easier to test, and managed by the framework.
3. **Automatic Data Validation**: Replaces manual `request.get_json()` checks with Pydantic models. If a payload is malformed, FastAPI automatically returns a standardized 422 Unprocessable Entity error.
4. **Auto-generated Documentation**: Instantly provides interactive Swagger UI (`/docs`) and ReDoc (`/redoc`) based on endpoint signatures, drastically simplifying admin and debugging interactions.
5. **Type Safety**: Enforces Python type hints (`int`, `str`, `List`) at the routing layer, reducing runtime bugs.

## APIs Requiring Migration
The following endpoints currently exist across the backend and require migration:

### 1. Main Cloud Run Service (`backend/src/agentic_traveler/interfaces/webhook.py`)
*   `POST /webhook/<secret>`: The core Telegram webhook handler. Needs to be refactored to use FastAPI's `BackgroundTasks` instead of spawning manual threads for the orchestrator.
*   `GET /health`: Cloud Run health check. Trivial migration.
*   `POST /admin/add-credits`: Needs a Pydantic model for the request body (`user_id`, `amount`) and dependency injection for the `X-Admin-Key` header.
*   `POST /promo/redeem`: Needs a Pydantic model for the request body (`user_id`, `code`).

### 2. Tally Webhook (`POST /tally-webhook`)
*   Currently integrated into the main Flask application (`webhook.py`).
*   **Recommendation**: Migrate this existing route to FastAPI. This allows us to use FastAPI's Pydantic validation for incoming Tally payloads, replacing manual dictionary parsing.

## Approach
1.  **Dependency Updates**: Replace `Flask` and `Werkzeug` with `fastapi` and `uvicorn` in `backend/requirements.txt` and `pyproject.toml`.
2.  **Pydantic Models**: Create a new file `backend/src/agentic_traveler/interfaces/schemas.py` to define the data structures for incoming requests.
3.  **Refactor Main App**: Rewrite `webhook.py` (or rename to `main.py`) to use FastAPI decorators.
4.  **Background Tasks**: Update the Telegram webhook dispatcher to utilize `fastapi.BackgroundTasks` for non-blocking agent execution.
5.  **Tally Migration**: Migrate the existing `/tally-webhook` logic to use a FastAPI router and Pydantic models for request validation.

## Alternatives Considered
*   **Flask 2.0 Async**: We could adopt Flask's newer async capabilities. *Why rejected:* Flask's async is bolted onto a synchronous WSGI core. It still doesn't provide Pydantic validation or Swagger docs, missing out on major developer experience improvements.
*   **Keep as is**: The current Flask app works. *Why rejected:* As the user base scales, the manual threading model for LLM calls will consume excessive memory per worker. FastAPI's event loop handles concurrency far more efficiently.

## Steps

1.  [ ] **Setup & Dependencies**: Add `fastapi` and `uvicorn` to backend requirements.
2.  [ ] **Model Definition**: Create Pydantic models for Admin/Promo endpoints and Tally payloads.
3.  [ ] **Endpoint Conversion (Admin & Health)**: Migrate `/health`, `/admin/add-credits`, and `/promo/redeem` to FastAPI.
    *   *Verify*: Curl endpoints locally to ensure validation and 200/400 responses match expectations.
4.  [ ] **Telegram Webhook Refactor**: Migrate the `/webhook/<secret>` endpoint.
    *   Replace `threading.Thread` with `BackgroundTasks`.
    *   Preserve all 5 layers of defense (Secret, IP whitelist, Rate limiting, etc.).
    *   *Verify*: Send test messages via Telegram to local ngrok environment.
5.  [ ] **Tally Integration**: Migrate the existing `tally_webhook` route to FastAPI.
    *   *Verify*: Send a mock Tally payload locally and ensure Supabase updates correctly.
6.  [ ] **Docker & Deployment Config**: Update `Dockerfile` to use `uvicorn` instead of Flask/Gunicorn. Update `DEPLOYMENT.md` instructions.
    *   *Verify*: Build docker container locally and run it.

## Proposed Improvements for Migration
Before starting, we should incorporate these modern FastAPI best practices to maximize the value of the rewrite:

1. **Modular Routing (`APIRouter`)**: Instead of keeping all endpoints in a single `webhook.py` file, we should split them logically:
   - `routers/telegram.py` (for `/webhook/<secret>`)
   - `routers/tally.py` (for `/tally-webhook`)
   - `routers/admin.py` (for `/admin/*` and `/promo/*`)
2. **Dependency Injection (`Depends`)**: Use FastAPI's dependency system for authentication. Create reusable dependencies like `verify_admin_key` or `verify_tally_token` instead of inline `if/else` checks.
3. **Lifespan Events**: Use FastAPI's modern `@asynccontextmanager` for lifespan events (startup/shutdown) instead of the deprecated `@app.on_event`. This is useful for initializing the Supabase client or pre-loading the Gemini models.
4. **Global Exception Handling**: Implement custom exception handlers (`@app.exception_handler`) to catch internal errors (like Supabase constraint violations) and map them to clean HTTP 400/500 JSON responses automatically.

## Risks & Open Questions
*   **WinError 10038**: In Flask, we had to suppress a specific Werkzeug socket error during local hot-reloads on Windows. We need to verify if Uvicorn exhibits similar behavior on Windows during local development.
*   **Rate Limiting**: The current rate limiter is an in-memory dictionary with a `threading.Lock`. Since FastAPI uses an event loop, this is technically thread-safe in async, but we need to ensure it behaves correctly across async context switches.

## Out of Scope
*   Replacing the `requests` library in the orchestrator with an async alternative (`httpx`). While `httpx` is more optimal for FastAPI, migrating the entire agent orchestration to `async/await` is a massive task. We will continue running the orchestrator synchronously inside FastAPI's background thread pool for now.
