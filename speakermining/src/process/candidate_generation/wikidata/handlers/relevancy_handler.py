from __future__ import annotations

import csv
from pathlib import Path

from . import V4Handler
from ..common import canonical_pid, canonical_qid
from ..event_log import build_entity_marked_relevant_event


class RelevancyHandler(V4Handler):
    """Mark entities as relevant by propagating relevancy via rule-governed triples.

    Seeds are authoritatively relevant. All other relevancy propagates when a
    triple (S, P, O) links a relevant entity to O via an approved predicate P.

    Reacts to: seed_registered, triple_discovered, class_resolved,
               entity_marked_relevant, rule_changed
    Emits: entity_marked_relevant
    Writes: relevancy_map.csv
    """

    def name(self) -> str:
        return "RelevancyHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._relevant: dict[str, dict] = {}  # qid → {first_marked_at, source_seed_qid, inherited_from_qid, inherited_via_pid, direction}
        self._rules: list[dict] = []  # loaded from rule_changed events
        self._rule_pids: set[str] = set()
        # pending triples where object's class is not yet resolved: class_qid → list of triple dicts
        self._pending_by_class: dict[str, list[dict]] = {}

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}
        ts = str(event.get("timestamp_utc", "") or "")

        if etype == "seed_registered":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid and qid not in self._relevant:
                self._mark_relevant(qid, ts, source_seed_qid=qid, inherited_from="", via_pid="", direction="")

        elif etype == "rule_changed":
            self._reload_rules_from_events()

        elif etype == "entity_marked_relevant":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid and qid not in self._relevant:
                self._relevant[qid] = {
                    "first_marked_at": ts,
                    "source_seed_qid": str(payload.get("source_seed_qid", "") or ""),
                    "inherited_from_qid": str(payload.get("inherited_from_qid", "") or ""),
                    "inherited_via_pid": str(payload.get("via_pid", "") or ""),
                    "direction": str(payload.get("direction", "") or ""),
                }

        elif etype == "triple_discovered":
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            if subject and pid and obj and subject in self._relevant and pid in self._rule_pids:
                if obj not in self._relevant:
                    seed = self._relevant[subject].get("source_seed_qid", subject)
                    self._mark_relevant(obj, ts, source_seed_qid=seed, inherited_from=subject, via_pid=pid, direction="forward")

    def _mark_relevant(self, qid: str, ts: str, *, source_seed_qid: str, inherited_from: str, via_pid: str, direction: str) -> None:
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
            core_class_qid="",
            via_rule=via_pid,
        ))

    def _reload_rules_from_events(self) -> None:
        from ..event_log import iter_all_events
        rules = []
        pids: set[str] = set()
        for event in iter_all_events(self._root):
            if event.get("event_type") != "rule_changed":
                continue
            p = event.get("payload", {}) or {}
            if str(p.get("rule_file", "")) == "relevancy_relation_contexts.csv":
                rules = self._load_rules_from_csv()
        for rule in rules:
            pid = canonical_pid(str(rule.get("predicate_pid", "") or ""))
            if pid:
                pids.add(pid)
        self._rules = rules
        self._rule_pids = pids

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
        out = proj_dir / "relevancy_map.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["entity_qid", "relevant", "first_marked_at", "source_seed_qid", "inherited_from_qid", "inherited_via_pid", "direction"])
            for qid, info in sorted(self._relevant.items()):
                writer.writerow([
                    qid,
                    "true",
                    info.get("first_marked_at", ""),
                    info.get("source_seed_qid", ""),
                    info.get("inherited_from_qid", ""),
                    info.get("inherited_via_pid", ""),
                    info.get("direction", ""),
                ])
