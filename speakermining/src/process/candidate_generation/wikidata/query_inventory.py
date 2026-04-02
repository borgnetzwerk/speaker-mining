from __future__ import annotations

import pandas as pd

from .event_log import get_query_event_field, iter_query_events


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
