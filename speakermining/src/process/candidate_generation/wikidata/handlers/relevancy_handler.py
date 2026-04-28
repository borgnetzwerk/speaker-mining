from __future__ import annotations

import csv
from pathlib import Path

from . import V4Handler
from ..common import canonical_pid, canonical_qid
from ..event_log import build_entity_marked_relevant_event


class RelevancyHandler(V4Handler):
    """Mark entities as relevant by propagating relevancy via rule-governed triples.

    Seeds are authoritatively relevant. All other relevancy propagates when a
    triple (S, P, O) links a relevant entity via an approved predicate.

    F9: direction (forward/backward/both) is now honoured.
    F10: subject_core_class_qid / object_core_class_qid constraints are now checked.

    Reacts to: seed_registered, triple_discovered, entity_basic_fetched,
               core_class_registered, class_resolved,
               entity_marked_relevant, rule_changed
    Emits: entity_marked_relevant
    Writes: relevancy_map.csv
    """

    def name(self) -> str:
        return "RelevancyHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._relevant: dict[str, dict] = {}
        self._rules: list[dict] = []
        self._rule_pids: set[str] = set()
        # pid → [{direction, subject_core_class_qid, object_core_class_qid}]
        self._rules_by_pid: dict[str, list[dict]] = {}
        # reverse triple index for backward propagation (F9)
        self._triples_by_object: dict[str, list[tuple[str, str]]] = {}  # obj → [(pid, subject)]
        # core class lookup tables (F10)
        self._p31_map: dict[str, list[str]] = {}     # entity → p31 class qids
        self._class_to_core: dict[str, str] = {}     # class_qid → core_class_qid

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}
        ts = str(event.get("timestamp_utc", "") or "")

        if etype == "seed_registered":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid and qid not in self._relevant:
                self._mark_relevant(qid, ts, source_seed_qid=qid, inherited_from="", via_pid="", direction="")

        elif etype == "rule_changed":
            self._reload_rules_from_csv_direct(str(payload.get("rule_file", "") or ""))

        elif etype == "core_class_registered":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._class_to_core[qid] = qid

        elif etype == "class_resolved":
            class_qid = canonical_qid(str(payload.get("class_qid", "") or ""))
            core = str(payload.get("core_class_ancestor", "") or "")
            if class_qid and core:
                self._class_to_core[class_qid] = core

        elif etype == "entity_basic_fetched":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            p31 = list(payload.get("p31_qids", []) or [])
            if qid and p31:
                self._p31_map[qid] = p31

        elif etype == "entity_marked_relevant":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid and qid not in self._relevant:
                self._relevant[qid] = {
                    "first_marked_at": ts,
                    "source_seed_qid": str(payload.get("source_seed_qid", "") or ""),
                    "inherited_from_qid": str(payload.get("inherited_from_qid", "") or ""),
                    "inherited_via_pid": str(payload.get("inherited_via_pid", "") or ""),
                    "direction": str(payload.get("direction", "") or ""),
                }
                # Trigger backward propagation for any pending triples (F9)
                self._propagate_backward_from(qid, ts)

        elif etype == "entity_rewired":
            # Synthetic triple from rewiring_catalogue.csv — treat like triple_discovered (F11)
            if str(payload.get("rule", "add") or "add").lower() != "add":
                return
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            if subject and pid and obj and pid in self._rule_pids:
                self._triples_by_object.setdefault(obj, []).append((pid, subject))
                for rule in self._rules_by_pid.get(pid, []):
                    direction = (rule.get("direction") or "forward").lower()
                    if direction in ("forward", "both"):
                        if subject in self._relevant and obj not in self._relevant:
                            if self._constraints_match(rule, subject, obj):
                                seed = self._relevant[subject].get("source_seed_qid", subject)
                                self._mark_relevant(obj, ts, source_seed_qid=seed,
                                                    inherited_from=subject, via_pid=pid, direction="forward")
                    if direction in ("backward", "both"):
                        if obj in self._relevant and subject not in self._relevant:
                            if self._constraints_match(rule, subject, obj):
                                seed = self._relevant[obj].get("source_seed_qid", obj)
                                self._mark_relevant(subject, ts, source_seed_qid=seed,
                                                    inherited_from=obj, via_pid=pid, direction="backward")

        elif etype == "triple_discovered":
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            if not (subject and pid and obj):
                return

            # Track P31 claims for class constraint checking (F20)
            if pid == "P31":
                existing = self._p31_map.get(subject, [])
                if obj not in existing:
                    self._p31_map[subject] = existing + [obj]

            if pid in self._rule_pids:
                # Build reverse index for future backward propagation
                self._triples_by_object.setdefault(obj, []).append((pid, subject))

                for rule in self._rules_by_pid.get(pid, []):
                    direction = (rule.get("direction") or "forward").lower()

                    # Forward: relevant subject → mark object relevant
                    if direction in ("forward", "both"):
                        if subject in self._relevant and obj not in self._relevant:
                            if self._constraints_match(rule, subject, obj):
                                seed = self._relevant[subject].get("source_seed_qid", subject)
                                self._mark_relevant(obj, ts, source_seed_qid=seed,
                                                    inherited_from=subject, via_pid=pid, direction="forward")

                    # Backward: relevant object → mark subject relevant
                    if direction in ("backward", "both"):
                        if obj in self._relevant and subject not in self._relevant:
                            if self._constraints_match(rule, subject, obj):
                                seed = self._relevant[obj].get("source_seed_qid", obj)
                                self._mark_relevant(subject, ts, source_seed_qid=seed,
                                                    inherited_from=obj, via_pid=pid, direction="backward")

    def _propagate_backward_from(self, newly_relevant: str, ts: str) -> None:
        """When an entity becomes relevant, check if any stored triples allow backward propagation."""
        for pid, subject in self._triples_by_object.get(newly_relevant, []):
            if pid not in self._rule_pids or subject in self._relevant:
                continue
            for rule in self._rules_by_pid.get(pid, []):
                direction = (rule.get("direction") or "forward").lower()
                if direction in ("backward", "both"):
                    if self._constraints_match(rule, subject, newly_relevant):
                        seed = self._relevant[newly_relevant].get("source_seed_qid", newly_relevant)
                        self._mark_relevant(subject, ts, source_seed_qid=seed,
                                            inherited_from=newly_relevant, via_pid=pid, direction="backward")
                        break

    def _constraints_match(self, rule: dict, subject: str, obj: str) -> bool:
        """Check subject_core_class_qid / object_core_class_qid constraints (F10).

        Only rejects when the actual class is KNOWN and differs from the constraint.
        Unknown class (empty string) passes — avoids blocking propagation before
        class hierarchy has been resolved for freshly full_fetched entities (F20b).
        """
        subj_cc = str(rule.get("subject_core_class_qid", "") or "")
        obj_cc = str(rule.get("object_core_class_qid", "") or "")
        if subj_cc:
            actual = self._get_core_class(subject)
            if actual and actual != subj_cc:
                return False
        if obj_cc:
            actual = self._get_core_class(obj)
            if actual and actual != obj_cc:
                return False
        return True

    def _get_core_class(self, qid: str) -> str:
        for p31_qid in self._p31_map.get(qid, []):
            core = self._class_to_core.get(p31_qid, "")
            if core:
                return core
        return ""

    def _mark_relevant(self, qid: str, ts: str, *, source_seed_qid: str,
                       inherited_from: str, via_pid: str, direction: str) -> None:
        if qid in self._relevant:
            return
        self._relevant[qid] = {
            "first_marked_at": ts,
            "source_seed_qid": source_seed_qid,
            "inherited_from_qid": inherited_from,
            "inherited_via_pid": via_pid,
            "direction": direction,
        }
        self._emit(build_entity_marked_relevant_event(
            qid=qid,
            source_seed_qid=source_seed_qid,
            inherited_from_qid=inherited_from,
            inherited_via_pid=via_pid,
            direction=direction,
        ))

    def _reload_rules_from_csv_direct(self, rule_file: str) -> None:
        if rule_file != "relevancy_relation_contexts.csv":
            return
        rules = self._load_rules_from_csv()
        pids: set[str] = set()
        rules_by_pid: dict[str, list[dict]] = {}
        for rule in rules:
            # CSV uses "property_qid" not "predicate_pid"
            pid = canonical_pid(str(rule.get("property_qid", "") or ""))
            if not pid:
                continue
            # Only propagate-enabled rules (can_inherit = TRUE); others are tracked only
            can_inherit = str(rule.get("can_inherit", "") or "").strip().upper()
            if can_inherit != "TRUE":
                continue
            pids.add(pid)
            # CSV uses "subject_class_qid" / "object_class_qid", not *_core_class_qid
            rules_by_pid.setdefault(pid, []).append({
                "direction": "forward",
                "subject_core_class_qid": canonical_qid(str(rule.get("subject_class_qid", "") or "")),
                "object_core_class_qid": canonical_qid(str(rule.get("object_class_qid", "") or "")),
            })
        self._rules = rules
        self._rule_pids = pids
        self._rules_by_pid = rules_by_pid

    def _load_rules_from_csv(self) -> list[dict]:
        from ..schemas import build_artifact_paths
        paths = build_artifact_paths(self._root)
        setup_csv = self._root / "data" / "00_setup" / "relevancy_relation_contexts.csv"
        source = setup_csv if setup_csv.exists() else paths.relevancy_relation_contexts_csv
        if not source.exists():
            return []
        with source.open(newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def is_relevant(self, qid: str) -> bool:
        return qid in self._relevant

    def _write(self, proj_dir: Path) -> None:
        header = ["entity_qid", "relevant", "first_marked_at", "source_seed_qid",
                  "inherited_from_qid", "inherited_via_pid", "direction"]
        rows = [
            [qid, "true", info.get("first_marked_at", ""), info.get("source_seed_qid", ""),
             info.get("inherited_from_qid", ""), info.get("inherited_via_pid", ""), info.get("direction", "")]
            for qid, info in sorted(self._relevant.items())
        ]
        self._atomic_write_csv_rows(proj_dir / "relevancy_map.csv", header, rows)
