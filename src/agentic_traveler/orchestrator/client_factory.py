import os
import logging
from typing import Optional
from google import genai

logger = logging.getLogger(__name__)

def get_client() -> Optional[genai.Client]:
    """
    Returns a configured genai.Client based on environment variables.
    
    If GEMINI_REGION is set, initializes the Vertex AI client to route requests
    to that specific Google Cloud region (e.g. 'europe-west1').
    
    Otherwise, falls back to the global Developer API using GOOGLE_API_KEY.
    """
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
