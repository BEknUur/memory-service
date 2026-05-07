#python imports
import json
from pathlib import Path


def test_recall_quality_fixture_has_expected_probe_coverage():
    fixture = json.loads(Path("tests/fixtures/recall_quality.json").read_text())

    probes = fixture["probes"]
    expected_names = {probe["name"] for probe in probes}

    assert {
        "employment_evolution",
        "employment_history",
        "location_move",
        "previous_city",
        "pet_name",
        "dog_location_multi_hop",
        "preference",
        "diet_evolution",
        "planning_style",
        "opinion_evolution",
        "cross_user_isolation",
        "other_user_memory",
    } <= expected_names
    assert all(probe.get("expected") or probe.get("expected_absent") for probe in probes)


def test_basic_fixture_quality_score_shape():
    fixture = json.loads(Path("tests/fixtures/recall_quality.json").read_text())

    required_probe_names = {
        "employment_evolution",
        "employment_history",
        "location_move",
        "previous_city",
        "pet_name",
        "dog_location_multi_hop",
        "preference",
        "diet_evolution",
        "planning_style",
        "opinion_evolution",
        "cross_user_isolation",
        "other_user_memory",
    }
    probe_names = {probe["name"] for probe in fixture["probes"]}
    total_expected = sum(len(probe.get("expected", [])) for probe in fixture["probes"])
    total_absent = sum(len(probe.get("expected_absent", [])) for probe in fixture["probes"])
    coverage_score = len(required_probe_names & probe_names) / len(required_probe_names)

    assert coverage_score == 1.0
    assert total_expected >= 14
    assert total_absent >= 2


def test_recall_quality_fixture_has_multiple_users_and_sessions():
    fixture = json.loads(Path("tests/fixtures/recall_quality.json").read_text())

    turns = [
        turn
        for conversation in fixture["conversations"]
        for turn in conversation["turns"]
    ]
    user_ids = {turn["user_id"] for turn in turns}
    session_ids = {turn["session_id"] for turn in turns}

    assert {"fixture-user", "other-fixture-user"} <= user_ids
    assert len(session_ids) >= 10


def test_recall_quality_fixture_has_evolution_cases():
    fixture = json.loads(Path("tests/fixtures/recall_quality.json").read_text())

    all_text = " ".join(
        message["content"]
        for conversation in fixture["conversations"]
        for turn in conversation["turns"]
        for message in turn["messages"]
    )

    assert "I work at Stripe" in all_text
    assert "I just joined Notion" in all_text
    assert "Actually I am vegan now, not vegetarian" in all_text
    assert "Actually, remote work is great" in all_text
