#python imports
from datetime import UTC, datetime
from uuid import uuid4

#project imports
from memory_service.config import Settings
from memory_service.db.models import Memory, MemoryEvidence, Turn
from memory_service.db.session import get_session
from memory_service.schemas.recall import RecallRequest
from memory_service.schemas.search import SearchRequest
from memory_service.services.embeddings import EmbeddingService
from memory_service.services.memory_extraction import (
    CombinedMemoryExtractor,
    LLMMemoryExtractor,
    MemoryCandidate,
    RuleBasedMemoryExtractor,
)
from memory_service.services.memory_slots import canonical_slot
from memory_service.services.recall import RecallService
from memory_service.services.search import SearchService
from memory_service.services.turns import TurnService


class FakeScalarResult:
    def __init__(self, item=None, items=None) -> None:
        self.item = item
        self.items = items or []

    def first(self):
        return self.item

    def all(self):
        return self.items


class FakeExecuteResult:
    def __init__(self, item=None, scalar_items=None) -> None:
        self.item = item
        self.scalar_items = scalar_items

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.item, self.scalar_items)

    def all(self):
        return self.scalar_items or []


class FakeSession:
    def __init__(self, existing_memory=None) -> None:
        self.added = []
        self.committed = False
        self.existing_memory = existing_memory
        self.executed = []
        self.execute_params = []
        self.flush_count = 0
        self.flushed_memory_ids = []
        self.flush_snapshots = []

    def add(self, item) -> None:
        self.added.append(item)

    async def execute(self, statement, params=None):
        self.executed.append(statement)
        self.execute_params.append(params)
        if "pg_advisory_xact_lock" in str(statement):
            return FakeExecuteResult()
        return FakeExecuteResult(self.existing_memory)

    async def flush(self) -> None:
        self.flush_count += 1
        self.flush_snapshots.append(
            [
                (item.id, item.active)
                for item in self.added
                if isinstance(item, Memory)
            ]
        )
        self.flushed_memory_ids.extend(
            item.id
            for item in self.added
            if isinstance(item, Memory) and item.id not in self.flushed_memory_ids
        )
        return None

    async def commit(self) -> None:
        self.committed = True


class FakeRecallSession:
    def __init__(self, rows_by_call: list[list[tuple]]) -> None:
        self.rows_by_call = rows_by_call
        self.executed = []

    async def execute(self, statement, params=None):
        self.executed.append(statement)
        rows = self.rows_by_call.pop(0) if self.rows_by_call else []
        return FakeExecuteResult(scalar_items=rows)


class FakeResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class FakeResponsesClient:
    def __init__(self, output_text: str | None = None, error: Exception | None = None) -> None:
        self.output_text = output_text
        self.error = error

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return FakeResponse(self.output_text or '{"memories":[]}')


class FakeOpenAIClient:
    def __init__(self, output_text: str | None = None, error: Exception | None = None) -> None:
        self.responses = FakeResponsesClient(output_text=output_text, error=error)


class FakeRuleExtractor:
    def __init__(self, candidates: list[MemoryCandidate]) -> None:
        self.candidates = candidates

    def extract(self, messages):
        return self.candidates


class FakeLLMExtractor:
    def __init__(self, candidates: list[MemoryCandidate]) -> None:
        self.candidates = candidates

    async def extract(self, messages):
        return self.candidates


def no_llm_extractor() -> CombinedMemoryExtractor:
    return CombinedMemoryExtractor(llm_extractor=FakeLLMExtractor([]))


def no_embedding_service() -> "FakeEmbeddingService":
    return FakeEmbeddingService(None)


class FakeEmbeddingService(EmbeddingService):
    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector

    async def embed(self, text: str) -> list[float] | None:
        return self.vector


def test_settings_read_environment(monkeypatch):
    monkeypatch.setenv("PORT", "9090")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/test")
    monkeypatch.setenv("MEMORY_AUTH_TOKEN", "secret")

    settings = Settings(_env_file=None)

    assert settings.port == 9090
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost:5432/test"
    assert settings.memory_auth_token == "secret"


def test_db_session_dependency_is_importable():
    assert callable(get_session)


def test_core_models_are_registered():
    assert Turn.__tablename__ == "turns"
    assert Memory.__tablename__ == "memories"
    assert MemoryEvidence.__tablename__ == "memory_evidence"
    assert "slot" in Memory.__table__.columns


def test_canonical_slot_normalizes_known_aliases():
    assert canonical_slot("employment.company") == "employment.current_company"
    assert canonical_slot("job.company") == "employment.current_company"
    assert canonical_slot("location.city") == "location.current_city"
    assert canonical_slot("home.city") == "location.current_city"
    assert canonical_slot("pet.dog") == "pet.dog.name"
    assert canonical_slot("opinion.typescript") == "opinion.typescript"


def test_memory_model_unique_indexes_use_slot():
    indexes = {index.name: index for index in Memory.__table__.indexes}

    assert {column.name for column in indexes["uq_memories_active_user_key"].columns} == {
        "user_id",
        "slot",
    }
    assert {column.name for column in indexes["uq_memories_active_session_key"].columns} == {
        "session_id",
        "slot",
    }


async def test_turn_service_prepares_raw_turn_for_persistence():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    fake_session = FakeSession()
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I moved to Berlin.")],
        timestamp=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
        metadata={"source": "unit-test"},
    )

    turn_id = await service.create_turn(payload)

    assert turn_id == fake_session.added[0].id
    assert fake_session.added[0].session_id == "session-1"
    assert fake_session.added[0].messages == [{"role": "user", "content": "I moved to Berlin."}]
    assert fake_session.added[0].metadata_ == {"source": "unit-test"}
    assert fake_session.committed is True


def test_rule_based_extractor_finds_location_employment_pet_and_preferences():
    from memory_service.schemas.turns import TurnMessage

    extractor = RuleBasedMemoryExtractor()
    candidates = extractor.extract(
        [
            TurnMessage(
                role="user",
                content=(
                    "I just moved to Berlin from NYC last month. "
                    "I just started at Notion last month. "
                    "My dog Biscuit is adjusting. "
                    "I'm vegetarian and I prefer concise direct answers."
                ),
            )
        ]
    )

    facts = {(candidate.key, candidate.value) for candidate in candidates}

    assert ("location.current_city", "Berlin") in facts
    assert ("location.previous_city", "NYC") in facts
    assert ("employment.current_company", "Notion") in facts
    assert ("pet.dog.name", "Biscuit") in facts
    assert ("preference.diet", "vegetarian") in facts
    assert ("preference.communication_style", "concise/direct") in facts


async def test_llm_extractor_parses_strict_structured_output():
    from memory_service.schemas.turns import TurnMessage

    client = FakeOpenAIClient(
        output_text=(
            '{"memories":[{"type":"opinion","key":"opinion.typescript",'
            '"value":"prefers Python for scripts","confidence":0.81,'
            '"evidence_quote":"I would use Python for scripts"}]}'
        )
    )
    extractor = LLMMemoryExtractor(client=client, model="gpt-test", api_key="test-key")

    candidates = await extractor.extract([TurnMessage(role="user", content="text")])

    assert candidates == [
        MemoryCandidate(
            type="opinion",
            key="opinion.typescript",
            value="prefers Python for scripts",
            confidence=0.81,
            evidence_quote="I would use Python for scripts",
        )
    ]
    assert client.responses.kwargs["model"] == "gpt-test"
    assert client.responses.kwargs["text"]["format"]["strict"] is True


async def test_llm_extractor_returns_empty_without_api_key():
    from memory_service.schemas.turns import TurnMessage

    extractor = LLMMemoryExtractor(api_key="")

    assert await extractor.extract([TurnMessage(role="user", content="text")]) == []


async def test_llm_extractor_returns_empty_on_malformed_output():
    from memory_service.schemas.turns import TurnMessage

    client = FakeOpenAIClient(output_text='{"memories":[{"type":"fact"}]}')
    extractor = LLMMemoryExtractor(client=client, model="gpt-test", api_key="test-key")

    assert await extractor.extract([TurnMessage(role="user", content="text")]) == []


async def test_combined_extractor_merges_and_dedupes_rule_based_and_llm_candidates():
    from memory_service.schemas.turns import TurnMessage

    duplicate = MemoryCandidate(
        type="fact",
        key="employment.current_company",
        value="Notion",
        confidence=0.9,
        evidence_quote="I work at Notion",
    )
    llm_only = MemoryCandidate(
        type="opinion",
        key="opinion.typescript",
        value="prefers Python for scripts",
        confidence=0.8,
        evidence_quote="I would use Python for scripts",
    )
    extractor = CombinedMemoryExtractor(
        rule_based_extractor=FakeRuleExtractor([duplicate]),
        llm_extractor=FakeLLMExtractor([duplicate, llm_only]),
    )

    candidates = await extractor.extract([TurnMessage(role="user", content="text")])

    assert candidates == [duplicate, llm_only]


async def test_turn_service_creates_memories_and_evidence_from_rule_based_extraction():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    fake_session = FakeSession()
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I just moved to Berlin from NYC.")],
        timestamp=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    memories = [item for item in fake_session.added if isinstance(item, Memory)]
    evidence = [item for item in fake_session.added if isinstance(item, MemoryEvidence)]

    assert len(memories) == 2
    assert len(evidence) == 2
    assert {memory.key for memory in memories} == {
        "location.current_city",
        "location.previous_city",
    }
    assert {memory.slot for memory in memories} == {
        "location.current_city",
        "location.previous_city",
    }
    assert all(row.turn_id == fake_session.added[0].id for row in evidence)
    assert all(row.quote for row in evidence)


async def test_turn_service_stores_embedding_when_available():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    fake_session = FakeSession()
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=FakeEmbeddingService([0.1] * 1536),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I work at Notion.")],
        timestamp=datetime(2025, 3, 16, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    memories = [item for item in fake_session.added if isinstance(item, Memory)]

    assert memories[0].embedding == [0.1] * 1536


async def test_turn_service_reinforces_existing_same_key_same_value_memory():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    existing_memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Notion",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    fake_session = FakeSession(existing_memory=existing_memory)
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I work at Notion.")],
        timestamp=datetime(2025, 3, 16, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    memories = [item for item in fake_session.added if isinstance(item, Memory)]
    evidence = [item for item in fake_session.added if isinstance(item, MemoryEvidence)]

    assert memories == []
    assert existing_memory.confirmation_count == 2
    assert existing_memory.confidence == 0.95
    assert existing_memory.last_confirmed_at == payload.timestamp
    assert len(evidence) == 1
    assert evidence[0].memory_id == existing_memory.id


async def test_turn_service_supersedes_existing_same_key_different_value_memory():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    existing_memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Stripe",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    fake_session = FakeSession(existing_memory=existing_memory)
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-3",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I just joined Notion.")],
        timestamp=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    memories = [item for item in fake_session.added if isinstance(item, Memory)]
    evidence = [item for item in fake_session.added if isinstance(item, MemoryEvidence)]
    new_memory = memories[0]

    assert existing_memory.active is False
    assert existing_memory.superseded_by_id == new_memory.id
    assert new_memory.active is True
    assert new_memory.key == "employment.current_company"
    assert new_memory.slot == "employment.current_company"
    assert new_memory.value == "Notion"
    assert new_memory.supersedes_id == existing_memory.id
    assert new_memory.id in fake_session.flushed_memory_ids
    assert len(evidence) == 1
    assert evidence[0].memory_id == new_memory.id


async def test_turn_service_flushes_new_memory_before_superseded_by_fk_update():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    class TrackingMemory(Memory):
        update_events = []

        def __setattr__(self, name, value):
            if name == "superseded_by_id":
                self.update_events.append(("superseded_by_id", value))
            super().__setattr__(name, value)

    existing_memory = TrackingMemory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Stripe",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    fake_session = FakeSession(existing_memory=existing_memory)
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-3",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I just joined Notion.")],
        timestamp=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    new_memory = [item for item in fake_session.added if isinstance(item, Memory)][0]

    assert new_memory.id in fake_session.flushed_memory_ids
    assert existing_memory.update_events == [("superseded_by_id", new_memory.id)]


async def test_turn_service_deactivates_existing_memory_before_inserting_replacement():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    class ConstraintCheckingSession(FakeSession):
        async def flush(self) -> None:
            active_replacements = [
                item
                for item in self.added
                if isinstance(item, Memory)
                and item.slot == "employment.current_company"
                and item.active
            ]
            if active_replacements and self.existing_memory.active:
                raise AssertionError("replacement inserted before existing active slot was freed")
            await super().flush()

    existing_memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Stripe",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    fake_session = ConstraintCheckingSession(existing_memory=existing_memory)
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-3",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I just joined Notion.")],
        timestamp=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    new_memory = [item for item in fake_session.added if isinstance(item, Memory)][0]

    assert existing_memory.active is False
    assert existing_memory.superseded_by_id == new_memory.id
    assert new_memory.active is True


async def test_turn_service_uses_advisory_lock_for_memory_slot():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    fake_session = FakeSession()
    service = TurnService(
        fake_session,
        extractor=no_llm_extractor(),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I work at Notion.")],
        timestamp=datetime(2025, 3, 16, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    assert any("pg_advisory_xact_lock" in str(statement) for statement in fake_session.executed)


async def test_turn_service_uses_canonical_slot_for_llm_key_alias():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    existing_memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Stripe",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    candidate = MemoryCandidate(
        type="fact",
        key="employment.company",
        value="Notion",
        confidence=0.91,
        evidence_quote="I joined Notion",
    )
    fake_session = FakeSession(existing_memory=existing_memory)
    service = TurnService(
        fake_session,
        extractor=CombinedMemoryExtractor(
            rule_based_extractor=FakeRuleExtractor([]),
            llm_extractor=FakeLLMExtractor([candidate]),
        ),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-2",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I joined Notion.")],
        timestamp=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    new_memory = [item for item in fake_session.added if isinstance(item, Memory)][0]

    assert existing_memory.active is False
    assert new_memory.key == "employment.company"
    assert new_memory.slot == "employment.current_company"
    assert new_memory.supersedes_id == existing_memory.id


async def test_turn_service_reinforces_same_slot_same_value_from_alias():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    existing_memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Notion",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    candidate = MemoryCandidate(
        type="fact",
        key="job.company",
        value="Notion",
        confidence=0.87,
        evidence_quote="I work at Notion",
    )
    fake_session = FakeSession(existing_memory=existing_memory)
    service = TurnService(
        fake_session,
        extractor=CombinedMemoryExtractor(
            rule_based_extractor=FakeRuleExtractor([]),
            llm_extractor=FakeLLMExtractor([candidate]),
        ),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-2",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I work at Notion.")],
        timestamp=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    new_memories = [item for item in fake_session.added if isinstance(item, Memory)]

    assert new_memories == []
    assert existing_memory.confirmation_count == 2
    assert existing_memory.active is True


async def test_turn_service_keeps_unknown_key_as_slot():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    candidate = MemoryCandidate(
        type="opinion",
        key="opinion.typescript",
        value="prefers Python for scripts",
        confidence=0.81,
        evidence_quote="I would use Python for scripts",
    )
    fake_session = FakeSession()
    service = TurnService(
        fake_session,
        extractor=CombinedMemoryExtractor(
            rule_based_extractor=FakeRuleExtractor([]),
            llm_extractor=FakeLLMExtractor([candidate]),
        ),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I would use Python for scripts.")],
        timestamp=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    memory = [item for item in fake_session.added if isinstance(item, Memory)][0]

    assert memory.key == "opinion.typescript"
    assert memory.slot == "opinion.typescript"


async def test_turn_service_advisory_lock_uses_canonical_slot():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    candidate = MemoryCandidate(
        type="fact",
        key="job.company",
        value="Notion",
        confidence=0.9,
        evidence_quote="I work at Notion",
    )
    fake_session = FakeSession()
    service = TurnService(
        fake_session,
        extractor=CombinedMemoryExtractor(
            rule_based_extractor=FakeRuleExtractor([]),
            llm_extractor=FakeLLMExtractor([candidate]),
        ),
        embedding_service=no_embedding_service(),
    )
    payload = TurnCreate(
        session_id="session-1",
        user_id="user-1",
        messages=[TurnMessage(role="user", content="I work at Notion.")],
        timestamp=datetime(2025, 3, 16, 10, 30, tzinfo=UTC),
        metadata={},
    )

    await service.create_turn(payload)

    expected_lock = service._advisory_lock_key("user:user-1:employment.current_company")
    assert {"lock_key": expected_lock} in fake_session.execute_params


async def test_recall_scope_for_user_allows_same_user_or_current_session():
    memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="older-session",
        type="fact",
        key="location.current_city",
        slot="location.current_city",
        value="Berlin",
        confidence=0.9,
        confirmation_count=1,
        active=True,
        created_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
    )
    session = FakeRecallSession(rows_by_call=[[(memory, uuid4(), "I moved to Berlin", 0.7)]])
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    await service.recall(
        RecallRequest(query="Where does user live?", session_id="new-session", user_id="user-1")
    )

    statement = str(session.executed[0])
    assert "memories.user_id = :user_id_1 OR memories.session_id = :session_id_1" in statement


async def test_recall_scope_without_user_is_session_only():
    session = FakeRecallSession(rows_by_call=[[]])
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    await service.recall(
        RecallRequest(query="Where does user live?", session_id="session-1", user_id=None)
    )

    statement = str(session.executed[0])
    assert "memories.user_id IS NULL" in statement
    assert "memories.session_id = :session_id_1" in statement


async def test_recall_returns_keyword_memory_context_and_citation():
    memory_id = uuid4()
    turn_id = uuid4()
    memory = Memory(
        id=memory_id,
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="location.current_city",
        slot="location.current_city",
        value="Berlin",
        confidence=0.92,
        confirmation_count=1,
        active=True,
        created_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
    )
    session = FakeRecallSession(rows_by_call=[[(memory, turn_id, "I moved to Berlin", 0.7)]])
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    response = await service.recall(
        RecallRequest(
            query="Where does the user live?",
            session_id="session-1",
            user_id="user-1",
            max_tokens=512,
        )
    )

    assert "location.current_city: Berlin" in response.context
    assert response.citations[0].turn_id == str(turn_id)
    assert response.citations[0].snippet == "I moved to Berlin"


async def test_recall_context_includes_direct_superseded_history():
    previous_memory_id = uuid4()
    current_memory_id = uuid4()
    turn_id = uuid4()
    previous_memory = Memory(
        id=previous_memory_id,
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Stripe",
        confidence=0.9,
        confirmation_count=1,
        active=False,
        created_at=datetime(2025, 3, 10, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 10, 10, 30, tzinfo=UTC),
    )
    current_memory = Memory(
        id=current_memory_id,
        user_id="user-1",
        session_id="session-3",
        type="fact",
        key="employment.current_company",
        slot="employment.current_company",
        value="Notion",
        confidence=0.95,
        confirmation_count=1,
        active=True,
        supersedes_id=previous_memory_id,
        created_at=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
    )
    session = FakeRecallSession(
        rows_by_call=[
            [(current_memory, turn_id, "I just joined Notion", 0.7)],
            [previous_memory],
        ]
    )
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    response = await service.recall(
        RecallRequest(
            query="Where does the user work?",
            session_id="session-4",
            user_id="user-1",
            max_tokens=512,
        )
    )

    assert "employment.current_company: Notion" in response.context
    assert "previously Stripe" in response.context


async def test_recall_context_dedupes_by_slot_not_raw_key():
    first = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.company",
        slot="employment.current_company",
        value="Notion",
        confidence=0.9,
        confirmation_count=1,
        active=True,
        created_at=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 18, 10, 30, tzinfo=UTC),
    )
    duplicate_slot = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="job.company",
        slot="employment.current_company",
        value="Notion",
        confidence=0.8,
        confirmation_count=1,
        active=True,
        created_at=datetime(2025, 3, 17, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 17, 10, 30, tzinfo=UTC),
    )
    session = FakeRecallSession(
        rows_by_call=[
            [
                (first, uuid4(), "I joined Notion", 0.7),
                (duplicate_slot, uuid4(), "I work at Notion", 0.6),
            ]
        ]
    )
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    response = await service.recall(
        RecallRequest(query="Where does user work?", session_id="session-1", user_id="user-1")
    )

    assert response.context.count("Notion") == 1


async def test_keyword_recall_query_indexes_memory_slot_text():
    session = FakeRecallSession(rows_by_call=[[]])
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    await service.recall(
        RecallRequest(query="Where does user work?", session_id="session-1", user_id="user-1")
    )

    statement = str(session.executed[0])
    assert "memories.slot" in statement


async def test_recall_returns_empty_context_when_no_candidates_match():
    session = FakeRecallSession(rows_by_call=[[], []])
    service = RecallService(session, embedding_service=FakeEmbeddingService(None))

    response = await service.recall(
        RecallRequest(query="Unknown topic", session_id="session-1", user_id="user-1")
    )

    assert response.context == ""
    assert response.citations == []


async def test_search_returns_structured_results_from_hybrid_retrieval():
    memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="pet.dog.name",
        slot="pet.dog.name",
        value="Biscuit",
        confidence=0.86,
        confirmation_count=1,
        active=True,
        created_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
        updated_at=datetime(2025, 3, 15, 10, 30, tzinfo=UTC),
    )
    turn_id = uuid4()
    session = FakeRecallSession(rows_by_call=[[(memory, turn_id, "my dog Biscuit", 0.8)]])
    service = SearchService(session, embedding_service=FakeEmbeddingService(None))

    response = await service.search(
        SearchRequest(query="dog name", session_id="session-1", user_id="user-1", limit=5)
    )

    assert response.results[0].content == "pet.dog.name: Biscuit"
    assert response.results[0].session_id == "session-1"
    assert response.results[0].metadata["turn_id"] == str(turn_id)


async def test_post_turns_rejects_malformed_payload(client):
    response = await client.post("/turns", json={"session_id": "session-1"})

    assert response.status_code == 422
