from datetime import UTC, datetime

from memory_service.config import Settings
from memory_service.db.models import Memory, MemoryEvidence, Turn
from memory_service.db.session import get_session
from memory_service.services.turns import TurnService


class FakeSession:
    def __init__(self) -> None:
        self.added = []
        self.committed = False

    def add(self, item) -> None:
        self.added.append(item)

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


async def test_post_turns_rejects_malformed_payload(client):
    response = await client.post("/turns", json={"session_id": "session-1"})

    assert response.status_code == 422
