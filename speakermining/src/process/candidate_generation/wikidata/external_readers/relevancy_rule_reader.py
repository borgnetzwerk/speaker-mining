from __future__ import annotations

from pathlib import Path

from ..event_log import build_rule_changed_event, iter_all_events
from ..schemas import build_artifact_paths
from . import ExternalEventReader


_SETUP_FILENAME = "relevancy_relation_contexts.csv"


class RelevancyRuleReader(ExternalEventReader):
    """Reads relevancy_relation_contexts.csv and emits rule_changed when the file hash changes.

    Only one event per hash is emitted — handlers react by re-evaluating relevancy.
    """

    def run(self) -> int:
        paths = build_artifact_paths(self._root)
        setup_csv = self._root / "data" / "00_setup" / _SETUP_FILENAME
        source = setup_csv if setup_csv.exists() else paths.relevancy_relation_contexts_csv

        current_hash = self._file_hash(source)
        last_emitted_hash = self._last_emitted_hash()
        emitted = 0
        if current_hash != last_emitted_hash:
            self._emit(build_rule_changed_event(
                rule_file=_SETUP_FILENAME,
                rule_hash=current_hash,
            ))
            emitted = 1

        self._validate_core_class_refs(source, paths)
        return emitted

    def _validate_core_class_refs(self, rules_csv: Path, paths) -> None:
        """F18: warn if rules reference core class QIDs not in core_class_registry.csv."""
        registry_csv = paths.projections_dir / "core_class_registry.csv"
        known = self._registered_qids_from_projection_csv(registry_csv)
        if known is None:
            return  # first run — registry not written yet, skip validation
        rows = self._read_csv(rules_csv)
        for row in rows:
            for col in ("subject_core_class_qid", "object_core_class_qid"):
                qid = str(row.get(col, "") or "").strip()
                if qid and qid not in known:
                    print(f"[F18 WARNING] relevancy rule references unknown core class {qid!r} (column {col!r})")

    def _last_emitted_hash(self) -> str:
        last = ""
        for event in iter_all_events(self._root):
            if event.get("event_type") != "rule_changed":
                continue
            p = event.get("payload", {}) or {}
            if str(p.get("rule_file", "")) == _SETUP_FILENAME:
                last = str(p.get("rule_hash", ""))
        return last
