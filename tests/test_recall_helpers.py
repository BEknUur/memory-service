#python imports
from datetime import UTC, datetime
from uuid import uuid4

#third-party imports
import pytest

#project imports
from memory_service.db.models import Memory
from memory_service.schemas.recall import RecallRequest
from memory_service.services.recall import RecallCandidate, RecallService


class NoopSession:
    async def execute(self, statement, params=None):
        raise AssertionError("database should not be called")


def make_memory(**overrides) -> Memory:
    data = {
        "id": uuid4(),
        "user_id": "user-1",
        "session_id": "session-1",
        "type": "fact",
        "key": "location.current_city",
        "slot": "location.current_city",
        "value": "Berlin",
        "confidence": 0.9,
        "confirmation_count": 1,
        "active": True,
        "created_at": datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 5, 7, 10, 0, tzinfo=UTC),
    }
    data.update(overrides)
    return Memory(**data)


@pytest.mark.parametrize(
    ("query", "expected_terms"),
    [
        ("Where does the user live?", {"location", "city", "current"}),
        ("What company does the user work at?", {"employment", "company", "current"}),
        ("What is the dog name?", {"pet", "dog", "cat", "name"}),
        ("Tell me about Biscuit", {"tell", "about", "biscuit"}),
    ],
)
def test_recall_query_term_expansion(query, expected_terms):
    service = RecallService(NoopSession())

    assert expected_terms <= set(service._query_terms(query))


@pytest.mark.parametrize(
    ("rank", "expected"),
    [
        (1, 1 / 61),
        (5, 1 / 65),
        (20, 1 / 80),
    ],
)
def test_recall_rrf_scores(rank, expected):
    service = RecallService(NoopSession())

    assert service._rrf(rank) == expected


@pytest.mark.parametrize(
    ("memory", "session_id", "expected_minimum"),
    [
        (make_memory(active=True, confirmation_count=1, confidence=0.5), "other", 0.55),
        (make_memory(active=True, confirmation_count=3, confidence=1.0), "other", 0.75),
        (make_memory(active=True, confirmation_count=1, confidence=0.5), "session-1", 0.8),
        (make_memory(active=False, confirmation_count=1, confidence=0.5), "other", 0.15),
    ],
)
def test_recall_boost_score_components(memory, session_id, expected_minimum):
    service = RecallService(NoopSession())
    candidate = RecallCandidate(memory=memory, turn_id=None, snippet="", score=0)
    request = RecallRequest(query="q", session_id=session_id, user_id="user-1")

    assert service._boost_score(candidate, request) >= expected_minimum


def test_recall_format_memory_without_previous_value():
    service = RecallService(NoopSession())
    memory = make_memory(key="pet.dog.name", slot="pet.dog.name", value="Biscuit")

    assert service._format_memory(memory) == (
        "pet.dog.name: Biscuit (confidence 0.90; updated 2026-05-07)"
    )


def test_recall_format_memory_with_previous_value():
    service = RecallService(NoopSession())
    previous = make_memory(value="Stripe")
    current = make_memory(
        key="employment.current_company",
        slot="employment.current_company",
        value="Notion",
    )
    current.previous_memory = previous

    assert service._format_memory(current) == (
        "employment.current_company: Notion "
        "(previously Stripe; confidence 0.90; updated 2026-05-07)"
    )


def test_recall_build_context_respects_budget():
    service = RecallService(NoopSession())
    candidates = [
        RecallCandidate(make_memory(key=f"fact.{index}", slot=f"fact.{index}"), None, "", 1.0)
        for index in range(20)
    ]

    context = service._build_context(candidates, max_tokens=30)

    assert len(context) <= 120
    assert context.startswith("## Known facts about this user")


def test_recall_build_context_dedupes_by_slot():
    service = RecallService(NoopSession())
    first = RecallCandidate(
        make_memory(key="employment.company", slot="employment.current_company"),
        None,
        "",
        1.0,
    )
    second = RecallCandidate(
        make_memory(key="job.company", slot="employment.current_company"),
        None,
        "",
        0.9,
    )

    context = service._build_context([first, second], max_tokens=512)

    assert context.count("employment.current_company") == 0
    assert context.count("employment.company") == 1
    assert "job.company" not in context


def test_recall_format_date_handles_none():
    service = RecallService(NoopSession())

    assert service._format_date(None) == "unknown"
