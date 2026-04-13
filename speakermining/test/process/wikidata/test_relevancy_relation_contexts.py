from __future__ import annotations

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.relevancy import (
    _load_class_labels,
    _load_property_labels,
    _merge_relation_context_catalog,
)
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_relevancy_label_lookups_read_projection_labels(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {"id": "Q11578774", "label_en": "broadcasting program", "label_de": "", "class_filename": "broadcasting_programs"},
            {"id": "Q215627", "label_en": "person", "label_de": "", "class_filename": "persons"},
        ]
    ).to_csv(paths.classes_csv, index=False)
    pd.DataFrame(
        [
            {"id": "P138", "label_en": "named after", "label_de": ""},
        ]
    ).to_csv(paths.properties_csv, index=False)

    class_labels = _load_class_labels(paths)
    property_labels = _load_property_labels(paths)

    assert class_labels["Q11578774"] == "broadcasting program"
    assert class_labels["Q215627"] == "person"
    assert property_labels["P138"] == "named after"


def test_relation_context_catalog_deduplicates_and_stamps_decision_timestamp(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)

    # Legacy shape with direction should be migrated to the new directionless shape.
    pd.DataFrame(
        [
            {
                "subject_class_qid": "Q215627",
                "subject_class_label": "person",
                "property_qid": "P138",
                "property_label": "named after",
                "object_class_qid": "Q11578774",
                "object_class_label": "broadcasting program",
                "direction": "outlink",
                "can_inherit": "x",
                "decision_last_updated_at": "",
            },
            {
                "subject_class_qid": "Q11578774",
                "subject_class_label": "broadcasting program",
                "property_qid": "P138",
                "property_label": "named after",
                "object_class_qid": "Q215627",
                "object_class_label": "person",
                "direction": "inlink",
                "can_inherit": "",
                "decision_last_updated_at": "",
            },
        ]
    ).to_csv(paths.relevancy_relation_contexts_csv, index=False)

    merged = _merge_relation_context_catalog(
        paths,
        detected_rows=[
            {
                "subject_class_qid": "Q11578774",
                "subject_class_label": "broadcasting program",
                "property_qid": "P138",
                "property_label": "named after",
                "object_class_qid": "Q215627",
                "object_class_label": "person",
            }
        ],
    )

    assert list(merged.columns) == [
        "subject_class_qid",
        "subject_class_label",
        "property_qid",
        "property_label",
        "object_class_qid",
        "object_class_label",
        "decision_last_updated_at",
        "can_inherit",
    ]
    # Now both directions are present
    assert len(merged) == 2

    rows = [row.to_dict() for _, row in merged.iterrows()]
    # Find the row with can_inherit == 'x' (should be the outlink direction)
    outlink_row = next(r for r in rows if str(r["can_inherit"]).strip().lower() == "x")
    assert outlink_row["subject_class_qid"] == "Q215627"
    assert outlink_row["object_class_qid"] == "Q11578774"
    assert str(outlink_row["decision_last_updated_at"]).strip() != ""


def test_relation_context_catalog_sorts_subject_then_object_then_property(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)

    merged = _merge_relation_context_catalog(
        paths,
        detected_rows=[
            {
                "subject_class_qid": "Q11578774",
                "subject_class_label": "broadcasting program",
                "property_qid": "P272",
                "property_label": "production company",
                "object_class_qid": "Q43229",
                "object_class_label": "organization",
            },
            {
                "subject_class_qid": "Q11578774",
                "subject_class_label": "broadcasting program",
                "property_qid": "P138",
                "property_label": "named after",
                "object_class_qid": "Q215627",
                "object_class_label": "person",
            },
            {
                "subject_class_qid": "Q11578774",
                "subject_class_label": "broadcasting program",
                "property_qid": "P162",
                "property_label": "producer",
                "object_class_qid": "Q43229",
                "object_class_label": "organization",
            },
        ],
    )

    pairs = merged[["subject_class_qid", "object_class_qid", "property_qid"]].to_dict(orient="records")
    # The output should contain all directed triples as given, sorted
    expected = [
        {"subject_class_qid": "Q11578774", "object_class_qid": "Q215627", "property_qid": "P138"},
        {"subject_class_qid": "Q11578774", "object_class_qid": "Q43229", "property_qid": "P162"},
        {"subject_class_qid": "Q11578774", "object_class_qid": "Q43229", "property_qid": "P272"},
    ]
    assert pairs == expected
