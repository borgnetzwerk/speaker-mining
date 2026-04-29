from __future__ import annotations

import json
from pathlib import Path

from ..event_handler import EventHandler
from ..event_log import _iso_now, iter_events_from
from ..schemas import build_artifact_paths


class V4Handler(EventHandler):
    """Base class for all v4 event handlers.

    Extends EventHandler with:
    - replay(): interruptible event processing with termination-flag check
    - _emit(): write an event to the shared event store
    - _atomic_write_text() / _atomic_write_json(): safe file writes (temp + rename)
    - progress persisted atomically as {projections_dir}/{name()}_progress.txt

    H3 (graceful shutdown): replay() checks should_terminate() after each event;
    all writes use atomic temp-file + rename so partial writes never corrupt state.

    H4 (heartbeat): replay() itself does not emit heartbeats — the outer work loop
    is wrapped with run_with_progress_heartbeat which runs a background thread.
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
        """Read unprocessed events one at a time, checking the termination flag
        after each. On early exit, persists progress up to the last processed
        event so the next replay resumes from a consistent checkpoint.
        """
        from ..graceful_shutdown import should_terminate

        new_events = list(iter_events_from(self._root, self._last_seq + 1))
        if not new_events:
            return self._last_seq

        last = self._last_seq
        for event in new_events:
            self._on_event(event)
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                last = max(last, seq)
            if should_terminate():
                break

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
        """Override to handle individual events during replay."""

    def _write(self, proj_dir: Path) -> None:
        """Override to write projection files to proj_dir.
        Use _atomic_write_text() / _atomic_write_json() for all file writes.
        """

    # ── Atomic file I/O helpers (H3) ──────────────────────────────────────

    def _atomic_write_text(self, path: Path, content: str, encoding: str = "utf-8") -> None:
        """Write content to path atomically: write to .tmp then rename."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(content, encoding=encoding)
        tmp.replace(path)

    def _atomic_write_json(self, path: Path, obj, *, indent: int = 2, ensure_ascii: bool = False) -> None:
        """Serialize obj as JSON and write to path atomically."""
        self._atomic_write_text(path, json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii))

    def _atomic_write_csv_rows(self, path: Path, header: list[str], rows: list[list]) -> None:
        """Write header + rows as CSV to path atomically."""
        import csv
        import io
        buf = io.StringIO()
        writer = csv.writer(buf, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
        self._atomic_write_text(path, buf.getvalue())

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
        self._atomic_write_text(self._progress_path(), str(seq))
