#python imports
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

#third-party imports
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

#project imports
from memory_service.db.models import Memory, MemoryEvidence
from memory_service.schemas.recall import RecallRequest, RecallResponse
from memory_service.services.embeddings import EmbeddingService


@dataclass
class RecallCandidate:
    memory: Memory
    turn_id: UUID | None
    snippet: str
    score: float


class RecallService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.session = session
        self.embedding_service = embedding_service or EmbeddingService()

    async def recall(self, request: RecallRequest) -> RecallResponse:
        candidates = await self.retrieve_candidates(request)
        if not candidates:
            return RecallResponse(context="", citations=[])

        await self._attach_previous_memories(candidates)
        context = self._build_context(candidates, request.max_tokens)
        if not context:
            return RecallResponse(context="", citations=[])

        citations = [
            {
                "turn_id": str(candidate.turn_id) if candidate.turn_id else "",
                "score": round(candidate.score, 4),
                "snippet": candidate.snippet,
            }
            for candidate in candidates[:5]
            if candidate.turn_id is not None
        ]
        return RecallResponse(context=context, citations=citations)

    async def retrieve_candidates(self, request: RecallRequest) -> list[RecallCandidate]:
        vector_candidates = await self._vector_candidates(request)
        keyword_candidates = await self._keyword_candidates(request)

        ranked: dict[UUID, RecallCandidate] = {}
        self._merge_ranked(ranked, vector_candidates, weight=1.0)
        self._merge_ranked(ranked, keyword_candidates, weight=1.25)

        for candidate in ranked.values():
            candidate.score += self._boost_score(candidate, request)

        candidates = sorted(ranked.values(), key=lambda candidate: candidate.score, reverse=True)
        return [candidate for candidate in candidates if candidate.score > 0.05][:12]

    async def _vector_candidates(self, request: RecallRequest) -> list[RecallCandidate]:
        query_embedding = await self.embedding_service.embed(request.query)
        if query_embedding is None:
            return []

        distance = Memory.embedding.cosine_distance(query_embedding)
        statement = (
            select(Memory, MemoryEvidence.turn_id, MemoryEvidence.quote, distance.label("distance"))
            .outerjoin(MemoryEvidence, MemoryEvidence.memory_id == Memory.id)
            .where(Memory.active.is_(True), Memory.embedding.is_not(None))
            .order_by(distance.asc())
            .limit(20)
        )
        statement = self._apply_scope(statement, request)
        rows = (await self.session.execute(statement)).all()

        candidates: list[RecallCandidate] = []
        for rank, (memory, turn_id, quote, raw_distance) in enumerate(rows, start=1):
            distance_value = float(raw_distance or 0.0)
            candidates.append(
                RecallCandidate(
                    memory=memory,
                    turn_id=turn_id,
                    snippet=quote or memory.value,
                    score=self._rrf(rank) + max(0.0, 1.0 - distance_value),
                )
            )
        return candidates

    async def _keyword_candidates(self, request: RecallRequest) -> list[RecallCandidate]:
        search_text = func.concat_ws(
            " ",
            func.replace(Memory.key, ".", " "),
            func.replace(Memory.slot, ".", " "),
            Memory.value,
            func.coalesce(MemoryEvidence.quote, ""),
        )
        search_vector = func.to_tsvector("english", search_text)
        query = func.plainto_tsquery("english", self._expanded_query(request.query))
        rank = func.ts_rank_cd(search_vector, query)
        statement = (
            select(Memory, MemoryEvidence.turn_id, MemoryEvidence.quote, rank.label("rank"))
            .outerjoin(MemoryEvidence, MemoryEvidence.memory_id == Memory.id)
            .where(Memory.active.is_(True), search_vector.op("@@")(query))
            .order_by(rank.desc(), Memory.updated_at.desc())
            .limit(20)
        )
        statement = self._apply_scope(statement, request)
        rows = (await self.session.execute(statement)).all()

        candidates: list[RecallCandidate] = []
        for memory, turn_id, quote, raw_rank in rows:
            candidates.append(
                RecallCandidate(
                    memory=memory,
                    turn_id=turn_id,
                    snippet=quote or memory.value,
                    score=float(raw_rank or 0.0),
                )
            )
        return candidates

    def _apply_scope(self, statement, request: RecallRequest):
        if request.user_id is not None:
            return statement.where(
                or_(
                    Memory.user_id == request.user_id,
                    Memory.session_id == request.session_id,
                )
            )
        return statement.where(Memory.user_id.is_(None), Memory.session_id == request.session_id)

    def _merge_ranked(
        self,
        ranked: dict[UUID, RecallCandidate],
        candidates: list[RecallCandidate],
        weight: float,
    ) -> None:
        for rank, candidate in enumerate(candidates, start=1):
            contribution = weight * self._rrf(rank) + candidate.score
            existing = ranked.get(candidate.memory.id)
            if existing is None:
                candidate.score = contribution
                ranked[candidate.memory.id] = candidate
            else:
                existing.score += contribution

    def _boost_score(self, candidate: RecallCandidate, request: RecallRequest) -> float:
        boost = 0.0
        if candidate.memory.active:
            boost += 0.4
        if candidate.memory.session_id == request.session_id:
            boost += 0.25
        boost += min(candidate.memory.confirmation_count, 5) * 0.05
        boost += min(candidate.memory.confidence, 1.0) * 0.2
        return boost

    def _build_context(self, candidates: list[RecallCandidate], max_tokens: int) -> str:
        budget_chars = max(120, max_tokens * 4)
        lines = ["## Known facts about this user"]
        used_slots: set[str] = set()

        for candidate in candidates:
            slot = getattr(candidate.memory, "slot", None) or candidate.memory.key
            if slot in used_slots:
                continue
            used_slots.add(slot)
            lines.append(f"- {self._format_memory(candidate.memory)}")
            if len("\n".join(lines)) >= budget_chars:
                break

        context = "\n".join(lines)
        return context[:budget_chars].rstrip()

    async def _attach_previous_memories(self, candidates: list[RecallCandidate]) -> None:
        previous_ids = {
            candidate.memory.supersedes_id
            for candidate in candidates
            if candidate.memory.supersedes_id is not None
        }
        if not previous_ids:
            return

        result = await self.session.execute(select(Memory).where(Memory.id.in_(previous_ids)))
        rows = result.scalars().all()
        previous_by_id = {memory.id: memory for memory in rows}
        for candidate in candidates:
            previous = previous_by_id.get(candidate.memory.supersedes_id)
            if previous is not None:
                candidate.memory.previous_memory = previous

    def _format_memory(self, memory: Memory) -> str:
        updated = self._format_date(memory.updated_at or memory.created_at)
        previous = getattr(memory, "previous_memory", None)
        if previous is not None:
            return (
                f"{memory.key}: {memory.value} "
                f"(previously {previous.value}; confidence {memory.confidence:.2f}; "
                f"updated {updated})"
            )
        return (
            f"{memory.key}: {memory.value} "
            f"(confidence {memory.confidence:.2f}; updated {updated})"
        )

    def _format_date(self, value: datetime | None) -> str:
        if value is None:
            return "unknown"
        return value.date().isoformat()

    def _query_terms(self, query: str) -> list[str]:
        stop_words = {
            "a",
            "an",
            "and",
            "does",
            "is",
            "of",
            "the",
            "this",
            "to",
            "user",
            "what",
            "where",
            "who",
        }
        terms = [
            term.strip(".,?!:;()[]{}'\"").lower()
            for term in query.split()
            if term.strip(".,?!:;()[]{}'\"")
        ]
        filtered_terms = [term for term in terms if len(term) > 2 and term not in stop_words]
        expanded_terms = set(filtered_terms)

        if {"live", "lives", "living", "where"} & set(terms):
            expanded_terms.update({"location", "city", "current"})
        if {"work", "works", "job", "company", "employer"} & set(terms):
            expanded_terms.update({"employment", "company", "current"})
        if {"dog", "cat", "pet", "named", "name"} & set(terms):
            expanded_terms.update({"pet", "dog", "cat", "name"})

        return list(expanded_terms)

    def _expanded_query(self, query: str) -> str:
        return " ".join([query, *self._query_terms(query)])

    def _rrf(self, rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank)
