from __future__ import annotations

import json
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .cache import _atomic_write_text
from .common import canonical_pid, canonical_qid
from .schemas import build_artifact_paths


_ENTITY_STORE_CACHE: dict[str, dict] = {}
_PROPERTY_STORE_CACHE: dict[str, dict] = {}
_ENTITY_STORE_DIRTY: set[str] = set()
_PROPERTY_STORE_DIRTY: set[str] = set()
_LOOKUP_INDEX_CACHE: dict[str, dict[str, dict]] = {}
_LOOKUP_INDEX_CACHE_MTIME: dict[str, float] = {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _recovery_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".recovery")


def _normalize_store_payload(payload: object, root_key: str) -> dict:
    if not isinstance(payload, dict):
        return {root_key: {}}
    normalized = dict(payload)
    if root_key not in normalized or not isinstance(normalized[root_key], dict):
        normalized[root_key] = {}
    return normalized


def _apply_recovery_if_present(path: Path, root_key: str) -> None:
    recovery = _recovery_path(path)
    if not recovery.exists():
        return

    try:
        recovery_payload = json.loads(recovery.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Found recovery file at {recovery}, but it is not readable JSON. "
            "Stop and inspect manually before continuing."
        ) from exc

    if isinstance(recovery_payload, dict) and isinstance(recovery_payload.get("text"), str):
        recovered_text = str(recovery_payload.get("text", "") or "")
        if not recovered_text:
            raise RuntimeError(
                f"Found recovery file at {recovery}, but no stored text payload was present. "
                "Stop and inspect manually before continuing."
            )
        try:
            recovered_store_raw = json.loads(recovered_text)
        except Exception as exc:
            raise RuntimeError(
                f"Found recovery file at {recovery}, but stored text is not valid JSON. "
                "Stop and inspect manually before continuing."
            ) from exc
    else:
        # Shared io_guardrails recovery snapshots store the target payload directly.
        recovered_store_raw = recovery_payload

    recovered_store = _normalize_store_payload(recovered_store_raw, root_key)
    current_store = _normalize_store_payload(
        json.loads(path.read_text(encoding="utf-8")) if path.exists() else {},
        root_key,
    )

    merged = dict(current_store)
    merged[root_key] = {
        **current_store.get(root_key, {}),
        **recovered_store.get(root_key, {}),
    }
    merged.setdefault("recovery_merge", {})
    if not isinstance(merged["recovery_merge"], dict):
        merged["recovery_merge"] = {}
    merged["recovery_merge"].update(
        {
            "last_merge_at_utc": _iso_now(),
            "last_merge_source": str(recovery),
        }
    )

    _atomic_write_text(path, json.dumps(merged, ensure_ascii=False, indent=2))
    recovery.unlink()


def _load_json(path: Path, root_key: str) -> dict:
    _apply_recovery_if_present(path, root_key)
    if not path.exists():
        return {root_key: {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {root_key: {}}
    if not isinstance(payload, dict):
        return {root_key: {}}
    if root_key not in payload or not isinstance(payload[root_key], dict):
        payload[root_key] = {}
    return payload


def _entity_minimal(entity_doc: dict) -> dict:
    claims = entity_doc.get("claims", {})
    return {
        "id": entity_doc.get("id", ""),
        "labels": entity_doc.get("labels", {}),
        "descriptions": entity_doc.get("descriptions", {}),
        "aliases": entity_doc.get("aliases", {}),
        "claims": {
            "P31": claims.get("P31", []) or [],
            "P279": claims.get("P279", []) or [],
        },
    }


def _property_minimal(property_doc: dict) -> dict:
    claims = property_doc.get("claims", {})
    return {
        "id": property_doc.get("id", ""),
        "labels": property_doc.get("labels", {}),
        "descriptions": property_doc.get("descriptions", {}),
        "aliases": property_doc.get("aliases", {}),
        "claims": {
            "P31": claims.get("P31", []) or [],
            "P1647": claims.get("P1647", []) or [],
        },
    }


def _append_unique_timestamp(current: dict, field: str, timestamp_utc: str) -> list[str]:
    values = list(current.get(field, []) or [])
    if timestamp_utc and timestamp_utc not in values:
        values.append(timestamp_utc)
    return sorted(values)


def _store_cache_key(path: Path) -> str:
    return str(Path(path).resolve())


def _cached_store(path: Path, root_key: str, cache: dict[str, dict]) -> dict:
    cache_key = _store_cache_key(path)
    store = cache.get(cache_key)
    if store is None:
        store = _load_json(path, root_key)
        cache[cache_key] = store
    return store


def _mark_store_dirty(path: Path, dirty: set[str]) -> None:
    dirty.add(_store_cache_key(path))


def _flush_store(path: Path, cache: dict[str, dict], dirty: set[str]) -> None:
    cache_key = _store_cache_key(path)
    if cache_key not in dirty:
        return
    store = cache.get(cache_key)
    if store is None:
        return
    _atomic_write_text(path, json.dumps(store, ensure_ascii=False, indent=2))
    dirty.discard(cache_key)


def flush_node_store(repo_root: Path) -> None:
    paths = build_artifact_paths(Path(repo_root))
    flush_entity_store(paths.entity_store_jsonl)
    flush_property_store(paths.property_store_jsonl)


def flush_entity_store(path: Path) -> None:
    flush_path = Path(path)
    _flush_store(flush_path, _ENTITY_STORE_CACHE, _ENTITY_STORE_DIRTY)


def flush_property_store(path: Path) -> None:
    flush_path = Path(path)
    _flush_store(flush_path, _PROPERTY_STORE_CACHE, _PROPERTY_STORE_DIRTY)


def reset_node_store_cache(repo_root: Path | None = None) -> None:
    if repo_root is None:
        _ENTITY_STORE_CACHE.clear()
        _PROPERTY_STORE_CACHE.clear()
        _ENTITY_STORE_DIRTY.clear()
        _PROPERTY_STORE_DIRTY.clear()
        _LOOKUP_INDEX_CACHE.clear()
        _LOOKUP_INDEX_CACHE_MTIME.clear()
        return
    paths = build_artifact_paths(Path(repo_root))
    for path in (
        paths.entity_store_jsonl,
        paths.property_store_jsonl,
    ):
        cache_key = _store_cache_key(path)
        _ENTITY_STORE_CACHE.pop(cache_key, None)
        _PROPERTY_STORE_CACHE.pop(cache_key, None)
        _ENTITY_STORE_DIRTY.discard(cache_key)
        _PROPERTY_STORE_DIRTY.discard(cache_key)
    lookup_key = _store_cache_key(paths.entity_lookup_index_csv)
    _LOOKUP_INDEX_CACHE.pop(lookup_key, None)
    _LOOKUP_INDEX_CACHE_MTIME.pop(lookup_key, None)


def _load_lookup_index(paths) -> dict[str, dict]:
    index_path = paths.entity_lookup_index_csv
    if not index_path.exists() or index_path.stat().st_size == 0:
        return {}
    cache_key = _store_cache_key(index_path)
    mtime = float(index_path.stat().st_mtime)
    cached_mtime = _LOOKUP_INDEX_CACHE_MTIME.get(cache_key)
    if cached_mtime is not None and cached_mtime == mtime and cache_key in _LOOKUP_INDEX_CACHE:
        return _LOOKUP_INDEX_CACHE[cache_key]

    rows: dict[str, dict] = {}
    with index_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            qid = canonical_qid(str(row.get("qid", "") or ""))
            if not qid:
                continue
            rows[qid] = dict(row)
    _LOOKUP_INDEX_CACHE[cache_key] = rows
    _LOOKUP_INDEX_CACHE_MTIME[cache_key] = mtime
    return rows


def _lookup_chunk_item(repo_root: Path, qid: str) -> dict | None:
    paths = build_artifact_paths(Path(repo_root))
    qid_norm = canonical_qid(qid)
    if not qid_norm:
        return None
    index = _load_lookup_index(paths)
    row = index.get(qid_norm)
    if not row:
        return None

    return _chunk_entity_from_index_row(paths, row)


def _chunk_entity_from_index_row(paths, row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None

    chunk_file = str(row.get("chunk_file", "") or "").strip()
    if not chunk_file:
        return None
    chunk_path = paths.entity_chunks_dir / chunk_file
    if not chunk_path.exists():
        return None

    try:
        byte_offset = int(str(row.get("byte_offset", "") or "0"))
        byte_length = int(str(row.get("byte_length", "") or "0"))
    except Exception:
        return None
    if byte_offset < 0 or byte_length <= 0:
        return None

    try:
        with chunk_path.open("rb") as f:
            f.seek(byte_offset)
            payload_bytes = f.read(byte_length)
    except Exception:
        return None
    if not payload_bytes:
        return None

    try:
        record = json.loads(payload_bytes.decode("utf-8").strip())
    except Exception:
        return None
    if not isinstance(record, dict):
        return None
    entity = record.get("entity")
    if isinstance(entity, dict):
        return entity
    return None


def upsert_discovered_item(repo_root: Path, qid: str, entity_doc: dict, discovered_at_utc: str) -> None:
    paths = build_artifact_paths(Path(repo_root))
    store = _cached_store(paths.entity_store_jsonl, "entities", _ENTITY_STORE_CACHE)
    qid = canonical_qid(qid)
    if not qid:
        return

    current = store["entities"].get(qid, {})
    minimal = _entity_minimal(entity_doc)
    # Refresh core discovery fields while preserving expansion metadata.
    merged = {**current, **minimal}
    merged["id"] = qid
    merged["discovered_at_utc"] = current.get("discovered_at_utc") or discovered_at_utc
    merged["discovered_at_utc_history"] = _append_unique_timestamp(current, "discovered_at_utc_history", discovered_at_utc)
    if "expanded_at_utc" in current:
        merged["expanded_at_utc"] = current.get("expanded_at_utc")
    if "expanded_at_utc_history" in current:
        merged["expanded_at_utc_history"] = list(current.get("expanded_at_utc_history", []) or [])
    merged.setdefault("expanded_at_utc", None)
    store["entities"][qid] = merged
    _mark_store_dirty(paths.entity_store_jsonl, _ENTITY_STORE_DIRTY)


def upsert_expanded_item(repo_root: Path, qid: str, expanded_payload: dict, expanded_at_utc: str) -> None:
    paths = build_artifact_paths(Path(repo_root))
    store = _cached_store(paths.entity_store_jsonl, "entities", _ENTITY_STORE_CACHE)
    qid = canonical_qid(qid)
    if not qid:
        return

    current = store["entities"].get(qid, {})
    merged = {**current, **expanded_payload}
    merged["id"] = qid
    merged["expanded_at_utc"] = expanded_at_utc
    merged["expanded_at_utc_history"] = _append_unique_timestamp(current, "expanded_at_utc_history", expanded_at_utc)
    merged["discovered_at_utc"] = current.get("discovered_at_utc") or expanded_at_utc
    merged["discovered_at_utc_history"] = _append_unique_timestamp(current, "discovered_at_utc_history", merged["discovered_at_utc"])
    store["entities"][qid] = merged
    _mark_store_dirty(paths.entity_store_jsonl, _ENTITY_STORE_DIRTY)


def upsert_discovered_property(repo_root: Path, pid: str, property_doc: dict, discovered_at_utc: str) -> None:
    paths = build_artifact_paths(Path(repo_root))
    store = _cached_store(paths.property_store_jsonl, "properties", _PROPERTY_STORE_CACHE)
    pid = canonical_pid(pid)
    if not pid:
        return

    current = store["properties"].get(pid, {})
    minimal = _property_minimal(property_doc)
    merged = {**minimal, **current}
    merged["id"] = pid
    merged["discovered_at_utc"] = current.get("discovered_at_utc") or discovered_at_utc
    merged["discovered_at_utc_history"] = _append_unique_timestamp(current, "discovered_at_utc_history", discovered_at_utc)
    store["properties"][pid] = merged
    _mark_store_dirty(paths.property_store_jsonl, _PROPERTY_STORE_DIRTY)


def get_item(repo_root: Path, qid: str) -> dict | None:
    paths = build_artifact_paths(Path(repo_root))
    store = _cached_store(paths.entity_store_jsonl, "entities", _ENTITY_STORE_CACHE)
    qid_norm = canonical_qid(qid)
    if not qid_norm:
        return None
    in_store = store["entities"].get(qid_norm)
    if in_store is not None:
        return in_store
    return _lookup_chunk_item(repo_root, qid_norm)


def iter_items(repo_root: Path) -> Iterator[dict]:
    paths = build_artifact_paths(Path(repo_root))
    store = _cached_store(paths.entity_store_jsonl, "entities", _ENTITY_STORE_CACHE)
    if store["entities"]:
        for qid in sorted(store["entities"]):
            yield store["entities"][qid]
        return

    index = _load_lookup_index(paths)
    for qid in sorted(index):
        entity = _chunk_entity_from_index_row(paths, index[qid])
        if isinstance(entity, dict) and entity:
            yield entity


def iter_properties(repo_root: Path) -> Iterator[dict]:
    paths = build_artifact_paths(Path(repo_root))
    store = _cached_store(paths.property_store_jsonl, "properties", _PROPERTY_STORE_CACHE)
    for pid in sorted(store["properties"]):
        yield store["properties"][pid]
