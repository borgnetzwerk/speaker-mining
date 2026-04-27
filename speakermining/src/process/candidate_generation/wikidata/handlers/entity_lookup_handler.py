from __future__ import annotations

from pathlib import Path

from . import V4Handler
from ..common import canonical_qid
from ..event_log import _iso_now


class EntityLookupIndexHandler(V4Handler):
    """Maintain a complete QID → label index.

    basic_fetched and fetched labels overwrite earlier values (they are more authoritative).

    Reacts to: entity_discovered, entity_basic_fetched, entity_fetched
    Writes: entity_lookup_index.csv (qid, label, last_updated_at)
    """

    def name(self) -> str:
        return "EntityLookupIndexHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._index: dict[str, dict] = {}  # qid → {label, last_updated_at}

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}
        ts = str(event.get("timestamp_utc", "") or _iso_now())

        if etype in ("entity_discovered", "entity_basic_fetched", "entity_fetched"):
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            label = str(payload.get("label", "") or "")
            if not qid:
                return
            existing = self._index.get(qid)
            if existing is None or etype != "entity_discovered":
                # entity_discovered only fills in if not already known
                self._index[qid] = {"label": label, "last_updated_at": ts}

    def get_label(self, qid: str) -> str:
        return self._index.get(qid, {}).get("label", "")

    def _write(self, proj_dir: Path) -> None:
        rows = [[qid, info.get("label", ""), info.get("last_updated_at", "")] for qid, info in sorted(self._index.items())]
        self._atomic_write_csv_rows(proj_dir / "entity_lookup_index.csv", ["qid", "label", "last_updated_at"], rows)
