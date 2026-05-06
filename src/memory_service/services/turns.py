from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from memory_service.db.models import Memory, MemoryEvidence, Turn
from memory_service.schemas.turns import TurnCreate


class TurnService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_turn(self, payload: TurnCreate) -> UUID:
        turn = Turn(
            id=uuid4(),
            session_id=payload.session_id,
            user_id=payload.user_id,
            messages=[message.model_dump(exclude_none=True) for message in payload.messages],
            metadata_=payload.metadata,
            timestamp=payload.timestamp,
        )

        self.session.add(turn)
        await self.session.flush()
        await self.session.commit()
        return turn.id

    async def delete_session(self, session_id: str) -> None:
        turn_ids = select(Turn.id).where(Turn.session_id == session_id)
        memory_ids = select(Memory.id).where(Memory.session_id == session_id)

        await self.session.execute(
            delete(MemoryEvidence).where(
                (MemoryEvidence.turn_id.in_(turn_ids)) | (MemoryEvidence.memory_id.in_(memory_ids))
            )
        )
        await self.session.execute(delete(Memory).where(Memory.session_id == session_id))
        await self.session.execute(delete(Turn).where(Turn.session_id == session_id))
        await self.session.commit()

    async def delete_user(self, user_id: str) -> None:
        turn_ids = select(Turn.id).where(Turn.user_id == user_id)
        memory_ids = select(Memory.id).where(Memory.user_id == user_id)

        await self.session.execute(
            delete(MemoryEvidence).where(
                (MemoryEvidence.turn_id.in_(turn_ids)) | (MemoryEvidence.memory_id.in_(memory_ids))
            )
        )
        await self.session.execute(delete(Memory).where(Memory.user_id == user_id))
        await self.session.execute(delete(Turn).where(Turn.user_id == user_id))
        await self.session.commit()
