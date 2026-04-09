from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_parquet_df, _atomic_write_text
from .common import language_projection_suffix, projection_languages
from .schemas import build_artifact_paths, canonical_class_filename, core_instances_projection_filename

_QID_RE = re.compile(r"^Q[1-9][0-9]*$")


def _empty_csv(path: Path, columns: list[str]) -> None:
    if not path.exists():
        empty_df = pd.DataFrame(columns=columns)
        _atomic_write_df(path, empty_df)
        _atomic_write_parquet_df(path.with_suffix(".parquet"), empty_df)


def _load_class_setup_rows(repo_root: Path, setup_filename: str) -> list[dict]:
    path = Path(repo_root) / "data" / "00_setup" / setup_filename
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows: list[dict] = []
    for _, row in df.iterrows():
        filename = canonical_class_filename(str(row.get("filename", "") or row.get("name", "")))
        rows.append(
            {
                "filename": filename,
                "label": str(row.get("label", "") or ""),
                "wikidata_id": str(row.get("wikidata_id", "") or ""),
            }
        )
    return rows


def load_core_classes(repo_root: Path) -> list[dict]:
    # Preferred split-aware setup layout.
    rows = _load_class_setup_rows(repo_root, "core_classes.csv")
    if rows:
        return rows

    # Backward-compatible fallback for older setup files.
    legacy_rows = _load_class_setup_rows(repo_root, "classes.csv")
    if not legacy_rows:
        return []
    return [row for row in legacy_rows if str(row.get("filename", "")) not in {"entities", "privacy_properties"}]


def load_root_classes(repo_root: Path) -> list[dict]:
    rows = _load_class_setup_rows(repo_root, "root_class.csv")
    if rows:
        return rows
    legacy_rows = _load_class_setup_rows(repo_root, "classes.csv")
    return [row for row in legacy_rows if str(row.get("filename", "")) == "entities"]


def load_other_interesting_classes(repo_root: Path) -> list[dict]:
    rows = _load_class_setup_rows(repo_root, "other_interesting_classes.csv")
    if rows:
        return rows
    legacy_rows = _load_class_setup_rows(repo_root, "classes.csv")
    return [row for row in legacy_rows if str(row.get("filename", "")) == "privacy_properties"]


def load_seed_instances(repo_root: Path) -> tuple[list[dict], list[dict]]:
    path = Path(repo_root) / "data" / "00_setup" / "broadcasting_programs.csv"
    if not path.exists():
        return [], []

    df = pd.read_csv(path)
    seeds: list[dict] = []
    skipped: list[dict] = []
    for _, row in df.iterrows():
        label = str(row.get("label", row.get("name", "")) or "").strip()
        qid = str(row.get("wikidata_id", "") or "").strip().upper()
        if not _QID_RE.match(qid):
            skipped.append({"label": label, "wikidata_id": qid, "reason": "invalid_wikidata_id"})
            continue
        seeds.append({"label": label, "wikidata_id": qid})
    return seeds, skipped


def ensure_output_bootstrap(repo_root: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    paths.projections_dir.mkdir(parents=True, exist_ok=True)
    paths.entity_chunks_dir.mkdir(parents=True, exist_ok=True)
    paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)
    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    paths.archive_dir.mkdir(parents=True, exist_ok=True)

    language_suffixes = [language_projection_suffix(lang) for lang in projection_languages()]
    label_columns = [f"label_{lang}" for lang in language_suffixes]
    description_columns = [f"description_{lang}" for lang in language_suffixes]
    alias_columns = [f"alias_{lang}" for lang in language_suffixes]

    _empty_csv(
        paths.classes_csv,
        [
            "id",
            *label_columns,
            *description_columns,
            *alias_columns,
            "path_to_core_class",
            "subclass_of_core_class",
            "discovered_count",
            "expanded_count",
        ],
    )
    _empty_csv(
        paths.class_hierarchy_csv,
        [
            "class_id",
            "class_filename",
            "path_to_core_class",
            "subclass_of_core_class",
            "is_core_class",
            "is_root_class",
            "parent_count",
            "parent_qids",
        ],
    )
    _empty_csv(
        paths.instances_csv,
        [
            "id",
            "class_id",
            "class_filename",
            *label_columns,
            *description_columns,
            *alias_columns,
            "path_to_core_class",
            "discovered_at_utc",
            "expanded_at_utc",
        ],
    )
    _empty_csv(
        paths.instances_leftovers_csv,
        [
            "id",
            "class_id",
            "class_filename",
            *label_columns,
            *description_columns,
            *alias_columns,
            "path_to_core_class",
            "subclass_of_core_class",
            "discovered_at_utc",
            "expanded_at_utc",
        ],
    )
    core_rows = load_core_classes(repo_root)
    active_core_projection_files: set[str] = set()
    for row in core_rows:
        class_filename = str(row.get("filename", "") or "")
        if not class_filename:
            continue
        projection_name = core_instances_projection_filename(class_filename)
        active_core_projection_files.add(projection_name)
        _empty_csv(
            paths.projections_dir / projection_name,
            [
                "id",
                "class_id",
                "class_filename",
                *label_columns,
                *description_columns,
                *alias_columns,
                "path_to_core_class",
                "subclass_of_core_class",
                "discovered_at_utc",
                "expanded_at_utc",
            ],
        )
    for core_projection_path in paths.projections_dir.glob("instances_core_*.csv"):
        if core_projection_path.name not in active_core_projection_files and core_projection_path.is_file():
            core_projection_path.unlink()
        core_projection_parquet = core_projection_path.with_suffix(".parquet")
        if core_projection_path.name not in active_core_projection_files and core_projection_parquet.is_file():
            core_projection_parquet.unlink()
    _empty_csv(paths.properties_csv, ["id", *label_columns, *description_columns, *alias_columns])
    active_alias_files: set[str] = set()
    for suffix in language_suffixes:
        alias_filename = f"aliases_{suffix}.csv"
        active_alias_files.add(alias_filename)
        _empty_csv(paths.projections_dir / alias_filename, ["alias", "qid"])
    for alias_path in paths.projections_dir.glob("aliases_*.csv"):
        if alias_path.name not in active_alias_files and alias_path.is_file():
            alias_path.unlink()
            alias_parquet = alias_path.with_suffix(".parquet")
            alias_parquet.unlink(missing_ok=True)
    _empty_csv(paths.triples_csv, ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"])
    _empty_csv(paths.query_inventory_csv, ["endpoint", "query_hash", "normalized_query", "key", "status", "timestamp_utc", "source_step"])
    _empty_csv(
        paths.entity_lookup_index_csv,
        [
            "qid",
            "chunk_file",
            "record_key",
            "resolved_core_class_id",
            "subclass_of_core_class",
            "discovered_at_utc",
            "expanded_at_utc",
            "byte_offset",
            "byte_length",
        ],
    )
    _empty_csv(paths.graph_stage_resolved_targets_csv, ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"])
    _empty_csv(paths.graph_stage_unresolved_targets_csv, ["mention_id", "mention_type", "mention_label", "context"])
    _empty_csv(paths.fallback_stage_candidates_csv, ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"])
    _empty_csv(paths.fallback_stage_eligible_for_expansion_csv, ["candidate_id"])
    _empty_csv(paths.fallback_stage_ineligible_csv, ["candidate_id"])

    if not paths.summary_json.exists():
        _atomic_write_text(paths.summary_json, "{}")


def initialize_bootstrap_files(repo_root: Path, core_classes: list[dict], seeds: list[dict]) -> None:
    paths = build_artifact_paths(Path(repo_root))
    root_classes = load_root_classes(repo_root)
    other_interesting_classes = load_other_interesting_classes(repo_root)
    if not paths.core_classes_csv.exists() or paths.core_classes_csv.stat().st_size == 0:
        core_df = pd.DataFrame(core_classes)
        _atomic_write_df(paths.core_classes_csv, core_df)
        _atomic_write_parquet_df(paths.core_classes_csv.with_suffix(".parquet"), core_df)
    if not paths.root_class_csv.exists() or paths.root_class_csv.stat().st_size == 0:
        root_df = pd.DataFrame(root_classes)
        _atomic_write_df(paths.root_class_csv, root_df)
        _atomic_write_parquet_df(paths.root_class_csv.with_suffix(".parquet"), root_df)
    if not paths.other_interesting_classes_csv.exists() or paths.other_interesting_classes_csv.stat().st_size == 0:
        other_df = pd.DataFrame(other_interesting_classes)
        _atomic_write_df(paths.other_interesting_classes_csv, other_df)
        _atomic_write_parquet_df(paths.other_interesting_classes_csv.with_suffix(".parquet"), other_df)
    if not paths.broadcasting_programs_csv.exists():
        seed_df = pd.DataFrame(seeds)
        _atomic_write_df(paths.broadcasting_programs_csv, seed_df)
        _atomic_write_parquet_df(paths.broadcasting_programs_csv.with_suffix(".parquet"), seed_df)
