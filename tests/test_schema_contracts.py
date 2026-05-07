#python imports
from datetime import UTC, datetime

#third-party imports
import pytest
from pydantic import ValidationError

#project imports
from memory_service.schemas.memories import MemoryResponse, UserMemoriesResponse
from memory_service.schemas.recall import RecallCitation, RecallRequest, RecallResponse
from memory_service.schemas.search import SearchRequest, SearchResponse, SearchResult
from memory_service.schemas.turns import TurnCreate, TurnCreated, TurnMessage


@pytest.mark.parametrize("role", ["user", "assistant", "tool"])
def test_turn_message_accepts_supported_roles(role):
    message = TurnMessage(role=role, content="hello")

    assert message.role == role


@pytest.mark.parametrize("role", ["system", "developer", "", "agent"])
def test_turn_message_rejects_unsupported_roles(role):
    with pytest.raises(ValidationError):
        TurnMessage(role=role, content="hello")


@pytest.mark.parametrize("content", ["", None])
def test_turn_message_rejects_empty_content(content):
    with pytest.raises(ValidationError):
        TurnMessage(role="user", content=content)


def test_turn_create_defaults_metadata_to_empty_dict():
    payload = TurnCreate(
        session_id="session-1",
        user_id=None,
        messages=[TurnMessage(role="user", content="hello")],
        timestamp=datetime(2026, 5, 7, tzinfo=UTC),
    )

    assert payload.metadata == {}


@pytest.mark.parametrize(
    "payload",
    [
        {"session_id": "", "messages": [{"role": "user", "content": "hello"}]},
        {"session_id": "s", "messages": []},
    ],
)
def test_turn_create_rejects_invalid_required_fields(payload):
    payload.setdefault("timestamp", "2026-05-07T10:00:00Z")

    with pytest.raises(ValidationError):
        TurnCreate.model_validate(payload)


def test_turn_created_response_shape():
    response = TurnCreated(id="turn-1")

    assert response.model_dump() == {"id": "turn-1"}


@pytest.mark.parametrize("max_tokens", [1, 512, 16000])
def test_recall_request_accepts_token_bounds(max_tokens):
    request = RecallRequest(query="Where?", session_id="session-1", max_tokens=max_tokens)

    assert request.max_tokens == max_tokens


@pytest.mark.parametrize("max_tokens", [0, -1, 16001])
def test_recall_request_rejects_invalid_token_bounds(max_tokens):
    with pytest.raises(ValidationError):
        RecallRequest(query="Where?", session_id="session-1", max_tokens=max_tokens)


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "", "session_id": "session-1"},
        {"query": "Where?", "session_id": ""},
    ],
)
def test_recall_request_rejects_empty_required_text(payload):
    with pytest.raises(ValidationError):
        RecallRequest.model_validate(payload)


def test_recall_response_serializes_citations():
    response = RecallResponse(
        context="Known facts",
        citations=[RecallCitation(turn_id="turn-1", score=0.9, snippet="quote")],
    )

    assert response.model_dump()["citations"][0]["turn_id"] == "turn-1"


@pytest.mark.parametrize("limit", [1, 10, 50])
def test_search_request_accepts_limit_bounds(limit):
    request = SearchRequest(query="Biscuit", limit=limit)

    assert request.limit == limit


@pytest.mark.parametrize("limit", [0, -1, 51])
def test_search_request_rejects_invalid_limit_bounds(limit):
    with pytest.raises(ValidationError):
        SearchRequest(query="Biscuit", limit=limit)


def test_search_response_serializes_results():
    result = SearchResult(
        content="pet.dog.name: Biscuit",
        score=0.9,
        session_id="session-1",
        timestamp=datetime(2026, 5, 7, tzinfo=UTC),
        metadata={"key": "pet.dog.name"},
    )
    response = SearchResponse(results=[result])

    assert response.results[0].metadata["key"] == "pet.dog.name"


def test_user_memories_response_serializes_memory_items():
    memory = MemoryResponse(
        id="memory-1",
        type="fact",
        key="location.current_city",
        value="Berlin",
        confidence=0.9,
        source_session="session-1",
        source_turn="turn-1",
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
        updated_at=datetime(2026, 5, 7, tzinfo=UTC),
        supersedes=None,
        superseded_by=None,
        active=True,
        confirmation_count=1,
    )
    response = UserMemoriesResponse(memories=[memory])

    assert response.memories[0].key == "location.current_city"
