from __future__ import annotations

import json
from pathlib import Path

from . import V4Handler
from ..common import canonical_qid, pick_entity_label


class CoreClassOutputHandler(V4Handler):
    """Write core_<class>.json and not_relevant_core_<class>.json handover files.

    Assembles the full per-entity record (triples, qualifier/reference PIDs,
    label, core_class assignment) from all domain events. Written once at end
    of run (step 7 in the notebook).

    Reacts to: entity_fetched, triple_discovered, entity_marked_relevant,
               entity_basic_fetched, class_resolved, core_class_registered
    Writes: core_<class>.json, not_relevant_core_<class>.json per core class
    """

    def name(self) -> str:
        return "CoreClassOutputHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._core_classes: dict[str, str] = {}           # qid → label
        self._core_class_mode: dict[str, str] = {}        # qid → projection_mode ("instances"|"subclasses")
        self._labels: dict[str, str] = {}          # qid → label
        self._descriptions: dict[str, str] = {}    # qid → description
        self._aliases: dict[str, list[str]] = {}   # qid → list of aliases
        self._triples: dict[str, list[dict]] = {}  # qid → list of triple records
        self._relevant: set[str] = set()
        self._p31_map: dict[str, list[str]] = {}   # entity qid → p31 qids
        self._class_to_core: dict[str, str] = {}   # class_qid → core_class_qid

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}

        if etype == "core_class_registered":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._core_classes[qid] = str(payload.get("label", "") or "")
                self._core_class_mode[qid] = str(payload.get("projection_mode", "") or "instances") or "instances"
                self._class_to_core[qid] = qid

        elif etype == "class_resolved":
            class_qid = canonical_qid(str(payload.get("class_qid", "") or ""))
            core = str(payload.get("core_class_qid", "") or "")
            if not core:
                # Try parent_qids path
                parents = payload.get("parent_qids", []) or []
                for p in parents:
                    if p in self._core_classes:
                        core = p
                        break
                    candidate = self._class_to_core.get(p, "")
                    if candidate:
                        core = candidate
                        break
            if class_qid and core:
                self._class_to_core[class_qid] = core

        elif etype == "entity_marked_relevant":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._relevant.add(qid)

        elif etype in ("entity_fetched", "entity_basic_fetched"):
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            label = str(payload.get("label", "") or "")
            if qid and label:
                self._labels[qid] = label
            desc = str(payload.get("description", "") or "")
            if qid and desc:
                self._descriptions[qid] = desc
            al = list(payload.get("aliases", []) or [])
            if qid and al:
                self._aliases[qid] = al
            p31 = payload.get("p31_qids", [])
            if qid and p31:
                self._p31_map[qid] = list(p31)

        elif etype == "triple_discovered":
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = str(payload.get("predicate_pid", "") or "")
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            if not (subject and pid and obj):
                return
            triple = {
                "predicate_pid": pid,
                "object_qid": obj,
                "qualifier_pids": list(payload.get("qualifier_pids", []) or []),
                "reference_pids": list(payload.get("reference_pids", []) or []),
            }
            self._triples.setdefault(subject, []).append(triple)
            # Also update p31 map for class resolution
            if pid == "P31":
                p31 = self._p31_map.setdefault(subject, [])
                if obj not in p31:
                    p31.append(obj)

    def _resolve_core_classes(self, qid: str) -> list[str]:
        """Return all core class QIDs this entity resolves to via P31 (instances strategy)."""
        cores = []
        for p31_qid in self._p31_map.get(qid, []):
            core = self._class_to_core.get(p31_qid, "")
            if not core and p31_qid in self._core_classes:
                core = p31_qid
            if core and core not in cores:
                cores.append(core)
        return cores

    def _subclass_entities_for_core(self, core_qid: str) -> set[str]:
        """Return all class-node QIDs whose core_class_ancestor is core_qid (subclasses strategy, F12)."""
        return {qid for qid, ancestor in self._class_to_core.items() if ancestor == core_qid}

    def _build_record(self, qid: str, core_class: str, conflict: bool) -> dict:
        return {
            "qid": qid,
            "label": self._labels.get(qid, ""),
            "description": self._descriptions.get(qid, ""),
            "aliases": self._aliases.get(qid, []),
            "core_class": core_class,
            "conflict": conflict,
            "triples": self._triples.get(qid, []),
        }

    def _write(self, proj_dir: Path) -> None:
        # Write core class registry CSV (F7: readers use this instead of scanning event log)
        registry_rows = [[qid, label] for qid, label in sorted(self._core_classes.items())]
        self._atomic_write_csv_rows(proj_dir / "core_class_registry.csv", ["qid", "label"], registry_rows)

        # Bucket entities by core class, respecting each class's projection_mode (F12)
        relevant_by_core: dict[str, list[dict]] = {qid: [] for qid in self._core_classes}
        not_relevant_by_core: dict[str, list[dict]] = {qid: [] for qid in self._core_classes}

        # Separate entity sets per strategy
        instances_cores = {qid for qid, mode in self._core_class_mode.items() if mode != "subclasses"}
        subclasses_cores = {qid for qid, mode in self._core_class_mode.items() if mode == "subclasses"}

        # Instances strategy: use P31 map
        all_entities = set(self._triples.keys()) | set(self._labels.keys())
        for entity_qid in all_entities:
            cores = [c for c in self._resolve_core_classes(entity_qid) if c in instances_cores]
            if not cores:
                continue
            conflict = len(self._resolve_core_classes(entity_qid)) > 1
            for core in cores:
                record = self._build_record(entity_qid, core, conflict)
                if entity_qid in self._relevant:
                    relevant_by_core[core].append(record)
                else:
                    not_relevant_by_core[core].append(record)

        # Subclasses strategy: use class_to_core (P279 chain) — F12
        for core_qid in subclasses_cores:
            subclass_qids = self._subclass_entities_for_core(core_qid)
            for entity_qid in subclass_qids:
                if entity_qid == core_qid:
                    continue  # skip the root class itself
                record = self._build_record(entity_qid, core_qid, False)
                if entity_qid in self._relevant:
                    relevant_by_core[core_qid].append(record)
                else:
                    not_relevant_by_core[core_qid].append(record)

        for core_qid in self._core_classes:
            from ..schemas import canonical_class_filename
            class_name = self._core_classes.get(core_qid, core_qid)
            try:
                filename = canonical_class_filename(class_name)
            except ValueError:
                filename = core_qid.lower()

            rel_out = proj_dir / f"core_{filename}.json"
            not_rel_out = proj_dir / f"not_relevant_core_{filename}.json"

            self._atomic_write_json(rel_out, relevant_by_core.get(core_qid, []))
            self._atomic_write_json(not_rel_out, not_relevant_by_core.get(core_qid, []))
