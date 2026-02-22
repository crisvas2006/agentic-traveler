"""
Manages conversation history stored in a Firestore user document.

Stores the last N raw message exchanges and a compacted summary of
older history.  Compaction uses a lightweight LLM call to summarise
when the raw buffer exceeds a threshold.

Firestore layout (under each user doc):
    conversation_history:
        recent_messages: [{ role, text, ts }, ...]
        summary: "..."
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

# How many raw message entries to keep before compacting.
# Each exchange = 2 entries (user + agent), so 10 = last 5 exchanges.
MAX_RECENT = 10
# How many entries to keep after compaction (the newest ones).
KEEP_AFTER_COMPACT = 4


class ConversationManager:
    """Load, append, compact, and save per-user conversation history."""

    def __init__(
        self,
        client: Optional[genai.Client] = None,
        model_name: str = "gemini-2.5-flash-lite",
    ):
        self.client = client
        self.model_name = model_name

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @staticmethod
    def load(user_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract conversation history from a user document.

        Returns:
            Dict with ``recent_messages`` (list) and ``summary`` (str).
        """
        history = user_doc.get("conversation_history", {})
        return {
            "recent_messages": history.get("recent_messages", []),
            "summary": history.get("summary", ""),
        }

    def build_context_block(self, user_doc: Dict[str, Any]) -> str:
        """
        Build a text block suitable for injection into agent prompts.

        Combines the compacted summary with the recent raw messages
        so the LLM has full conversational context.
        """
        history = self.load(user_doc)
        parts: List[str] = []

        if history["summary"]:
            parts.append(f"Previous conversation summary:\n{history['summary']}")

        if history["recent_messages"]:
            lines = []
            for msg in history["recent_messages"]:
                role = "User" if msg.get("role") == "user" else "Agent"
                lines.append(f"{role}: {msg.get('text', '')}")
            parts.append("Recent messages:\n" + "\n".join(lines))

        return "\n\n".join(parts) if parts else ""

    def append_and_save(
        self,
        user_doc: Dict[str, Any],
        user_doc_ref,
        user_msg: str,
        agent_reply: str,
    ) -> None:
        """
        Append an exchange to history.  Compacts if the buffer overflows,
        then persists to Firestore.
        """
        history = self.load(user_doc)
        now = datetime.now(timezone.utc).isoformat()

        history["recent_messages"].append(
            {"role": "user", "text": user_msg, "ts": now}
        )
        history["recent_messages"].append(
            {"role": "agent", "text": agent_reply, "ts": now}
        )

        # Compact if we exceeded the buffer
        if len(history["recent_messages"]) > MAX_RECENT:
            history = self._compact(history)

        # Persist
        user_doc_ref.set(
            {"conversation_history": history},
            merge=True,
        )
        logger.debug(
            "Saved conversation history (%d recent msgs).",
            len(history["recent_messages"]),
        )

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

    def _summarise(
        self, messages: List[Dict[str, Any]], existing_summary: str
    ) -> str:
        """Call the LLM to produce a combined summary."""
        if not self.client:
            # Fallback: just concatenate texts
            lines = [f"{m.get('role','')}: {m.get('text','')}" for m in messages]
            return (existing_summary + "\n" + "\n".join(lines)).strip()

        conversation_text = "\n".join(
            f"{m.get('role','').title()}: {m.get('text','')}" for m in messages
        )

        prompt = f"""\
Summarise the following conversation fragment into a concise paragraph.
Preserve any concrete facts — destination names, dates, budgets, preferences,
decisions made, and questions still open.

{"Existing summary of earlier conversation:\n" + existing_summary if existing_summary else ""}

New messages to incorporate:
{conversation_text}

Write ONLY the updated summary, nothing else.
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=300,
                ),
            )
            return response.text.strip()
        except Exception:
            logger.exception("Compaction LLM call failed — raw fallback.")
            lines = [f"{m.get('role','')}: {m.get('text','')}" for m in messages]
            return (existing_summary + "\n" + "\n".join(lines)).strip()
