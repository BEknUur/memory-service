#python imports
from uuid import UUID, uuid4

#third-party imports
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

#project imports
from memory_service.db.models import Memory, MemoryEvidence, Turn
from memory_service.schemas.turns import TurnCreate
from memory_service.services.memory_extraction import (
    MemoryCandidate,
    RuleBasedMemoryExtractor,
)


class TurnService:
    def __init__(
        self,
        session: AsyncSession,
        extractor: RuleBasedMemoryExtractor | None = None,
    ) -> None:
        self.session = session
        self.extractor = extractor or RuleBasedMemoryExtractor()

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

        for candidate in self.extractor.extract(payload.messages):
            await self._apply_candidate(payload, turn, candidate)

        await self.session.commit()
        return turn.id

    async def _apply_candidate(
        self,
        payload: TurnCreate,
        turn: Turn,
        candidate: MemoryCandidate,
    ) -> None:
        existing_memory = await self._find_existing_active_memory(payload, candidate)

        if existing_memory is not None:
            existing_memory.confirmation_count += 1
            boosted_confidence = max(existing_memory.confidence, candidate.confidence) + 0.05
            existing_memory.confidence = round(min(1.0, boosted_confidence), 4)
            existing_memory.last_confirmed_at = payload.timestamp
            memory = existing_memory
        else:
            memory = Memory(
                id=uuid4(),
                user_id=payload.user_id,
                session_id=payload.session_id,
                type=candidate.type,
                key=candidate.key,
                value=candidate.value,
                confidence=candidate.confidence,
                confirmation_count=1,
                active=True,
                last_confirmed_at=payload.timestamp,
            )
            self.session.add(memory)

        self.session.add(
            MemoryEvidence(
                memory_id=memory.id,
                turn_id=turn.id,
                quote=candidate.evidence_quote,
                confidence=candidate.confidence,
            )
        )

    async def _find_existing_active_memory(
        self,
        payload: TurnCreate,
        candidate: MemoryCandidate,
    ) -> Memory | None:
        statement = select(Memory).where(
            Memory.key == candidate.key,
            Memory.value == candidate.value,
            Memory.active.is_(True),
        )

        if payload.user_id is not None:
            statement = statement.where(Memory.user_id == payload.user_id)
        else:
            statement = statement.where(
                Memory.user_id.is_(None),
                Memory.session_id == payload.session_id,
            )

        result = await self.session.execute(statement)
        return result.scalars().first()

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
