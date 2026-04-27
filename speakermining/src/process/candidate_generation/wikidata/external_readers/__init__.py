from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from ..event_log import iter_all_events
from ..event_writer import get_event_store


class ExternalEventReader:
    """Base class for startup-only actors that translate config CSVs into events.

    Each reader is idempotent: it checks the event store for already-registered
    entries and only emits events for entries not yet present.
    """

    def __init__(self, repo_root: Path):
        self._root = Path(repo_root)
        self._store = get_event_store(self._root)

    def run(self) -> int:
        """Emit any missing events. Returns count of newly emitted events."""
        raise NotImplementedError

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_registered_qids(self, event_type: str, qid_field: str = "qid") -> set[str]:
        """Return set of QIDs already registered by a given event_type."""
        registered: set[str] = set()
        for event in iter_all_events(self._root):
            if event.get("event_type") == event_type:
                payload = event.get("payload", {}) or {}
                qid = str(payload.get(qid_field, "") or "").strip()
                if qid:
                    registered.add(qid)
        return registered

    def _registered_qids_from_projection_csv(self, csv_path: Path, col: str = "qid") -> set[str] | None:
        """Read QIDs from a handler-written projection CSV. Returns None if the file doesn't exist
        (caller should fall back to event-log scan). F7: avoids full log scan on startup."""
        if not csv_path.exists():
            return None
        rows = self._read_csv(csv_path)
        return {str(r.get(col, "") or "").strip() for r in rows if r.get(col)}

    def _emit(self, event: dict) -> int:
        from ..event_log import _iso_now
        event.setdefault("timestamp_utc", _iso_now())
        return self._store.append_event(event)

    @staticmethod
    def _file_hash(path: Path) -> str:
        raw = path.read_bytes() if path.exists() else b""
        return hashlib.md5(raw).hexdigest()

    @staticmethod
    def _read_csv(path: Path) -> list[dict]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
