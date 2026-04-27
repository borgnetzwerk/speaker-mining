from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from .bootstrap import load_seed_instances
from .cache import _atomic_write_df
from .common import canonical_pid, canonical_qid
from .event_log import iter_all_events, write_relevance_assigned_event
from .node_store import flush_node_store, mark_item_relevant
from .schemas import build_artifact_paths


def _is_truthy(value: object) -> bool:
    token = str(value or "").strip().lower()
    return token in {"1", "true", "yes", "y", "on", "x"}


def _is_false_like(value: object) -> bool:
    token = str(value or "").strip().lower()
    return token in {"", "0", "false", "no", "n", "off"}


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _label_from_row(row: dict) -> str:
    return str(
        row.get("label_en", "")
        or row.get("label_de", "")
        or row.get("class_filename", "")
        or row.get("id", "")
        or ""
    )


def _load_class_labels(paths) -> dict[str, str]:
    class_labels: dict[str, str] = {}
    if not paths.classes_csv.exists() or paths.classes_csv.stat().st_size == 0:
        return class_labels
    try:
        frame = pd.read_csv(paths.classes_csv, dtype=str).fillna("")
    except Exception:
        return class_labels
    for row in frame.to_dict(orient="records"):
        qid = canonical_qid(str(row.get("id", "") or ""))
        if not qid:
            continue
        class_labels[qid] = _label_from_row(row)
    return class_labels


def _load_property_labels(paths) -> dict[str, str]:
    property_labels: dict[str, str] = {}
    if not paths.properties_csv.exists() or paths.properties_csv.stat().st_size == 0:
        return property_labels
    try:
        frame = pd.read_csv(paths.properties_csv, dtype=str).fillna("")
    except Exception:
        return property_labels
    for row in frame.to_dict(orient="records"):
        pid = canonical_pid(str(row.get("id", "") or ""))
        if not pid:
            continue
        property_labels[pid] = str(row.get("label_en", "") or row.get("label_de", "") or row.get("id", "") or "")
    return property_labels


def _canonical_relation_context(subject_class_qid: str, property_qid: str, object_class_qid: str) -> tuple[str, str, str]:
    subject = canonical_qid(subject_class_qid)
    predicate = canonical_pid(property_qid)
    obj = canonical_qid(object_class_qid)
    if not subject or not predicate or not obj:
        return "", "", ""
    # Always preserve direction: (subject, property, object)
    return subject, predicate, obj


@dataclass(frozen=True)
class RelevancyBootstrapResult:
    relation_context_rows: int
    newly_emitted_relevancy_events: int
    final_relevant_qids: int


def _load_existing_relevance_qids(repo_root: Path) -> set[str]:
    relevant_qids: set[str] = set()
    for event in iter_all_events(repo_root) or []:
        if event.get("event_type") != "relevance_assigned":
            continue
        payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
        qid = canonical_qid(str(payload.get("entity_qid", "") or ""))
        if not qid:
            continue
        if bool(payload.get("relevant", False)):
            relevant_qids.add(qid)
    return relevant_qids


def _merge_relation_context_catalog(
    paths,
    *,
    detected_rows: list[dict],
) -> pd.DataFrame:
    columns = [
        "subject_class_qid",
        "subject_class_label",
        "property_qid",
        "property_label",
        "object_class_qid",
        "object_class_label",
        "decision_last_updated_at",
        "can_inherit",
    ]

    import sys
    existing_by_key: dict[tuple[str, str, str], dict] = {}
    # 1. Load the setup file as a read-only seed
    setup_path = Path(paths.root).parent.parent / "data/00_setup/relevancy_relation_contexts.csv"
    if setup_path.exists() and setup_path.stat().st_size > 0:
        try:
            setup_df = pd.read_csv(setup_path, dtype=str).fillna("")
            for row in setup_df.to_dict(orient="records"):
                key = _canonical_relation_context(
                    str(row.get("subject_class_qid", "") or ""),
                    str(row.get("property_qid", "") or ""),
                    str(row.get("object_class_qid", "") or ""),
                )
                if not all(key):
                    continue
                incoming = {
                    "subject_class_qid": key[0],
                    "subject_class_label": str(row.get("subject_class_label", "") or ""),
                    "property_qid": key[1],
                    "property_label": str(row.get("property_label", "") or ""),
                    "object_class_qid": key[2],
                    "object_class_label": str(row.get("object_class_label", "") or ""),
                    "decision_last_updated_at": str(row.get("decision_last_updated_at", "") or ""),
                    "can_inherit": str(row.get("can_inherit", "") or ""),
                }
                existing_by_key[key] = incoming
        except Exception as e:
            print(f"[WARN] Could not read setup relevancy_relation_contexts.csv: {e}", file=sys.stderr)

    # 2. Load the projection file as before
    existing_path = paths.relevancy_relation_contexts_csv
    if existing_path.exists() and existing_path.stat().st_size > 0:
        try:
            existing_df = pd.read_csv(existing_path, dtype=str).fillna("")
            for row in existing_df.to_dict(orient="records"):
                key = _canonical_relation_context(
                    str(row.get("subject_class_qid", "") or ""),
                    str(row.get("property_qid", "") or ""),
                    str(row.get("object_class_qid", "") or ""),
                )
                if not all(key):
                    continue
                incoming = {
                    "subject_class_qid": key[0],
                    "subject_class_label": str(row.get("subject_class_label", "") or ""),
                    "property_qid": key[1],
                    "property_label": str(row.get("property_label", "") or ""),
                    "object_class_qid": key[2],
                    "object_class_label": str(row.get("object_class_label", "") or ""),
                    "decision_last_updated_at": str(row.get("decision_last_updated_at", "") or ""),
                    "can_inherit": str(row.get("can_inherit", "") or ""),
                }
                prior = existing_by_key.get(key)
                if isinstance(prior, dict):
                    # If there is a conflict, print a warning and keep the setup value
                    for col in ["can_inherit", "decision_last_updated_at"]:
                        if str(prior.get(col, "")).strip() != str(incoming.get(col, "")).strip() and str(prior.get(col, "")).strip():
                            print(f"[WARN] Conflict for {key}: setup {col}='{prior.get(col, '')}' overrides projection '{incoming.get(col, '')}'", file=sys.stderr)
                    # Setup value always wins
                    continue
                existing_by_key[key] = incoming
        except Exception:
            pass

    merged: dict[tuple[str, str, str], dict] = dict(existing_by_key)

    # Add detected_rows to merged
    for row in detected_rows:
        subject = str(row.get("subject_class_qid", "") or "")
        property = str(row.get("property_qid", "") or "")
        obj = str(row.get("object_class_qid", "") or "")
        key = _canonical_relation_context(subject, property, obj)
        if not all(key):
            continue

        prior = merged.get(key)
        preserved_can_inherit = ""
        preserved_decision_ts = ""
        if isinstance(prior, dict):
            preserved_can_inherit = str(prior.get("can_inherit", "") or "")
            preserved_decision_ts = str(prior.get("decision_last_updated_at", "") or "")

        merged[key] = {
            "subject_class_qid": key[0],
            "subject_class_label": str(row.get("subject_class_label", "") or ""),
            "property_qid": key[1],
            "property_label": str(row.get("property_label", "") or ""),
            "object_class_qid": key[2],
            "object_class_label": str(row.get("object_class_label", "") or ""),
            "decision_last_updated_at": preserved_decision_ts,
            "can_inherit": preserved_can_inherit,
        }

    now_iso = _iso_now()
    for row in merged.values():
        can_inherit = str(row.get("can_inherit", "") or "").strip()
        decision_ts = str(row.get("decision_last_updated_at", "") or "").strip()
        if can_inherit and not decision_ts:
            row["decision_last_updated_at"] = now_iso

    if not merged:
        return pd.DataFrame(columns=columns)

    merged_df = pd.DataFrame(list(merged.values()), columns=columns)
    return merged_df.sort_values(["subject_class_qid", "object_class_qid", "property_qid"]).reset_index(drop=True)


def bootstrap_relevancy_events(
    repo_root: Path,
    *,
    instances_df: pd.DataFrame,
    class_hierarchy_df: pd.DataFrame,
    class_resolution_map_df: pd.DataFrame,
    triples_df: pd.DataFrame,
    core_qid_to_label: dict[str, str],
) -> RelevancyBootstrapResult:
    repo_root = Path(repo_root)
    paths = build_artifact_paths(repo_root)

    if instances_df.empty:
        _atomic_write_df(
            paths.relevancy_relation_contexts_csv,
            pd.DataFrame(
            columns=[
                "subject_class_qid",
                "subject_class_label",
                "property_qid",
                "property_label",
                "object_class_qid",
                "object_class_label",
                "decision_last_updated_at",
                "can_inherit",
            ]
            ),
        )
        return RelevancyBootstrapResult(0, 0, 0)

    class_labels = _load_class_labels(paths)
    property_labels = _load_property_labels(paths)

    class_node_ids: set[str] = set()
    if not class_hierarchy_df.empty and "class_id" in class_hierarchy_df.columns:
        class_node_ids = {
            canonical_qid(str(value or ""))
            for value in class_hierarchy_df["class_id"].tolist()
            if canonical_qid(str(value or ""))
        }

    base_df = instances_df.copy()
    if class_node_ids:
        base_df = base_df[~base_df["id"].isin(class_node_ids)].copy()

    resolution_lookup: dict[str, str] = {}
    if not class_resolution_map_df.empty:
        for row in class_resolution_map_df.to_dict(orient="records"):
            class_id = canonical_qid(str(row.get("class_id", "") or ""))
            core_id = canonical_qid(str(row.get("resolved_core_class_id", "") or ""))
            if class_id and core_id:
                resolution_lookup[class_id] = core_id

    qid_to_core_class: dict[str, str] = {}
    for row in base_df.to_dict(orient="records"):
        qid = canonical_qid(str(row.get("id", "") or ""))
        class_id = canonical_qid(str(row.get("class_id", "") or ""))
        if not qid or not class_id:
            continue
        resolved_core = resolution_lookup.get(class_id, "")
        if not resolved_core:
            path = str(row.get("path_to_core_class", "") or "")
            tokens = [canonical_qid(tok) for tok in path.split("|") if canonical_qid(tok)]
            resolved_core = next((tok for tok in reversed(tokens) if tok in set(core_qid_to_label.keys())), "")
        if resolved_core:
            qid_to_core_class[qid] = resolved_core

    # Build a parallel lookup for class nodes (P279 hierarchy items) → their resolved
    # core class.  Mirrors qid_to_core_class but covers class-space QIDs such as role
    # subclasses (journalist Q1930187 → Q214339/role) that are filtered out of base_df.
    class_qid_to_core_class: dict[str, str] = {}
    core_set = set(core_qid_to_label.keys())
    if not class_hierarchy_df.empty:
        for row in class_hierarchy_df.to_dict(orient="records"):
            cid = canonical_qid(str(row.get("class_id", "") or ""))
            if not cid:
                continue
            # Core-class nodes map to themselves.
            if str(row.get("is_core_class", "")).strip().lower() in {"true", "1", "yes"}:
                if cid in core_set:
                    class_qid_to_core_class[cid] = cid
                continue
            path = str(row.get("path_to_core_class", "") or "")
            tokens = [canonical_qid(tok) for tok in path.split("|") if canonical_qid(tok)]
            resolved = next((tok for tok in reversed(tokens) if tok in core_set), "")
            if resolved:
                class_qid_to_core_class[cid] = resolved

    detected_context_rows: list[dict] = []
    outgoing_by_source: dict[str, list[dict]] = {}

    if not triples_df.empty:
        for triple in triples_df.to_dict(orient="records"):
            subject = canonical_qid(str(triple.get("subject", "") or ""))
            obj = canonical_qid(str(triple.get("object", "") or ""))
            pid = canonical_pid(str(triple.get("predicate", "") or ""))
            if not subject or not obj or not pid:
                continue

            subject_core = qid_to_core_class.get(subject, "") or class_qid_to_core_class.get(subject, "")
            object_core = qid_to_core_class.get(obj, "") or class_qid_to_core_class.get(obj, "")
            if not subject_core or not object_core:
                continue

            context_subject, context_property, context_object = _canonical_relation_context(subject_core, pid, object_core)
            if not context_subject or not context_property or not context_object:
                continue

            detected_context_rows.append(
                {
                    "subject_class_qid": context_subject,
                    "subject_class_label": str(
                        class_labels.get(context_subject)
                        or core_qid_to_label.get(context_subject)
                        or context_subject
                    ),
                    "property_qid": context_property,
                    "property_label": str(property_labels.get(context_property) or context_property),
                    "object_class_qid": context_object,
                    "object_class_label": str(
                        class_labels.get(context_object)
                        or core_qid_to_label.get(context_object)
                        or context_object
                    ),
                }
            )

            outgoing_by_source.setdefault(subject, []).append(
                {
                    "target_qid": obj,
                    "property_qid": pid,
                    "direction": "outlink",
                    "context": _canonical_relation_context(subject_core, pid, object_core),
                }
            )
            outgoing_by_source.setdefault(obj, []).append(
                {
                    "target_qid": subject,
                    "property_qid": pid,
                    "direction": "inlink",
                    "context": _canonical_relation_context(subject_core, pid, object_core),
                }
            )

    relation_context_df = _merge_relation_context_catalog(paths, detected_rows=detected_context_rows)
    _atomic_write_df(paths.relevancy_relation_contexts_csv, relation_context_df)

    approved_contexts: set[tuple[str, str, str]] = set()
    if not relation_context_df.empty:
        for row in relation_context_df.to_dict(orient="records"):
            can_inherit = row.get("can_inherit", "")
            if _is_false_like(can_inherit):
                continue
            if not _is_truthy(can_inherit):
                # Any non-empty value is considered approval.
                if str(can_inherit or "").strip() == "":
                    continue
            context = _canonical_relation_context(
                str(row.get("subject_class_qid", "") or ""),
                str(row.get("property_qid", "") or ""),
                str(row.get("object_class_qid", "") or ""),
            )
            if all(context):
                approved_contexts.add(context)

    existing_relevant_qids = _load_existing_relevance_qids(repo_root)

    seeds, _skipped = load_seed_instances(repo_root)
    seed_qids = {
        canonical_qid(str(seed.get("wikidata_id", "") or ""))
        for seed in seeds
        if canonical_qid(str(seed.get("wikidata_id", "") or ""))
    }

    relevant_qids: set[str] = set(existing_relevant_qids)
    queue: deque[str] = deque()
    emitted = 0

    for seed_qid in sorted(seed_qids):
        if seed_qid not in qid_to_core_class:
            continue
        if seed_qid not in relevant_qids:
            write_relevance_assigned_event(
                repo_root,
                entity_qid=seed_qid,
                relevant=True,
                assignment_type="seed",
                relevant_seed_source="listed_broadcasting_program",
                relevance_first_assigned_at="",
                is_core_class_instance=True,
            )
            mark_item_relevant(
                repo_root,
                qid=seed_qid,
                relevant_seed_source="listed_broadcasting_program",
                relevance_first_assigned_at="",
            )
            emitted += 1
        if seed_qid not in relevant_qids:
            relevant_qids.add(seed_qid)
            queue.append(seed_qid)

    for qid in sorted(existing_relevant_qids):
        queue.append(qid)

    seen_for_propagation: set[str] = set()
    while queue:
        source_qid = canonical_qid(queue.popleft())
        if not source_qid or source_qid in seen_for_propagation:
            continue
        seen_for_propagation.add(source_qid)

        for edge in outgoing_by_source.get(source_qid, []):
            context = edge.get("context")
            if not isinstance(context, tuple) or tuple(context) not in approved_contexts:
                continue

            target_qid = canonical_qid(str(edge.get("target_qid", "") or ""))
            property_qid = canonical_pid(str(edge.get("property_qid", "") or ""))
            direction = str(edge.get("direction", "") or "")
            if not target_qid or not property_qid or target_qid in relevant_qids:
                continue
            target_is_class_node = target_qid in class_node_ids
            if target_qid not in qid_to_core_class and not target_is_class_node:
                continue

            write_relevance_assigned_event(
                repo_root,
                entity_qid=target_qid,
                relevant=True,
                assignment_type="inherited",
                relevant_seed_source="",
                relevance_first_assigned_at="",
                relevance_inherited_from_qid=source_qid,
                relevance_inherited_via_property_qid=property_qid,
                relevance_inherited_via_direction=direction,
                is_core_class_instance=not target_is_class_node,
            )
            mark_item_relevant(
                repo_root,
                qid=target_qid,
                relevant_seed_source="",
                relevance_first_assigned_at="",
                relevance_inherited_from_qid=source_qid,
                relevance_inherited_via_property_qid=property_qid,
                relevance_inherited_via_direction=direction,
            )
            emitted += 1
            relevant_qids.add(target_qid)
            queue.append(target_qid)

    flush_node_store(repo_root)

    return RelevancyBootstrapResult(
        relation_context_rows=int(len(relation_context_df)),
        newly_emitted_relevancy_events=int(emitted),
        final_relevant_qids=int(len(relevant_qids)),
    )
