"""
Manages conversation history stored in the Supabase ``conversations`` table.

Stores the last N raw message exchanges and a compacted summary of
older history.  Compaction uses a lightweight LLM call to summarise
when the raw buffer exceeds a threshold.

Supabase layout (``conversations`` table, one row per user):
    user_id         : UUID  — FK → users.id
    recent_messages : JSONB — [{ role, text, ts }, ...]
    summary         : TEXT
    updated_at      : TIMESTAMPTZ
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from agentic_traveler.orchestrator.client_factory import (
    gemini_generate,
    suppress_usage_capture,
)
from agentic_traveler.core.observability import traceable

from agentic_traveler.analytics import usage_tracker

load_dotenv()

logger = logging.getLogger(__name__)

# How many raw message entries to keep before compacting.
# Each exchange = 2 entries (user + agent), so 12 = last 6 exchanges.
MAX_RECENT = 12
# How many entries to keep after compaction (the newest ones: 3 exchanges).
KEEP_AFTER_COMPACT = 6


class ConversationManager:
    """Load, append, compact, and save per-user conversation history."""

    def __init__(
        self,
        client: Optional[genai.Client] = None,
        model_name: str = "gemini-3.1-flash-lite",
    ):
        self.client = client
        self.model_name = model_name

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load(user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract conversation history from the assembled user doc.

        Returns:
            Dict with ``recent_messages`` (list) and ``summary`` (str).
        """
        history = user_doc.get("conversation_history", {})
        return {
            "recent_messages": history.get("recent_messages", []),
            "summary": history.get("summary", ""),
        }

    def build_context_block(
        self,
        user_doc: Dict[str, Any],
        max_messages: Optional[int] = None,
    ) -> str:
        """
        Build a text block suitable for injection into agent prompts.

        Args:
            user_doc:     The assembled user document.
            max_messages: When set, include only the last N message entries and
                          omit the compacted summary.  Use this for lightweight
                          callers (e.g. the router) that only need recent context
                          for intent classification.
                          When None (default), include the full summary + all
                          recent messages for specialized agents that need
                          complete conversational context.
        """
        history = self.load(user_doc)
        parts: List[str] = []

        messages = history["recent_messages"]
        if max_messages is not None:
            # Slim path: no summary, only the last N entries
            messages = messages[-max_messages:]
        else:
            # Full path: prepend compacted summary
            if history["summary"]:
                parts.append(f"Previous conversation summary:\n{history['summary']}")

        if messages:
            lines = []
            for msg in messages:
                role = "User" if msg.get("role") == "user" else "Agent"
                lines.append(f"{role}: {msg.get('text', '')}")
            parts.append("Recent messages:\n" + "\n".join(lines))

        return "\n\n".join(parts) if parts else ""

    def append_and_save(
        self,
        user_doc: Dict[str, Any],
        user_id: str,
        user_msg: str,
        agent_reply: str,
    ) -> None:
        """
        Append an exchange to history.  Compacts if the buffer overflows,
        then persists to the ``conversations`` table.

        Args:
            user_doc:   The assembled user doc dict.
            user_id:    The user's UUID.
            user_msg:   The user's message text.
            agent_reply: The agent's reply text.
        """
        from agentic_traveler.tools.db_client import get_db

        history = self.load(user_doc)
        now = datetime.now(timezone.utc).isoformat()

        history["recent_messages"].append(
            {"role": "user", "text": user_msg, "ts": now}
        )
        history["recent_messages"].append(
            {"role": "agent", "text": agent_reply, "ts": now}
        )

        if len(history["recent_messages"]) > MAX_RECENT:
            history = self._compact(history)

        try:
            get_db().table("conversations").upsert(
                {
                    "user_id": user_id,
                    "recent_messages": history["recent_messages"],
                    "summary": history["summary"],
                }
            ).execute()
            logger.debug(
                "Saved conversation history (%d recent msgs).",
                len(history["recent_messages"]),
            )
        except Exception:
            logger.exception("Failed to save conversation history for user_id=%s", user_id)

    # ------------------------------------------------------------------
    # Compaction
    # ------------------------------------------------------------------

    def _compact(self, history: Dict[str, Any]) -> Dict[str, Any]:
        """
        Summarise the oldest messages and merge into the existing summary.

        Keeps only the ``KEEP_AFTER_COMPACT`` newest messages as raw text.
        """
        messages = history["recent_messages"]
        to_compact = messages[:-KEEP_AFTER_COMPACT]
        to_keep = messages[-KEEP_AFTER_COMPACT:]

        old_summary = history.get("summary", "")
        new_summary = self._summarise(to_compact, old_summary)

        logger.info(
            "Compacted %d messages into summary (%d chars).",
            len(to_compact),
            len(new_summary),
        )
        return {
            "recent_messages": to_keep,
            "summary": new_summary,
        }

    @traceable(name="conversation_manager.summarise")
    def _summarise(
        self, messages: List[Dict[str, Any]], existing_summary: str
    ) -> str:
        """Call the LLM to produce a combined summary."""
        if not self.client:
            lines = [f"{m.get('role','')}: {m.get('text','')}" for m in messages]
            return (existing_summary + "\n" + "\n".join(lines)).strip()

        conversation_text = "\n".join(
            f"{m.get('role','').title()}: {m.get('text','')}" for m in messages
        )

        existing_block = (
            f"Existing summary of earlier conversation:\n{existing_summary}"
            if existing_summary
            else ""
        )

        prompt = f"""\
Summarise the following conversation fragment into a concise paragraph.
Preserve any concrete facts — destination names, dates, budgets, preferences (especially tone/communication style requests),
decisions made, and questions still open.

{existing_block}

New messages to incorporate:
{conversation_text}

Write ONLY the updated summary, nothing else.
"""
        try:
            t = time.time()
            # System-paid call: compaction must never enter the user's
            # per-turn billing records (task 51); it self-logs below.
            with suppress_usage_capture():
                response = gemini_generate(
                    self.client,
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        max_output_tokens=1800,
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
                        ]
                    ),
                )
            usage_tracker.log_and_accumulate(
                agent_name="compaction",
                model_name=self.model_name,
                user_id="system",
                response=response,
                latency_ms=(time.time() - t) * 1000,
            )
            return response.text.strip()
        except Exception:
            logger.exception("Compaction LLM call failed — raw fallback.")
            lines = [f"{m.get('role','')}: {m.get('text','')}" for m in messages]
            return (existing_summary + "\n" + "\n".join(lines)).strip()
