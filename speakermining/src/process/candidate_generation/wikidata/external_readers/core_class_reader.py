from __future__ import annotations

from pathlib import Path

from ..event_log import build_core_class_registered_event
from ..schemas import build_artifact_paths
from . import ExternalEventReader


class CoreClassReader(ExternalEventReader):
    """Reads core_classes.csv and emits core_class_registered for each new QID."""

    def run(self) -> int:
        paths = build_artifact_paths(self._root)
        setup_csv = self._root / "data" / "00_setup" / "core_classes.csv"
        source = setup_csv if setup_csv.exists() else paths.core_classes_csv

        rows = self._read_csv(source)
        # F7: read projection CSV written by CoreClassOutputHandler instead of scanning event log
        fast = self._registered_qids_from_projection_csv(paths.projections_dir / "core_class_registry.csv")
        registered = fast if fast is not None else self._get_registered_qids("core_class_registered")
        emitted = 0
        for row in rows:
            qid = str(row.get("wikidata_id") or row.get("qid") or row.get("QID") or "").strip()
            if not qid or qid in registered:
                continue
            # Use filename column for output file naming (e.g. "persons"), not label ("person")
            label = str(row.get("filename") or row.get("label") or "").strip()
            self._emit(build_core_class_registered_event(qid=qid, label=label))
            registered.add(qid)
            emitted += 1
        return emitted
