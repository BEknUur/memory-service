#python imports
from uuid import UUID

#third-party imports
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

#project imports
from memory_service.db.models import Memory, MemoryEvidence
from memory_service.schemas.memories import MemoryResponse


class MemoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_user_memories(self, user_id: str) -> list[MemoryResponse]:
        statement = (
            select(Memory, MemoryEvidence.turn_id)
            .outerjoin(MemoryEvidence, MemoryEvidence.memory_id == Memory.id)
            .where(Memory.user_id == user_id)
            .order_by(Memory.created_at.asc(), MemoryEvidence.created_at.asc())
        )
        rows = (await self.session.execute(statement)).all()

        memories_by_id: dict[UUID, MemoryResponse] = {}
        for memory, turn_id in rows:
            if memory.id in memories_by_id:
                continue

            memories_by_id[memory.id] = MemoryResponse(
                id=str(memory.id),
                type=memory.type,
                key=memory.key,
                value=memory.value,
                confidence=memory.confidence,
                source_session=memory.session_id,
                source_turn=str(turn_id) if turn_id else None,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
                supersedes=str(memory.supersedes_id) if memory.supersedes_id else None,
                superseded_by=str(memory.superseded_by_id) if memory.superseded_by_id else None,
                active=memory.active,
                confirmation_count=memory.confirmation_count,
            )

        return list(memories_by_id.values())
