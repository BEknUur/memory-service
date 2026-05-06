#python imports
from datetime import datetime
from typing import Any

#third-party imports
from pydantic import BaseModel, Field

#project imports


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    session_id: str | None = None
    user_id: str | None = None
    limit: int = Field(default=10, ge=1, le=50)


class SearchResult(BaseModel):
    content: str
    score: float
    session_id: str
    timestamp: datetime
    metadata: dict[str, Any]


class SearchResponse(BaseModel):
    results: list[SearchResult]
