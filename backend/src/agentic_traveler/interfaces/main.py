import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

# Load environment variables before any local modules are imported
load_dotenv(override=True)

from agentic_traveler.analytics import metrics_tracker
from agentic_traveler.core.logging_config import setup_logging
from agentic_traveler.interfaces.routers.admin import router as admin_router
from agentic_traveler.interfaces.routers.tally import router as tally_router
from agentic_traveler.interfaces.routers.telegram import router as telegram_router
setup_logging(verbose=os.getenv("VERBOSE", "").lower() in ("1", "true"))
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FastAPI application...")
    yield
    # Shutdown
    logger.info("Shutting down... flushing metrics.")
    metrics_tracker.flush(sync=True)
    logger.info("Graceful shutdown complete.")

app = FastAPI(
    title="Agentic Traveler API",
    lifespan=lifespan,
)

app.include_router(telegram_router, tags=["Telegram"])
app.include_router(tally_router, tags=["Tally"])
app.include_router(admin_router, prefix="/admin", tags=["Admin"])

@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint for Cloud Run."""
    return {"status": "ok"}
