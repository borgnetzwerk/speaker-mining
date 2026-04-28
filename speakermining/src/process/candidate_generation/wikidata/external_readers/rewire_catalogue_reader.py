from __future__ import annotations

from pathlib import Path

from ..common import canonical_pid, canonical_qid
from ..event_log import build_entity_rewired_event
from ..schemas import build_artifact_paths
from . import ExternalEventReader


_SETUP_FILENAME = "rewiring_catalogue.csv"


class RewireCatalogueReader(ExternalEventReader):
    """Reads rewiring_catalogue.csv and emits entity_rewired for each new entry.

    Each row adds (rule=add) or removes (rule=remove) a synthetic triple.
    Only 'add' is currently acted on by handlers — 'remove' is recorded for
    future use.

    Idempotency key: (subject_qid, predicate_pid, object_qid, rule) tuple.
    """

    def run(self) -> int:
        paths = build_artifact_paths(self._root)
        setup_csv = self._root / "data" / "00_setup" / _SETUP_FILENAME
        projections_csv = paths.projections_dir / _SETUP_FILENAME
        source = setup_csv if setup_csv.exists() else projections_csv

        if not source.exists():
            return 0  # optional file — no error if absent

        rows = self._read_csv(source)
        registered = self._get_registered_rewire_keys()
        emitted = 0
        for row in rows:
            subject = canonical_qid(str(row.get("subject", "") or "").strip())
            predicate = canonical_pid(str(row.get("predicate", "") or "").strip())
            obj = canonical_qid(str(row.get("object", "") or "").strip())
            rule = str(row.get("rule", "add") or "add").strip().lower() or "add"
            if not (subject and predicate and obj):
                continue
            key = (subject, predicate, obj, rule)
            if key in registered:
                continue
            self._emit(build_entity_rewired_event(
                subject_qid=subject,
                predicate_pid=predicate,
                object_qid=obj,
                rule=rule,
            ))
            registered.add(key)
            emitted += 1
        return emitted

    def _get_registered_rewire_keys(self) -> set[tuple]:
        from ..event_log import iter_all_events
        keys: set[tuple] = set()
        for event in iter_all_events(self._root):
            if event.get("event_type") != "entity_rewired":
                continue
            p = event.get("payload", {}) or {}
            keys.add((
                str(p.get("subject_qid", "")),
                str(p.get("predicate_pid", "")),
                str(p.get("object_qid", "")),
                str(p.get("rule", "add")),
            ))
        return keys
