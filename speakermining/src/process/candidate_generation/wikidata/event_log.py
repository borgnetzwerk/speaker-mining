from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .event_writer import get_event_store
from .schemas import SOURCE_STEPS


_EVENT_TYPES = {
    # Infrastructure
    "query_response",
    "candidate_matched",
    # v3 domain events (kept for backward-compatible log replay)
    "entity_expanded",
    "expansion_decision",
    "class_membership_resolved",
    "eligibility_transition",
    "relevance_assigned",
    # v4 domain events
    "entity_discovered",
    "triple_discovered",
    "entity_fetched",
    "entity_basic_fetched",
    "class_resolved",
    "entity_marked_relevant",
    "fetch_decision",
    "rule_changed",
    # v4 external reader events
    "seed_registered",
    "core_class_registered",
    "full_fetch_rule_registered",
    "entity_rewired",
}
_ENDPOINTS = {"wikidata_api", "wikidata_sparql", "derived_local"}
_STATUSES = {"success", "cache_hit", "http_error", "timeout", "fallback_cache", "not_found", "skipped"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_query_descriptor(descriptor: str) -> str:
    return " ".join(str(descriptor or "").split())


def compute_query_hash(endpoint: str, normalized_query: str) -> str:
    raw = f"{endpoint}|{normalized_query}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def build_query_event(
    *,
    endpoint: str,
    normalized_query: str,
    source_step: str,
    status: str,
    key: str,
    payload: dict,
    http_status: int | None,
    error: str | None,
    event_type: str = "query_response",
    timestamp_utc: str | None = None,
) -> dict:
    normalized_query = normalize_query_descriptor(normalized_query)
    if event_type not in _EVENT_TYPES:
        raise ValueError(f"Unsupported event_type: {event_type}")
    if endpoint not in _ENDPOINTS:
        raise ValueError(f"Unsupported endpoint: {endpoint}")
    if status not in _STATUSES:
        raise ValueError(f"Unsupported status: {status}")
    if source_step not in SOURCE_STEPS:
        raise ValueError(f"Unsupported source_step: {source_step}")

    return {
        "event_version": "v3",
        "event_type": event_type,
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "endpoint": endpoint,
            "normalized_query": normalized_query,
            "query_hash": compute_query_hash(endpoint, normalized_query),
            "source_step": str(source_step or ""),
            "status": status,
            "key": str(key or ""),
            "http_status": http_status,
            "error": error,
            "response_data": payload if isinstance(payload, dict) else {},
        },
    }


def build_entity_discovered_event(
    *,
    qid: str,
    label: str,
    source_step: str,
    discovery_method: str = "seed",
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build an entity_discovered domain event.
    
    Emitted when a new entity is first encountered in the expansion process.
    
    Args:
        qid: The Wikidata QID identifier (e.g., "Q123")
        label: Human-readable label for the entity
        source_step: Where this discovery occurred (entity_fetch, inlinks_fetch, outlinks_build, etc.)
        discovery_method: How entity was discovered (seed, inlink, outlink, fallback_match, etc.)
        payload: Additional context (entity type, description, claims count, etc.)
        timestamp_utc: ISO 8601 timestamp; defaults to now
    
    Returns:
        Dict ready to emit via event_emitter or append_event
    """
    return {
        "event_version": "v3",
        "event_type": "entity_discovered",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
            "source_step": str(source_step or ""),
            "discovery_method": str(discovery_method or "unknown"),
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_entity_expanded_event(
    *,
    qid: str,
    label: str,
    expansion_type: str,
    inlink_count: int = 0,
    outlink_count: int = 0,
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build an entity_expanded domain event.
    
    Emitted when an entity's neighborhood (inlinks, outlinks, properties) is fetched/expanded.
    
    Args:
        qid: The Wikidata QID
        label: Human-readable label
        expansion_type: Type of expansion performed (inlinks, outlinks, properties, triple_expansion, etc.)
        inlink_count: Number of inlinks fetched (if applicable)
        outlink_count: Number of outlinks fetched (if applicable)
        payload: Additional context (e.g., expansion duration, result summary)
        timestamp_utc: ISO 8601 timestamp
    
    Returns:
        Dict ready to emit
    """
    return {
        "event_version": "v3",
        "event_type": "entity_expanded",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
            "expansion_type": str(expansion_type or ""),
            "inlink_count": int(inlink_count or 0),
            "outlink_count": int(outlink_count or 0),
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_expansion_decision_event(
    *,
    qid: str,
    label: str,
    decision: str,
    decision_reason: str = "",
    eligibility: dict | None = None,
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build an expansion_decision domain event.
    
    Emitted when a decision is made about whether to proceed with further expansion of an entity.
    Examples: queue_seed, queue_for_expansion, mark_seed_complete, skip_expansion, mark_budget_exhausted.
    
    Args:
        qid: The Wikidata QID
        label: Human-readable label
        decision: The decision made (queue_seed, queue_for_expansion, mark_complete, skip, mark_budget_exhausted, etc.)
        decision_reason: Why the decision was made (e.g., "budget_exhausted", "already_expanded", "not_person", etc.)
        eligibility: Dict with eligibility criteria and scores (e.g., {is_person: True, score: 0.95})
        payload: Additional context
        timestamp_utc: ISO 8601 timestamp
    
    Returns:
        Dict ready to emit
    """
    return {
        "event_version": "v3",
        "event_type": "expansion_decision",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
            "decision": str(decision or ""),
            "decision_reason": str(decision_reason or ""),
            "eligibility": eligibility if isinstance(eligibility, dict) else {},
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_triple_discovered_event(
    *,
    subject_qid: str,
    predicate_pid: str,
    object_qid: str,
    source_step: str,
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build a triple_discovered domain event.

    Emitted when a new triple edge (subject-predicate-object) is discovered and persisted.
    """
    return {
        "event_version": "v3",
        "event_type": "triple_discovered",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "subject_qid": str(subject_qid or ""),
            "predicate_pid": str(predicate_pid or ""),
            "object_qid": str(object_qid or ""),
            "source_step": str(source_step or ""),
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_class_membership_resolved_event(
    *,
    entity_qid: str,
    class_id: str,
    path_to_core_class: str,
    subclass_of_core_class: bool,
    is_class_node: bool,
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build a class_membership_resolved domain event.

    Emitted when class resolution for an entity is evaluated to support eligibility decisions.
    """
    return {
        "event_version": "v3",
        "event_type": "class_membership_resolved",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "entity_qid": str(entity_qid or ""),
            "class_id": str(class_id or ""),
            "path_to_core_class": str(path_to_core_class or ""),
            "subclass_of_core_class": bool(subclass_of_core_class),
            "is_class_node": bool(is_class_node),
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_eligibility_transition_event(
    *,
    entity_qid: str,
    previous_eligible: bool,
    current_eligible: bool,
    previous_reason: str,
    current_reason: str,
    path_to_core_class: str,
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build an eligibility_transition domain event.

    Emitted when node integrity reclassifies an entity eligibility state.
    """
    return {
        "event_version": "v3",
        "event_type": "eligibility_transition",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "entity_qid": str(entity_qid or ""),
            "previous_eligible": bool(previous_eligible),
            "current_eligible": bool(current_eligible),
            "previous_reason": str(previous_reason or ""),
            "current_reason": str(current_reason or ""),
            "path_to_core_class": str(path_to_core_class or ""),
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_relevance_assigned_event(
    *,
    entity_qid: str,
    relevant: bool,
    assignment_type: str,
    relevant_seed_source: str = "",
    relevance_first_assigned_at: str | None = None,
    relevance_inherited_from_qid: str = "",
    relevance_inherited_via_property_qid: str = "",
    relevance_inherited_via_direction: str = "",
    is_core_class_instance: bool = True,
    payload: dict | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    """Build a relevance_assigned domain event.

    Emitted when an entity gains relevance (monotonic false->true only).
    """
    return {
        "event_version": "v3",
        "event_type": "relevance_assigned",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "entity_qid": str(entity_qid or ""),
            "relevant": bool(relevant),
            "assignment_type": str(assignment_type or ""),
            "relevant_seed_source": str(relevant_seed_source or ""),
            "relevance_first_assigned_at": str(relevance_first_assigned_at or timestamp_utc or _iso_now()),
            "relevance_inherited_from_qid": str(relevance_inherited_from_qid or ""),
            "relevance_inherited_via_property_qid": str(relevance_inherited_via_property_qid or ""),
            "relevance_inherited_via_direction": str(relevance_inherited_via_direction or ""),
            "is_core_class_instance": bool(is_core_class_instance),
            **(payload if isinstance(payload, dict) else {}),
        },
    }


def build_entity_fetched_event(
    *,
    qid: str,
    label: str,
    depth: int,
    triple_count: int = 0,
    description: str = "",
    aliases: list | None = None,
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "entity_fetched",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
            "description": str(description or ""),
            "aliases": list(aliases or []),
            "depth": int(depth),
            "triple_count": int(triple_count),
        },
    }


def build_entity_basic_fetched_event(
    *,
    qid: str,
    label: str,
    p31_qids: list[str],
    p279_qids: list[str],
    source: str = "network",
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "entity_basic_fetched",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
            "p31_qids": list(p31_qids or []),
            "p279_qids": list(p279_qids or []),
            "source": str(source),
        },
    }


def build_class_resolved_event(
    *,
    class_qid: str,
    parent_qids: list[str],
    depth: int,
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "class_resolved",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "class_qid": str(class_qid or ""),
            "parent_qids": list(parent_qids or []),
            "depth": int(depth),
        },
    }


def build_entity_marked_relevant_event(
    *,
    qid: str,
    core_class_qid: str = "",
    via_rule: str = "",
    source_seed_qid: str = "",
    inherited_from_qid: str = "",
    inherited_via_pid: str = "",
    direction: str = "",
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "entity_marked_relevant",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "core_class_qid": str(core_class_qid or ""),
            "via_rule": str(via_rule or ""),
            "source_seed_qid": str(source_seed_qid or ""),
            "inherited_from_qid": str(inherited_from_qid or ""),
            "inherited_via_pid": str(inherited_via_pid or ""),
            "direction": str(direction or ""),
        },
    }


def build_fetch_decision_event(
    *,
    qid: str,
    decision: str,
    reason: str = "",
    depth: int = 0,
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "fetch_decision",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "decision": str(decision or ""),
            "reason": str(reason or ""),
            "depth": int(depth),
        },
    }


def build_rule_changed_event(
    *,
    rule_file: str,
    rule_hash: str,
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "rule_changed",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "rule_file": str(rule_file or ""),
            "rule_hash": str(rule_hash or ""),
        },
    }


def build_seed_registered_event(
    *,
    qid: str,
    label: str = "",
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "seed_registered",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
        },
    }


def build_core_class_registered_event(
    *,
    qid: str,
    label: str = "",
    projection_mode: str = "instances",
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "core_class_registered",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "qid": str(qid or ""),
            "label": str(label or ""),
            "projection_mode": str(projection_mode or "instances"),
        },
    }


def build_entity_rewired_event(
    *,
    subject_qid: str,
    predicate_pid: str,
    object_qid: str,
    rule: str = "add",
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "entity_rewired",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "subject_qid": str(subject_qid or ""),
            "predicate_pid": str(predicate_pid or ""),
            "object_qid": str(object_qid or ""),
            "rule": str(rule or "add"),
        },
    }


def build_full_fetch_rule_registered_event(
    *,
    rule_type: str,
    group_id: int,
    subject: str,
    predicate: str,
    object: str,
    note: str = "",
    timestamp_utc: str | None = None,
) -> dict:
    return {
        "event_version": "v4",
        "event_type": "full_fetch_rule_registered",
        "timestamp_utc": timestamp_utc or _iso_now(),
        "payload": {
            "rule_type": str(rule_type or ""),
            "group_id": int(group_id),
            "subject": str(subject or ""),
            "predicate": str(predicate or ""),
            "object": str(object or ""),
            "note": str(note or ""),
        },
    }


def _query_payload(event: dict) -> dict:
    payload = event.get("payload", {}) if isinstance(event, dict) else {}
    return payload if isinstance(payload, dict) else {}


def get_query_event_field(event: dict, field_name: str, default=None):
    payload = _query_payload(event)
    if field_name in payload:
        return payload.get(field_name)
    return event.get(field_name, default) if isinstance(event, dict) else default


def get_query_event_response_data(event: dict) -> dict:
    payload = _query_payload(event)
    response_data = payload.get("response_data")
    if isinstance(response_data, dict):
        return response_data
    return payload


def _chunks_dir(repo_root: Path) -> Path:
    return Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "chunks"


def _iter_jsonl_events(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                break
            if isinstance(payload, dict):
                yield payload


def _chunk_id_fallback(path: Path) -> str:
    return f"chunk_{path.stem}"


def _read_first_jsonl_event(path: Path) -> dict | None:
    """Return the first valid JSON object in a JSONL file. O(1) — reads only until first event."""
    try:
        with path.open("r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return None


def _read_last_jsonl_event(path: Path) -> dict | None:
    """Return the last valid JSON object in a JSONL file. O(1) — reads final 4 KB only."""
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            if size == 0:
                return None
            f.seek(max(0, size - 4096))
            tail = f.read().decode("utf-8", errors="replace")
        for line in reversed(tail.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return None


def _chunk_boundary_summary(path: Path) -> dict:
    """Return chunk metadata by reading only the first and last events. O(1) per chunk."""
    chunk_id = _chunk_id_fallback(path)
    prev_chunk_id = ""
    next_chunk_id = ""
    first_sequence = 0

    first_event = _read_first_jsonl_event(path)
    if isinstance(first_event, dict):
        seq = first_event.get("sequence_num")
        if isinstance(seq, int):
            first_sequence = seq
        if first_event.get("event_type") == "eventstore_opened":
            payload = first_event.get("payload", {}) or {}
            chunk_id = str(payload.get("chunk_id") or chunk_id)
            prev_chunk_id = str(payload.get("prev_chunk_id") or "")

    last_event = _read_last_jsonl_event(path)
    if isinstance(last_event, dict) and last_event.get("event_type") == "eventstore_closed":
        payload = last_event.get("payload", {}) or {}
        chunk_id = str(payload.get("chunk_id") or chunk_id)
        next_chunk_id = str(payload.get("next_chunk_id") or "")

    return {
        "path": path,
        "chunk_id": chunk_id,
        "prev_chunk_id": prev_chunk_id,
        "next_chunk_id": next_chunk_id,
        "first_sequence": first_sequence,
    }


def _canonical_chunk_paths(repo_root: Path) -> list[Path]:
    chunks_dir = _chunks_dir(Path(repo_root))
    if not chunks_dir.exists():
        return []

    infos = [_chunk_boundary_summary(path) for path in sorted(chunks_dir.glob("*.jsonl"))]
    if not infos:
        return []

    by_chunk_id = {str(info["chunk_id"]): info for info in infos}

    start_candidates = [
        info
        for info in infos
        if not info["prev_chunk_id"] or str(info["prev_chunk_id"]) not in by_chunk_id
    ]
    if start_candidates:
        current = min(start_candidates, key=lambda row: (int(row["first_sequence"]), str(row["chunk_id"])))
    else:
        current = min(infos, key=lambda row: (int(row["first_sequence"]), str(row["chunk_id"])))

    ordered: list[Path] = []
    visited: set[str] = set()

    while current:
        chunk_id = str(current["chunk_id"])
        if chunk_id in visited:
            break
        visited.add(chunk_id)
        ordered.append(current["path"])
        next_chunk_id = str(current["next_chunk_id"] or "")
        if not next_chunk_id:
            break
        current = by_chunk_id.get(next_chunk_id)

    for info in sorted(infos, key=lambda row: (int(row["first_sequence"]), str(row["chunk_id"]))):
        chunk_id = str(info["chunk_id"])
        if chunk_id in visited:
            continue
        ordered.append(info["path"])

    return ordered


def iter_all_events(repo_root: Path):
    for chunk_path in _canonical_chunk_paths(Path(repo_root)):
        for event in _iter_jsonl_events(chunk_path):
            yield event


def iter_events_from(repo_root: Path, from_sequence: int):
    """Yield all events with sequence_num >= from_sequence, skipping earlier chunks.

    F3 fix: _chunk_boundary_summary now reads only first+last lines (O(1) per chunk),
    and chunks whose next sibling starts at or below from_sequence are skipped entirely.
    This reduces replay cost from O(total events) to O(relevant chunk events).
    """
    if from_sequence <= 0:
        yield from iter_all_events(repo_root)
        return

    repo_root = Path(repo_root)
    chunks_dir = _chunks_dir(repo_root)
    if not chunks_dir.exists():
        return

    infos = [_chunk_boundary_summary(p) for p in sorted(chunks_dir.glob("*.jsonl"))]
    if not infos:
        return

    # Order infos using the same linked-list logic as _canonical_chunk_paths,
    # but without re-reading chunk files (infos already have all required fields).
    by_chunk_id = {str(info["chunk_id"]): info for info in infos}
    start_candidates = [i for i in infos if not i["prev_chunk_id"] or i["prev_chunk_id"] not in by_chunk_id]
    current = min(start_candidates or infos, key=lambda r: (r["first_sequence"], r["chunk_id"]))

    ordered: list[dict] = []
    visited: set[str] = set()
    while current:
        cid = str(current["chunk_id"])
        if cid in visited:
            break
        visited.add(cid)
        ordered.append(current)
        nxt = str(current["next_chunk_id"] or "")
        if not nxt:
            break
        current = by_chunk_id.get(nxt)

    for info in sorted(infos, key=lambda r: (r["first_sequence"], r["chunk_id"])):
        if str(info["chunk_id"]) not in visited:
            ordered.append(info)

    for i, info in enumerate(ordered):
        # Skip chunk if next chunk starts at or before from_sequence —
        # every event in this chunk has seq < from_sequence.
        if i + 1 < len(ordered) and ordered[i + 1]["first_sequence"] <= from_sequence:
            continue
        for event in _iter_jsonl_events(info["path"]):
            seq = event.get("sequence_num")
            if isinstance(seq, int) and seq >= from_sequence:
                yield event


def iter_query_events(repo_root: Path):
    for event in iter_all_events(Path(repo_root)):
        if event.get("event_type") == "query_response":
            yield event


def write_query_event(
    repo_root: Path,
    *,
    endpoint: str,
    normalized_query: str,
    source_step: str,
    status: str,
    key: str,
    payload: dict,
    http_status: int | None,
    error: str | None,
) -> Path:
    event = build_query_event(
        endpoint=endpoint,
        normalized_query=normalized_query,
        source_step=source_step,
        status=status,
        key=key,
        payload=payload,
        http_status=http_status,
        error=error,
    )
    store = get_event_store(Path(repo_root))
    store.append_event(event)
    from .cache import _remember_latest_cached_record
    from .query_inventory import remember_query_inventory_record

    _remember_latest_cached_record(Path(repo_root), event, force=True)
    remember_query_inventory_record(Path(repo_root), event)
    return store.active_chunk_path


def write_candidate_matched_event(
    repo_root: Path,
    *,
    mention_id: str,
    mention_type: str,
    mention_label: str,
    candidate_id: str,
    candidate_label: str,
    source: str,
    context: str | None = None,
) -> Path:
    """Emit a candidate_matched event when fallback matching finds a candidate."""
    event = {
        "event_version": "v3",
        "event_type": "candidate_matched",
        "timestamp_utc": _iso_now(),
        "payload": {
            "mention_id": str(mention_id or ""),
            "mention_type": str(mention_type or ""),
            "mention_label": str(mention_label or ""),
            "candidate_id": str(candidate_id or ""),
            "candidate_label": str(candidate_label or ""),
            "source": str(source or ""),
            "context": str(context or ""),
        },
    }
    store = get_event_store(Path(repo_root))
    store.append_event(event)
    return store.active_chunk_path


def write_relevance_assigned_event(
    repo_root: Path,
    *,
    entity_qid: str,
    relevant: bool,
    assignment_type: str,
    relevant_seed_source: str = "",
    relevance_first_assigned_at: str | None = None,
    relevance_inherited_from_qid: str = "",
    relevance_inherited_via_property_qid: str = "",
    relevance_inherited_via_direction: str = "",
    is_core_class_instance: bool = True,
    payload: dict | None = None,
) -> Path:
    event = build_relevance_assigned_event(
        entity_qid=entity_qid,
        relevant=relevant,
        assignment_type=assignment_type,
        relevant_seed_source=relevant_seed_source,
        relevance_first_assigned_at=relevance_first_assigned_at,
        relevance_inherited_from_qid=relevance_inherited_from_qid,
        relevance_inherited_via_property_qid=relevance_inherited_via_property_qid,
        relevance_inherited_via_direction=relevance_inherited_via_direction,
        is_core_class_instance=is_core_class_instance,
        payload=payload,
    )
    store = get_event_store(Path(repo_root))
    store.append_event(event)
    return store.active_chunk_path


def list_query_events(repo_root: Path) -> list[Path]:
    chunks_dir = _chunks_dir(Path(repo_root))
    if not chunks_dir.exists():
        return []
    return sorted(chunks_dir.glob("*.jsonl"))


def read_query_event(path: Path, sequence_num: int | None = None) -> dict:
    if sequence_num is not None:
        for event in _iter_jsonl_events(Path(path)):
            if event.get("event_type") != "query_response":
                continue
            if event.get("sequence_num") == sequence_num:
                return event
        raise ValueError(f"query_response with sequence_num={sequence_num} not found in {path}")

    for event in _iter_jsonl_events(Path(path)):
        if event.get("event_type") == "query_response":
            return event
    raise ValueError(f"No query_response event found in {path}")
