from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class AddCreditsRequest(BaseModel):
    user_id: str = Field(..., description="The Telegram user ID to add credits to")
    amount: int = Field(..., gt=0, description="The positive amount of credits to add")

class TelegramWebhookPayload(BaseModel):
    # Telegram webhooks are complex, so we accept a flexible dict for now
    # We could strongly type this with a Telegram library, but keeping it simple.
    message: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")

class TallyWebhookPayload(BaseModel):
    data: dict[str, Any] | None = None

    model_config = ConfigDict(extra="allow")


# ── Web chat ──────────────────────────────────────────────────────────────────

class ChatSendRequest(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000, description="The message text")


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
    has_more: bool


class ChatSearchResponse(BaseModel):
    results: list[ChatMessageOut]
