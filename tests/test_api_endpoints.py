#python imports
from datetime import UTC, datetime
from uuid import uuid4

#third-party imports
import pytest
from fastapi import status

#project imports
from memory_service.api.deps import (
    get_memory_service,
    get_recall_service,
    get_search_service,
    get_turn_service,
)
from memory_service.schemas.memories import MemoryResponse
from memory_service.schemas.recall import RecallResponse
from memory_service.schemas.search import SearchResponse


class CapturingTurnService:
    def __init__(self) -> None:
        self.created_payloads = []
        self.deleted_sessions = []
        self.deleted_users = []

    async def create_turn(self, payload):
        self.created_payloads.append(payload)
        return uuid4()

    async def delete_session(self, session_id: str) -> None:
        self.deleted_sessions.append(session_id)

    async def delete_user(self, user_id: str) -> None:
        self.deleted_users.append(user_id)


class EndpointMemoryService:
    async def list_user_memories(self, user_id: str):
        now = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
        return [
            MemoryResponse(
                id=str(uuid4()),
                type="fact",
                key="employment.current_company",
                value="Notion",
                confidence=0.9,
                source_session="session-work-2",
                source_turn=str(uuid4()),
                created_at=now,
                updated_at=now,
                supersedes=str(uuid4()),
                superseded_by=None,
                active=True,
                confirmation_count=1,
            )
        ]


class EndpointRecallService:
    def __init__(self, context: str = "## Known facts about this user\n- Berlin") -> None:
        self.payloads = []
        self.context = context

    async def recall(self, payload):
        self.payloads.append(payload)
        return RecallResponse(
            context=self.context,
            citations=[{"turn_id": str(uuid4()), "score": 0.91, "snippet": "moved to Berlin"}],
        )


class EndpointSearchService:
    def __init__(self) -> None:
        self.payloads = []

    async def search(self, payload):
        self.payloads.append(payload)
        return SearchResponse(
            results=[
                {
                    "content": "pet.dog.name: Biscuit",
                    "score": 0.97,
                    "session_id": "session-berlin-1",
                    "timestamp": datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
                    "metadata": {"key": "pet.dog.name", "active": True},
                }
            ]
        )


@pytest.fixture
def endpoint_turn_service(app):
    service = CapturingTurnService()

    async def override():
        return service

    app.dependency_overrides[get_turn_service] = override
    return service


@pytest.fixture
def endpoint_memory_service(app):
    service = EndpointMemoryService()

    async def override():
        return service

    app.dependency_overrides[get_memory_service] = override
    return service


@pytest.fixture
def endpoint_recall_service(app):
    service = EndpointRecallService()

    async def override():
        return service

    app.dependency_overrides[get_recall_service] = override
    return service


@pytest.fixture
def endpoint_search_service(app):
    service = EndpointSearchService()

    async def override():
        return service

    app.dependency_overrides[get_search_service] = override
    return service


@pytest.mark.parametrize(
    ("content", "expected_user_id"),
    [
        ("I just moved to Berlin from NYC.", "user-1"),
        ("I work at Stripe.", "user-1"),
        ("My dog Biscuit is adjusting.", "user-1"),
        ("I prefer concise direct answers.", "user-1"),
        ("I just joined Notion.", "user-1"),
        ("I am vegetarian.", "user-1"),
        ("Actually, I work at Notion now.", "user-1"),
    ],
)
async def test_post_turns_accepts_real_endpoint_payloads(
    client,
    endpoint_turn_service,
    content,
    expected_user_id,
):
    response = await client.post(
        "/turns",
        json={
            "session_id": "session-1",
            "user_id": expected_user_id,
            "messages": [{"role": "user", "content": content}],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {"source": "endpoint-test"},
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["id"]
    assert endpoint_turn_service.created_payloads[-1].messages[0].content == content


@pytest.mark.parametrize(
    "payload",
    [
        {
            "user_id": "user-1",
            "messages": [{"role": "user", "content": "hello"}],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {},
        },
        {
            "session_id": "",
            "user_id": "user-1",
            "messages": [{"role": "user", "content": "hello"}],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {},
        },
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "messages": [],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {},
        },
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "messages": [{"role": "system", "content": "hello"}],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {},
        },
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "messages": [{"role": "user", "content": ""}],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {},
        },
        {
            "session_id": "session-1",
            "user_id": "user-1",
            "messages": [{"role": "user", "content": "hello"}],
            "timestamp": "not-a-date",
            "metadata": {},
        },
    ],
)
async def test_post_turns_rejects_bad_endpoint_payloads(client, endpoint_turn_service, payload):
    response = await client.post("/turns", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert endpoint_turn_service.created_payloads == []


@pytest.mark.parametrize(
    ("query", "max_tokens"),
    [
        ("Where does the user live?", 256),
        ("What is the dog's name?", 512),
        ("Where does the user work?", 1024),
        ("What should I remember about communication style?", 2048),
    ],
)
async def test_post_recall_endpoint_accepts_valid_queries(
    client,
    endpoint_recall_service,
    query,
    max_tokens,
):
    response = await client.post(
        "/recall",
        json={
            "query": query,
            "session_id": "session-probe",
            "user_id": "user-1",
            "max_tokens": max_tokens,
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert "Known facts" in response.json()["context"]
    assert endpoint_recall_service.payloads[-1].query == query


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "", "session_id": "session-1", "user_id": "user-1", "max_tokens": 512},
        {"query": "Where?", "session_id": "", "user_id": "user-1", "max_tokens": 512},
        {"query": "Where?", "session_id": "session-1", "user_id": "user-1", "max_tokens": 0},
        {"query": "Where?", "session_id": "session-1", "user_id": "user-1", "max_tokens": 16001},
        {"session_id": "session-1", "user_id": "user-1", "max_tokens": 512},
    ],
)
async def test_post_recall_endpoint_rejects_bad_payloads(client, endpoint_recall_service, payload):
    response = await client.post("/recall", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert endpoint_recall_service.payloads == []


@pytest.mark.parametrize(
    ("query", "limit"),
    [
        ("dog Biscuit", 1),
        ("Berlin", 5),
        ("current company", 10),
        ("concise answers", 50),
    ],
)
async def test_post_search_endpoint_accepts_valid_queries(
    client,
    endpoint_search_service,
    query,
    limit,
):
    response = await client.post(
        "/search",
        json={
            "query": query,
            "session_id": "session-probe",
            "user_id": "user-1",
            "limit": limit,
        },
    )

    payload = response.json()

    assert response.status_code == status.HTTP_200_OK
    assert payload["results"][0]["content"] == "pet.dog.name: Biscuit"
    assert endpoint_search_service.payloads[-1].limit == limit


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "", "session_id": "session-1", "user_id": "user-1", "limit": 10},
        {"query": "dog", "session_id": "session-1", "user_id": "user-1", "limit": 0},
        {"query": "dog", "session_id": "session-1", "user_id": "user-1", "limit": 51},
        {"session_id": "session-1", "user_id": "user-1", "limit": 10},
    ],
)
async def test_post_search_endpoint_rejects_bad_payloads(client, endpoint_search_service, payload):
    response = await client.post("/search", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert endpoint_search_service.payloads == []


async def test_get_user_memories_endpoint_returns_supersession_fields(
    client,
    endpoint_memory_service,
):
    response = await client.get("/users/user-1/memories")
    memory = response.json()["memories"][0]

    assert response.status_code == status.HTTP_200_OK
    assert memory["key"] == "employment.current_company"
    assert memory["value"] == "Notion"
    assert memory["active"] is True
    assert memory["supersedes"] is not None


async def test_delete_session_endpoint_calls_service(client, endpoint_turn_service):
    response = await client.delete("/sessions/session-1")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert endpoint_turn_service.deleted_sessions == ["session-1"]


async def test_delete_user_endpoint_calls_service(client, endpoint_turn_service):
    response = await client.delete("/users/user-1")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert endpoint_turn_service.deleted_users == ["user-1"]


async def test_endpoint_flow_write_then_recall_then_search(
    client,
    endpoint_turn_service,
    endpoint_recall_service,
    endpoint_search_service,
):
    turn_response = await client.post(
        "/turns",
        json={
            "session_id": "session-flow-1",
            "user_id": "user-flow",
            "messages": [
                {
                    "role": "user",
                    "content": "I just moved to Berlin from NYC. My dog Biscuit is adjusting.",
                }
            ],
            "timestamp": "2026-05-07T10:00:00Z",
            "metadata": {"source": "endpoint-flow"},
        },
    )
    recall_response = await client.post(
        "/recall",
        json={
            "query": "Where does the user live?",
            "session_id": "session-flow-2",
            "user_id": "user-flow",
            "max_tokens": 512,
        },
    )
    search_response = await client.post(
        "/search",
        json={
            "query": "dog Biscuit",
            "session_id": "session-flow-2",
            "user_id": "user-flow",
            "limit": 5,
        },
    )

    assert turn_response.status_code == status.HTTP_201_CREATED
    assert recall_response.status_code == status.HTTP_200_OK
    assert search_response.status_code == status.HTTP_200_OK
    assert endpoint_turn_service.created_payloads[-1].user_id == "user-flow"
    assert "Berlin" in recall_response.json()["context"]
    assert search_response.json()["results"][0]["metadata"]["key"] == "pet.dog.name"
