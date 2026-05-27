import os
import logging
from typing import Optional
from google import genai

logger = logging.getLogger(__name__)

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
                    "preference_updated": None,
                    "response": None
                })
            else:
                MockResponse.text = "*Mocked travel suggestion!* You should visit Rome and enjoy the local culinary scenes."
                
            return MockResponse()

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
