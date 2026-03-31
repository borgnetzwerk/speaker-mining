from __future__ import annotations

import pandas as pd

from .event_log import list_query_events, read_query_event


def _status_rank(status: str) -> int:
    status = str(status or "")
    if status == "success":
        return 3
    if status in {"cache_hit", "fallback_cache"}:
        return 2
    if status in {"http_error", "timeout"}:
        return 1
    return 0


def rebuild_query_inventory(repo_root) -> list[dict]:
    dedup: dict[tuple[str, str], dict] = {}
    for path in list_query_events(repo_root):
        try:
            event = read_query_event(path)
        except Exception:
            continue
        key = (event.get("query_hash", ""), event.get("endpoint", ""))
        current = dedup.get(key)
        if current is None:
            dedup[key] = event
            continue

        current_rank = _status_rank(current.get("status", ""))
        event_rank = _status_rank(event.get("status", ""))
        if event_rank > current_rank:
            dedup[key] = event
            continue
        if event_rank == current_rank and event.get("timestamp_utc", "") >= current.get("timestamp_utc", ""):
            dedup[key] = event

    rows: list[dict] = []
    for (_, _), event in sorted(dedup.items(), key=lambda kv: (kv[1].get("endpoint", ""), kv[1].get("normalized_query", ""))):
        rows.append(
            {
                "endpoint": event.get("endpoint", ""),
                "query_hash": event.get("query_hash", ""),
                "normalized_query": event.get("normalized_query", ""),
                "key": event.get("key", ""),
                "status": event.get("status", ""),
                "timestamp_utc": event.get("timestamp_utc", ""),
                "source_step": event.get("source_step", ""),
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
