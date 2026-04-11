from __future__ import annotations

import csv
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from process.io_guardrails import atomic_write_text

from ...notebook_event_log import NOTEBOOK_21_ID


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _notebook_event_log_path(repo_root: Path, notebook_id: str = NOTEBOOK_21_ID) -> Path:
    return Path(repo_root) / "data" / "logs" / "notebooks" / f"{notebook_id}.events.jsonl"


def _backoff_history_csv_path(repo_root: Path) -> Path:
    return (
        Path(repo_root)
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "backoff_delay_learning.csv"
    )


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _round_delay(delay_seconds: float) -> float:
    return round(max(0.0, float(delay_seconds or 0.0)), 6)


class NotebookEventTailObserver:
    """Track newly appended notebook events and summarize network/backoff counts."""

    def __init__(self, repo_root: Path, *, notebook_id: str = NOTEBOOK_21_ID, phase: str | None = None) -> None:
        self.repo_root = Path(repo_root)
        self.path = _notebook_event_log_path(self.repo_root, notebook_id=notebook_id)
        self.phase = str(phase or "")
        self._offset = 0

    def read_increment(self) -> dict:
        if not self.path.exists():
            return {"calls": 0, "backoffs": 0, "events": 0}

        calls = 0
        backoffs = 0
        events = 0

        with self.path.open("r", encoding="utf-8") as handle:
            handle.seek(self._offset)
            while True:
                line = handle.readline()
                if line == "":
                    break
                self._offset = handle.tell()
                raw = line.strip()
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                if self.phase and str(event.get("phase", "") or "") != self.phase:
                    continue

                events += 1
                event_type = str(event.get("event_type", "") or "")
                if event_type == "network_call_started":
                    calls += 1
                elif event_type == "network_backoff_applied":
                    backoffs += 1

        return {
            "calls": int(calls),
            "backoffs": int(backoffs),
            "events": int(events),
        }


def append_backoff_learning_row(
    repo_root: Path,
    *,
    phase: str,
    action: str,
    configured_delay_seconds: float,
    new_delay_seconds: float,
    window_calls: int,
    window_backoffs: int,
    reason: str,
) -> None:
    path = _backoff_history_csv_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    row = {
        "timestamp_utc": _iso_now(),
        "phase": str(phase or ""),
        "action": str(action or ""),
        "configured_delay_seconds": _round_delay(configured_delay_seconds),
        "new_delay_seconds": _round_delay(new_delay_seconds),
        "window_calls": int(window_calls or 0),
        "window_backoffs": int(window_backoffs or 0),
        "reason": str(reason or ""),
    }

    fieldnames = [
        "timestamp_utc",
        "phase",
        "action",
        "configured_delay_seconds",
        "new_delay_seconds",
        "window_calls",
        "window_backoffs",
        "reason",
    ]

    rows: list[dict] = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for existing in reader:
                    if isinstance(existing, dict):
                        rows.append({k: existing.get(k, "") for k in fieldnames})
        except Exception:
            rows = []

    rows.append(row)

    lines = [",".join(fieldnames)]
    for item in rows:
        values = []
        for key in fieldnames:
            value = item.get(key, "")
            value_str = str(value).replace("\n", " ")
            if "," in value_str or '"' in value_str:
                value_str = '"' + value_str.replace('"', '""') + '"'
            values.append(value_str)
        lines.append(",".join(values))

    atomic_write_text(path, "\n".join(lines) + "\n", encoding="utf-8")


def recommend_query_delay_from_history(
    repo_root: Path,
    *,
    configured_delay_seconds: float,
    min_samples: int = 20,
    notebook_id: str = NOTEBOOK_21_ID,
) -> dict:
    """Build operator guidance from persisted network/backoff history."""
    repo_root = Path(repo_root)
    configured = _round_delay(configured_delay_seconds)
    stats = defaultdict(lambda: {"calls": 0, "backoffs": 0})

    event_log_path = _notebook_event_log_path(repo_root, notebook_id=notebook_id)
    if event_log_path.exists():
        for raw in event_log_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("event_type", "") or "")
            rate_limit = event.get("rate_limit", {})
            if not isinstance(rate_limit, dict):
                continue
            delay = _safe_float(rate_limit.get("query_delay_seconds_configured", 0.0), 0.0)
            delay_key = _round_delay(delay)
            if delay_key <= 0.0:
                continue
            if event_type == "network_call_started":
                stats[delay_key]["calls"] += 1
            elif event_type == "network_backoff_applied":
                stats[delay_key]["backoffs"] += 1

    history_csv = _backoff_history_csv_path(repo_root)
    if history_csv.exists():
        try:
            with history_csv.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if not isinstance(row, dict):
                        continue
                    delay = _round_delay(_safe_float(row.get("configured_delay_seconds", 0.0), 0.0))
                    if delay <= 0.0:
                        continue
                    stats[delay]["calls"] += int(_safe_float(row.get("window_calls", 0), 0))
                    stats[delay]["backoffs"] += int(_safe_float(row.get("window_backoffs", 0), 0))
        except Exception:
            pass

    calls = int(stats[configured]["calls"])
    backoffs = int(stats[configured]["backoffs"])
    backoff_rate = (float(backoffs) / float(calls)) if calls > 0 else 0.0

    safe_delays = [
        delay
        for delay, row in stats.items()
        if int(row["calls"]) >= int(min_samples) and int(row["backoffs"]) == 0
    ]
    safe_delays_sorted = sorted(safe_delays)

    recommended = configured
    known_backoff_prone = calls >= int(min_samples) and backoffs > 0
    warning_message = ""

    if known_backoff_prone:
        candidate = configured * 1.05
        for delay in safe_delays_sorted:
            if delay >= configured:
                candidate = delay
                break
        recommended = _round_delay(candidate)
        warning_message = (
            f"Configured query delay {configured:.3f}s has historical backoff activity "
            f"({backoffs}/{calls} calls). Suggested start: {recommended:.3f}s."
        )

    return {
        "configured_delay_seconds": configured,
        "recommended_delay_seconds": _round_delay(recommended),
        "known_backoff_prone": bool(known_backoff_prone),
        "samples": int(calls),
        "backoffs": int(backoffs),
        "backoff_rate": float(backoff_rate),
        "known_safe_delay_range": [
            float(safe_delays_sorted[0]),
            float(safe_delays_sorted[-1]),
        ]
        if safe_delays_sorted
        else [],
        "message": warning_message,
    }


class AdaptiveBackoffController:
    """Adjust runtime query delay from observed backoff patterns."""

    def __init__(
        self,
        repo_root: Path,
        *,
        phase: str,
        interval_seconds: int,
        pattern_heartbeats: int = 3,
        increase_factor: float = 0.05,
        decrease_factor: float = 0.01,
        min_delay_seconds: float = 0.05,
        max_delay_seconds: float = 30.0,
        enabled: bool = True,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.phase = str(phase or "")
        self.interval_seconds = max(1, int(interval_seconds or 1))
        self.pattern_heartbeats = max(1, int(pattern_heartbeats or 1))
        self.increase_factor = max(0.0, float(increase_factor or 0.0))
        self.decrease_factor = max(0.0, float(decrease_factor or 0.0))
        self.min_delay_seconds = max(0.0, float(min_delay_seconds or 0.0))
        self.max_delay_seconds = max(self.min_delay_seconds, float(max_delay_seconds or self.min_delay_seconds))
        self.enabled = bool(enabled)

        self._observer = NotebookEventTailObserver(self.repo_root, phase=self.phase)
        self._backoff_windows = deque(maxlen=self.pattern_heartbeats)
        self._safe_delay_samples: list[float] = []
        self._backoff_delay_samples: list[float] = []

    def observe_window(self, *, current_delay_seconds: float) -> dict:
        snapshot = self._observer.read_increment()
        calls = int(snapshot.get("calls", 0) or 0)
        backoffs = int(snapshot.get("backoffs", 0) or 0)

        if calls > 0:
            delay = _round_delay(current_delay_seconds)
            if backoffs > 0:
                self._backoff_delay_samples.append(delay)
            else:
                self._safe_delay_samples.append(delay)

        self._backoff_windows.append(backoffs > 0)
        return {
            "window_calls": calls,
            "window_backoffs": backoffs,
            "window_backoff_present": bool(backoffs > 0),
            "window_size": len(self._backoff_windows),
        }

    def decide_adjustment(self, *, current_delay_seconds: float) -> dict | None:
        if not self.enabled:
            return None
        if len(self._backoff_windows) < self.pattern_heartbeats:
            return None

        delay = _round_delay(current_delay_seconds)
        if delay <= 0.0:
            return None

        if all(self._backoff_windows):
            new_delay = _round_delay(min(self.max_delay_seconds, delay * (1.0 + self.increase_factor)))
            if new_delay > delay:
                self._backoff_windows.clear()
                return {
                    "action": "increase",
                    "previous_delay_seconds": delay,
                    "new_delay_seconds": new_delay,
                    "reason": f"backoff observed in last {self.pattern_heartbeats} heartbeats",
                }

        if not any(self._backoff_windows):
            new_delay = _round_delay(max(self.min_delay_seconds, delay * (1.0 - self.decrease_factor)))
            if 0.0 < new_delay < delay:
                self._backoff_windows.clear()
                return {
                    "action": "decrease",
                    "previous_delay_seconds": delay,
                    "new_delay_seconds": new_delay,
                    "reason": f"no backoff observed in last {self.pattern_heartbeats} heartbeats",
                }

        return None

    def summarize_range(self) -> dict:
        safe = sorted(self._safe_delay_samples)
        risky = sorted(self._backoff_delay_samples)
        return {
            "safe_delay_range": [float(safe[0]), float(safe[-1])] if safe else [],
            "backoff_delay_range": [float(risky[0]), float(risky[-1])] if risky else [],
            "safe_samples": int(len(safe)),
            "backoff_samples": int(len(risky)),
        }
