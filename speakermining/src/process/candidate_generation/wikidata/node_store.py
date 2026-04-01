from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .cache import _atomic_write_text
from .common import canonical_pid, canonical_qid
from .schemas import build_artifact_paths


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

    if not isinstance(recovery_payload, dict):
        raise RuntimeError(
            f"Found recovery file at {recovery}, but content format is invalid. "
            "Stop and inspect manually before continuing."
        )

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


def upsert_discovered_item(repo_root: Path, qid: str, entity_doc: dict, discovered_at_utc: str) -> None:
    paths = build_artifact_paths(Path(repo_root))
    store = _load_json(paths.entities_json, "entities")
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
    _atomic_write_text(paths.entities_json, json.dumps(store, ensure_ascii=False, indent=2))


def upsert_expanded_item(repo_root: Path, qid: str, expanded_payload: dict, expanded_at_utc: str) -> None:
    paths = build_artifact_paths(Path(repo_root))
    store = _load_json(paths.entities_json, "entities")
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
    _atomic_write_text(paths.entities_json, json.dumps(store, ensure_ascii=False, indent=2))


def upsert_discovered_property(repo_root: Path, pid: str, property_doc: dict, discovered_at_utc: str) -> None:
    paths = build_artifact_paths(Path(repo_root))
    store = _load_json(paths.properties_json, "properties")
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
    _atomic_write_text(paths.properties_json, json.dumps(store, ensure_ascii=False, indent=2))


def get_item(repo_root: Path, qid: str) -> dict | None:
    paths = build_artifact_paths(Path(repo_root))
    store = _load_json(paths.entities_json, "entities")
    return store["entities"].get(canonical_qid(qid))


def iter_items(repo_root: Path) -> Iterator[dict]:
    paths = build_artifact_paths(Path(repo_root))
    store = _load_json(paths.entities_json, "entities")
    for qid in sorted(store["entities"]):
        yield store["entities"][qid]


def iter_properties(repo_root: Path) -> Iterator[dict]:
    paths = build_artifact_paths(Path(repo_root))
    store = _load_json(paths.properties_json, "properties")
    for pid in sorted(store["properties"]):
        yield store["properties"][pid]
