from __future__ import annotations

# pyright: reportMissingImports=false

from process.candidate_generation.wikidata.expansion_engine import _filter_seed_instances_by_broadcasting_program, is_expandable_target
from process.candidate_generation.wikidata.node_store import upsert_discovered_item


def test_expandability_decision_table() -> None:
    seeds = {"Q100"}

    # Class node is never expandable.
    assert is_expandable_target(
        "Q1",
        seed_qids=seeds,
        has_direct_link_to_seed=True,
        p31_core_match=True,
        is_class_node=True,
    ) is False

    # Seed node is expandable.
    assert is_expandable_target(
        "Q100",
        seed_qids=seeds,
        has_direct_link_to_seed=False,
        p31_core_match=False,
        is_class_node=False,
    ) is True

    # Non-seed without direct link is not expandable.
    assert is_expandable_target(
        "Q2",
        seed_qids=seeds,
        has_direct_link_to_seed=False,
        p31_core_match=True,
        is_class_node=False,
    ) is False

    # Non-seed with direct link but without P31 core match is not expandable.
    assert is_expandable_target(
        "Q3",
        seed_qids=seeds,
        has_direct_link_to_seed=True,
        p31_core_match=False,
        is_class_node=False,
    ) is False

    # Non-seed with direct link and P31 core match is expandable.
    assert is_expandable_target(
        "Q4",
        seed_qids=seeds,
        has_direct_link_to_seed=True,
        p31_core_match=True,
        is_class_node=False,
    ) is True


def test_seed_filter_enforces_broadcasting_program_instance_from_cached_data(tmp_path) -> None:
    upsert_discovered_item(
        tmp_path,
        "Q100",
        {
            "id": "Q100",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q11578774"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-03-31T12:00:00Z",
    )

    upsert_discovered_item(
        tmp_path,
        "Q200",
        {
            "id": "Q200",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q5"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-03-31T12:01:00Z",
    )

    accepted, skipped = _filter_seed_instances_by_broadcasting_program(
        tmp_path,
        seeds=[
            {"label": "Program", "wikidata_id": "Q100"},
            {"label": "Not Program", "wikidata_id": "Q200"},
        ],
        expected_class_qid="Q11578774",
        cache_max_age_days=365,
        timeout_seconds=30,
    )

    assert len(accepted) == 1
    assert accepted[0]["wikidata_id"] == "Q100"
    assert len(skipped) == 1
    assert skipped[0]["wikidata_id"] == "Q200"
    assert skipped[0]["reason"] == "not_broadcasting_program_instance"


def test_seed_filter_accepts_uncached_seed_without_network(tmp_path) -> None:
    accepted, skipped = _filter_seed_instances_by_broadcasting_program(
        tmp_path,
        seeds=[{"label": "Unknown", "wikidata_id": "Q999"}],
        expected_class_qid="Q11578774",
        cache_max_age_days=365,
        timeout_seconds=30,
    )

    assert len(accepted) == 1
    assert accepted[0]["wikidata_id"] == "Q999"
    assert skipped == []
