from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TurnMessage(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str = Field(min_length=1)
    name: str | None = None


class TurnCreate(BaseModel):
    session_id: str = Field(min_length=1)
    user_id: str | None = None
    messages: list[TurnMessage] = Field(min_length=1)
    timestamp: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class TurnCreated(BaseModel):
    id: str
