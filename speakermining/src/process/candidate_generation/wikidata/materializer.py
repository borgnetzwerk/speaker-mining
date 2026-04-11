from __future__ import annotations

import json
import os
import hashlib
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from collections import Counter

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_parquet_df, _atomic_write_text, _entity_from_payload
from .bootstrap import load_core_classes, load_other_interesting_classes, load_root_classes
from .bootstrap import load_seed_instances
from .class_resolver import (
    RecoveredLineageEvidence,
    compute_class_rollups,
    load_recovered_class_hierarchy,
    resolve_class_path,
)
from .common import (
    DEFAULT_WIKIDATA_FALLBACK_LANGUAGE,
    canonical_qid,
    effective_core_class_qids,
    language_projection_suffix,
    projection_languages,
)
from .event_log import get_query_event_field, get_query_event_response_data, iter_query_events
from .node_store import flush_node_store, iter_items, iter_properties
from .query_inventory import materialize_query_inventory
from .schemas import build_artifact_paths
from .schemas import core_instances_json_filename
from .schemas import core_instances_projection_filename
from .triple_store import flush_triple_events, iter_unique_triples


@dataclass(frozen=True)
class SnapshotArtifactParity:
    artifact_name: str
    left_exists: bool
    right_exists: bool
    left_rows: int
    right_rows: int
    left_digest: str
    right_digest: str
    matches: bool


@dataclass(frozen=True)
class MaterializationParityReport:
    left_root: str
    right_root: str
    artifacts_compared: list[SnapshotArtifactParity]

    @property
    def matches(self) -> bool:
        return all(row.matches for row in self.artifacts_compared)


_PARITY_CSV_ARTIFACTS = (
    "instances_csv",
    "classes_csv",
    "properties_csv",
    "triples_csv",
    "class_hierarchy_csv",
    "query_inventory_csv",
    "entity_lookup_index_csv",
    "instances_leftovers_csv",
    "fallback_stage_candidates_csv",
    "fallback_stage_eligible_for_expansion_csv",
    "fallback_stage_ineligible_csv",
)


def _artifact_signature_for_csv(path: Path) -> tuple[int, str]:
    if not path.exists() or path.stat().st_size == 0:
        return 0, hashlib.sha256(b"").hexdigest()

    df = pd.read_csv(path)
    if df.empty:
        normalized = df.copy()
    else:
        normalized = df.fillna("").copy()
        ordered_columns = sorted(normalized.columns.tolist())
        normalized = normalized[ordered_columns]
        sort_columns = ordered_columns or list(normalized.columns)
        if sort_columns:
            normalized = normalized.sort_values(sort_columns).reset_index(drop=True)

    normalized_csv = normalized.to_csv(index=False)
    digest = hashlib.sha256(normalized_csv.encode("utf-8")).hexdigest()
    return int(len(normalized)), digest


def compare_materialization_snapshots(
    left_repo_root: Path | str,
    right_repo_root: Path | str,
    *,
    artifact_names: tuple[str, ...] = _PARITY_CSV_ARTIFACTS,
) -> MaterializationParityReport:
    """Compare two materialization snapshots using deterministic CSV normalization.

    This is intended for parity validation between incremental bootstrap runs and
    controlled full-rebuild runs, without depending on raw file ordering.
    """

    left_repo_root = Path(left_repo_root)
    right_repo_root = Path(right_repo_root)
    left_paths = build_artifact_paths(left_repo_root)
    right_paths = build_artifact_paths(right_repo_root)

    compared: list[SnapshotArtifactParity] = []
    for artifact_name in artifact_names:
        left_path = getattr(left_paths, artifact_name)
        right_path = getattr(right_paths, artifact_name)
        left_rows, left_digest = _artifact_signature_for_csv(left_path)
        right_rows, right_digest = _artifact_signature_for_csv(right_path)
        compared.append(
            SnapshotArtifactParity(
                artifact_name=artifact_name,
                left_exists=left_path.exists(),
                right_exists=right_path.exists(),
                left_rows=left_rows,
                right_rows=right_rows,
                left_digest=left_digest,
                right_digest=right_digest,
                matches=bool(left_path.exists() == right_path.exists() and left_rows == right_rows and left_digest == right_digest),
            )
        )

    return MaterializationParityReport(
        left_root=str(left_repo_root),
        right_root=str(right_repo_root),
        artifacts_compared=compared,
    )


def _lineage_resolution_policy() -> str:
    policy = str(os.getenv("WIKIDATA_LINEAGE_RESOLUTION_POLICY", "runtime_then_recovered_then_network") or "").strip()
    return policy or "runtime_then_recovered_then_network"


def _load_recovered_lineage_evidence(repo_root: Path, paths) -> tuple[RecoveredLineageEvidence | None, str]:
    reverse_engineering_path = (
        Path(repo_root)
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "reverse_engineering_potential"
        / "class_hierarchy.csv"
    )
    if reverse_engineering_path.exists():
        return load_recovered_class_hierarchy(reverse_engineering_path), "reverse_engineering_potential"

    if paths.class_hierarchy_csv.exists():
        return load_recovered_class_hierarchy(paths.class_hierarchy_csv), "projection_cache"

    return None, "none"


def _pick_lang_text(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""

    node = mapping.get(lang, {})
    value = node.get("value", "") if isinstance(node, dict) else ""
    if value:
        return str(value)

    fallback_node = mapping.get(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE, {})
    fallback = fallback_node.get("value", "") if isinstance(fallback_node, dict) else ""
    if fallback:
        return str(fallback)
    return ""


def _alias_pipe(mapping: dict, lang: str) -> str:
    if not isinstance(mapping, dict):
        return ""

    values: set[str] = set()

    for item in mapping.get(lang, []) or []:
        if isinstance(item, dict) and item.get("value"):
            values.add(str(item.get("value")))

    for item in mapping.get(DEFAULT_WIKIDATA_FALLBACK_LANGUAGE, []) or []:
        if isinstance(item, dict) and item.get("value"):
            values.add(str(item.get("value")))

    return "|".join(sorted(values))


def _projection_language_columns() -> tuple[list[str], list[str], list[str]]:
    languages = [language_projection_suffix(lang) for lang in projection_languages()]
    label_columns = [f"label_{lang}" for lang in languages]
    description_columns = [f"description_{lang}" for lang in languages]
    alias_columns = [f"alias_{lang}" for lang in languages]
    return label_columns, description_columns, alias_columns


def _extract_claim_qids(claims: dict, pid: str) -> list[str]:
    out: list[str] = []
    for claim in claims.get(pid, []) or []:
        mainsnak = claim.get("mainsnak", {}) if isinstance(claim, dict) else {}
        value = (mainsnak.get("datavalue", {}) or {}).get("value")
        if isinstance(value, dict) and value.get("entity-type") == "item":
            qid = canonical_qid(value.get("id", ""))
            if qid:
                out.append(qid)
    return sorted(set(out))


def _class_filename_lookup(repo_root: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    setup_rows = load_core_classes(repo_root) + load_root_classes(repo_root) + load_other_interesting_classes(repo_root)
    for row in setup_rows:
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        filename = str(row.get("filename", "") or "")
        if qid and filename:
            lookup[qid] = filename
    return lookup


def _core_class_qids(repo_root: Path) -> set[str]:
    return effective_core_class_qids(
        {
            canonical_qid(str(row.get("wikidata_id", "") or ""))
            for row in load_core_classes(repo_root)
            if canonical_qid(str(row.get("wikidata_id", "") or ""))
        }
    )


def _root_class_qids(repo_root: Path) -> set[str]:
    return {
        canonical_qid(str(row.get("wikidata_id", "") or ""))
        for row in load_root_classes(repo_root)
        if canonical_qid(str(row.get("wikidata_id", "") or ""))
    }


def _latest_entity_cache_docs(repo_root: Path) -> dict[str, dict]:
    """Index latest entity_fetch payload per QID from v3 query_response events."""
    latest: dict[str, tuple[int, dict]] = {}
    for event in iter_query_events(repo_root) or []:
        if get_query_event_field(event, "source_step", "") != "entity_fetch":
            continue
        qid = canonical_qid(str(get_query_event_field(event, "key", "") or ""))
        if not qid:
            continue
        seq = event.get("sequence_num")
        if not isinstance(seq, int):
            continue
        payload = get_query_event_response_data(event)
        if not isinstance(payload, dict):
            continue
        prior = latest.get(qid)
        if prior is None or seq > prior[0]:
            latest[qid] = (seq, payload)

    docs: dict[str, dict] = {}
    for qid, (_seq, payload) in latest.items():
        node_doc = _entity_from_payload(payload, qid)
        if isinstance(node_doc, dict) and node_doc:
            docs[qid] = node_doc
    return docs


def _build_instances_df(
    repo_root: Path,
    core_class_qids: set[str],
    *,
    recovered_lineage: RecoveredLineageEvidence | None,
    resolution_policy: str,
    resolution_reasons: Counter,
) -> pd.DataFrame:
    rows = []
    label_columns, description_columns, alias_columns = _projection_language_columns()
    languages = [column.replace("label_", "", 1) for column in label_columns]
    class_filename_lookup = _class_filename_lookup(repo_root)
    parent_doc_cache: dict[str, dict] = {}
    items = list(iter_items(repo_root))
    item_by_id = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in items
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_docs = _latest_entity_cache_docs(repo_root)

    def _get_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None

        node = item_by_id.get(qid_norm)
        if node:
            return node
        if qid_norm in parent_doc_cache:
            return parent_doc_cache[qid_norm]

        node_doc = latest_entity_docs.get(qid_norm)
        if node_doc is None:
            return None
        parent_doc_cache[qid_norm] = node_doc if isinstance(node_doc, dict) else {}
        return parent_doc_cache[qid_norm]

    for item in items:
        claims = item.get("claims", {}) if isinstance(item.get("claims"), dict) else {}
        resolution = resolve_class_path(
            item,
            core_class_qids,
            _get_entity,
            on_resolved=lambda payload: resolution_reasons.update(
                [str(payload.get("resolution_reason", "unknown") or "unknown")]
            ),
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        class_id = str(resolution.get("class_id", "") or "")
        row = {
            "id": item.get("id", ""),
            "class_id": class_id,
            "class_filename": class_filename_lookup.get(class_id, ""),
            "path_to_core_class": str(resolution.get("path_to_core_class", "") or ""),
            "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
            "discovered_at_utc": item.get("discovered_at_utc", ""),
            "expanded_at_utc": item.get("expanded_at_utc") or "",
        }
        for lang in languages:
            row[f"label_{lang}"] = _pick_lang_text(item.get("labels", {}), lang)
            row[f"description_{lang}"] = _pick_lang_text(item.get("descriptions", {}), lang)
            row[f"alias_{lang}"] = _alias_pipe(item.get("aliases", {}), lang)
        rows.append(row)
    columns = [
        "id", "class_id", "class_filename",
        *label_columns,
        *description_columns,
        *alias_columns,
        "path_to_core_class", "subclass_of_core_class", "discovered_at_utc", "expanded_at_utc",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates(subset=["id"]).sort_values("id").reset_index(drop=True)


def _build_classes_df(repo_root: Path, instances_df: pd.DataFrame) -> pd.DataFrame:
    label_columns, description_columns, alias_columns = _projection_language_columns()
    languages = [column.replace("label_", "", 1) for column in label_columns]
    columns = [
        "id", *label_columns, *description_columns, *alias_columns,
        "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count",
    ]
    if instances_df.empty:
        return pd.DataFrame(columns=columns)

    rollup_rows = compute_class_rollups(instances_df.to_dict(orient="records"))
    class_meta: dict[str, dict[str, str]] = {}
    for item in iter_items(repo_root):
        qid = str(item.get("id", "") or "")
        if not qid:
            continue
        meta = {}
        for lang in languages:
            meta[f"label_{lang}"] = _pick_lang_text(item.get("labels", {}), lang)
            meta[f"description_{lang}"] = _pick_lang_text(item.get("descriptions", {}), lang)
            meta[f"alias_{lang}"] = _alias_pipe(item.get("aliases", {}), lang)
        class_meta[qid] = meta
    for row in rollup_rows:
        meta = class_meta.get(str(row.get("id", "") or ""), {})
        for key in [*label_columns, *description_columns, *alias_columns]:
            if meta.get(key):
                row[key] = meta[key]
    return pd.DataFrame(rollup_rows)[columns].sort_values("id").reset_index(drop=True)


def _build_properties_df(repo_root: Path) -> pd.DataFrame:
    label_columns, description_columns, alias_columns = _projection_language_columns()
    languages = [column.replace("label_", "", 1) for column in label_columns]
    columns = ["id", *label_columns, *description_columns, *alias_columns]
    rows = []
    for prop in iter_properties(repo_root):
        row = {
            "id": prop.get("id", ""),
        }
        for lang in languages:
            row[f"label_{lang}"] = _pick_lang_text(prop.get("labels", {}), lang)
            row[f"description_{lang}"] = _pick_lang_text(prop.get("descriptions", {}), lang)
            row[f"alias_{lang}"] = _alias_pipe(prop.get("aliases", {}), lang)
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].drop_duplicates(subset=["id"]).sort_values("id").reset_index(drop=True)


def _build_alias_df(instances_df: pd.DataFrame, lang: str) -> pd.DataFrame:
    column = f"alias_{language_projection_suffix(lang)}"
    rows = []
    for _, row in instances_df.iterrows():
        qid = str(row.get("id", ""))
        for alias in str(row.get(column, "")).split("|"):
            alias = alias.strip()
            if alias:
                rows.append({"alias": alias, "qid": qid})
    if not rows:
        return pd.DataFrame(columns=["alias", "qid"])
    return pd.DataFrame(rows).drop_duplicates(subset=["alias", "qid"]).sort_values(["alias", "qid"]).reset_index(drop=True)


def _remove_stale_alias_projections(paths, active_alias_files: set[str]) -> None:
    for alias_path in paths.projections_dir.glob("aliases_*.csv"):
        if alias_path.name not in active_alias_files and alias_path.is_file():
            alias_path.unlink()
        alias_parquet = alias_path.with_suffix(".parquet")
        if alias_path.name not in active_alias_files and alias_parquet.is_file():
            alias_parquet.unlink()


def _build_triples_df(repo_root: Path) -> pd.DataFrame:
    columns = ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"]
    rows = list(iter_unique_triples(repo_root))
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns].sort_values(["subject", "predicate", "object"]).reset_index(drop=True)


def _build_class_hierarchy_df(
    repo_root: Path,
    core_class_qids: set[str],
    root_class_qids: set[str],
    *,
    recovered_lineage: RecoveredLineageEvidence | None,
    resolution_policy: str,
    resolution_reasons: Counter,
) -> pd.DataFrame:
    columns = [
        "class_id",
        "class_filename",
        "path_to_core_class",
        "subclass_of_core_class",
        "is_core_class",
        "is_root_class",
        "parent_count",
        "parent_qids",
    ]
    class_filename_lookup = _class_filename_lookup(repo_root)
    items = list(iter_items(repo_root))
    item_by_id = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in items
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_docs = _latest_entity_cache_docs(repo_root)

    def _get_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None
        node = item_by_id.get(qid_norm)
        if node:
            return node
        node_doc = latest_entity_docs.get(qid_norm)
        if isinstance(node_doc, dict):
            return node_doc
        return None

    candidate_class_qids: set[str] = set()
    for item in items:
        qid = canonical_qid(str(item.get("id", "") or ""))
        if not qid:
            continue
        claims = item.get("claims", {}) if isinstance(item.get("claims"), dict) else {}
        p31 = _extract_claim_qids(claims, "P31")
        p279 = _extract_claim_qids(claims, "P279")
        if p279:
            candidate_class_qids.add(qid)
        candidate_class_qids.update(p31)
        candidate_class_qids.update(p279)

    rows: list[dict] = []
    for class_qid in sorted(candidate_class_qids):
        class_doc = _get_entity(class_qid) or {}
        claims = class_doc.get("claims", {}) if isinstance(class_doc.get("claims"), dict) else {}
        parent_qids = _extract_claim_qids(claims, "P279")
        resolution = (
            resolve_class_path(
                class_doc,
                core_class_qids,
                _get_entity,
                on_resolved=lambda payload: resolution_reasons.update(
                    [str(payload.get("resolution_reason", "unknown") or "unknown")]
                ),
                recovered_lineage=recovered_lineage,
                resolution_policy=resolution_policy,
            )
            if class_doc
            else {
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            }
        )
        rows.append(
            {
                "class_id": class_qid,
                "class_filename": class_filename_lookup.get(class_qid, ""),
                "path_to_core_class": str(resolution.get("path_to_core_class", "") or ""),
                "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
                "is_core_class": bool(class_qid in core_class_qids),
                "is_root_class": bool(class_qid in root_class_qids),
                "parent_count": int(len(parent_qids)),
                "parent_qids": "|".join(parent_qids),
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows)[columns].sort_values(["is_core_class", "subclass_of_core_class", "class_id"], ascending=[False, False, True]).reset_index(drop=True)


def _resolve_row_core_class_id(row: pd.Series, core_class_qids: set[str]) -> str:
    path = str(row.get("path_to_core_class", "") or "")
    if path:
        tokens = [canonical_qid(token) for token in path.split("|") if canonical_qid(token)]
        for token in reversed(tokens):
            if token in core_class_qids:
                return token
    class_id = canonical_qid(str(row.get("class_id", "") or ""))
    if class_id in core_class_qids and bool(row.get("subclass_of_core_class", False)):
        return class_id
    return ""


def _remove_stale_core_instance_projections(paths, active_projection_files: set[str]) -> None:
    for projection_path in paths.projections_dir.glob("instances_core_*.csv"):
        is_active = projection_path.name in active_projection_files
        if not is_active and projection_path.is_file():
            projection_path.unlink()
        projection_parquet = projection_path.with_suffix(".parquet")
        if not is_active and projection_parquet.is_file():
            projection_parquet.unlink()
        if projection_path.name.startswith("instances_core_") and projection_path.name.endswith(".csv"):
            class_filename = projection_path.name[len("instances_core_") : -len(".csv")]
            legacy_json_path = paths.projections_dir / core_instances_json_filename(class_filename)
            if not is_active and legacy_json_path.is_file():
                legacy_json_path.unlink()


def _write_tabular_artifact(csv_path: Path, df: pd.DataFrame) -> None:
    _atomic_write_df(csv_path, df)
    _atomic_write_parquet_df(csv_path.with_suffix(".parquet"), df)


_WIKIDATA_ENTITY_KEY_ORDER = (
    "_fetched_literal_languages",
    "type",
    "id",
    "labels",
    "descriptions",
    "aliases",
    "claims",
)


def _order_entity_doc_keys(entity_doc: dict) -> dict:
    if not isinstance(entity_doc, dict):
        return {}

    ordered: dict = {}
    for key in _WIKIDATA_ENTITY_KEY_ORDER:
        if key in entity_doc:
            ordered[key] = entity_doc[key]

    for key, value in entity_doc.items():
        if key not in ordered:
            ordered[key] = value

    return ordered


def _write_json_object_artifact(json_path: Path, payload: dict) -> None:
    if not isinstance(payload, dict):
        payload = {}

    ordered_payload = {
        str(qid): _order_entity_doc_keys(entity_doc) if isinstance(entity_doc, dict) else entity_doc
        for qid, entity_doc in sorted(payload.items(), key=lambda item: str(item[0]))
    }
    _atomic_write_text(json_path, json.dumps(ordered_payload, ensure_ascii=False, indent=2))


def _resolve_chunk_max_bytes() -> int:
    default_bytes = 50 * 1024 * 1024
    raw_value = str(os.getenv("WIKIDATA_ENTITY_CHUNK_MAX_BYTES", str(default_bytes))).strip()
    try:
        value = int(raw_value)
    except Exception:
        return default_bytes
    return max(1024, value)


def _build_graph_edges_lookup(triples_df: pd.DataFrame) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    outgoing: dict[str, list[dict]] = {}
    incoming: dict[str, list[dict]] = {}
    if triples_df.empty:
        return outgoing, incoming

    for row in triples_df.to_dict(orient="records"):
        subject = canonical_qid(str(row.get("subject", "") or ""))
        predicate = str(row.get("predicate", "") or "")
        obj = canonical_qid(str(row.get("object", "") or ""))
        discovered_at_utc = str(row.get("discovered_at_utc", "") or "")
        source_query_file = str(row.get("source_query_file", "") or "")
        if not subject or not obj or not predicate:
            continue

        outgoing.setdefault(subject, []).append(
            {
                "pid": predicate,
                "to_qid": obj,
                "discovered_at_utc": discovered_at_utc,
                "source_query_file": source_query_file,
            }
        )
        incoming.setdefault(obj, []).append(
            {
                "from_qid": subject,
                "pid": predicate,
                "discovered_at_utc": discovered_at_utc,
                "source_query_file": source_query_file,
            }
        )

    for qid in outgoing:
        outgoing[qid] = sorted(
            outgoing[qid],
            key=lambda edge: (
                str(edge.get("pid", "")),
                str(edge.get("to_qid", "")),
                str(edge.get("discovered_at_utc", "")),
                str(edge.get("source_query_file", "")),
            ),
        )
    for qid in incoming:
        incoming[qid] = sorted(
            incoming[qid],
            key=lambda edge: (
                str(edge.get("from_qid", "")),
                str(edge.get("pid", "")),
                str(edge.get("discovered_at_utc", "")),
                str(edge.get("source_query_file", "")),
            ),
        )
    return outgoing, incoming


def _build_entity_lookup_rows(
    repo_root: Path,
    core_class_qids: set[str],
    triples_df: pd.DataFrame,
    *,
    recovered_lineage: RecoveredLineageEvidence | None,
    resolution_policy: str,
    resolution_reasons: Counter,
) -> tuple[list[dict], list[dict]]:
    items = list(iter_items(repo_root))
    item_by_id = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in items
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_docs = _latest_entity_cache_docs(repo_root)
    outgoing_lookup, incoming_lookup = _build_graph_edges_lookup(triples_df)

    def _get_entity(qid: str) -> dict | None:
        qid_norm = canonical_qid(qid)
        if not qid_norm:
            return None
        node = item_by_id.get(qid_norm)
        if node:
            return node
        cached = latest_entity_docs.get(qid_norm)
        return cached if isinstance(cached, dict) else None

    records: list[dict] = []
    for item in items:
        qid = canonical_qid(str(item.get("id", "") or ""))
        if not qid:
            continue
        claims = item.get("claims", {}) if isinstance(item.get("claims"), dict) else {}
        resolution = resolve_class_path(
            item,
            core_class_qids,
            _get_entity,
            on_resolved=lambda payload: resolution_reasons.update(
                [str(payload.get("resolution_reason", "unknown") or "unknown")]
            ),
            recovered_lineage=recovered_lineage,
            resolution_policy=resolution_policy,
        )
        direct_p31 = _extract_claim_qids(claims, "P31")
        direct_p279 = _extract_claim_qids(claims, "P279")
        path_to_core_class = str(resolution.get("path_to_core_class", "") or "")
        resolved_core_class_id = ""
        if path_to_core_class:
            tokens = [canonical_qid(token) for token in path_to_core_class.split("|") if canonical_qid(token)]
            for token in reversed(tokens):
                if token in core_class_qids:
                    resolved_core_class_id = token
                    break
        record = {
            "qid": qid,
            "labels": item.get("labels", {}) if isinstance(item.get("labels"), dict) else {},
            "descriptions": item.get("descriptions", {}) if isinstance(item.get("descriptions"), dict) else {},
            "aliases": item.get("aliases", {}) if isinstance(item.get("aliases"), dict) else {},
            "class_info": {
                "direct_p31": direct_p31,
                "direct_p279": direct_p279,
                "resolved_core_class_id": resolved_core_class_id,
                "path_to_core_class": path_to_core_class,
                "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
                "is_class_node": bool(len(direct_p279) > 0),
            },
            "graph_edges": {
                "outgoing": outgoing_lookup.get(qid, []),
                "incoming": incoming_lookup.get(qid, []),
            },
            "graph_summary": {
                "outgoing_count": int(len(outgoing_lookup.get(qid, []))),
                "incoming_count": int(len(incoming_lookup.get(qid, []))),
            },
            "provenance_summary": {
                "discovered_at_utc": str(item.get("discovered_at_utc", "") or ""),
                "expanded_at_utc": str(item.get("expanded_at_utc", "") or ""),
                "discovered_at_utc_history": sorted({str(ts) for ts in (item.get("discovered_at_utc_history", []) or []) if str(ts)}),
                "expanded_at_utc_history": sorted({str(ts) for ts in (item.get("expanded_at_utc_history", []) or []) if str(ts)}),
            },
            "eligibility_summary": {
                "has_direct_seed_link": False,
                "direct_or_subclass_core_match": bool(resolution.get("subclass_of_core_class", False)),
                "is_expandable_target": bool(
                    resolution.get("subclass_of_core_class", False) and not len(direct_p279)
                ),
            },
            "entity": item,
        }
        records.append(record)

    records = sorted(records, key=lambda rec: str(rec.get("qid", "")))
    index_rows: list[dict] = []
    chunk_records: list[dict] = []
    for rec in records:
        qid = str(rec.get("qid", ""))
        if not qid:
            continue
        index_rows.append(
            {
                "qid": qid,
                "resolved_core_class_id": str(rec.get("class_info", {}).get("resolved_core_class_id", "") or ""),
                "subclass_of_core_class": bool(rec.get("class_info", {}).get("subclass_of_core_class", False)),
                "discovered_at_utc": str(rec.get("provenance_summary", {}).get("discovered_at_utc", "") or ""),
                "expanded_at_utc": str(rec.get("provenance_summary", {}).get("expanded_at_utc", "") or ""),
            }
        )
        chunk_records.append(rec)
    return index_rows, chunk_records


def _write_entity_lookup_artifacts(
    repo_root: Path,
    paths,
    core_class_qids: set[str],
    triples_df: pd.DataFrame,
    *,
    recovered_lineage: RecoveredLineageEvidence | None,
    resolution_policy: str,
    resolution_reasons: Counter,
) -> int:
    _, chunk_records = _build_entity_lookup_rows(
        repo_root,
        core_class_qids,
        triples_df,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
    )
    max_bytes = _resolve_chunk_max_bytes()
    paths.entity_chunks_dir.mkdir(parents=True, exist_ok=True)

    for old_chunk in sorted(paths.entity_chunks_dir.glob("*.jsonl")):
        if old_chunk.is_file():
            old_chunk.unlink()

    lookup_rows: list[dict] = []
    part = 1
    current_file = f"entities_{part:04d}.jsonl"
    current_lines: list[str] = []
    current_size = 0
    current_offset = 0
    pending_rows: list[dict] = []

    def _flush_current() -> None:
        nonlocal current_file, current_lines, current_size, current_offset, pending_rows
        if not current_lines:
            return
        chunk_path = paths.entity_chunks_dir / current_file
        text = "".join(current_lines)
        _atomic_write_text(chunk_path, text)
        lookup_rows.extend(pending_rows)
        current_lines = []
        current_size = 0
        current_offset = 0
        pending_rows = []

    for rec in chunk_records:
        qid = str(rec.get("qid", ""))
        if not qid:
            continue
        line = json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n"
        line_size = len(line.encode("utf-8"))
        if current_lines and current_size + line_size > max_bytes:
            _flush_current()
            part += 1
            current_file = f"entities_{part:04d}.jsonl"

        pending_rows.append(
            {
                "qid": qid,
                "chunk_file": current_file,
                "record_key": f"{current_offset}:{line_size}",
                "resolved_core_class_id": str(rec.get("class_info", {}).get("resolved_core_class_id", "") or ""),
                "subclass_of_core_class": bool(rec.get("class_info", {}).get("subclass_of_core_class", False)),
                "discovered_at_utc": str(rec.get("provenance_summary", {}).get("discovered_at_utc", "") or ""),
                "expanded_at_utc": str(rec.get("provenance_summary", {}).get("expanded_at_utc", "") or ""),
                "byte_offset": current_offset,
                "byte_length": line_size,
            }
        )
        current_lines.append(line)
        current_size += line_size
        current_offset += line_size
    _flush_current()

    index_df = pd.DataFrame(lookup_rows)
    if index_df.empty:
        index_df = pd.DataFrame(
            columns=[
                "qid",
                "chunk_file",
                "record_key",
                "resolved_core_class_id",
                "subclass_of_core_class",
                "discovered_at_utc",
                "expanded_at_utc",
                "byte_offset",
                "byte_length",
            ]
        )
    else:
        index_df = index_df.sort_values("qid").reset_index(drop=True)
    _write_tabular_artifact(paths.entity_lookup_index_csv, index_df)
    return int(len(index_df))


def _write_core_instance_projections(paths, instances_df: pd.DataFrame, class_hierarchy_df: pd.DataFrame, repo_root: Path, core_class_qids: set[str]) -> dict[str, int]:
    projection_row_counts: dict[str, int] = {}
    if instances_df.empty:
        _write_tabular_artifact(paths.instances_leftovers_csv, instances_df)
        _remove_stale_core_instance_projections(paths, set())
        return projection_row_counts

    class_node_ids: set[str] = set()
    if not class_hierarchy_df.empty and "class_id" in class_hierarchy_df.columns:
        class_node_ids = {
            canonical_qid(class_id)
            for class_id in class_hierarchy_df["class_id"].tolist()
            if canonical_qid(class_id)
        }

    non_class_instances_df = instances_df[~instances_df["id"].isin(class_node_ids)].copy()
    if non_class_instances_df.empty:
        _write_tabular_artifact(paths.instances_leftovers_csv, non_class_instances_df)
        _remove_stale_core_instance_projections(paths, set())
        return projection_row_counts

    non_class_instances_df = _apply_core_output_boundary_filter(repo_root, non_class_instances_df)
    if non_class_instances_df.empty:
        _write_tabular_artifact(paths.instances_leftovers_csv, non_class_instances_df)
        _remove_stale_core_instance_projections(paths, set())
        return projection_row_counts

    non_class_instances_df["resolved_core_class_id"] = non_class_instances_df.apply(
        lambda row: _resolve_row_core_class_id(row, core_class_qids), axis=1
    )

    entity_by_qid = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in iter_items(repo_root)
        if canonical_qid(str(item.get("id", "") or ""))
    }
    latest_entity_docs = _latest_entity_cache_docs(repo_root)

    def _claim_statement_count(entity_doc: dict) -> int:
        claims = entity_doc.get("claims", {}) if isinstance(entity_doc, dict) else {}
        if not isinstance(claims, dict):
            return 0
        return int(sum(len(v) for v in claims.values() if isinstance(v, list)))

    for qid, latest_doc in latest_entity_docs.items():
        existing_doc = entity_by_qid.get(qid)
        if not isinstance(existing_doc, dict):
            entity_by_qid[qid] = latest_doc
            continue
        if _claim_statement_count(latest_doc) >= _claim_statement_count(existing_doc):
            entity_by_qid[qid] = latest_doc

    core_rows = load_core_classes(repo_root)
    active_projection_files: set[str] = set()
    for row in core_rows:
        class_filename = str(row.get("filename", "") or "")
        core_qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        if not class_filename or not core_qid:
            continue
        projection_name = core_instances_projection_filename(class_filename)
        projection_path = paths.projections_dir / projection_name
        json_path = paths.projections_dir / core_instances_json_filename(class_filename)
        active_projection_files.add(projection_name)
        core_projection_df = non_class_instances_df[non_class_instances_df["resolved_core_class_id"] == core_qid].copy()
        if "resolved_core_class_id" in core_projection_df.columns:
            core_projection_df = core_projection_df.drop(columns=["resolved_core_class_id"])
        core_projection_df = core_projection_df.sort_values("id").reset_index(drop=True)
        _write_tabular_artifact(projection_path, core_projection_df)
        core_json_payload = {
            qid: entity_by_qid[qid]
            for qid in core_projection_df["id"].tolist()
            if qid in entity_by_qid
        }
        _write_json_object_artifact(json_path, core_json_payload)
        projection_row_counts[projection_name] = int(len(core_projection_df))

    leftovers_df = non_class_instances_df[non_class_instances_df["resolved_core_class_id"] == ""].copy()
    if "resolved_core_class_id" in leftovers_df.columns:
        leftovers_df = leftovers_df.drop(columns=["resolved_core_class_id"])
    leftovers_df = leftovers_df.sort_values("id").reset_index(drop=True)
    _write_tabular_artifact(paths.instances_leftovers_csv, leftovers_df)
    projection_row_counts[paths.instances_leftovers_csv.name] = int(len(leftovers_df))

    _remove_stale_core_instance_projections(paths, active_projection_files)
    return projection_row_counts


def _apply_core_output_boundary_filter(repo_root: Path, instances_df: pd.DataFrame) -> pd.DataFrame:
    if instances_df.empty:
        return instances_df

    seeds, _skipped = load_seed_instances(repo_root)
    seed_qids = {
        canonical_qid(str(seed.get("wikidata_id", "") or ""))
        for seed in seeds
        if canonical_qid(str(seed.get("wikidata_id", "") or ""))
    }
    if not seed_qids:
        return instances_df

    adjacency: dict[str, set[str]] = {}
    for triple in iter_unique_triples(repo_root):
        subject = canonical_qid(str(triple.get("subject", "") or ""))
        obj = canonical_qid(str(triple.get("object", "") or ""))
        if not subject or not obj:
            continue
        adjacency.setdefault(subject, set()).add(obj)
        adjacency.setdefault(obj, set()).add(subject)

    if not adjacency:
        return instances_df

    first_hop: set[str] = set()
    for seed_qid in seed_qids:
        first_hop.update(adjacency.get(seed_qid, set()))

    second_hop: set[str] = set()
    for hop_qid in first_hop:
        second_hop.update(adjacency.get(hop_qid, set()))

    # Include seeds for stable downstream behavior while enforcing the two-hop contract.
    allowed = seed_qids | first_hop | second_hop
    if not allowed:
        return instances_df

    filtered = instances_df[instances_df["id"].isin(allowed)].copy()
    return filtered.sort_values("id").reset_index(drop=True)


def _write_summary(paths, run_id: str, stage: str, stats: dict) -> None:
    summary = {
        "run_id": run_id,
        "stage": stage,
        **stats,
    }
    _atomic_write_text(paths.summary_json, json.dumps(summary, ensure_ascii=False, indent=2))


def _materialize(repo_root: Path, *, run_id: str, stage: str, seed_id: str | None) -> dict:
    total_t0 = perf_counter()
    print(f"[materializer] Start stage={stage} run_id={run_id}", flush=True)
    flush_node_store(repo_root)
    flush_triple_events(repo_root)
    paths = build_artifact_paths(Path(repo_root))
    core_class_qids = _core_class_qids(repo_root)
    root_class_qids = _root_class_qids(repo_root)
    recovered_lineage, recovered_lineage_source = _load_recovered_lineage_evidence(repo_root, paths)
    resolution_policy = _lineage_resolution_policy()
    resolution_reasons: Counter = Counter()

    t0 = perf_counter()
    instances_df = _build_instances_df(
        repo_root,
        core_class_qids,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
    )
    print(f"[materializer] build instances done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    classes_df = _build_classes_df(repo_root, instances_df)
    print(f"[materializer] build classes done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    properties_df = _build_properties_df(repo_root)
    print(f"[materializer] build properties done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    alias_dfs: dict[str, pd.DataFrame] = {}
    for lang in projection_languages():
        alias_dfs[lang] = _build_alias_df(instances_df, lang)
    print(f"[materializer] build aliases done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    triples_df = _build_triples_df(repo_root)
    print(f"[materializer] build triples done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    class_hierarchy_df = _build_class_hierarchy_df(
        repo_root,
        core_class_qids,
        root_class_qids,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
    )
    print(f"[materializer] build class_hierarchy done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    query_inventory_df = materialize_query_inventory(repo_root)
    print(f"[materializer] build query_inventory done in {perf_counter() - t0:.2f}s", flush=True)

    t0 = perf_counter()
    active_alias_files: set[str] = set()
    for lang, alias_df in alias_dfs.items():
        suffix = language_projection_suffix(lang)
        alias_filename = f"aliases_{suffix}.csv"
        alias_path = paths.projections_dir / alias_filename
        _write_tabular_artifact(alias_path, alias_df)
        active_alias_files.add(alias_filename)
    _remove_stale_alias_projections(paths, active_alias_files)
    _write_tabular_artifact(paths.triples_csv, triples_df)
    _write_tabular_artifact(paths.class_hierarchy_csv, class_hierarchy_df)
    _write_tabular_artifact(paths.query_inventory_csv, query_inventory_df)
    _write_tabular_artifact(paths.instances_csv, instances_df)
    _write_tabular_artifact(paths.classes_csv, classes_df)
    _write_tabular_artifact(paths.properties_csv, properties_df)
    entity_lookup_rows = _write_entity_lookup_artifacts(
        repo_root,
        paths,
        core_class_qids,
        triples_df,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
    )
    core_projection_counts = _write_core_instance_projections(
        paths,
        instances_df,
        class_hierarchy_df,
        repo_root,
        core_class_qids,
    )
    print(f"[materializer] write tabular artifacts done in {perf_counter() - t0:.2f}s", flush=True)

    stats = {
        "seed_id": seed_id,
        "instances_rows": int(len(instances_df)),
        "classes_rows": int(len(classes_df)),
        "properties_rows": int(len(properties_df)),
        "triples_rows": int(len(triples_df)),
        "query_inventory_rows": int(len(query_inventory_df)),
        "entity_lookup_rows": int(entity_lookup_rows),
        "core_instance_projection_files": int(len(core_projection_counts)),
        "instances_leftovers_rows": int(core_projection_counts.get(paths.instances_leftovers_csv.name, 0)),
        "lineage_resolution_policy": resolution_policy,
        "lineage_recovered_source": recovered_lineage_source,
        "lineage_resolution_reason_counts": dict(sorted(resolution_reasons.items())),
    }
    _write_summary(paths, run_id, stage, stats)
    elapsed = perf_counter() - total_t0
    print(f"[materializer] Completed stage={stage} in {elapsed:.2f}s", flush=True)
    if elapsed > 20.0:
        print(
            f"[materializer][warning] Stage {stage} exceeded 20s target ({elapsed:.2f}s)",
            flush=True,
        )
    return stats


def materialize_checkpoint(repo_root: Path, *, run_id: str, checkpoint_ts: str, seed_id: str | None) -> dict:
    return _materialize(repo_root, run_id=run_id, stage=f"checkpoint:{checkpoint_ts}", seed_id=seed_id)


def materialize_final(repo_root: Path, *, run_id: str) -> dict:
    return _materialize(repo_root, run_id=run_id, stage="final", seed_id=None)
