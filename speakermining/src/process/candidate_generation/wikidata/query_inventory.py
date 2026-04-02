from __future__ import annotations

from pathlib import Path

import pandas as pd

from .cache import _atomic_write_df
from .event_log import get_query_event_field, iter_query_events


_QUERY_INVENTORY_CACHE: dict[str, dict[tuple[str, str], dict]] = {}
_QUERY_INVENTORY_PRIMED: set[str] = set()


def _status_rank(status: str) -> int:
    status = str(status or "")
    if status == "success":
        return 3
    if status in {"cache_hit", "fallback_cache"}:
        return 2
    if status in {"http_error", "timeout"}:
        return 1
    return 0


def _cache_key(repo_root: Path) -> str:
    return str(Path(repo_root).resolve())


def _empty_inventory_cache() -> dict[tuple[str, str], dict]:
    return {}


def _prime_query_inventory_cache(repo_root: Path) -> dict[tuple[str, str], dict]:
    root_key = _cache_key(repo_root)
    cache = _QUERY_INVENTORY_CACHE.get(root_key)
    if cache is not None and root_key in _QUERY_INVENTORY_PRIMED:
        return cache
    cache = {}
    path = Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "projections" / "query_inventory.csv"
    if path.exists():
        try:
            df = pd.read_csv(path)
        except Exception:
            df = pd.DataFrame()
        if not df.empty:
            for _, row in df.iterrows():
                endpoint = str(row.get("endpoint", "") or "")
                query_hash = str(row.get("query_hash", "") or "")
                if not endpoint or not query_hash:
                    continue
                key = (query_hash, endpoint)
                current = cache.get(key)
                candidate = {
                    "endpoint": endpoint,
                    "query_hash": query_hash,
                    "normalized_query": str(row.get("normalized_query", "") or ""),
                    "key": str(row.get("key", "") or ""),
                    "status": str(row.get("status", "") or ""),
                    "timestamp_utc": str(row.get("timestamp_utc", "") or ""),
                    "source_step": str(row.get("source_step", "") or ""),
                }
                if current is None:
                    cache[key] = candidate
                    continue
                current_rank = _status_rank(str(current.get("status", "") or ""))
                candidate_rank = _status_rank(candidate["status"])
                if candidate_rank > current_rank or (
                    candidate_rank == current_rank and candidate["timestamp_utc"] >= str(current.get("timestamp_utc", "") or "")
                ):
                    cache[key] = candidate
    _QUERY_INVENTORY_CACHE[root_key] = cache
    _QUERY_INVENTORY_PRIMED.add(root_key)
    return cache


def reset_query_inventory_cache(repo_root: Path | None = None) -> None:
    if repo_root is None:
        _QUERY_INVENTORY_CACHE.clear()
        _QUERY_INVENTORY_PRIMED.clear()
        return
    root_key = _cache_key(repo_root)
    _QUERY_INVENTORY_CACHE.pop(root_key, None)
    _QUERY_INVENTORY_PRIMED.discard(root_key)


def remember_query_inventory_record(repo_root: Path, event: dict) -> None:
    if not isinstance(event, dict) or event.get("event_type") != "query_response":
        return
    root_key = _cache_key(repo_root)
    cache = _prime_query_inventory_cache(repo_root)
    query_hash = str(get_query_event_field(event, "query_hash", "") or "")
    endpoint = str(get_query_event_field(event, "endpoint", "") or "")
    if not query_hash or not endpoint:
        return
    key = (query_hash, endpoint)
    candidate = {
        "endpoint": endpoint,
        "query_hash": query_hash,
        "normalized_query": str(get_query_event_field(event, "normalized_query", "") or ""),
        "key": str(get_query_event_field(event, "key", "") or ""),
        "status": str(get_query_event_field(event, "status", "") or ""),
        "timestamp_utc": str(event.get("timestamp_utc", "") or ""),
        "source_step": str(get_query_event_field(event, "source_step", "") or ""),
    }
    current = cache.get(key)
    if current is None:
        cache[key] = candidate
        return
    current_rank = _status_rank(str(current.get("status", "") or ""))
    candidate_rank = _status_rank(candidate["status"])
    if candidate_rank > current_rank or (
        candidate_rank == current_rank and candidate["timestamp_utc"] >= str(current.get("timestamp_utc", "") or "")
    ):
        cache[key] = candidate
    _QUERY_INVENTORY_CACHE[root_key] = cache


def materialize_query_inventory(repo_root: Path) -> pd.DataFrame:
    cache = _prime_query_inventory_cache(repo_root)
    rows = list(cache.values())
    df = to_dataframe(rows)
    output_path = Path(repo_root) / "data" / "20_candidate_generation" / "wikidata" / "projections" / "query_inventory.csv"
    _atomic_write_df(output_path, df)
    return df


def rebuild_query_inventory(repo_root) -> list[dict]:
    dedup: dict[tuple[str, str], dict] = {}
    for event in iter_query_events(repo_root) or []:
        query_hash = str(get_query_event_field(event, "query_hash", "") or "")
        endpoint = str(get_query_event_field(event, "endpoint", "") or "")
        key = (query_hash, endpoint)
        current = dedup.get(key)
        if current is None:
            dedup[key] = event
            continue

        current_rank = _status_rank(str(get_query_event_field(current, "status", "") or ""))
        event_rank = _status_rank(str(get_query_event_field(event, "status", "") or ""))
        if event_rank > current_rank:
            dedup[key] = event
            continue
        if event_rank == current_rank and event.get("timestamp_utc", "") >= current.get("timestamp_utc", ""):
            dedup[key] = event

    rows: list[dict] = []
    for (_, _), event in sorted(
        dedup.items(),
        key=lambda kv: (
            str(get_query_event_field(kv[1], "endpoint", "") or ""),
            str(get_query_event_field(kv[1], "normalized_query", "") or ""),
        ),
    ):
        rows.append(
            {
                "endpoint": str(get_query_event_field(event, "endpoint", "") or ""),
                "query_hash": str(get_query_event_field(event, "query_hash", "") or ""),
                "normalized_query": str(get_query_event_field(event, "normalized_query", "") or ""),
                "key": str(get_query_event_field(event, "key", "") or ""),
                "status": str(get_query_event_field(event, "status", "") or ""),
                "timestamp_utc": event.get("timestamp_utc", ""),
                "source_step": str(get_query_event_field(event, "source_step", "") or ""),
            }
        )
    return rows


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    columns = ["endpoint", "query_hash", "normalized_query", "key", "status", "timestamp_utc", "source_step"]
    if not rows:
        return pd.DataFrame(columns=columns)
    df = pd.DataFrame(rows)
    for col in columns:
        if col not in df.columns:
            df[col] = ""
    return df[columns].sort_values(["endpoint", "normalized_query", "key"]).reset_index(drop=True)
