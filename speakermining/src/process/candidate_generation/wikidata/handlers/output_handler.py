from __future__ import annotations

from pathlib import Path

from . import V4Handler
from ..common import canonical_qid


class CoreClassOutputHandler(V4Handler):
    """Write core_<class>.json and not_relevant_core_<class>.json handover files.

    Reads entity classification from domain events, then fetches full raw Wikidata
    JSON from the entity cache for each entity. Output format: {QID: raw_entity_doc}.

    Reacts to: entity_fetched, entity_basic_fetched, triple_discovered (P31 only),
               entity_marked_relevant, class_resolved, core_class_registered
    Writes: core_<class>.json, not_relevant_core_<class>.json per core class
    """

    def name(self) -> str:
        return "CoreClassOutputHandler"

    def _load_seq(self) -> int:
        return 0  # always replay all events to reconstruct classification state

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._core_classes: dict[str, str] = {}           # qid → label
        self._core_class_mode: dict[str, str] = {}        # qid → projection_mode
        self._labels: dict[str, str] = {}                 # qid → label (entity existence registry)
        self._relevant: set[str] = set()
        self._p31_map: dict[str, list[str]] = {}          # entity qid → p31 qids
        self._class_to_core: dict[str, str] = {}          # class_qid → core_class_qid
        self._class_parent_qids: dict[str, list[str]] = {}  # class_qid → parent_qids (for backprop)

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
            parents = list(payload.get("parent_qids", []) or [])
            if class_qid and parents:
                self._class_parent_qids[class_qid] = parents
            if not core:
                # Fallback for old events where core_class_qid was emitted empty (pre-F32)
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
            if qid:
                self._labels[qid] = label
            p31 = payload.get("p31_qids", [])
            if qid and p31:
                self._p31_map[qid] = list(p31)

        elif etype == "triple_discovered":
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = str(payload.get("predicate_pid", "") or "")
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            if subject and pid == "P31" and obj:
                p31 = self._p31_map.setdefault(subject, [])
                if obj not in p31:
                    p31.append(obj)

    def _resolve_core_classes(self, qid: str) -> list[str]:
        cores = []
        for p31_qid in self._p31_map.get(qid, []):
            core = self._class_to_core.get(p31_qid, "")
            if not core and p31_qid in self._core_classes:
                core = p31_qid
            if core and core not in cores:
                cores.append(core)
        return cores

    def _subclass_entities_for_core(self, core_qid: str) -> set[str]:
        return {qid for qid, ancestor in self._class_to_core.items() if ancestor == core_qid}

    def _backpropagate_class_to_core(self) -> None:
        """Multi-pass propagation over _class_to_core until stable.

        Fills gaps from old events where core_class_qid was emitted empty (pre-F32).
        Uses _class_parent_qids to walk from each unmapped class toward its core ancestor.
        """
        changed = True
        while changed:
            changed = False
            for class_qid, parents in self._class_parent_qids.items():
                if class_qid in self._class_to_core:
                    continue
                for p in parents:
                    if p in self._core_classes:
                        self._class_to_core[class_qid] = p
                        changed = True
                        break
                    candidate = self._class_to_core.get(p, "")
                    if candidate:
                        self._class_to_core[class_qid] = candidate
                        changed = True
                        break

    def _get_entity_from_cache(self, qid: str) -> dict | None:
        from ..cache import _entity_from_payload, _latest_cached_record
        from ..event_log import get_query_event_response_data
        # Prefer full entity_fetch data; fall back to basic_fetch for non-full_fetched entities (F29/F30)
        for cache_type in ("entity", "basic_fetch"):
            cached = _latest_cached_record(self._root, cache_type, qid)
            if cached is not None:
                break
        else:
            return None
        record, _ = cached
        response_data = get_query_event_response_data(record)
        return _entity_from_payload({"entities": response_data.get("entities", {})}, qid) or None

    def _write(self, proj_dir: Path) -> None:
        from ..schemas import canonical_class_filename

        # Repair any class→core mappings that were empty due to pre-F32 event ordering
        self._backpropagate_class_to_core()

        # Write core class registry CSV
        registry_rows = [[qid, label] for qid, label in sorted(self._core_classes.items())]
        self._atomic_write_csv_rows(proj_dir / "core_class_registry.csv", ["qid", "label"], registry_rows)

        relevant_by_core: dict[str, dict] = {qid: {} for qid in self._core_classes}
        not_relevant_by_core: dict[str, dict] = {qid: {} for qid in self._core_classes}

        instances_cores = {qid for qid, mode in self._core_class_mode.items() if mode != "subclasses"}
        subclasses_cores = {qid for qid, mode in self._core_class_mode.items() if mode == "subclasses"}

        # Instances strategy: classify via P31 map
        for entity_qid in set(self._labels.keys()):
            cores = [c for c in self._resolve_core_classes(entity_qid) if c in instances_cores]
            if not cores:
                continue
            entity_doc = self._get_entity_from_cache(entity_qid)
            if entity_doc is None:
                continue
            for core in cores:
                if entity_qid in self._relevant:
                    relevant_by_core[core][entity_qid] = entity_doc
                else:
                    not_relevant_by_core[core][entity_qid] = entity_doc

        # Subclasses strategy: classify via P279 chain
        for core_qid in subclasses_cores:
            for entity_qid in self._subclass_entities_for_core(core_qid):
                if entity_qid == core_qid:
                    continue
                entity_doc = self._get_entity_from_cache(entity_qid)
                if entity_doc is None:
                    continue
                if entity_qid in self._relevant:
                    relevant_by_core[core_qid][entity_qid] = entity_doc
                else:
                    not_relevant_by_core[core_qid][entity_qid] = entity_doc

        for core_qid in self._core_classes:
            class_name = self._core_classes.get(core_qid, core_qid)
            try:
                filename = canonical_class_filename(class_name)
            except ValueError:
                filename = core_qid.lower()

            self._atomic_write_json(proj_dir / f"core_{filename}.json", relevant_by_core.get(core_qid, {}))
            self._atomic_write_json(proj_dir / f"not_relevant_core_{filename}.json", not_relevant_by_core.get(core_qid, {}))
