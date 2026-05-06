#python imports
import hashlib
from uuid import UUID, uuid4

#third-party imports
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
#project imports
from memory_service.db.models import(
     Memory, 
     MemoryEvidence,
       Turn
)
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
        await self._lock_memory_slot(payload, candidate)
        existing_memory = await self._find_existing_active_memory_for_key(payload, candidate)

        if existing_memory is not None and existing_memory.value == candidate.value:
            self._reinforce_memory(existing_memory, candidate, payload)
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
                supersedes_id=existing_memory.id if existing_memory else None,
                last_confirmed_at=payload.timestamp,
            )
            self.session.add(memory)

            if existing_memory is not None:
                existing_memory.active = False
                existing_memory.superseded_by_id = memory.id

        self.session.add(
            MemoryEvidence(
                memory_id=memory.id,
                turn_id=turn.id,
                quote=candidate.evidence_quote,
                confidence=candidate.confidence,
            )
        )

    def _reinforce_memory(
        self,
        memory: Memory,
        candidate: MemoryCandidate,
        payload: TurnCreate,
    ) -> None:
        memory.confirmation_count += 1
        boosted_confidence = max(memory.confidence, candidate.confidence) + 0.05
        memory.confidence = round(min(1.0, boosted_confidence), 4)
        memory.last_confirmed_at = payload.timestamp

    async def _lock_memory_slot(
        self,
        payload: TurnCreate,
        candidate: MemoryCandidate,
    ) -> None:
        if payload.user_id is not None:
            scope = f"user:{payload.user_id}"
        else:
            scope = f"session:{payload.session_id}"

        lock_key = self._advisory_lock_key(f"{scope}:{candidate.key}")
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": lock_key},
        )

    def _advisory_lock_key(self, value: str) -> int:
        digest = hashlib.sha256(value.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big", signed=True)

    async def _find_existing_active_memory_for_key(
        self,
        payload: TurnCreate,
        candidate: MemoryCandidate,
    ) -> Memory | None:
        statement = select(Memory).where(
            Memory.key == candidate.key,
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
