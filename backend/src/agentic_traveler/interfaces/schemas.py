from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class AddCreditsRequest(BaseModel):
    user_id: str = Field(..., description="The Telegram user ID to add credits to")
    amount: int = Field(..., gt=0, description="The positive amount of credits to add")

class TelegramWebhookPayload(BaseModel):
    # Telegram webhooks are complex, so we accept a flexible dict for now
    # We could strongly type this with a Telegram library, but keeping it simple.
    message: dict[str, Any] | None = None
    # Inline-keyboard taps arrive as callback_query updates (Task 43), not as
    # `message`. Kept loosely typed for the same reason as `message`.
    callback_query: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")

class TallyWebhookPayload(BaseModel):
    data: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


# ── Web chat ──────────────────────────────────────────────────────────────────

class SelectionIn(BaseModel):
    """A tapped multiple-choice answer (Task 43). ``slot`` is the categorical
    slot being filled; ``values`` are the chosen option ids/values (one for a
    single-select slot, possibly several for an ``allow_multi`` slot). The
    backend re-validates every value against the slot's legal options."""

    slot: str = Field(..., min_length=1, max_length=64)
    values: list[str] = Field(..., min_length=1, max_length=10)


class ChatSendRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000, description="The message text")
    # When present, the message is a tapped chip rather than typed text: `body`
    # is the human-readable chosen label (shown in the bubble) and `selection`
    # carries the structured answer applied deterministically (Task 43).
    selection: SelectionIn | None = None


class ChatMessageOut(BaseModel):
    id: int
    thread_id: str
    sender_type: str
    sender_user_id: str | None = None
    body: str
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class ChatSendResponse(BaseModel):
    user_message: ChatMessageOut
    reply: ChatMessageOut


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageOut]
    has_more: bool  # backward compat, means has_more_older
    has_more_newer: bool = False


class ChatSearchResponse(BaseModel):
    results: list[ChatMessageOut]
