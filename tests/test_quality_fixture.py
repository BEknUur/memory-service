#python imports
import json
from pathlib import Path


def test_recall_quality_fixture_has_expected_probe_coverage():
    fixture = json.loads(Path("tests/fixtures/recall_quality.json").read_text())

    probes = fixture["probes"]
    expected_names = {probe["name"] for probe in probes}

    assert {
        "employment_evolution",
        "location_move",
        "pet_name",
        "preference",
        "opinion_evolution",
    } <= expected_names
    assert all(probe["expected"] for probe in probes)


def test_basic_fixture_quality_score_shape():
    fixture = json.loads(Path("tests/fixtures/recall_quality.json").read_text())

    required_probe_names = {
        "employment_evolution",
        "location_move",
        "pet_name",
        "preference",
        "opinion_evolution",
    }
    probe_names = {probe["name"] for probe in fixture["probes"]}
    total_expected = sum(len(probe["expected"]) for probe in fixture["probes"])
    coverage_score = len(required_probe_names & probe_names) / len(required_probe_names)

    assert coverage_score == 1.0
    assert total_expected >= 4
