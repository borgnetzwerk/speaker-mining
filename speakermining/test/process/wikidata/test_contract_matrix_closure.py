from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

import pandas as pd
import pytest

from process.candidate_generation.wikidata.bootstrap import ensure_output_bootstrap
from process.candidate_generation.wikidata.expansion_engine import ExpansionConfig, run_graph_expansion_stage
from process.candidate_generation.wikidata.fallback_matcher import (
    enqueue_eligible_fallback_qids,
    run_fallback_string_matching_stage,
)
from process.candidate_generation.wikidata.materializer import materialize_final
from process.candidate_generation.wikidata.schemas import build_artifact_paths
from process.candidate_generation.wikidata.triple_store import record_item_edges


def _write_setup_csvs(repo_root: Path) -> None:
    setup_dir = Path(repo_root) / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)

    classes_df = pd.DataFrame(
        [
            {"filename": "persons", "label": "Person", "wikidata_id": "Q215627"},
            {"filename": "broadcasting_programs", "label": "Broadcasting Program", "wikidata_id": "Q11578774"},
        ]
    )
    seeds_df = pd.DataFrame(
        [
            {"label": "Seed A", "wikidata_id": "Q100"},
            {"label": "Seed B", "wikidata_id": "Q101"},
        ]
    )
    classes_df.to_csv(setup_dir / "classes.csv", index=False)
    seeds_df.to_csv(setup_dir / "broadcasting_programs.csv", index=False)


def _fake_entity_for_qid(qid: str) -> dict:
    p31 = "Q11578774" if qid in {"Q100", "Q101"} else "Q215627"
    return {
        "id": qid,
        "labels": {"de": {"value": f"Label {qid}"}},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [
                {
                    "mainsnak": {
                        "datavalue": {
                            "value": {"entity-type": "item", "id": p31}
                        }
                    }
                }
            ],
            "P279": [],
        },
    }


def test_deterministic_multi_seed_queue_ordering_with_neighbor_permutations(tmp_path: Path, monkeypatch) -> None:
    _write_setup_csvs(tmp_path)

    outlinks_map = {
        "Q100": ["Q300", "Q200"],
        "Q101": ["Q401", "Q400"],
        "Q200": [],
        "Q300": [],
        "Q400": [],
        "Q401": [],
    }

    expanded_order: list[str] = []

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        return {"entities": {qid: _fake_entity_for_qid(qid)}}

    def _fake_get_or_build_outlinks(_repo_root, qid, _entity_payload, _cache_max_age_days):
        neighbors = outlinks_map.get(qid, [])
        return {
            "qid": qid,
            "property_ids": [],
            "linked_qids": neighbors,
            "edges": [{"pid": "P463", "to_qid": neighbor} for neighbor in neighbors],
        }

    def _fake_get_or_fetch_inlinks(_repo_root, _qid, _cache_max_age_days, _inlinks_limit, offset=0, timeout=30):
        _ = (offset, timeout)
        return {"rows": []}

    def _capture_expanded(_repo_root, qid, _entity_doc, _timestamp):
        expanded_order.append(qid)

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entity",
        _fake_get_or_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_build_outlinks",
        _fake_get_or_build_outlinks,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_inlinks",
        _fake_get_or_fetch_inlinks,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.parse_inlinks_results",
        lambda payload: payload.get("rows", []),
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_property",
        lambda *args, **kwargs: {"entities": {}},
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.upsert_expanded_item",
        _capture_expanded,
    )

    config = ExpansionConfig(
        max_depth=1,
        max_nodes=20,
        total_query_budget=-1,
        per_seed_query_budget=-1,
        max_neighbors_per_node=20,
    )
    run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids={"Q215627"},
        config=config,
        requested_mode="append",
    )

    assert expanded_order == ["Q100", "Q200", "Q300", "Q101", "Q400", "Q401"]


@pytest.mark.parametrize(
    "seed_summary,total_budget,expected_stop_reason,expected_seeds_completed",
    [
        (
            {
                "seed_qid": "Q100",
                "discovered_qids": {"Q100"},
                "expanded_qids": {"Q100"},
                "network_queries": 1,
                "stop_reason": "per_seed_budget_exhausted",
                "inlinks_cursor": None,
            },
            5,
            "per_seed_budget_exhausted",
            0,
        ),
        (
            {
                "seed_qid": "Q100",
                "discovered_qids": {"Q100"},
                "expanded_qids": {"Q100"},
                "network_queries": 1,
                "stop_reason": "per_seed_budget_exhausted",
                "inlinks_cursor": None,
            },
            1,
            "total_query_budget_exhausted",
            0,
        ),
        (
            {
                "seed_qid": "Q100",
                "discovered_qids": {"Q100"},
                "expanded_qids": {"Q100"},
                "network_queries": 1,
                "stop_reason": "seed_complete",
                "inlinks_cursor": None,
            },
            1,
            "total_query_budget_exhausted",
            1,
        ),
    ],
)
def test_stop_condition_precedence_matrix(
    tmp_path: Path,
    monkeypatch,
    seed_summary: dict,
    total_budget: int,
    expected_stop_reason: str,
    expected_seeds_completed: int,
) -> None:
    _write_setup_csvs(tmp_path)

    def _fake_run_seed_expansion(*args, **kwargs):
        _ = (args, kwargs)
        return seed_summary

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.run_seed_expansion",
        _fake_run_seed_expansion,
    )

    result = run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids={"Q215627"},
        config=ExpansionConfig(
            max_depth=1,
            max_nodes=10,
            total_query_budget=total_budget,
            per_seed_query_budget=1,
        ),
        requested_mode="append",
    )

    assert result.checkpoint_stats["stop_reason"] == expected_stop_reason
    assert int(result.checkpoint_stats["seeds_completed"]) == expected_seeds_completed


def test_full_materialization_schema_headers_contract(tmp_path: Path) -> None:
    ensure_output_bootstrap(tmp_path)
    _write_setup_csvs(tmp_path)

    run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids=set(),
        config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0),
        requested_mode="append",
    )

    paths = build_artifact_paths(tmp_path)
    expected_headers = {
        "classes": (
            paths.classes_csv,
            [
                "id",
                "class_filename",
                "label_en",
                "label_de",
                "description_en",
                "description_de",
                "alias_en",
                "alias_de",
                "path_to_core_class",
                "subclass_of_core_class",
                "discovered_count",
                "expanded_count",
            ],
        ),
        "instances": (
            paths.instances_csv,
            [
                "id",
                "class_id",
                "class_filename",
                "label_de",
                "label_en",
                "description_de",
                "description_en",
                "alias_de",
                "alias_en",
                "wikidata_claim_properties",
                "wikidata_claim_property_count",
                "wikidata_claim_statement_count",
                "wikidata_property_counts_json",
                "wikidata_p31_qids",
                "wikidata_p279_qids",
                "wikidata_p179_qids",
                "wikidata_p106_qids",
                "wikidata_p39_qids",
                "wikidata_p921_qids",
                "wikidata_p527_qids",
                "wikidata_p361_qids",
                "relevant",
                "relevant_seed_source",
                "relevance_first_assigned_at",
                "relevance_last_updated_at",
                "relevance_inherited_from_qid",
                "relevance_inherited_via_property_qid",
                "relevance_inherited_via_direction",
                "path_to_core_class",
                "subclass_of_core_class",
                "discovered_at_utc",
                "expanded_at_utc",
            ],
        ),
        "properties": (
            paths.properties_csv,
            ["id", "label_de", "label_en", "description_de", "description_en", "alias_de", "alias_en"],
        ),
        "aliases_en": (paths.aliases_en_csv, ["alias", "qid"]),
        "aliases_de": (paths.aliases_de_csv, ["alias", "qid"]),
        "triples": (
            paths.triples_csv,
            ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"],
        ),
        "query_inventory": (
            paths.query_inventory_csv,
            ["query_hash", "endpoint", "normalized_query", "status", "first_seen", "last_seen", "count"],
        ),
        "graph_resolved": (
            paths.graph_stage_resolved_targets_csv,
            ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"],
        ),
        "graph_unresolved": (
            paths.graph_stage_unresolved_targets_csv,
            ["mention_id", "mention_type", "mention_label", "context"],
        ),
        "fallback_candidates": (
            paths.fallback_stage_candidates_csv,
            ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"],
        ),
        "fallback_eligible": (paths.fallback_stage_eligible_for_expansion_csv, ["candidate_id"]),
        "fallback_ineligible": (paths.fallback_stage_ineligible_csv, ["candidate_id"]),
        "relevancy": (
            paths.relevancy_csv,
            [
                "qid",
                "is_core_class_instance",
                "relevant",
                "relevant_seed_source",
                "relevance_first_assigned_at",
                "relevance_last_updated_at",
                "relevance_inherited_from_qid",
                "relevance_inherited_via_property_qid",
                "relevance_inherited_via_direction",
                "relevance_evidence_event_sequence",
            ],
        ),
        "relevancy_relation_contexts": (
            paths.relevancy_relation_contexts_csv,
            [
                "subject_class_qid",
                "subject_class_label",
                "property_qid",
                "property_label",
                "object_class_qid",
                "object_class_label",
                "decision_last_updated_at",
                "can_inherit",
            ],
        ),
    }

    for _, (csv_path, columns) in expected_headers.items():
        assert csv_path.exists()
        assert list(pd.read_csv(csv_path).columns) == columns

    assert not paths.entities_json.exists()
    assert not paths.properties_json.exists()
    assert not paths.triples_events_json.exists()
    assert paths.summary_json.exists()


def test_end_to_end_stage_a_stage_b_reentry_and_final_materialization(tmp_path: Path, monkeypatch) -> None:
    _write_setup_csvs(tmp_path)

    def _graph_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        return {"entities": {qid: _fake_entity_for_qid(qid)}}

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entity",
        _graph_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_build_outlinks",
        lambda *_args, **_kwargs: {"qid": "", "property_ids": [], "linked_qids": [], "edges": []},
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_inlinks",
        lambda *_args, **_kwargs: {"rows": []},
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.parse_inlinks_results",
        lambda payload: payload.get("rows", []),
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_property",
        lambda *args, **kwargs: {"entities": {}},
    )

    graph_targets = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Alice",
            "context": "integration",
        }
    ]

    graph_result = run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=graph_targets,
        core_class_qids={"Q215627"},
        config=ExpansionConfig(max_depth=0, max_nodes=10, total_query_budget=0, per_seed_query_budget=0),
        requested_mode="append",
    )
    assert len(graph_result.unresolved_targets) == 1

    # Direct-link evidence makes fallback candidate eligible for re-entry.
    record_item_edges(
        tmp_path,
        "Q500",
        [{"pid": "P463", "to_qid": "Q100"}],
        discovered_at_utc="2026-03-31T13:00:00Z",
        source_query_file="test_fixture",
    )

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_search_entities_by_label",
        lambda *_args, **_kwargs: {"search": [{"id": "Q500"}]},
    )

    def _fallback_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        return {
            "entities": {
                qid: {
                    "id": qid,
                    "labels": {"de": {"value": "Alice"}},
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
                        ],
                        "P279": [],
                    },
                }
            }
        }

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.fallback_matcher.get_or_fetch_entity",
        _fallback_fetch_entity,
    )

    fallback_result = run_fallback_string_matching_stage(
        tmp_path,
        unresolved_targets=graph_result.unresolved_targets,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        class_scope_hints={"person": {"Q215627"}},
        config={
            "fallback_search_limit": 5,
            "fallback_search_languages": ["de"],
            "fallback_enabled_mention_types": ["person"],
        },
    )

    assert len(fallback_result.fallback_candidates) == 1
    assert fallback_result.fallback_candidates[0]["candidate_id"] == "Q500"
    assert "Q500" in fallback_result.eligible_for_expansion_qids

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.run_seed_expansion",
        lambda repo_root, **kwargs: {
            "seed_qid": kwargs["seed"].get("wikidata_id", ""),
            "discovered_qids": {kwargs["seed"].get("wikidata_id", "")},
            "expanded_qids": {kwargs["seed"].get("wikidata_id", "")},
            "network_queries": 0,
            "stop_reason": "seed_complete",
            "inlinks_cursor": None,
        },
    )

    reentry = enqueue_eligible_fallback_qids(
        tmp_path,
        candidate_qids=fallback_result.eligible_for_expansion_qids,
        seeds={"Q100"},
        core_class_qids={"Q215627"},
        expansion_config=ExpansionConfig(max_depth=0, max_nodes=10, total_query_budget=0, per_seed_query_budget=0),
    )

    assert reentry["eligible_qids"] == ["Q500"]
    assert reentry["expanded"] == 1

    materialize_final(tmp_path, run_id="e2e")
    paths = build_artifact_paths(tmp_path)

    fallback_df = pd.read_csv(paths.fallback_stage_candidates_csv)
    assert "Q500" in set(fallback_df["candidate_id"])

    instances_df = pd.read_csv(paths.instances_csv)
    assert "Q500" in set(instances_df["id"])

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert summary.get("stage") == "final"
