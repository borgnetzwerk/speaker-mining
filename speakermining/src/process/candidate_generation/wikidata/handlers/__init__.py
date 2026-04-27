from __future__ import annotations

from pathlib import Path

from ..event_handler import EventHandler
from ..event_log import _iso_now, iter_events_from
from ..schemas import build_artifact_paths


class V4Handler(EventHandler):
    """Base class for all v4 event handlers.

    Extends EventHandler with:
    - replay(): read new events from log and materialize
    - _emit(): write an event to the shared event store
    - progress persisted as {projections_dir}/{name()}_progress.txt
    """

    def __init__(self, repo_root: Path, event_store=None):
        self._root = Path(repo_root)
        self._store = event_store
        self._paths = build_artifact_paths(self._root)
        self._proj = self._paths.projections_dir
        self._last_seq: int = self._load_seq()

    # ── EventHandler contract ──────────────────────────────────────────────

    def last_processed_sequence(self) -> int:
        return self._last_seq

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            self._on_event(event)

    def materialize(self, output_path: Path) -> None:
        self._write(output_path)

    def update_progress(self, last_seq: int) -> None:
        self._save_seq(last_seq)

    # ── V4 extensions ─────────────────────────────────────────────────────

    def replay(self) -> int:
        """Read all unprocessed events from the log, update state, persist."""
        new_events = list(iter_events_from(self._root, self._last_seq + 1))
        if not new_events:
            return self._last_seq
        self.process_batch(new_events)
        last = max(
            (e.get("sequence_num", 0) for e in new_events if isinstance(e.get("sequence_num"), int)),
            default=self._last_seq,
        )
        self._write(self._proj)
        self._save_seq(last)
        self._last_seq = last
        return last

    def _emit(self, event: dict) -> int:
        if self._store is None:
            raise RuntimeError(f"{self.name()} has no event_store — cannot emit events")
        event.setdefault("timestamp_utc", _iso_now())
        return self._store.append_event(event)

    # ── Subclass hooks ─────────────────────────────────────────────────────

    def _on_event(self, event: dict) -> None:
        """Override to handle individual events during process_batch."""

    def _write(self, proj_dir: Path) -> None:
        """Override to write projection files to proj_dir."""

    # ── Progress persistence ───────────────────────────────────────────────

    def _progress_path(self) -> Path:
        return self._proj / f"{self.name()}_progress.txt"

    def _load_seq(self) -> int:
        p = self._progress_path()
        try:
            return int(p.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            return 0

    def _save_seq(self, seq: int) -> None:
        p = self._progress_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(seq), encoding="utf-8")
