from __future__ import annotations

# pyright: reportMissingImports=false

from process.candidate_generation.wikidata.expansion_engine import ExpansionConfig, run_graph_expansion_stage
from process.candidate_generation.wikidata.node_store import upsert_discovered_item
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_graph_stage_materialization_is_deterministic_for_same_inputs(tmp_path) -> None:
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
            "context": "determinism",
        }
    ]

    cfg = ExpansionConfig(max_depth=0, max_nodes=0, total_query_budget=0, per_seed_query_budget=0)
    run_graph_expansion_stage(tmp_path, seeds=[], targets=targets, core_class_qids={"Q215627"}, config=cfg, requested_mode="append")
    paths = build_artifact_paths(tmp_path)
    first_instances = paths.instances_csv.read_text(encoding="utf-8")
    first_resolved = paths.graph_stage_resolved_targets_csv.read_text(encoding="utf-8")

    run_graph_expansion_stage(tmp_path, seeds=[], targets=targets, core_class_qids={"Q215627"}, config=cfg, requested_mode="append")
    second_instances = paths.instances_csv.read_text(encoding="utf-8")
    second_resolved = paths.graph_stage_resolved_targets_csv.read_text(encoding="utf-8")

    assert first_instances == second_instances
    assert first_resolved == second_resolved
