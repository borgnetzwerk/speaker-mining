"""BackoffLearningHandler: learns network pressure patterns from query events.

Maintains a windowed projection so early lenient calls do not skew long-run tuning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.event_log import get_query_event_field
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


_BACKOFF_WINDOW_SIZE = 100


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


class BackoffLearningHandler(EventHandler):
    """Aggregates query outcomes into ordinal windows for pattern detection."""

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self._windows: dict[tuple[str, str, int], dict] = {}
        self._call_ordinal_by_scope: dict[tuple[str, str], int] = {}

    def name(self) -> str:
        return "BackoffLearningHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def bootstrap_from_projection(self, output_path: Path) -> bool:
        output_path = Path(output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            return False
        try:
            df = pd.read_csv(output_path)
        except Exception:
            return False
        if df.empty:
            self._windows = {}
            self._call_ordinal_by_scope = {}
            return True

        df = df.fillna(0)
        windows: dict[tuple[str, str, int], dict] = {}
        ordinal_by_scope: dict[tuple[str, str], int] = {}

        for row in df.to_dict(orient="records"):
            endpoint = str(row.get("endpoint", "") or "")
            source_step = str(row.get("source_step", "") or "")
            window_index = _as_int(row.get("window_index", 0), 0)
            key = (endpoint, source_step, window_index)

            record = {
                "endpoint": endpoint,
                "source_step": source_step,
                "window_index": int(window_index),
                "calls": _as_int(row.get("calls", 0), 0),
                "success": _as_int(row.get("success", 0), 0),
                "http_error": _as_int(row.get("http_error", 0), 0),
                "timeout": _as_int(row.get("timeout", 0), 0),
                "rate_limited_like": _as_int(row.get("rate_limited_like", 0), 0),
                "http_status_429": _as_int(row.get("http_status_429", 0), 0),
                "http_status_5xx": _as_int(row.get("http_status_5xx", 0), 0),
                "first_sequence": _as_int(row.get("first_sequence", 0), 0),
                "last_sequence": _as_int(row.get("last_sequence", 0), 0),
                "start_call_ordinal": _as_int(row.get("start_call_ordinal", 0), 0),
                "end_call_ordinal": _as_int(row.get("end_call_ordinal", 0), 0),
            }
            windows[key] = record

            scope_key = (endpoint, source_step)
            ordinal_by_scope[scope_key] = max(
                int(record["end_call_ordinal"]),
                int(ordinal_by_scope.get(scope_key, 0) or 0),
            )

        self._windows = windows
        self._call_ordinal_by_scope = ordinal_by_scope
        return True

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            if event.get("event_type") != "query_response":
                continue

            endpoint = str(get_query_event_field(event, "endpoint", "") or "")
            source_step = str(get_query_event_field(event, "source_step", "") or "")
            status = str(get_query_event_field(event, "status", "") or "")
            http_status = _as_int(get_query_event_field(event, "http_status", 0), 0)

            if endpoint not in {"wikidata_api", "wikidata_sparql"}:
                continue
            if status in {"cache_hit", "fallback_cache", "skipped"}:
                continue

            scope_key = (endpoint, source_step)
            next_ordinal = int(self._call_ordinal_by_scope.get(scope_key, 0) or 0) + 1
            self._call_ordinal_by_scope[scope_key] = next_ordinal
            window_index = (next_ordinal - 1) // _BACKOFF_WINDOW_SIZE
            window_key = (endpoint, source_step, window_index)

            seq = _as_int(event.get("sequence_num", 0), 0)
            row = self._windows.get(window_key)
            if row is None:
                start_ordinal = (window_index * _BACKOFF_WINDOW_SIZE) + 1
                row = {
                    "endpoint": endpoint,
                    "source_step": source_step,
                    "window_index": window_index,
                    "calls": 0,
                    "success": 0,
                    "http_error": 0,
                    "timeout": 0,
                    "rate_limited_like": 0,
                    "http_status_429": 0,
                    "http_status_5xx": 0,
                    "first_sequence": seq,
                    "last_sequence": seq,
                    "start_call_ordinal": start_ordinal,
                    "end_call_ordinal": start_ordinal - 1,
                }
                self._windows[window_key] = row

            row["calls"] = int(row["calls"]) + 1
            row["last_sequence"] = max(int(row.get("last_sequence", 0) or 0), seq)
            first_seq = int(row.get("first_sequence", 0) or 0)
            row["first_sequence"] = seq if first_seq == 0 else min(first_seq, seq)
            row["end_call_ordinal"] = max(int(row.get("end_call_ordinal", 0) or 0), int(next_ordinal))

            if status == "success":
                row["success"] = int(row["success"]) + 1
            elif status == "timeout":
                row["timeout"] = int(row["timeout"]) + 1
                row["rate_limited_like"] = int(row["rate_limited_like"]) + 1
            elif status == "http_error":
                row["http_error"] = int(row["http_error"]) + 1
                if http_status == 429:
                    row["http_status_429"] = int(row["http_status_429"]) + 1
                    row["rate_limited_like"] = int(row["rate_limited_like"]) + 1
                if 500 <= http_status <= 599:
                    row["http_status_5xx"] = int(row["http_status_5xx"]) + 1
                    row["rate_limited_like"] = int(row["rate_limited_like"]) + 1

            self._last_seq = max(self._last_seq, seq)

    def materialize(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rows = []
        for key in sorted(self._windows.keys(), key=lambda item: (item[0], item[1], int(item[2]))):
            row = dict(self._windows[key])
            calls = max(1, int(row.get("calls", 0) or 0))
            row["success_ratio"] = _as_float(row.get("success", 0), 0.0) / float(calls)
            row["error_ratio"] = (
                _as_float(row.get("http_error", 0), 0.0) + _as_float(row.get("timeout", 0), 0.0)
            ) / float(calls)
            row["backoff_like_ratio"] = _as_float(row.get("rate_limited_like", 0), 0.0) / float(calls)
            rows.append(row)

        columns = [
            "endpoint",
            "source_step",
            "window_index",
            "start_call_ordinal",
            "end_call_ordinal",
            "calls",
            "success",
            "http_error",
            "timeout",
            "rate_limited_like",
            "http_status_429",
            "http_status_5xx",
            "success_ratio",
            "error_ratio",
            "backoff_like_ratio",
            "first_sequence",
            "last_sequence",
        ]
        df = pd.DataFrame(rows, columns=columns) if rows else pd.DataFrame(columns=columns)
        _atomic_write_df(output_path, df)

    def update_progress(self, last_seq: int) -> None:
        self._last_seq = max(self._last_seq, int(last_seq or 0))
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), self._last_seq)
