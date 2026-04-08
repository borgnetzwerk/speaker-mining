from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv

COLUMNS = ["handler_name", "last_processed_sequence", "artifact_path", "updated_at"]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_progress(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=COLUMNS)

    for column in COLUMNS:
        if column not in df.columns:
            df[column] = ""
    return df.reindex(columns=COLUMNS)


def get_last_processed_sequence(path: Path, handler_name: str) -> int:
    df = load_progress(path)
    if df.empty:
        return 0
    matched = df[df["handler_name"].astype(str) == str(handler_name)]
    if matched.empty:
        return 0
    value = matched.iloc[0].get("last_processed_sequence", 0)
    try:
        return int(value or 0)
    except Exception:
        return 0


def upsert_progress(path: Path, *, handler_name: str, last_processed_sequence: int, artifact_path: str) -> Path:
    df = load_progress(path)
    df = df[df["handler_name"].astype(str) != str(handler_name)].copy()
    row = {
        "handler_name": str(handler_name),
        "last_processed_sequence": int(last_processed_sequence),
        "artifact_path": str(artifact_path),
        "updated_at": _utc_now(),
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    df = df.reindex(columns=COLUMNS)
    df = df.sort_values("handler_name").reset_index(drop=True)
    atomic_write_csv(path, df, index=False)
    return path


def keep_only_handlers(path: Path, handler_names: set[str]) -> Path:
    """Keep only managed handler rows and drop stale/legacy progress entries."""
    df = load_progress(path)
    if df.empty:
        return path
    normalized = {str(name) for name in handler_names}
    filtered = df[df["handler_name"].astype(str).isin(normalized)].copy()
    filtered = filtered.reindex(columns=COLUMNS)
    filtered = filtered.sort_values("handler_name").reset_index(drop=True)
    atomic_write_csv(path, filtered, index=False)
    return path
