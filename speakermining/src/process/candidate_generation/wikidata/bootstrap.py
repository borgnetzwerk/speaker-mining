from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_text
from .schemas import build_artifact_paths, canonical_class_filename

_QID_RE = re.compile(r"^Q[1-9][0-9]*$")


def _empty_csv(path: Path, columns: list[str]) -> None:
    if not path.exists():
        _atomic_write_df(path, pd.DataFrame(columns=columns))


def load_core_classes(repo_root: Path) -> list[dict]:
    path = Path(repo_root) / "data" / "00_setup" / "classes.csv"
    if not path.exists():
        return []
    df = pd.read_csv(path)
    rows = []
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
    paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)
    paths.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    paths.archive_dir.mkdir(parents=True, exist_ok=True)

    _empty_csv(paths.classes_csv, ["id", "label_en", "label_de", "description_en", "description_de", "alias_en", "alias_de", "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count"])
    _empty_csv(paths.instances_csv, ["id", "class_id", "class_filename", "label_en", "label_de", "description_en", "description_de", "alias_en", "alias_de", "path_to_core_class", "discovered_at_utc", "expanded_at_utc"])
    _empty_csv(paths.properties_csv, ["id", "label_en", "label_de", "description_en", "description_de", "alias_en", "alias_de"])
    _empty_csv(paths.aliases_en_csv, ["alias", "qid"])
    _empty_csv(paths.aliases_de_csv, ["alias", "qid"])
    _empty_csv(paths.triples_csv, ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"])
    _empty_csv(paths.query_inventory_csv, ["endpoint", "query_hash", "normalized_query", "key", "status", "timestamp_utc", "source_step"])
    _empty_csv(paths.graph_stage_resolved_targets_csv, ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"])
    _empty_csv(paths.graph_stage_unresolved_targets_csv, ["mention_id", "mention_type", "mention_label", "context"])
    _empty_csv(paths.fallback_stage_candidates_csv, ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"])
    _empty_csv(paths.fallback_stage_eligible_for_expansion_csv, ["candidate_id"])
    _empty_csv(paths.fallback_stage_ineligible_csv, ["candidate_id"])

    if not paths.entities_json.exists():
        _atomic_write_text(paths.entities_json, '{"entities": {}}')
    if not paths.properties_json.exists():
        _atomic_write_text(paths.properties_json, '{"properties": {}}')
    if not paths.triples_events_json.exists():
        _atomic_write_text(paths.triples_events_json, "[]")
    if not paths.summary_json.exists():
        _atomic_write_text(paths.summary_json, "{}")


def initialize_bootstrap_files(repo_root: Path, core_classes: list[dict], seeds: list[dict]) -> None:
    paths = build_artifact_paths(Path(repo_root))
    if not paths.core_classes_csv.exists():
        _atomic_write_df(paths.core_classes_csv, pd.DataFrame(core_classes))
    if not paths.broadcasting_programs_csv.exists():
        _atomic_write_df(paths.broadcasting_programs_csv, pd.DataFrame(seeds))
