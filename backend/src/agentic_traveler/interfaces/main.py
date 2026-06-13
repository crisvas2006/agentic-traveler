import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables before any local modules are imported
load_dotenv(override=True)

from agentic_traveler.analytics import metrics_tracker  # noqa: E402
from agentic_traveler.core.logging_config import setup_logging  # noqa: E402
from agentic_traveler.interfaces.routers.admin import router as admin_router  # noqa: E402
from agentic_traveler.interfaces.routers.chat import router as chat_router  # noqa: E402
from agentic_traveler.interfaces.routers.metrics import router as metrics_router  # noqa: E402
from agentic_traveler.interfaces.routers.tally import router as tally_router  # noqa: E402
from agentic_traveler.interfaces.routers.telegram import router as telegram_router  # noqa: E402
from agentic_traveler.interfaces.routers.profile import router as profile_router  # noqa: E402
from agentic_traveler.interfaces.routers.trips import router as trips_router  # noqa: E402
setup_logging(verbose=os.getenv("VERBOSE", "").lower() in ("1", "true"))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI application...")
    
    # Unlock Python's thread pool to match Cloud Run's concurrency limits for SSE
    try:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=50))
        logger.info("Set default asyncio ThreadPoolExecutor max_workers to 50.")
    except Exception as e:
        logger.warning(f"Failed to set ThreadPoolExecutor: {e}")

    yield
    # Shutdown
    logger.info("Shutting down... flushing metrics.")
    metrics_tracker.flush(sync=True)
    logger.info("Graceful shutdown complete.")

app = FastAPI(
    title="Agentic Traveler API",
    lifespan=lifespan,
)

# CORS — only needed for the web chat endpoint. Telegram/Tally are S2S.
# FRONTEND_ORIGIN should be a comma-separated list (e.g. "https://app.example.com,http://localhost:3000").
_origins = [o.strip() for o in os.getenv("FRONTEND_ORIGIN", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

app.include_router(telegram_router, tags=["Telegram"])
app.include_router(tally_router, tags=["Tally"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])
app.include_router(chat_router)
app.include_router(metrics_router)
app.include_router(trips_router)
app.include_router(profile_router)

@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "ok"}
