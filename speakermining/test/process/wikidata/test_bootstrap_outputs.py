from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.bootstrap import ensure_output_bootstrap, initialize_bootstrap_files
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_empty_target_bootstraps_required_tree(tmp_path: Path) -> None:
    ensure_output_bootstrap(tmp_path)
    paths = build_artifact_paths(tmp_path)

    assert paths.raw_queries_dir.exists()
    assert paths.classes_csv.exists()
    assert paths.instances_csv.exists()
    assert paths.properties_csv.exists()
    assert paths.triples_csv.exists()
    assert paths.query_inventory_csv.exists()
    assert paths.graph_stage_resolved_targets_csv.exists()
    assert paths.graph_stage_unresolved_targets_csv.exists()
    assert paths.fallback_stage_candidates_csv.exists()
    assert paths.fallback_stage_eligible_for_expansion_csv.exists()
    assert paths.fallback_stage_ineligible_csv.exists()
    assert paths.entities_json.exists()
    assert paths.properties_json.exists()


def test_initialize_bootstrap_files_does_not_overwrite_existing_runtime_refs(tmp_path: Path) -> None:
    ensure_output_bootstrap(tmp_path)
    paths = build_artifact_paths(tmp_path)

    paths.core_classes_csv.write_text("filename,label,wikidata_id\nold,Old,Q1\n", encoding="utf-8")
    paths.broadcasting_programs_csv.write_text("label,wikidata_id\nOld Seed,Q2\n", encoding="utf-8")

    initialize_bootstrap_files(
        tmp_path,
        core_classes=[{"filename": "new", "label": "New", "wikidata_id": "Q10"}],
        seeds=[{"label": "New Seed", "wikidata_id": "Q20"}],
    )

    assert "old,Old,Q1" in paths.core_classes_csv.read_text(encoding="utf-8")
    assert "Old Seed,Q2" in paths.broadcasting_programs_csv.read_text(encoding="utf-8")
