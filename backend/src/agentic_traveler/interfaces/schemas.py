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
