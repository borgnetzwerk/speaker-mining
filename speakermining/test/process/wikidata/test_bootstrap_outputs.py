from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.bootstrap import ensure_output_bootstrap, initialize_bootstrap_files
from process.candidate_generation.wikidata.common import get_active_wikidata_languages, set_active_wikidata_languages
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


def test_bootstrap_projection_columns_follow_configured_languages(tmp_path: Path) -> None:
    previous = get_active_wikidata_languages()
    try:
        set_active_wikidata_languages({"it": True})
        ensure_output_bootstrap(tmp_path)
        paths = build_artifact_paths(tmp_path)

        instances_columns = list(pd.read_csv(paths.instances_csv).columns)
        classes_columns = list(pd.read_csv(paths.classes_csv).columns)
        properties_columns = list(pd.read_csv(paths.properties_csv).columns)

        assert "label_it" in instances_columns
        assert "description_it" in instances_columns
        assert "alias_it" in instances_columns
        assert "label_en" not in instances_columns
        assert "label_de" not in instances_columns

        assert "label_it" in classes_columns
        assert "description_it" in classes_columns
        assert "alias_it" in classes_columns
        assert "label_en" not in classes_columns
        assert "label_de" not in classes_columns

        assert "label_it" in properties_columns
        assert "description_it" in properties_columns
        assert "alias_it" in properties_columns
        assert "label_en" not in properties_columns
        assert "label_de" not in properties_columns

        assert (paths.projections_dir / "aliases_it.csv").exists()
        assert not (paths.projections_dir / "aliases_en.csv").exists()
        assert not (paths.projections_dir / "aliases_de.csv").exists()
    finally:
        set_active_wikidata_languages(previous)
