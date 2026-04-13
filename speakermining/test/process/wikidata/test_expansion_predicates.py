from __future__ import annotations

# pyright: reportMissingImports=false

from process.candidate_generation.wikidata.expansion_engine import (
    _filter_seed_instances_by_broadcasting_program,
    _rank_neighbors_for_cap,
    _resolve_direct_or_subclass_core_match,
    is_expandable_target,
)
from process.candidate_generation.wikidata.node_store import upsert_discovered_item


def test_expandability_decision_table() -> None:
    seeds = {"Q100"}
    relevant_qids: set[str] = set()

    # Class node is never expandable.
    assert is_expandable_target(
        "Q1",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=1,
        direct_or_subclass_core_match=True,
        is_class_node=True,
    ) is False

    # Seed node is expandable.
    assert is_expandable_target(
        "Q100",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=None,
        direct_or_subclass_core_match=False,
        is_class_node=False,
    ) is True

    # Non-seed without first/second-degree seed-neighborhood evidence is not expandable.
    assert is_expandable_target(
        "Q2",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=None,
        direct_or_subclass_core_match=True,
        is_class_node=False,
    ) is False

    # Non-seed with eligible seed-neighborhood degree but without class match is not expandable.
    assert is_expandable_target(
        "Q3",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=1,
        direct_or_subclass_core_match=False,
        is_class_node=False,
    ) is False

    # Non-seed with first-degree seed-neighborhood and class match is expandable.
    assert is_expandable_target(
        "Q4",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=1,
        direct_or_subclass_core_match=True,
        is_class_node=False,
    ) is True

    # Second-degree neighbors are also eligible when class match holds.
    assert is_expandable_target(
        "Q5",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=2,
        direct_or_subclass_core_match=True,
        is_class_node=False,
    ) is True

    # Third-degree-or-more neighbors are not eligible.
    assert is_expandable_target(
        "Q6",
        seed_qids=seeds,
        relevant_qids=relevant_qids,
        seed_neighbor_degree=3,
        direct_or_subclass_core_match=True,
        is_class_node=False,
    ) is False

    # Relevant nodes are expandable even without seed-neighborhood/class checks.
    assert is_expandable_target(
        "Q77",
        seed_qids=seeds,
        relevant_qids={"Q77"},
        seed_neighbor_degree=None,
        direct_or_subclass_core_match=False,
        is_class_node=False,
    ) is True


def test_resolve_direct_or_subclass_core_match_accepts_subclass_paths(tmp_path) -> None:
    upsert_discovered_item(
        tmp_path,
        "Q500",
        {
            "id": "Q500",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q15416"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-04-09T10:00:00Z",
    )
    upsert_discovered_item(
        tmp_path,
        "Q15416",
        {
            "id": "Q15416",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q1983062"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-04-09T10:01:00Z",
    )

    candidate_doc = {
        "id": "Q500",
        "labels": {},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"entity-type": "item", "id": "Q15416"}
                        }
                    }
                }
            ]
        },
    }

    assert _resolve_direct_or_subclass_core_match(
        tmp_path,
        entity_doc=candidate_doc,
        core_class_qids={"Q1983062"},
        cache_max_age_days=365,
        timeout_seconds=30,
        discovered_qids=set(),
    ) is True


def test_rank_neighbors_for_cap_is_deterministic_and_prioritized(tmp_path) -> None:
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
                                "value": {"entity-type": "item", "id": "Q215627"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-04-09T10:02:00Z",
    )
    upsert_discovered_item(
        tmp_path,
        "Q300",
        {
            "id": "Q300",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q215627"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-04-09T10:03:00Z",
    )

    ranked = _rank_neighbors_for_cap(
        tmp_path,
        neighbor_qids={"Q300", "Q200", "Q900"},
        direct_link_to_seed={"Q200"},
        core_class_qids={"Q215627"},
        max_neighbors_per_node=2,
    )
    assert ranked == ["Q200", "Q300"]


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

    accepted, skipped, used = _filter_seed_instances_by_broadcasting_program(
        tmp_path,
        seeds=[
            {"label": "Program", "wikidata_id": "Q100"},
            {"label": "Not Program", "wikidata_id": "Q200"},
        ],
        expected_class_qid="Q11578774",
        cache_max_age_days=365,
        timeout_seconds=30,
        request_budget_remaining=10,
        query_delay_seconds=0.0,
        network_progress_every=0,
    )

    assert len(accepted) == 1
    assert accepted[0]["wikidata_id"] == "Q100"
    assert len(skipped) == 1
    assert skipped[0]["wikidata_id"] == "Q200"
    assert skipped[0]["reason"] == "not_broadcasting_program_instance"
    assert 0 <= used <= 10


def test_seed_filter_accepts_uncached_seed_without_network(tmp_path) -> None:
    accepted, skipped, used = _filter_seed_instances_by_broadcasting_program(
        tmp_path,
        seeds=[{"label": "Unknown", "wikidata_id": "Q999"}],
        expected_class_qid="Q11578774",
        cache_max_age_days=365,
        timeout_seconds=30,
        request_budget_remaining=10,
        query_delay_seconds=0.0,
        network_progress_every=0,
    )

    assert len(accepted) == 1
    assert accepted[0]["wikidata_id"] == "Q999"
    assert skipped == []
    assert used == 0


def test_seed_filter_accepts_subclass_of_broadcasting_program(tmp_path) -> None:
    upsert_discovered_item(
        tmp_path,
        "Q1587023",
        {
            "id": "Q1587023",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q15416"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-03-31T12:02:00Z",
    )

    upsert_discovered_item(
        tmp_path,
        "Q15416",
        {
            "id": "Q15416",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [
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
        "2026-03-31T12:03:00Z",
    )

    accepted, skipped, used = _filter_seed_instances_by_broadcasting_program(
        tmp_path,
        seeds=[{"label": "Hart aber fair", "wikidata_id": "Q1587023"}],
        expected_class_qid="Q11578774",
        cache_max_age_days=365,
        timeout_seconds=30,
        request_budget_remaining=10,
        query_delay_seconds=0.0,
        network_progress_every=0,
    )

    assert len(accepted) == 1
    assert accepted[0]["wikidata_id"] == "Q1587023"
    assert skipped == []
    assert used == 0


def test_seed_filter_fetches_missing_class_doc_under_explicit_budget(tmp_path, monkeypatch) -> None:
    upsert_discovered_item(
        tmp_path,
        "Q1587023",
        {
            "id": "Q1587023",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q15416"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-03-31T12:02:00Z",
    )

    calls: list[str] = []

    def _fake_fetch(root, qid, cache_max_age_days, timeout=30):
        calls.append(str(qid))
        assert qid == "Q15416"
        return {
            "entities": {
                "Q15416": {
                    "id": "Q15416",
                    "labels": {},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {
                        "P279": [
                            {
                                "mainsnak": {
                                    "datavalue": {
                                        "value": {"entity-type": "item", "id": "Q11578774"}
                                    }
                                }
                            }
                        ]
                    },
                }
            }
        }

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entity",
        _fake_fetch,
    )

    accepted, skipped, used = _filter_seed_instances_by_broadcasting_program(
        tmp_path,
        seeds=[{"label": "Hart aber fair", "wikidata_id": "Q1587023"}],
        expected_class_qid="Q11578774",
        cache_max_age_days=365,
        timeout_seconds=30,
        request_budget_remaining=1,
        query_delay_seconds=0.0,
        network_progress_every=0,
    )

    assert calls == ["Q15416"]
    assert len(accepted) == 1
    assert accepted[0]["wikidata_id"] == "Q1587023"
    assert skipped == []
    # Mocked fetch bypasses low-level HTTP, so request-context counter remains zero.
    assert used == 0
