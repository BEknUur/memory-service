from datetime import datetime
from typing import Literal

from pydantic import BaseModel

MemoryType = Literal["fact", "preference", "opinion", "event"]


class MemoryResponse(BaseModel):
    id: str
    type: MemoryType | str
    key: str
    value: str
    confidence: float
    source_session: str
    source_turn: str | None
    created_at: datetime
    updated_at: datetime
    supersedes: str | None
    superseded_by: str | None
    active: bool
    confirmation_count: int


class UserMemoriesResponse(BaseModel):
    memories: list[MemoryResponse]
