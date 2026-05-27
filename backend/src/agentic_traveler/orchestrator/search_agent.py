"""
Search Agent — Google Search grounding proxy.

Isolates all grounded calls so the $0.035/prompt grounding fee is only
incurred when an agent explicitly needs real-time data, not on every call.
"""

import logging
import time
from typing import Optional, Any

from google import genai
from google.genai import types

from agentic_traveler.orchestrator.client_factory import get_client

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.1-flash-lite"

_SYSTEM_PROMPT = """\
You are a factual search assistant. Given a query and a desired output
format, search the web and return results matching that format.

If the caller asks for "comprehensive", provide detailed findings with
full context and analysis.
If the caller asks for "headline", provide a one-line summary.
If the caller asks for "structured", provide key facts as bullet points.

Always cite sources. Do not add opinions or recommendations.
"""


class SearchAgent:
    """
    Grounded search proxy. Called as a tool by Chat, Trip, and Planner agents.

    Keeps Google Search grounding strictly opt-in: the fee is only incurred
    when an agent explicitly calls search().
    """

    def __init__(self, client: Optional[genai.Client] = None):
        self._client = client or get_client()

    def search(self, query: str, format: str = "structured") -> str:
        """
        Search the web for current, time-sensitive information.

        Call this when you need real-time data that you cannot answer from
        general knowledge: visa requirements, travel advisories, event dates,
        current prices, opening hours, or live conditions.

        Do NOT call for general destination knowledge, cultural context,
        or geography — you already know those.

        Args:
            query: The specific question to search for.
            format: Desired output format — "headline" (1-line summary),
                    "structured" (key facts as bullet points),
                    or "comprehensive" (detailed analysis with full context).

        Returns:
            Factual results with source citations.
        """
        text, _, _ = self.search_with_metadata(query, format)
        return text

    def search_with_metadata(self, query: str, format: str = "structured") -> tuple[str, Any, float]:
        """Internal method that returns the text, raw response, and latency."""
        logger.info("🔍 SearchAgent.search(query=%s, format=%s)", query[:80], format)
        t = time.time()
        try:
            response = self._client.models.generate_content(
                model=_MODEL,
                contents=f"Format: {format}\n\nQuery: {query}",
                config=types.GenerateContentConfig(
                    system_instruction=_SYSTEM_PROMPT,
                    temperature=0.2,
                    max_output_tokens=3500,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(
                        maximum_remote_calls=3,
                    ),
                    safety_settings=[
                        types.SafetySetting(
                            category=c,
                            threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        ) for c in [
                            types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        ]
                    ],
                ),
            )
            lat = (time.time() - t) * 1000
            logger.info("⏱ SearchAgent: %.0fms", lat)
            return response.text or "No results found.", response, lat
        except Exception:
            logger.exception("SearchAgent.search failed.")
            return "I couldn't retrieve search results right now. Please try again.", None, 0.0

    def create_tool(self, context_list: list):
        """
        Creates a tool function for the LLM that wraps search_with_metadata
        and appends its usage data to context_list.
        """
        def search_web(query: str, format: str = "structured") -> str:
            text, raw, lat = self.search_with_metadata(query, format)
            if raw:
                context_list.append({"raw": raw, "lat": lat})
            return text
            
        search_web.__doc__ = self.search.__doc__
        return search_web
