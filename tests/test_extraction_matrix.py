#python imports

#third-party imports
import pytest

#project imports
from memory_service.schemas.turns import TurnMessage
from memory_service.services.memory_extraction import (
    MemoryCandidate,
    RuleBasedMemoryExtractor,
    dedupe_candidates,
)
from memory_service.services.memory_slots import canonical_slot


def extract_facts(text: str) -> set[tuple[str, str]]:
    candidates = RuleBasedMemoryExtractor().extract([TurnMessage(role="user", content=text)])
    return {(candidate.key, candidate.value) for candidate in candidates}


@pytest.mark.parametrize(
    ("text", "expected_current", "expected_previous"),
    [
        ("I just moved to Berlin from NYC.", "Berlin", "NYC"),
        ("I moved to Paris from London last month.", "Paris", "London"),
        ("I moved to San Francisco from New York.", "San Francisco", "New York"),
        ("I just moved to Almaty from Astana and love it.", "Almaty", "Astana"),
        ("I moved to Tokyo from Seoul!", "Tokyo", "Seoul"),
    ],
)
def test_rule_based_location_move_variants(text, expected_current, expected_previous):
    facts = extract_facts(text)

    assert ("location.current_city", expected_current) in facts
    assert ("location.previous_city", expected_previous) in facts


@pytest.mark.parametrize(
    ("text", "expected_company"),
    [
        ("I work at Stripe.", "Stripe"),
        ("I currently work at Notion.", "Notion"),
        ("I just joined OpenAI.", "OpenAI"),
        ("I started at Linear recently.", "Linear"),
        ("I started working at Figma now.", "Figma"),
        ("I work at Acme Labs and like the team.", "Acme Labs"),
    ],
)
def test_rule_based_employment_variants(text, expected_company):
    facts = extract_facts(text)

    assert ("employment.current_company", expected_company) in facts


@pytest.mark.parametrize(
    ("text", "expected_key", "expected_name"),
    [
        ("My dog Biscuit is adjusting.", "pet.dog.name", "Biscuit"),
        ("My dog named Mochi loves parks.", "pet.dog.name", "Mochi"),
        ("A cat named Luna sleeps here.", "pet.cat.name", "Luna"),
        ("My cat Nori is shy.", "pet.cat.name", "Nori"),
    ],
)
def test_rule_based_pet_variants(text, expected_key, expected_name):
    facts = extract_facts(text)

    assert (expected_key, expected_name) in facts


@pytest.mark.parametrize(
    "text",
    [
        "I'm vegetarian.",
        "I am vegetarian and cook at home.",
    ],
)
def test_rule_based_vegetarian_preference_variants(text):
    facts = extract_facts(text)

    assert ("preference.diet", "vegetarian") in facts


@pytest.mark.parametrize(
    "text",
    [
        "I prefer concise answers.",
        "I prefer short direct replies.",
        "I prefer brief and direct responses.",
    ],
)
def test_rule_based_communication_style_variants(text):
    facts = extract_facts(text)

    assert ("preference.communication_style", "concise/direct") in facts


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("employment.company", "employment.current_company"),
        ("employment.current_company", "employment.current_company"),
        ("job.company", "employment.current_company"),
        ("location.city", "location.current_city"),
        ("location.current_city", "location.current_city"),
        ("home.city", "location.current_city"),
        ("pet.dog", "pet.dog.name"),
        ("pet.dog.name", "pet.dog.name"),
        (" Employment.Company ", "employment.current_company"),
        ("opinion.remote_work", "opinion.remote_work"),
    ],
)
def test_canonical_slot_matrix(raw, expected):
    assert canonical_slot(raw) == expected


def test_dedupe_candidates_keeps_first_case_insensitive_duplicate():
    first = MemoryCandidate("fact", "pet.dog.name", "Biscuit", 0.8, "My dog Biscuit")
    duplicate = MemoryCandidate("fact", "pet.dog.name", "biscuit", 0.9, "dog biscuit")

    assert dedupe_candidates([first, duplicate]) == [first]


def test_dedupe_candidates_keeps_same_value_for_different_keys():
    city = MemoryCandidate("fact", "location.current_city", "Berlin", 0.9, "moved to Berlin")
    trip = MemoryCandidate("event", "event.trip", "Berlin", 0.7, "trip to Berlin")

    assert dedupe_candidates([city, trip]) == [city, trip]


def test_rule_based_extractor_returns_empty_for_unrecognized_text():
    candidates = RuleBasedMemoryExtractor().extract(
        [TurnMessage(role="user", content="Let's talk about the weather.")]
    )

    assert candidates == []
