#python imports

#third-party imports
from sqlalchemy.ext.asyncio import AsyncSession

#project imports
from memory_service.schemas.recall import RecallRequest
from memory_service.schemas.search import SearchRequest, SearchResponse
from memory_service.services.embeddings import EmbeddingService
from memory_service.services.recall import RecallService


class SearchService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.recall_service = RecallService(session, embedding_service=embedding_service)

    async def search(self, request: SearchRequest) -> SearchResponse:
        candidates = await self.recall_service.retrieve_candidates(
            RecallRequest(
                query=request.query,
                session_id=request.session_id or "",
                user_id=request.user_id,
                max_tokens=4096,
            )
        )
        results = []
        for candidate in candidates[: request.limit]:
            results.append(
                {
                    "content": f"{candidate.memory.key}: {candidate.memory.value}",
                    "score": round(candidate.score, 4),
                    "session_id": candidate.memory.session_id,
                    "timestamp": candidate.memory.updated_at or candidate.memory.created_at,
                    "metadata": {
                        "memory_id": str(candidate.memory.id),
                        "type": candidate.memory.type,
                        "key": candidate.memory.key,
                        "active": candidate.memory.active,
                        "snippet": candidate.snippet,
                        "turn_id": str(candidate.turn_id) if candidate.turn_id else None,
                    },
                }
            )
        return SearchResponse(results=results)
