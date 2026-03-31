from __future__ import annotations

# pyright: reportMissingImports=false

from process.candidate_generation.wikidata.expansion_engine import ExpansionConfig, run_graph_expansion_stage
from process.candidate_generation.wikidata.node_store import upsert_discovered_item
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_graph_stage_resolves_targets_from_discovered_nodes(tmp_path) -> None:
    entity_doc = {
        "id": "Q1499182",
        "labels": {"de": {"value": "Markus Lanz"}},
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
    }
    upsert_discovered_item(tmp_path, "Q1499182", entity_doc, "2026-03-31T12:00:00Z")

    targets = [
        {
            "mention_id": "m1",
            "mention_type": "person",
            "mention_label": "Markus Lanz",
            "context": "test",
        },
        {
            "mention_id": "m2",
            "mention_type": "person",
            "mention_label": "Unmatched Person",
            "context": "test",
        },
    ]

    result = run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=targets,
        core_class_qids={"Q215627"},
        config=ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0),
        requested_mode="append",
    )

    assert "m1" in result.resolved_target_ids
    assert "m2" not in result.resolved_target_ids
    assert len(result.discovered_candidates) == 1
    assert result.discovered_candidates[0]["candidate_id"] == "Q1499182"
    assert len(result.unresolved_targets) == 1
    assert result.unresolved_targets[0]["mention_id"] == "m2"

    paths = build_artifact_paths(tmp_path)
    assert paths.graph_stage_resolved_targets_csv.exists()
    assert paths.graph_stage_unresolved_targets_csv.exists()
