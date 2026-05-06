#python imports
from datetime import UTC, datetime
from uuid import uuid4

#third-party imports

#project imports
from memory_service.config import Settings
from memory_service.db.models import Memory, MemoryEvidence, Turn
from memory_service.db.session import get_session
from memory_service.services.memory_extraction import RuleBasedMemoryExtractor
from memory_service.services.turns import TurnService


class FakeScalarResult:
    def __init__(self, item) -> None:
        self.item = item

    def first(self):
        return self.item


class FakeExecuteResult:
    def __init__(self, item=None) -> None:
        self.item = item

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self.item)


class FakeSession:
    def __init__(self, existing_memory=None) -> None:
        self.added = []
        self.committed = False
        self.existing_memory = existing_memory
        self.executed = []

    def add(self, item) -> None:
        self.added.append(item)

    async def execute(self, statement):
        self.executed.append(statement)
        return FakeExecuteResult(self.existing_memory)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


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


async def test_turn_service_prepares_raw_turn_for_persistence():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    fake_session = FakeSession()
    service = TurnService(fake_session)
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


async def test_turn_service_creates_memories_and_evidence_from_rule_based_extraction():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    fake_session = FakeSession()
    service = TurnService(fake_session)
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
    assert all(row.turn_id == fake_session.added[0].id for row in evidence)
    assert all(row.quote for row in evidence)


async def test_turn_service_reinforces_existing_same_key_same_value_memory():
    from memory_service.schemas.turns import TurnCreate, TurnMessage

    existing_memory = Memory(
        id=uuid4(),
        user_id="user-1",
        session_id="session-1",
        type="fact",
        key="employment.current_company",
        value="Notion",
        confidence=0.9,
        confirmation_count=1,
        active=True,
    )
    fake_session = FakeSession(existing_memory=existing_memory)
    service = TurnService(fake_session)
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


async def test_post_turns_rejects_malformed_payload(client):
    response = await client.post("/turns", json={"session_id": "session-1"})

    assert response.status_code == 422
