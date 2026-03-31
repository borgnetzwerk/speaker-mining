from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .cache import _atomic_write_text
from .schemas import SOURCE_STEPS, build_artifact_paths


_EVENT_TYPES = {"query_response"}
_ENDPOINTS = {"wikidata_api", "wikidata_sparql", "derived_local"}
_STATUSES = {"success", "cache_hit", "http_error", "timeout", "fallback_cache"}


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
        "event_version": "v2",
        "event_type": event_type,
        "endpoint": endpoint,
        "normalized_query": normalized_query,
        "query_hash": compute_query_hash(endpoint, normalized_query),
        "timestamp_utc": timestamp_utc or _iso_now(),
        "source_step": str(source_step or ""),
        "status": status,
        "key": str(key or ""),
        "http_status": http_status,
        "error": error,
        "payload": payload if isinstance(payload, dict) else {},
    }


def _event_filename(event: dict) -> str:
    ts = event["timestamp_utc"].replace("-", "").replace(":", "").replace("T", "T").replace("Z", "Z")
    ts = ts.replace(".", "")
    key = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in event.get("key", "na"))
    source_step = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in event.get("source_step", "unknown"))
    # Keep append-only safety even for same-second, same-key events.
    return f"{ts}__{source_step}__{key}__{uuid4().hex[:8]}.json"


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
    paths = build_artifact_paths(Path(repo_root))
    paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)
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
    path = paths.raw_queries_dir / _event_filename(event)
    _atomic_write_text(path, json.dumps(event, ensure_ascii=False, indent=2))
    return path


def list_query_events(repo_root: Path) -> list[Path]:
    paths = build_artifact_paths(Path(repo_root))
    if not paths.raw_queries_dir.exists():
        return []
    return sorted(paths.raw_queries_dir.glob("*.json"))


def read_query_event(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("event_version") != "v2":
        raise ValueError(f"Invalid canonical event schema in {path}")
    return payload
