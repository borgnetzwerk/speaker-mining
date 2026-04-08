from __future__ import annotations

import json
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .paths import FernsehserienPaths


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FernsehserienEventStore:
    """Append-only JSONL event store for fernsehserien.de runtime events."""

    def __init__(self, paths: FernsehserienPaths) -> None:
        self.paths = paths
        self.paths.ensure()
        self.chunk_path = self.paths.chunks_dir / "chunk_000001.jsonl"
        self._buffer: list[str] = []
        self._flush_every_events = 100
        self._recent_events: deque[tuple[float, dict]] = deque()
        self._recent_window_seconds = 600.0
        self._last_event: dict | None = None
        self._next_sequence = self._load_next_sequence()

    def _load_next_sequence(self) -> int:
        max_seen = 0
        for event in self.iter_events():
            seq = int(event.get("sequence_num", 0) or 0)
            if seq > max_seen:
                max_seen = seq
        return max_seen + 1

    def iter_events(self) -> Iterator[dict]:
        self.flush()
        if not self.chunk_path.exists():
            return
        with self.chunk_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict):
                    yield event

    def _record_recent_event(self, event: dict) -> None:
        now = time.monotonic()
        self._recent_events.append((now, event))
        self._last_event = event
        cutoff = now - self._recent_window_seconds
        while self._recent_events and self._recent_events[0][0] < cutoff:
            self._recent_events.popleft()

    def get_recent_activity(self, *, window_seconds: float = 60.0) -> dict:
        now = time.monotonic()
        cutoff = now - max(float(window_seconds), 1.0)
        rows = [evt for ts, evt in self._recent_events if ts >= cutoff and isinstance(evt, dict)]
        counts = Counter(str(evt.get("event_type", "")) for evt in rows if str(evt.get("event_type", "")))

        last_event = self._last_event if isinstance(self._last_event, dict) else None
        last_summary = {}
        if isinstance(last_event, dict):
            payload = last_event.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            last_summary = {
                "sequence_num": int(last_event.get("sequence_num", 0) or 0),
                "event_type": str(last_event.get("event_type", "")),
                "payload": payload,
            }

        return {
            "events_in_window": int(len(rows)),
            "event_type_counts": dict(counts.most_common(8)),
            "last_event": last_summary,
        }

    def flush(self) -> None:
        if not self._buffer:
            return
        self.chunk_path.parent.mkdir(parents=True, exist_ok=True)
        with self.chunk_path.open("a", encoding="utf-8") as handle:
            handle.write("".join(self._buffer))
        self._buffer.clear()

    def close(self) -> None:
        self.flush()

    def __del__(self) -> None:
        try:
            self.flush()
        except Exception:
            pass

    def append(self, *, event_type: str, payload: dict, event_version: str = "v1_fsd") -> dict:
        event = {
            "sequence_num": self._next_sequence,
            "event_version": event_version,
            "event_type": str(event_type),
            "timestamp_utc": _iso_now(),
            "recorded_at": _iso_now(),
            "payload": payload if isinstance(payload, dict) else {},
        }
        self._next_sequence += 1

        line = json.dumps(event, ensure_ascii=False)
        self._buffer.append(line + "\n")
        self._record_recent_event(event)
        if len(self._buffer) >= self._flush_every_events:
            self.flush()
        return event
