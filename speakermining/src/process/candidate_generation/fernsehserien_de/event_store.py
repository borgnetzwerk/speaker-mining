from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from process.io_guardrails import atomic_write_text

from .paths import FernsehserienPaths


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FernsehserienEventStore:
    """Append-only JSONL event store for fernsehserien.de runtime events."""

    def __init__(self, paths: FernsehserienPaths) -> None:
        self.paths = paths
        self.paths.ensure()
        self.chunk_path = self.paths.chunks_dir / "chunk_000001.jsonl"
        self._next_sequence = self._load_next_sequence()

    def _load_next_sequence(self) -> int:
        max_seen = 0
        for event in self.iter_events():
            seq = int(event.get("sequence_num", 0) or 0)
            if seq > max_seen:
                max_seen = seq
        return max_seen + 1

    def iter_events(self) -> Iterator[dict]:
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

        self.chunk_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False)
        existing = ""
        if self.chunk_path.exists():
            existing = self.chunk_path.read_text(encoding="utf-8")
        atomic_write_text(self.chunk_path, existing + line + "\n", encoding="utf-8")
        return event
