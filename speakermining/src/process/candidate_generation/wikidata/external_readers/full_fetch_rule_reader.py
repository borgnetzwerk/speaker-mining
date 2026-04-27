from __future__ import annotations

from pathlib import Path

from ..event_log import build_full_fetch_rule_registered_event
from ..schemas import build_artifact_paths
from . import ExternalEventReader


_SETUP_FILENAME = "full_fetch_rules.csv"


class FullFetchRuleReader(ExternalEventReader):
    """Reads full_fetch_rules.csv and emits full_fetch_rule_registered for each new rule row.

    Idempotency key: (rule_type, group_id, subject, predicate, object) tuple.
    Already-registered rules (exact match) are skipped.
    """

    def run(self) -> int:
        paths = build_artifact_paths(self._root)
        setup_csv = self._root / "data" / "00_setup" / _SETUP_FILENAME
        projections_csv = paths.projections_dir / _SETUP_FILENAME
        source = setup_csv if setup_csv.exists() else projections_csv

        rows = self._read_csv(source)
        registered = self._get_registered_rule_keys()
        emitted = 0
        for row in rows:
            rule_type = str(row.get("rule_type") or "").strip()
            group_id_raw = str(row.get("group_id") or "0").strip()
            subject = str(row.get("subject") or "").strip()
            predicate = str(row.get("predicate") or "").strip()
            obj = str(row.get("object") or "").strip()
            note = str(row.get("note") or "").strip()
            try:
                group_id = int(group_id_raw)
            except ValueError:
                continue
            key = (rule_type, group_id, subject, predicate, obj)
            if not rule_type or key in registered:
                continue
            self._emit(build_full_fetch_rule_registered_event(
                rule_type=rule_type,
                group_id=group_id,
                subject=subject,
                predicate=predicate,
                object=obj,
                note=note,
            ))
            registered.add(key)
            emitted += 1
        return emitted

    def _get_registered_rule_keys(self) -> set[tuple]:
        from ..event_log import iter_all_events
        keys: set[tuple] = set()
        for event in iter_all_events(self._root):
            if event.get("event_type") != "full_fetch_rule_registered":
                continue
            p = event.get("payload", {}) or {}
            key = (
                str(p.get("rule_type", "")),
                int(p.get("group_id", 0)),
                str(p.get("subject", "")),
                str(p.get("predicate", "")),
                str(p.get("object", "")),
            )
            keys.add(key)
        return keys
