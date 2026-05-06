#python imports
from uuid import uuid4

#third-party imports
import pytest
from fastapi import status

#project imports
from memory_service.api.deps import get_memory_service, get_search_service, get_turn_service
from memory_service.main import create_app
from memory_service.schemas.search import SearchResponse


class FakeTurnService:
    def __init__(self) -> None:
        self.created_payload = None
        self.deleted_sessions: list[str] = []
        self.deleted_users: list[str] = []

    async def create_turn(self, payload):
        self.created_payload = payload
        return uuid4()

    async def delete_session(self, session_id: str) -> None:
        self.deleted_sessions.append(session_id)

    async def delete_user(self, user_id: str) -> None:
        self.deleted_users.append(user_id)


class FakeMemoryService:
    async def list_user_memories(self, user_id: str):
        assert user_id == "user-1"
        return []


class FakeSearchService:
    async def search(self, _):
        return SearchResponse(results=[])


def test_app_is_created_with_health_route():
    app = create_app()

    routes = {route.path for route in app.routes}

    assert app.title == "Memory Service"
    assert "/health" in routes
    assert "/turns" in routes
    assert "/recall" in routes
    assert "/search" in routes
    assert "/users/{user_id}/memories" in routes
    assert "/users/{user_id}" in routes
    assert "/sessions/{session_id}" in routes


async def test_lifespan_runs_migrations(monkeypatch):
    called = False

    async def fake_run_migrations() -> None:
        nonlocal called
        called = True

    monkeypatch.setattr("memory_service.main.run_migrations", fake_run_migrations)

    app = create_app()
    async with app.router.lifespan_context(app):
        pass

    assert called is True


@pytest.fixture
def fake_turn_service(app):
    service = FakeTurnService()

    async def override():
        return service

    app.dependency_overrides[get_turn_service] = override
    return service


@pytest.fixture
def fake_memory_service(app):
    service = FakeMemoryService()

    async def override():
        return service

    app.dependency_overrides[get_memory_service] = override
    return service


@pytest.fixture
def fake_search_service(app):
    service = FakeSearchService()

    async def override():
        return service

    app.dependency_overrides[get_search_service] = override
    return service


async def test_post_turns_accepts_contract_payload(client, fake_turn_service):
    response = await client.post(
        "/turns",
        json={
            "session_id": "session-1",
            "user_id": "user-1",
            "messages": [
                {"role": "user", "content": "I just moved to Berlin from NYC."},
                {"role": "assistant", "content": "How are you settling in?"},
            ],
            "timestamp": "2025-03-15T10:30:00Z",
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert "id" in response.json()
    assert fake_turn_service.created_payload.session_id == "session-1"


async def test_recall_stub_returns_empty_context(client):
    response = await client.post(
        "/recall",
        json={
            "query": "Where does the user live?",
            "session_id": "session-1",
            "user_id": "user-1",
            "max_tokens": 512,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"context": "", "citations": []}


async def test_search_stub_returns_empty_results(client, fake_search_service):
    response = await client.post(
        "/search",
        json={"query": "Berlin", "session_id": "session-1", "user_id": "user-1", "limit": 10},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"results": []}


async def test_user_memories_returns_structured_list(client, fake_memory_service):
    response = await client.get("/users/user-1/memories")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"memories": []}


async def test_delete_session_returns_no_content(client, fake_turn_service):
    response = await client.delete("/sessions/session-1")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert fake_turn_service.deleted_sessions == ["session-1"]


async def test_delete_user_returns_no_content(client, fake_turn_service):
    response = await client.delete("/users/user-1")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert fake_turn_service.deleted_users == ["user-1"]
