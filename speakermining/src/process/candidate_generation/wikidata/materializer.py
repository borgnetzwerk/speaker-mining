from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime, timezone
from collections import deque
from dataclasses import dataclass
from urllib.parse import quote
from pathlib import Path
from time import perf_counter
from collections import Counter

import pandas as pd

from process.notebook_event_log import NOTEBOOK_21_ID, get_or_create_notebook_logger
from .cache import (
    WIKIDATA_SPARQL_ENDPOINT,
    _atomic_write_df,
    _atomic_write_parquet_df,
    _atomic_write_text,
    _entity_from_payload,
    _http_get_json,
    _latest_cached_record,
    begin_request_context,
    end_request_context,
    get_request_context_network_queries,
)
from .bootstrap import load_core_classes, load_other_interesting_classes, load_root_classes
from .bootstrap import load_seed_instances
from .class_resolver import (
    RewiringCatalogue,
    apply_rewiring_to_claim_qids,
    RecoveredLineageEvidence,
    compute_class_rollups,
    load_rewiring_catalogue,
    load_recovered_class_hierarchy,
    resolve_class_path,
)
from .common import (
    DEFAULT_WIKIDATA_FALLBACK_LANGUAGE,
    canonical_pid,
    canonical_qid,
    effective_core_class_qids,
    language_projection_suffix,
    parquet_sidecars_enabled,
    projection_languages,
)
from .event_log import get_query_event_field, get_query_event_response_data, iter_query_events, write_query_event
from .node_store import (
    activate_core_subclass,
    flush_node_store,
    iter_items,
    iter_properties,
    mark_inactive_core_subclass,
)
from .inlinks import build_subclass_inlinks_query, parse_subclass_inlinks_results
from .entity import get_or_fetch_entities_batch, get_or_fetch_entity
from .schemas import build_artifact_paths
from .schemas import core_instances_json_filename
from .triple_store import flush_triple_events, iter_unique_triples
from .graceful_shutdown import should_terminate


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
    "class_resolution_map_csv",
    "query_inventory_csv",
    "entity_lookup_index_csv",
    "instances_leftovers_csv",
    "fallback_stage_candidates_csv",
    "fallback_stage_eligible_for_expansion_csv",
    "fallback_stage_ineligible_csv",
)


def _subclass_expansion_max_depth() -> int:
    raw = str(os.getenv("WIKIDATA_SUBCLASS_EXPANSION_MAX_DEPTH", "2") or "2").strip()
    try:
        value = int(raw)
    except Exception:
        value = 2
    return max(0, value)


def _shutdown_path(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / ".shutdown"


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


def _claim_property_profile(claims: dict) -> dict[str, str]:
    if not isinstance(claims, dict):
        claims = {}

    property_counts: dict[str, int] = {}
    total_statements = 0
    for pid, statements in claims.items():
        if not isinstance(statements, list):
            continue
        property_counts[str(pid)] = len(statements)
        total_statements += len(statements)

    property_ids = sorted(property_counts.keys())
    return {
        "wikidata_claim_properties": "|".join(property_ids),
        "wikidata_claim_property_count": str(len(property_ids)),
        "wikidata_claim_statement_count": str(total_statements),
        "wikidata_property_counts_json": json.dumps(property_counts, ensure_ascii=False, sort_keys=True),
        "wikidata_p31_qids": "|".join(_extract_claim_qids(claims, "P31")),
        "wikidata_p279_qids": "|".join(_extract_claim_qids(claims, "P279")),
        "wikidata_p179_qids": "|".join(_extract_claim_qids(claims, "P179")),
        "wikidata_p106_qids": "|".join(_extract_claim_qids(claims, "P106")),
        "wikidata_p39_qids": "|".join(_extract_claim_qids(claims, "P39")),
        "wikidata_p921_qids": "|".join(_extract_claim_qids(claims, "P921")),
        "wikidata_p527_qids": "|".join(_extract_claim_qids(claims, "P527")),
        "wikidata_p361_qids": "|".join(_extract_claim_qids(claims, "P361")),
    }


def _class_filename_lookup(repo_root: Path) -> dict[str, str]:
    lookup: dict[str, str] = {}
    setup_rows = load_core_classes(repo_root) + load_root_classes(repo_root) + load_other_interesting_classes(repo_root)
    for row in setup_rows:
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        filename = str(row.get("filename", "") or "")
        if qid and filename:
            lookup[qid] = filename
    return lookup


def _core_precedence_lookup(repo_root: Path) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for idx, row in enumerate(load_core_classes(repo_root)):
        qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        if qid and qid not in lookup:
            lookup[qid] = idx
    return lookup


def _load_rewiring_catalogue(repo_root: Path) -> RewiringCatalogue | None:
    rewiring_path = (
        Path(repo_root)
        / "data"
        / "00_setup"
        / "rewiring_catalogue.csv"
    )
    catalogue = load_rewiring_catalogue(rewiring_path)
    if int(catalogue.diagnostics.get("loaded_rows", 0)) <= 0:
        return None
    return catalogue


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
    rewiring_catalogue: RewiringCatalogue | None,
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
            rewiring_catalogue=rewiring_catalogue,
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
            **_claim_property_profile(claims),
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
    rewiring_catalogue: RewiringCatalogue | None,
) -> pd.DataFrame:
    columns = [
        "class_id",
        "class_filename",
        "path_to_core_class",
        "distance_to_core_min",
        "superclass_explored_depth_max",
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
        p279 = apply_rewiring_to_claim_qids(
            subject_qid=qid,
            predicate="P279",
            base_qids=_extract_claim_qids(claims, "P279"),
            rewiring_catalogue=rewiring_catalogue,
        )
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
                rewiring_catalogue=rewiring_catalogue,
            )
            if class_doc
            else {
            "path_to_core_class": "",
            "subclass_of_core_class": False,
            }
        )
        path_to_core_class = str(resolution.get("path_to_core_class", "") or "")
        path_tokens = [canonical_qid(token) for token in path_to_core_class.split("|") if canonical_qid(token)]
        base_distance = int(len(path_tokens) - 1) if path_tokens else pd.NA
        if path_tokens and path_tokens[0] != class_qid:
            base_distance = int(base_distance) + 1
        distance_to_core_min = base_distance
        superclass_explored_depth_max = int(base_distance) if not pd.isna(base_distance) else 0

        rows.append(
            {
                "class_id": class_qid,
                "class_filename": class_filename_lookup.get(class_qid, ""),
                "path_to_core_class": path_to_core_class,
                "distance_to_core_min": distance_to_core_min,
                "superclass_explored_depth_max": superclass_explored_depth_max,
                "subclass_of_core_class": bool(resolution.get("subclass_of_core_class", False)),
                "is_core_class": bool(class_qid in core_class_qids),
                "is_root_class": bool(class_qid in root_class_qids),
                "parent_count": int(len(parent_qids)),
                "parent_qids": "|".join(parent_qids),
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)[columns]
    df["distance_to_core_min"] = pd.to_numeric(df["distance_to_core_min"], errors="coerce").astype("Int64")
    df["superclass_explored_depth_max"] = pd.to_numeric(
        df["superclass_explored_depth_max"], errors="coerce"
    ).fillna(0).astype("Int64")
    return df.sort_values(["is_core_class", "subclass_of_core_class", "class_id"], ascending=[False, False, True]).reset_index(drop=True)


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


def _build_class_resolution_map_df(
    repo_root: Path,
    class_hierarchy_df: pd.DataFrame,
    core_class_qids: set[str],
    rewiring_catalogue: RewiringCatalogue | None,
    max_depth: int,
) -> pd.DataFrame:
    columns = [
        "class_id",
        "resolved_core_class_id",
        "resolution_depth",
        "resolution_reason",
        "conflict_flag",
        "candidate_core_class_ids",
        "candidate_paths_json",
        "max_depth",
    ]
    if class_hierarchy_df.empty:
        return pd.DataFrame(columns=columns)

    core_precedence = _core_precedence_lookup(repo_root)
    item_by_qid = {
        canonical_qid(str(item.get("id", "") or "")): item
        for item in iter_items(repo_root)
        if canonical_qid(str(item.get("id", "") or ""))
    }

    def _parents_for(qid: str) -> list[str]:
        item = item_by_qid.get(qid, {})
        claims = item.get("claims", {}) if isinstance(item, dict) else {}
        base = _extract_claim_qids(claims, "P279")
        return apply_rewiring_to_claim_qids(
            subject_qid=qid,
            predicate="P279",
            base_qids=base,
            rewiring_catalogue=rewiring_catalogue,
        )

    rows: list[dict] = []
    class_ids = [canonical_qid(x) for x in class_hierarchy_df.get("class_id", pd.Series(dtype=str)).tolist()]
    class_ids = [x for x in class_ids if x]

    for class_id in sorted(set(class_ids)):
        queue: deque[tuple[str, int, list[str]]] = deque([(class_id, 0, [class_id])])
        seen_depth: dict[str, int] = {class_id: 0}
        candidates: list[tuple[str, int, list[str]]] = []

        while queue:
            node, depth, path = queue.popleft()
            if node in core_class_qids:
                candidates.append((node, depth, path))
                continue
            if depth >= max_depth:
                continue
            for parent in _parents_for(node):
                next_depth = depth + 1
                prev = seen_depth.get(parent)
                if prev is not None and prev <= next_depth:
                    continue
                seen_depth[parent] = next_depth
                queue.append((parent, next_depth, path + [parent]))

        candidates = sorted(
            candidates,
            key=lambda c: (
                c[1],
                core_precedence.get(c[0], 10_000),
                c[0],
            ),
        )

        if candidates:
            best_core, best_depth, _best_path = candidates[0]
            conflict = len({c[0] for c in candidates}) > 1
            candidate_paths_json = json.dumps(
                [
                    {
                        "core_class_id": core,
                        "depth": depth,
                        "path": path,
                    }
                    for core, depth, path in candidates
                ],
                ensure_ascii=False,
                sort_keys=True,
            )
            rows.append(
                {
                    "class_id": class_id,
                    "resolved_core_class_id": best_core,
                    "resolution_depth": int(best_depth),
                    "resolution_reason": (
                        "deterministic_conflict_resolution" if conflict else "unique_candidate"
                    ),
                    "conflict_flag": bool(conflict),
                    "candidate_core_class_ids": "|".join(sorted({c[0] for c in candidates})),
                    "candidate_paths_json": candidate_paths_json,
                    "max_depth": int(max_depth),
                }
            )
        else:
            rows.append(
                {
                    "class_id": class_id,
                    "resolved_core_class_id": "",
                    "resolution_depth": pd.NA,
                    "resolution_reason": "no_core_match_within_max_depth",
                    "conflict_flag": False,
                    "candidate_core_class_ids": "",
                    "candidate_paths_json": "[]",
                    "max_depth": int(max_depth),
                }
            )

    df = pd.DataFrame(rows, columns=columns).sort_values("class_id").reset_index(drop=True)
    # Keep numeric columns in deterministic nullable integer dtypes for CSV and parquet parity.
    if not df.empty:
        df["resolution_depth"] = pd.to_numeric(df["resolution_depth"], errors="coerce").astype("Int64")
        df["max_depth"] = pd.to_numeric(df["max_depth"], errors="coerce").astype("Int64")
    return df


def _remove_stale_core_instance_projections(paths, active_json_files: set[str]) -> None:
    # Remove legacy tabular sidecars for deprecated core-instance projections.
    for legacy_csv_path in paths.projections_dir.glob("instances_core_*.csv"):
        if legacy_csv_path.is_file():
            legacy_csv_path.unlink()
        legacy_parquet_path = legacy_csv_path.with_suffix(".parquet")
        legacy_parquet_path.unlink(missing_ok=True)

    for json_path in paths.projections_dir.glob("instances_core_*.json"):
        if json_path.name not in active_json_files and json_path.is_file():
            json_path.unlink()

    # Remove deprecated duplicate top-level class JSON outputs
    # (e.g. persons.json, episodes.json) in favor of instances_core_*.json.
    for active_name in active_json_files:
        if not active_name.startswith("instances_core_") or not active_name.endswith(".json"):
            continue
        class_filename = active_name[len("instances_core_") : -len(".json")]
        legacy_core_json_path = paths.projections_dir / f"{class_filename}.json"
        if legacy_core_json_path.is_file():
            legacy_core_json_path.unlink()


def _write_tabular_artifact(csv_path: Path, df: pd.DataFrame) -> None:
    _atomic_write_df(csv_path, df)
    parquet_path = csv_path.with_suffix(".parquet")
    if parquet_sidecars_enabled():
        _atomic_write_parquet_df(parquet_path, df)
    else:
        parquet_path.unlink(missing_ok=True)


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
    rewiring_catalogue: RewiringCatalogue | None,
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
            rewiring_catalogue=rewiring_catalogue,
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
    rewiring_catalogue: RewiringCatalogue | None,
) -> int:
    _, chunk_records = _build_entity_lookup_rows(
        repo_root,
        core_class_qids,
        triples_df,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
        rewiring_catalogue=rewiring_catalogue,
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


def _write_core_instance_projections(
    paths,
    instances_df: pd.DataFrame,
    class_hierarchy_df: pd.DataFrame,
    repo_root: Path,
    core_class_qids: set[str],
    rewiring_catalogue: RewiringCatalogue | None,
    class_resolution_map_df: pd.DataFrame | None,
) -> dict[str, int]:
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

    resolution_lookup: dict[str, str] = {}
    if class_resolution_map_df is not None and not class_resolution_map_df.empty:
        for _, r in class_resolution_map_df.iterrows():
            class_id = canonical_qid(str(r.get("class_id", "") or ""))
            core_id = canonical_qid(str(r.get("resolved_core_class_id", "") or ""))
            if class_id and core_id:
                resolution_lookup[class_id] = core_id

    if resolution_lookup:
        non_class_instances_df["resolved_core_class_id"] = non_class_instances_df["class_id"].map(
            lambda q: resolution_lookup.get(canonical_qid(str(q or "")), "")
        )
        fallback_mask = non_class_instances_df["resolved_core_class_id"] == ""
        if bool(fallback_mask.any()):
            non_class_instances_df.loc[fallback_mask, "resolved_core_class_id"] = non_class_instances_df.loc[
                fallback_mask
            ].apply(lambda row: _resolve_row_core_class_id(row, core_class_qids), axis=1)
    else:
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
    include_map: dict[str, set[str]] = {}
    exclude_map: dict[str, set[str]] = {}
    if rewiring_catalogue is not None:
        for (subject, predicate), objects in rewiring_catalogue.add_edges.items():
            if predicate != "P279":
                continue
            for obj in objects:
                include_map.setdefault(obj, set()).add(subject)
        for (subject, predicate), objects in rewiring_catalogue.remove_edges.items():
            if predicate != "P279":
                continue
            for obj in objects:
                exclude_map.setdefault(obj, set()).add(subject)

    active_json_files: set[str] = set()
    for row in core_rows:
        class_filename = str(row.get("filename", "") or "")
        core_qid = canonical_qid(str(row.get("wikidata_id", "") or ""))
        if not class_filename or not core_qid:
            continue
        json_path = paths.projections_dir / core_instances_json_filename(class_filename)
        active_json_files.add(json_path.name)
        include_class_ids = include_map.get(core_qid, set())
        exclude_class_ids = exclude_map.get(core_qid, set())

        mask_resolved = non_class_instances_df["resolved_core_class_id"] == core_qid
        mask_rewired = non_class_instances_df["class_id"].isin(include_class_ids)
        core_projection_df = non_class_instances_df[mask_resolved | mask_rewired].copy()
        if exclude_class_ids:
            core_projection_df = core_projection_df[~core_projection_df["class_id"].isin(exclude_class_ids)].copy()
        if "resolved_core_class_id" in core_projection_df.columns:
            core_projection_df = core_projection_df.drop(columns=["resolved_core_class_id"])
        core_projection_df = core_projection_df.sort_values("id").reset_index(drop=True)
        core_json_payload = {
            qid: entity_by_qid[qid]
            for qid in core_projection_df["id"].tolist()
            if qid in entity_by_qid
        }
        _write_json_object_artifact(json_path, core_json_payload)
        projection_row_counts[json_path.name] = int(len(core_projection_df))

    leftovers_df = non_class_instances_df[non_class_instances_df["resolved_core_class_id"] == ""].copy()
    if "resolved_core_class_id" in leftovers_df.columns:
        leftovers_df = leftovers_df.drop(columns=["resolved_core_class_id"])
    leftovers_df = leftovers_df.sort_values("id").reset_index(drop=True)
    _write_tabular_artifact(paths.instances_leftovers_csv, leftovers_df)
    projection_row_counts[paths.instances_leftovers_csv.name] = int(len(leftovers_df))

    _remove_stale_core_instance_projections(paths, active_json_files)
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
    def _run_profile() -> str:
        raw = str(os.getenv("WIKIDATA_RUN_PROFILE", "operational") or "operational").strip().lower()
        allowed = {"operational", "smoke", "cache_only"}
        return raw if raw in allowed else "operational"

    def _allow_non_operational_overwrite() -> bool:
        raw = str(os.getenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", "0") or "0").strip().lower()
        return raw in {"1", "true", "yes", "y", "on"}

    run_profile = _run_profile()
    write_primary_baseline = run_profile == "operational" or _allow_non_operational_overwrite()
    summary = {
        "run_id": run_id,
        "stage": stage,
        "run_profile": run_profile,
        "summary_primary_updated": bool(write_primary_baseline),
        **stats,
    }

    summary_profiles_dir = paths.projections_dir / "summary_profiles" / run_profile
    summary_profiles_dir.mkdir(parents=True, exist_ok=True)
    ts_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    _atomic_write_text(
        summary_profiles_dir / f"summary_{ts_token}.json",
        json.dumps(summary, ensure_ascii=False, indent=2),
    )
    _atomic_write_text(
        summary_profiles_dir / "summary_latest.json",
        json.dumps(summary, ensure_ascii=False, indent=2),
    )

    if write_primary_baseline:
        _atomic_write_text(paths.summary_json, json.dumps(summary, ensure_ascii=False, indent=2))


def _subclass_inlinks_cache_key(qid: str, limit: int, offset: int) -> str:
    return f"{canonical_qid(qid)}_limit{int(limit)}_offset{int(offset)}"


def _fetch_subclass_inlinks_page(
    repo_root: Path,
    qid: str,
    *,
    limit: int,
    offset: int,
    timeout_seconds: int,
) -> tuple[list[str], bool]:
    qid_norm = canonical_qid(qid)
    if not qid_norm:
        return [], True

    cache_key = _subclass_inlinks_cache_key(qid_norm, limit, offset)
    cached = _latest_cached_record(repo_root, "subclass_inlinks", cache_key)
    if cached:
        return parse_subclass_inlinks_results(get_query_event_response_data(cached[0])), True

    query = build_subclass_inlinks_query(qid_norm, limit=limit, offset=offset)
    url = f"{WIKIDATA_SPARQL_ENDPOINT}?format=json&query={quote(query, safe='')}"
    payload = _http_get_json(url, accept="application/sparql-results+json", timeout=timeout_seconds)
    write_query_event(
        repo_root,
        endpoint="wikidata_sparql",
        normalized_query=f"subclass_inlinks:target={qid_norm};page_size={int(limit)};offset={int(offset)};order=source",
        source_step="subclass_inlinks_fetch",
        status="success",
        key=cache_key,
        payload=payload,
        http_status=200,
        error=None,
    )
    return parse_subclass_inlinks_results(payload), False


def crawl_subclass_expansion(
    repo_root: Path,
    *,
    run_id: str,
    max_depth: int,
    query_budget_remaining: int,
    cache_max_age_days: int,
    query_timeout_seconds: int,
    query_delay_seconds: float,
    progress_every_calls: int,
    progress_every_seconds: float,
    http_max_retries: int,
    http_backoff_base_seconds: float,
    page_limit: int,
    superclass_branch_discovery_max_depth: int = 0,
) -> dict:
    """Crawl subclass frontiers from every core class using direct incoming P279 links.

    The crawl is breadth-first per core class, cache-first per page of subclass results,
    and stops as soon as the configured network budget is exhausted.
    """
    total_t0 = perf_counter()
    paths = build_artifact_paths(Path(repo_root))
    core_rows = load_core_classes(repo_root)
    core_class_qids = [
        canonical_qid(str(row.get("wikidata_id", "") or ""))
        for row in core_rows
    ]
    core_class_qids = [qid for qid in core_class_qids if qid]
    core_precedence = {qid: idx for idx, qid in enumerate(core_class_qids)}
    core_label_by_qid = {
        canonical_qid(str(row.get("wikidata_id", "") or "")): str(row.get("filename", "") or "")
        for row in core_rows
        if canonical_qid(str(row.get("wikidata_id", "") or ""))
    }
    max_depth = max(0, int(max_depth))
    page_limit = max(1, int(page_limit))
    progress_every_calls = max(0, int(progress_every_calls))
    progress_every_seconds = max(0.0, float(progress_every_seconds))
    next_heartbeat_call = progress_every_calls if progress_every_calls > 0 else 0
    budget_label = "unlimited" if int(query_budget_remaining) == -1 else str(int(query_budget_remaining))

    print("[materializer] Start subclass crawl", flush=True)
    print(f"[materializer]   core_classes={len(core_class_qids)} max_depth={max_depth} page_limit={page_limit}", flush=True)

    notebook_logger = get_or_create_notebook_logger(Path(repo_root), NOTEBOOK_21_ID)
    notebook_logger.append_event(
        event_type="subclass_expansion_started",
        phase="subclass_expansion_preflight",
        message="subclass expansion preflight started",
        extra={
            "run_id": str(run_id),
            "max_depth": int(max_depth),
            "page_limit": int(page_limit),
            "superclass_branch_discovery_max_depth": int(superclass_branch_discovery_max_depth),
        },
    )

    begin_request_context(
        budget_remaining=query_budget_remaining,
        query_delay_seconds=float(query_delay_seconds),
        progress_every_calls=int(progress_every_calls),
        progress_every_seconds=float(progress_every_seconds),
        http_max_retries=int(http_max_retries),
        http_backoff_base_seconds=float(http_backoff_base_seconds),
        context_label="subclass_expansion",
    )

    combined_paths: dict[str, list[dict[str, object]]] = {}
    depth_histogram: Counter = Counter()
    cache_hit_pages = 0
    network_pages = 0
    subclass_network_calls = 0
    entity_hydration_network_calls = 0
    hydrated_entity_qids = 0
    active_classes_from_triples = 0
    active_core_subclass_count = 0
    inactive_core_subclass_count = 0
    inactive_guarded_qids = 0
    superclass_branch_network_calls = 0
    superclass_branch_connected_active_classes = 0
    superclass_branch_nodes = 0
    pruned_by_known_distance = 0
    stop_reason = "queue_exhausted"
    last_heartbeat_ts = perf_counter()
    last_phase_progress_ts = perf_counter()

    current_core_index = 0
    current_core_qid = ""
    current_core_label = ""
    current_node_qid = ""
    current_depth = 0
    current_queue_size = 0
    current_core_known = 0
    current_core_cache_hit_pages = 0
    current_core_network_pages = 0
    current_core_subclass_network_calls = 0
    current_core_hydration_network_calls = 0
    current_core_hydrated_entities = 0

    known_distance_to_core: dict[str, int] = {}
    if paths.class_hierarchy_csv.exists() and paths.class_hierarchy_csv.stat().st_size > 0:
        try:
            known_distance_df = pd.read_csv(
                paths.class_hierarchy_csv,
                usecols=["class_id", "distance_to_core_min"],
                dtype={"class_id": str},
            )
            for row in known_distance_df.to_dict(orient="records"):
                qid = canonical_qid(str(row.get("class_id", "") or ""))
                raw_distance = row.get("distance_to_core_min", pd.NA)
                if not qid or pd.isna(raw_distance):
                    continue
                try:
                    known_distance_to_core[qid] = int(raw_distance)
                except Exception:
                    continue
        except Exception:
            known_distance_to_core = {}

    def _emit_subclass_heartbeat(*, force: bool = False, reason: str = "progress") -> None:
        nonlocal last_heartbeat_ts, next_heartbeat_call
        now = perf_counter()
        network_calls_used = int(get_request_context_network_queries())
        other_network_calls = max(
            0,
            network_calls_used - int(subclass_network_calls) - int(entity_hydration_network_calls) - int(superclass_branch_network_calls),
        )
        by_calls = progress_every_calls > 0 and network_calls_used >= next_heartbeat_call
        by_time = progress_every_seconds > 0.0 and (now - last_heartbeat_ts) >= progress_every_seconds
        if not (force or by_calls or by_time):
            return

        known_for_core = max(0, int(current_core_known))
        newly_found_for_core = max(0, known_for_core - 1)
        print(
            (
                f"[subclass_expansion][heartbeat] reason={reason} "
                f"core={current_core_index}/{len(core_class_qids)} "
                f"core_class={current_core_qid or '-'}({current_core_label or 'n/a'}) "
                f"node={current_node_qid or '-'} node_depth={current_depth}/{max_depth} "
                f"discovering_depth={min(max_depth, current_depth + 1)} queue={current_queue_size} "
                f"known_for_core={known_for_core} newly_found_for_core={newly_found_for_core} "
                f"pruned_by_known_distance={int(pruned_by_known_distance)} "
                f"pages_core(cache={current_core_cache_hit_pages},network={current_core_network_pages}) "
                f"pages_total(cache={cache_hit_pages},network={network_pages}) "
                f"hydrated_entities_core={current_core_hydrated_entities} hydrated_entities_total={hydrated_entity_qids} "
                f"network_calls_core(subclass={current_core_subclass_network_calls},hydration={current_core_hydration_network_calls}) "
                f"network_calls_total(subclass={subclass_network_calls},superclass_branch={superclass_branch_network_calls},"
                f"hydration={entity_hydration_network_calls},other={other_network_calls},all={network_calls_used}/{budget_label})"
            ),
            flush=True,
        )

        if progress_every_calls > 0:
            while next_heartbeat_call > 0 and network_calls_used >= next_heartbeat_call:
                next_heartbeat_call += progress_every_calls
        last_heartbeat_ts = now

    def _emit_phase_progress(
        *,
        event_type: str,
        message: str,
        extra: dict | None = None,
        force: bool = False,
    ) -> None:
        nonlocal last_phase_progress_ts
        now = perf_counter()
        if not force and (now - last_phase_progress_ts) < max(5.0, progress_every_seconds):
            return
        print(f"[subclass_expansion][phase] {message}", flush=True)
        notebook_logger.append_event(
            event_type=event_type,
            phase="subclass_expansion_preflight",
            message=message,
            extra=extra or {},
        )
        last_phase_progress_ts = now

    try:
        for core_idx, core_qid in enumerate(core_class_qids, start=1):
            current_core_index = int(core_idx)
            current_core_qid = str(core_qid)
            current_core_label = str(core_label_by_qid.get(core_qid, "") or "")
            current_node_qid = core_qid
            current_depth = 0
            current_queue_size = 1
            current_core_known = 1
            current_core_cache_hit_pages = 0
            current_core_network_pages = 0
            current_core_subclass_network_calls = 0
            current_core_hydration_network_calls = 0
            current_core_hydrated_entities = 0

            print(
                (
                    f"[subclass_expansion] core_start {core_idx}/{len(core_class_qids)} "
                    f"qid={core_qid} label={current_core_label or 'n/a'}"
                ),
                flush=True,
            )
            queue: deque[tuple[str, int, list[str]]] = deque([(core_qid, 0, [core_qid])])
            seen_depth: dict[str, int] = {core_qid: 0}
            core_paths: dict[str, tuple[int, list[str]]] = {core_qid: (0, [core_qid])}

            while queue:
                node_qid, depth, path = queue.popleft()
                current_node_qid = str(node_qid)
                current_depth = int(depth)
                current_queue_size = int(len(queue))
                remaining_depth_budget = max(0, int(max_depth - depth))
                known_distance = known_distance_to_core.get(str(node_qid))
                if known_distance is not None and int(known_distance) > remaining_depth_budget:
                    pruned_by_known_distance += 1
                    _emit_subclass_heartbeat()
                    continue
                if depth >= max_depth:
                    _emit_subclass_heartbeat()
                    continue

                offset = 0
                while True:
                    page_calls_before = int(get_request_context_network_queries())
                    try:
                        child_qids, came_from_cache = _fetch_subclass_inlinks_page(
                            repo_root,
                            node_qid,
                            limit=page_limit,
                            offset=offset,
                            timeout_seconds=query_timeout_seconds,
                        )
                    except RuntimeError as exc:
                        if str(exc) == "Network query budget hit":
                            stop_reason = "per_seed_budget_exhausted"
                            queue.clear()
                            break
                        raise
                    except TimeoutError:
                        stop_reason = "network_timeout"
                        queue.clear()
                        break

                    page_calls_after = int(get_request_context_network_queries())
                    page_network_delta = max(0, page_calls_after - page_calls_before)
                    subclass_network_calls += page_network_delta
                    current_core_subclass_network_calls += page_network_delta

                    if came_from_cache:
                        cache_hit_pages += 1
                        current_core_cache_hit_pages += 1
                    else:
                        network_pages += 1
                        current_core_network_pages += 1

                    next_depth = depth + 1
                    if child_qids:
                        depth_histogram[next_depth] += len(child_qids)

                    for child_qid in child_qids:
                        if not child_qid:
                            continue
                        child_path = path + [child_qid]
                        previous_depth = seen_depth.get(child_qid)
                        if previous_depth is None or next_depth < previous_depth:
                            seen_depth[child_qid] = next_depth
                            core_paths[child_qid] = (next_depth, child_path)
                            queue.append((child_qid, next_depth, child_path))

                    current_queue_size = int(len(queue))
                    current_core_known = int(len(core_paths))
                    _emit_subclass_heartbeat()

                    if len(child_qids) < page_limit:
                        break
                    offset += page_limit

                if stop_reason == "per_seed_budget_exhausted":
                    break
                if stop_reason == "network_timeout":
                    break

            current_core_known = int(len(core_paths))
            current_queue_size = int(len(queue))
            _emit_subclass_heartbeat(force=True, reason="core_complete")

            for class_qid, (depth, path) in core_paths.items():
                combined_paths.setdefault(class_qid, []).append(
                    {
                        "core_class_id": core_qid,
                        "depth": int(depth),
                        "path": list(reversed(path)),
                    }
                )

            if stop_reason == "per_seed_budget_exhausted":
                break
            if stop_reason == "network_timeout":
                break

        # Pass 2: load compact projections and intersect active instance classes
        # with the discovered core-subclass set. This keeps the memory footprint
        # bounded by the projection columns we actually need.
        core_subclass_qids: set[str] = set()
        classes_projection_path = paths.classes_csv
        classes_projection_rows = 0
        if classes_projection_path.exists() and classes_projection_path.stat().st_size > 0:
            try:
                classes_df = pd.read_csv(
                    classes_projection_path,
                    usecols=["id", "subclass_of_core_class"],
                    dtype={"id": str},
                    keep_default_na=False,
                    na_filter=False,
                )
                classes_projection_rows = int(len(classes_df))
                subclass_mask = classes_df["subclass_of_core_class"].astype(str).str.strip().str.lower().isin({"1", "true", "yes", "y"})
                core_subclass_qids = {
                    canonical_qid(str(qid))
                    for qid in classes_df.loc[subclass_mask, "id"].astype(str).tolist()
                    if canonical_qid(str(qid))
                }
            except Exception:
                core_subclass_qids = set(combined_paths.keys())
        if not core_subclass_qids:
            core_subclass_qids = set(combined_paths.keys())

        notebook_logger.append_event(
            event_type="subclass_expansion_pass2_started",
            phase="subclass_expansion_preflight",
            message="pass 2 active-class scan started",
            extra={
                "core_subclass_count": int(len(core_subclass_qids)),
                "core_classes_projection_rows": int(classes_projection_rows),
                "core_classes_projection_path": str(classes_projection_path),
            },
        )
        _emit_phase_progress(
            event_type="subclass_expansion_pass2_progress",
            message=(
                "pass 2 class projection scan prepared "
                f"core_subclass_count={int(len(core_subclass_qids))} classes_rows={int(classes_projection_rows)}"
            ),
            force=True,
        )

        triple_active_classes: set[str] = set()
        triples_projection_path = paths.triples_csv
        triple_projection_rows = 0
        if triples_projection_path.exists() and triples_projection_path.stat().st_size > 0:
            try:
                triples_df = pd.read_csv(
                    triples_projection_path,
                    usecols=["predicate", "object"],
                    dtype={"predicate": str, "object": str},
                    keep_default_na=False,
                    na_filter=False,
                )
                triple_projection_rows = int(len(triples_df))
                p31_mask = triples_df["predicate"].astype(str).map(canonical_pid) == "P31"
                triple_active_classes = {
                    canonical_qid(str(qid))
                    for qid in triples_df.loc[p31_mask, "object"].astype(str).tolist()
                    if canonical_qid(str(qid))
                }
            except Exception:
                triple_active_classes = set()

        if not triple_active_classes:
            # Fallback: derive the set from the already-discovered active-class evidence
            # that lives in the current pass. This should be rare and is only used when
            # the projection files are unavailable or unreadable.
            triple_active_classes = set()
            fallback_triple_scan_count = 0
            for triple in iter_unique_triples(repo_root):
                fallback_triple_scan_count += 1
                if should_terminate(_shutdown_path(Path(repo_root))):
                    stop_reason = "user_interrupted"
                    _emit_phase_progress(
                        event_type="subclass_expansion_interrupted",
                        message=(
                            "pass 2 fallback triple scan interrupted "
                            f"scanned_rows={int(fallback_triple_scan_count)}"
                        ),
                        extra={"fallback_triple_scan_count": int(fallback_triple_scan_count)},
                        force=True,
                    )
                    break
                predicate = canonical_pid(str(triple.get("predicate", "") or ""))
                if predicate == "P31":
                    object_qid = canonical_qid(str(triple.get("object", "") or ""))
                    if object_qid:
                        triple_active_classes.add(object_qid)
                if fallback_triple_scan_count % 250000 == 0:
                    _emit_phase_progress(
                        event_type="subclass_expansion_pass2_progress",
                        message=(
                            "pass 2 fallback triple scan progress "
                            f"scanned_rows={int(fallback_triple_scan_count)} active_classes={int(len(triple_active_classes))}"
                        ),
                    )

        active_classes_from_triples = int(len(triple_active_classes))
        notebook_logger.append_event(
            event_type="subclass_expansion_pass2_completed",
            phase="subclass_expansion_preflight",
            message="pass 2 active-class scan completed",
            extra={
                "triple_projection_rows": int(triple_projection_rows),
                "active_classes_from_triples": int(active_classes_from_triples),
                "core_subclass_count": int(len(core_subclass_qids)),
            },
        )
        _emit_phase_progress(
            event_type="subclass_expansion_pass2_progress",
            message=(
                "pass 2 active-class scan completed "
                f"triple_rows={int(triple_projection_rows)} active_classes={int(active_classes_from_triples)}"
            ),
            force=True,
        )

        # Optional reverse route: from active instance classes, climb upward via P279
        # for a small bounded depth so active classes can connect to core-subclass tree.
        superclass_branch_discovery_max_depth = max(0, int(superclass_branch_discovery_max_depth or 0))
        if superclass_branch_discovery_max_depth > 0 and triple_active_classes:
            parent_cache: dict[str, list[str]] = {}
            branch_progress_last_emit = perf_counter()
            branch_progress_every_seconds = 60.0
            branch_nodes_processed = 0
            active_classes_total = int(len(triple_active_classes))
            active_classes_processed = 0

            _emit_phase_progress(
                event_type="subclass_expansion_pass2_branch_started",
                message=(
                    "pass 2 upward branch discovery started "
                    f"active_classes={active_classes_total} depth={int(superclass_branch_discovery_max_depth)}"
                ),
                force=True,
            )

            def _parents_via_cache_first(class_qid: str) -> list[str]:
                nonlocal superclass_branch_network_calls
                qid_norm = canonical_qid(class_qid)
                if not qid_norm:
                    return []
                if qid_norm in parent_cache:
                    return parent_cache[qid_norm]

                before_calls = int(get_request_context_network_queries())
                payload = get_or_fetch_entity(
                    repo_root,
                    qid_norm,
                    cache_max_age_days=cache_max_age_days,
                    timeout=query_timeout_seconds,
                )
                after_calls = int(get_request_context_network_queries())
                superclass_branch_network_calls += max(0, after_calls - before_calls)

                entity_doc = payload.get("entities", {}).get(qid_norm, {}) if isinstance(payload, dict) else {}
                claims = entity_doc.get("claims", {}) if isinstance(entity_doc, dict) else {}
                parents: list[str] = []
                for claim in (claims.get("P279", []) or []):
                    mainsnak = claim.get("mainsnak", {}) if isinstance(claim, dict) else {}
                    value = (mainsnak.get("datavalue", {}) or {}).get("value")
                    if isinstance(value, dict) and value.get("entity-type") == "item":
                        parent_qid = canonical_qid(str(value.get("id", "") or ""))
                        if parent_qid:
                            parents.append(parent_qid)
                deduped = sorted(set(parents))
                parent_cache[qid_norm] = deduped
                return deduped

            for active_class_qid in sorted(triple_active_classes):
                active_classes_processed += 1
                if should_terminate(_shutdown_path(Path(repo_root))):
                    stop_reason = "user_interrupted"
                    print("[subclass_expansion] pass2_branch interrupted; stopping upward branch discovery", flush=True)
                    notebook_logger.append_event(
                        event_type="subclass_expansion_interrupted",
                        phase="subclass_expansion_preflight",
                        message="pass 2 upward branch discovery interrupted",
                        extra={
                            "superclass_branch_nodes": int(superclass_branch_nodes),
                            "superclass_branch_connected_active_classes": int(superclass_branch_connected_active_classes),
                        },
                    )
                    break
                if not active_class_qid or active_class_qid in core_subclass_qids:
                    continue

                queue: deque[tuple[str, int, list[str]]] = deque([(active_class_qid, 0, [active_class_qid])])
                seen_up: set[str] = {active_class_qid}
                connection_found = False
                branch_nodes_local: set[str] = {active_class_qid}

                while queue:
                    if should_terminate(_shutdown_path(Path(repo_root))):
                        stop_reason = "user_interrupted"
                        queue.clear()
                        break
                    node_qid, up_depth, up_path = queue.popleft()
                    branch_nodes_processed += 1

                    if branch_nodes_processed % 1000 == 0:
                        _emit_phase_progress(
                            event_type="subclass_expansion_pass2_branch_progress",
                            message=(
                                "pass 2 branch traversal progress "
                                f"active_classes_processed={int(active_classes_processed)}/{int(active_classes_total)} "
                                f"branch_nodes_processed={int(branch_nodes_processed)} "
                                f"connected_active_classes={int(superclass_branch_connected_active_classes)}"
                            ),
                        )

                    if node_qid in core_subclass_qids:
                        for candidate in combined_paths.get(node_qid, []):
                            candidate_path = [canonical_qid(str(x or "")) for x in (candidate.get("path", []) or [])]
                            candidate_path = [x for x in candidate_path if x]
                            if not candidate_path:
                                continue
                            combined_path = up_path + candidate_path[1:]
                            # Keep branch memory bounded: only record resolution for
                            # the originating active class, not every intermediate node.
                            combined_paths.setdefault(active_class_qid, []).append(
                                {
                                    "core_class_id": str(candidate.get("core_class_id", "") or ""),
                                    "depth": int(len(combined_path) - 1),
                                    "path": combined_path,
                                }
                            )
                        connection_found = True
                        continue

                    if up_depth >= superclass_branch_discovery_max_depth:
                        continue

                    try:
                        parent_candidates = _parents_via_cache_first(node_qid)
                    except RuntimeError as exc:
                        if str(exc) == "Network query budget hit":
                            stop_reason = "per_seed_budget_exhausted"
                            queue.clear()
                            break
                        raise
                    except TimeoutError:
                        stop_reason = "network_timeout"
                        queue.clear()
                        break

                    for parent_qid in parent_candidates:
                        if not parent_qid or parent_qid in seen_up:
                            continue
                        seen_up.add(parent_qid)
                        branch_nodes_local.add(parent_qid)
                        queue.append((parent_qid, up_depth + 1, up_path + [parent_qid]))

                if connection_found:
                    superclass_branch_connected_active_classes += 1
                superclass_branch_nodes += len(branch_nodes_local)

                # Heartbeat remains meaningful during long upward branch discovery runs.
                _emit_subclass_heartbeat()
                if (perf_counter() - branch_progress_last_emit) >= branch_progress_every_seconds:
                    branch_network_calls = int(superclass_branch_network_calls)
                    total_network_calls = int(get_request_context_network_queries())
                    print(
                        (
                            f"[subclass_expansion] pass2_branch progress active_classes={len(triple_active_classes)} "
                            f"connected={superclass_branch_connected_active_classes} branch_nodes={superclass_branch_nodes} "
                            f"network_calls_branch={branch_network_calls} "
                            f"network_calls_total={total_network_calls}/{budget_label}"
                        ),
                        flush=True,
                    )
                    notebook_logger.append_event(
                        event_type="subclass_expansion_pass2_branch_progress",
                        phase="subclass_expansion_preflight",
                        message="pass 2 upward branch discovery progress",
                        extra={
                            "active_classes_from_triples": int(active_classes_from_triples),
                            "connected_active_classes": int(superclass_branch_connected_active_classes),
                            "branch_nodes": int(superclass_branch_nodes),
                        },
                    )
                    branch_progress_last_emit = perf_counter()

                if stop_reason in {"per_seed_budget_exhausted", "network_timeout", "user_interrupted"}:
                    break

            _emit_phase_progress(
                event_type="subclass_expansion_pass2_branch_completed",
                message=(
                    "pass 2 upward branch discovery completed "
                    f"active_classes_processed={int(active_classes_processed)}/{int(active_classes_total)} "
                    f"branch_nodes_processed={int(branch_nodes_processed)} "
                    f"connected_active_classes={int(superclass_branch_connected_active_classes)}"
                ),
                force=True,
            )

            # Re-evaluate core-subclass universe after branch discovery has potentially
            # created additional class-to-core candidate paths.
            core_subclass_qids = set(combined_paths.keys())

        active_core_subclass_qids = sorted(core_subclass_qids & triple_active_classes)
        active_core_subclass_count = int(len(active_core_subclass_qids))
        inactive_core_subclass_qids = sorted(core_subclass_qids - set(active_core_subclass_qids))
        inactive_core_subclass_count = max(0, int(len(core_subclass_qids) - active_core_subclass_count))

        for inactive_qid in inactive_core_subclass_qids:
            if should_terminate(_shutdown_path(Path(repo_root))):
                stop_reason = "user_interrupted"
                _emit_phase_progress(
                    event_type="subclass_expansion_interrupted",
                    message=(
                        "inactive subclass guard interrupted "
                        f"processed={int(inactive_guarded_qids)}/{int(inactive_core_subclass_count)}"
                    ),
                    extra={
                        "inactive_guarded_qids": int(inactive_guarded_qids),
                        "inactive_core_subclass_count": int(inactive_core_subclass_count),
                    },
                    force=True,
                )
                break
            candidate_paths = combined_paths.get(inactive_qid, [])
            if candidate_paths:
                best_path = sorted(
                    candidate_paths,
                    key=lambda candidate: (
                        int(candidate.get("depth", 0) or 0),
                        core_precedence.get(str(candidate.get("core_class_id", "") or ""), 10_000),
                    ),
                )[0]
                resolved_core_for_inactive = str(best_path.get("core_class_id", "") or "")
                resolution_depth_for_inactive = int(best_path.get("depth", 0) or 0)
            else:
                resolved_core_for_inactive = ""
                resolution_depth_for_inactive = None
            discovered_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            mark_inactive_core_subclass(
                repo_root,
                inactive_qid,
                discovered_at_utc=discovered_at_utc,
                resolved_core_class_id=resolved_core_for_inactive,
                resolution_depth=resolution_depth_for_inactive,
                max_depth=int(max_depth),
            )
            inactive_guarded_qids += 1
            if inactive_guarded_qids % 1000 == 0:
                _emit_phase_progress(
                    event_type="subclass_expansion_inactive_guard_progress",
                    message=(
                        "inactive subclass guard progress "
                        f"processed={int(inactive_guarded_qids)}/{int(inactive_core_subclass_count)}"
                    ),
                )

        print(
            (
                f"[subclass_expansion] activation_start active_from_triples={active_classes_from_triples} "
                f"core_subclasses={len(core_subclass_qids)} active_core_subclasses={active_core_subclass_count} "
                f"inactive_core_subclasses={inactive_core_subclass_count}"
            ),
            flush=True,
        )
        notebook_logger.append_event(
            event_type="subclass_expansion_activation_started",
            phase="subclass_expansion_preflight",
            message="activation hydration started",
            extra={
                "active_core_subclasses": int(active_core_subclass_count),
                "inactive_core_subclasses": int(inactive_core_subclass_count),
            },
        )

        activation_batch_size = 100
        activation_processed = 0
        if stop_reason in {"per_seed_budget_exhausted", "network_timeout"}:
            print(
                (
                    f"[subclass_expansion] activation_skipped reason={stop_reason} "
                    f"active_core_subclasses={active_core_subclass_count}"
                ),
                flush=True,
            )
        for start in range(0, active_core_subclass_count, activation_batch_size):
            if should_terminate(_shutdown_path(Path(repo_root))):
                stop_reason = "user_interrupted"
                print("[subclass_expansion] activation interrupted; stopping batch hydration", flush=True)
                notebook_logger.append_event(
                    event_type="subclass_expansion_interrupted",
                    phase="subclass_expansion_preflight",
                    message="activation hydration interrupted",
                    extra={
                        "activation_processed": int(activation_processed),
                        "hydrated_entity_qids": int(hydrated_entity_qids),
                    },
                )
                break
            if stop_reason in {"per_seed_budget_exhausted", "network_timeout"}:
                break
            batch_qids = active_core_subclass_qids[start : start + activation_batch_size]
            if not batch_qids:
                continue

            hydration_calls_before = int(get_request_context_network_queries())
            try:
                activated_payloads = get_or_fetch_entities_batch(
                    repo_root,
                    batch_qids,
                    cache_max_age_days=cache_max_age_days,
                    timeout=query_timeout_seconds,
                )
            except RuntimeError as exc:
                if str(exc) == "Network query budget hit":
                    stop_reason = "per_seed_budget_exhausted"
                    break
                raise
            except TimeoutError:
                stop_reason = "network_timeout"
                break

            hydration_calls_after = int(get_request_context_network_queries())
            hydration_network_delta = max(0, hydration_calls_after - hydration_calls_before)
            entity_hydration_network_calls += hydration_network_delta

            hydrated_batch = 0
            for activated_qid, payload in activated_payloads.items():
                entity_doc = payload.get("entities", {}).get(activated_qid, {}) if isinstance(payload, dict) else {}
                if isinstance(entity_doc, dict) and entity_doc:
                    discovered_at_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    activate_core_subclass(
                        repo_root,
                        activated_qid,
                        entity_doc,
                        discovered_at_utc,
                        activation_source="subclass_preflight_p31_intersection",
                    )
                    hydrated_batch += 1

            hydrated_entity_qids += hydrated_batch
            activation_processed += len(batch_qids)

            if activation_processed % 500 == 0 or activation_processed >= active_core_subclass_count:
                print(
                    (
                        f"[subclass_expansion] activation_progress processed={activation_processed}/{active_core_subclass_count} "
                        f"hydrated={hydrated_entity_qids} network_calls_activation={entity_hydration_network_calls}"
                    ),
                    flush=True,
                )
                notebook_logger.append_event(
                    event_type="subclass_expansion_activation_progress",
                    phase="subclass_expansion_preflight",
                    message="activation hydration progress",
                    extra={
                        "activation_processed": int(activation_processed),
                        "active_core_subclasses": int(active_core_subclass_count),
                        "hydrated_entity_qids": int(hydrated_entity_qids),
                        "network_calls_activation": int(entity_hydration_network_calls),
                    },
                )
    finally:
        _emit_subclass_heartbeat(force=True, reason=stop_reason)
        network_queries = int(end_request_context())

    rows: list[dict] = []
    total_class_rows = int(len(combined_paths))
    for row_index, class_id in enumerate(sorted(combined_paths), start=1):
        if should_terminate(_shutdown_path(Path(repo_root))):
            stop_reason = "user_interrupted"
            _emit_phase_progress(
                event_type="subclass_expansion_interrupted",
                message=(
                    "class resolution map assembly interrupted "
                    f"processed={int(row_index - 1)}/{int(total_class_rows)}"
                ),
                extra={
                    "rows_processed": int(row_index - 1),
                    "rows_total": int(total_class_rows),
                },
                force=True,
            )
            break
        candidates = combined_paths[class_id]
        if not candidates:
            continue
        candidate_core_ids = sorted({str(candidate.get("core_class_id", "") or "") for candidate in candidates if str(candidate.get("core_class_id", "") or "")})
        candidate_core_ids = [qid for qid in candidate_core_ids if qid]
        candidates = sorted(
            candidates,
            key=lambda candidate: (
                int(candidate.get("depth", 0) or 0),
                core_precedence.get(str(candidate.get("core_class_id", "") or ""), 10_000),
                str(candidate.get("core_class_id", "") or ""),
                str(candidate.get("path", [])),
            ),
        )
        best = candidates[0]
        best_core = str(best.get("core_class_id", "") or "")
        best_depth = int(best.get("depth", 0) or 0)
        conflict = len(candidate_core_ids) > 1
        rows.append(
            {
                "class_id": class_id,
                "resolved_core_class_id": best_core,
                "resolution_depth": best_depth,
                "resolution_reason": "deterministic_conflict_resolution" if conflict else "unique_candidate",
                "conflict_flag": bool(conflict),
                "candidate_core_class_ids": "|".join(candidate_core_ids),
                "candidate_paths_json": json.dumps(
                    [
                        {
                            "core_class_id": str(candidate.get("core_class_id", "") or ""),
                            "depth": int(candidate.get("depth", 0) or 0),
                            "path": list(candidate.get("path", [])),
                        }
                        for candidate in candidates
                    ],
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "max_depth": int(max_depth),
            }
        )
        if row_index % 1000 == 0:
            _emit_phase_progress(
                event_type="subclass_expansion_map_assembly_progress",
                message=f"class resolution map assembly progress processed={int(row_index)}/{int(total_class_rows)}",
            )

    class_resolution_map_df = pd.DataFrame(
        rows,
        columns=[
            "class_id",
            "resolved_core_class_id",
            "resolution_depth",
            "resolution_reason",
            "conflict_flag",
            "candidate_core_class_ids",
            "candidate_paths_json",
            "max_depth",
        ],
    ).sort_values("class_id").reset_index(drop=True)
    if not class_resolution_map_df.empty:
        class_resolution_map_df["resolution_depth"] = pd.to_numeric(class_resolution_map_df["resolution_depth"], errors="coerce").astype("Int64")
        class_resolution_map_df["max_depth"] = pd.to_numeric(class_resolution_map_df["max_depth"], errors="coerce").astype("Int64")

    _write_tabular_artifact(paths.class_resolution_map_csv, class_resolution_map_df)

    stats = {
        "run_id": run_id,
        "stage": "subclass_expansion",
        "subclass_expansion_max_depth": int(max_depth),
        "core_class_count": int(len(core_class_qids)),
        "class_resolution_rows": int(len(class_resolution_map_df)),
        "class_resolution_conflict_rows": int(class_resolution_map_df["conflict_flag"].sum()) if not class_resolution_map_df.empty else 0,
        "candidate_frontier_rows": int(sum(len(paths_for_class) for paths_for_class in combined_paths.values())),
        "depth_histogram": dict(sorted(depth_histogram.items())),
        "cache_hit_pages": int(cache_hit_pages),
        "network_pages": int(network_pages),
        "subclass_network_calls": int(subclass_network_calls),
        "pruned_by_known_distance": int(pruned_by_known_distance),
        "superclass_branch_discovery_max_depth": int(superclass_branch_discovery_max_depth),
        "superclass_branch_network_calls": int(superclass_branch_network_calls),
        "superclass_branch_connected_active_classes": int(superclass_branch_connected_active_classes),
        "superclass_branch_nodes": int(superclass_branch_nodes),
        "active_classes_from_triples": int(active_classes_from_triples),
        "active_core_subclass_count": int(active_core_subclass_count),
        "inactive_core_subclass_count": int(inactive_core_subclass_count),
        "inactive_guarded_qids": int(inactive_guarded_qids),
        "entity_hydration_network_calls": int(entity_hydration_network_calls),
        "hydrated_entity_qids": int(hydrated_entity_qids),
        "network_queries": int(network_queries),
        "stop_reason": stop_reason,
        "elapsed_seconds": round(perf_counter() - total_t0, 3),
    }
    _write_summary(paths, run_id, "subclass_expansion", stats)
    print(f"[materializer] Completed subclass crawl in {stats['elapsed_seconds']:.2f}s", flush=True)
    return stats


def _materialize(repo_root: Path, *, run_id: str, stage: str, seed_id: str | None) -> dict:
    total_t0 = perf_counter()
    print(f"[materializer] Start stage={stage} run_id={run_id}", flush=True)
    flush_node_store(repo_root)
    flush_triple_events(repo_root)
    paths = build_artifact_paths(Path(repo_root))
    core_class_qids = _core_class_qids(repo_root)
    root_class_qids = _root_class_qids(repo_root)
    recovered_lineage, recovered_lineage_source = _load_recovered_lineage_evidence(repo_root, paths)
    rewiring_catalogue = _load_rewiring_catalogue(repo_root)
    subclass_max_depth = _subclass_expansion_max_depth()
    resolution_policy = _lineage_resolution_policy()
    resolution_reasons: Counter = Counter()

    t0 = perf_counter()
    instances_df = _build_instances_df(
        repo_root,
        core_class_qids,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
        rewiring_catalogue=rewiring_catalogue,
    )
    print(f"[materializer] build instances done in {perf_counter() - t0:.2f}s", flush=True)
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
        rewiring_catalogue=rewiring_catalogue,
    )
    print(f"[materializer] build class_hierarchy done in {perf_counter() - t0:.2f}s", flush=True)
    t0 = perf_counter()
    class_resolution_map_df = _build_class_resolution_map_df(
        repo_root,
        class_hierarchy_df,
        core_class_qids,
        rewiring_catalogue,
        subclass_max_depth,
    )
    print(f"[materializer] build class_resolution_map done in {perf_counter() - t0:.2f}s", flush=True)
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
    _write_tabular_artifact(paths.class_resolution_map_csv, class_resolution_map_df)
    _write_tabular_artifact(paths.instances_csv, instances_df)
    _write_tabular_artifact(paths.properties_csv, properties_df)
    from .handlers.orchestrator import run_handlers

    handler_summary = run_handlers(repo_root, materialization_mode="incremental")
    if paths.query_inventory_csv.exists() and paths.query_inventory_csv.stat().st_size > 0:
        query_inventory_rows = int(pd.read_csv(paths.query_inventory_csv).shape[0])
    else:
        query_inventory_rows = 0
    entity_lookup_rows = _write_entity_lookup_artifacts(
        repo_root,
        paths,
        core_class_qids,
        triples_df,
        recovered_lineage=recovered_lineage,
        resolution_policy=resolution_policy,
        resolution_reasons=resolution_reasons,
        rewiring_catalogue=rewiring_catalogue,
    )
    core_projection_counts = _write_core_instance_projections(
        paths,
        instances_df,
        class_hierarchy_df,
        repo_root,
        core_class_qids,
        rewiring_catalogue,
        class_resolution_map_df,
    )
    print(f"[materializer] write tabular artifacts done in {perf_counter() - t0:.2f}s", flush=True)

    stats = {
        "seed_id": seed_id,
        "instances_rows": int(len(instances_df)),
        "classes_rows": int(pd.read_csv(paths.classes_csv).shape[0]) if paths.classes_csv.exists() else 0,
        "properties_rows": int(len(properties_df)),
        "triples_rows": int(len(triples_df)),
        "query_inventory_rows": int(query_inventory_rows),
        "entity_lookup_rows": int(entity_lookup_rows),
        "core_instance_projection_files": int(len(core_projection_counts)),
        "instances_leftovers_rows": int(core_projection_counts.get(paths.instances_leftovers_csv.name, 0)),
        "lineage_resolution_policy": resolution_policy,
        "lineage_recovered_source": recovered_lineage_source,
        "lineage_resolution_reason_counts": dict(sorted(resolution_reasons.items())),
        "subclass_expansion_max_depth": int(subclass_max_depth),
        "class_resolution_rows": int(len(class_resolution_map_df)),
        "class_resolution_conflict_rows": int(
            int(class_resolution_map_df["conflict_flag"].sum()) if not class_resolution_map_df.empty else 0
        ),
        "handler_projection_summary_rows": int(len(handler_summary)),
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
