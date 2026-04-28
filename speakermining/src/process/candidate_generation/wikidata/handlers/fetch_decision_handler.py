from __future__ import annotations

import csv
from pathlib import Path

from . import V4Handler
from ..common import canonical_pid, canonical_qid
from ..event_log import build_fetch_decision_event


class FetchDecisionHandler(V4Handler):
    """Classify objects of full_fetched relevant entities as potentially_relevant or unlikely_relevant.

    Reacts to: triple_discovered, entity_fetched, entity_marked_relevant,
               entity_basic_fetched, rule_changed
    Emits: fetch_decision
    Writes: discovery_classification.csv
    """

    def name(self) -> str:
        return "FetchDecisionHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._rule_pids: set[str] = set()
        self._full_fetched: set[str] = set()   # subjects that have been entity_fetched
        self._relevant: set[str] = set()        # entities marked relevant
        self._basic_fetched: set[str] = set()   # already basic_fetched objects (skip)
        # pending triples: waiting for subject to become full_fetched AND relevant
        self._pending: dict[str, list[tuple[str, str]]] = {}  # subject_qid → [(pid, obj_qid)]
        self._decisions: dict[str, dict] = {}  # obj_qid → {subject_qid, predicate_pid, classification, basic_fetch_status}

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}

        if etype == "rule_changed":
            self._reload_rule_pids()
            self._reevaluate_deferred()

        elif etype == "entity_fetched":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._full_fetched.add(qid)
                self._flush_pending(qid)

        elif etype == "entity_marked_relevant":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._relevant.add(qid)
                self._flush_pending(qid)

        elif etype == "entity_basic_fetched":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._basic_fetched.add(qid)
                if qid in self._decisions:
                    self._decisions[qid]["basic_fetch_status"] = "complete"

        elif etype == "fetch_decision":
            obj_qid = canonical_qid(str(payload.get("qid", "") or ""))
            if obj_qid and obj_qid not in self._decisions:
                self._decisions[obj_qid] = {
                    "subject_qid": "",
                    "predicate_pid": "",
                    "classification": str(payload.get("decision", "") or ""),
                    "basic_fetch_status": "pending",
                }

        elif etype == "triple_discovered":
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            if not (subject and pid and obj):
                return
            if obj in self._decisions or obj in self._basic_fetched:
                return
            ready = subject in self._full_fetched and subject in self._relevant
            if ready:
                self._classify(subject, pid, obj)
            else:
                self._pending.setdefault(subject, []).append((pid, obj))

    def _flush_pending(self, qid: str) -> None:
        if qid not in self._full_fetched or qid not in self._relevant:
            return
        for pid, obj in self._pending.pop(qid, []):
            if obj not in self._decisions and obj not in self._basic_fetched:
                self._classify(qid, pid, obj)

    def _classify(self, subject: str, pid: str, obj: str) -> None:
        classification = "potentially_relevant" if pid in self._rule_pids else "unlikely_relevant"
        self._emit(build_fetch_decision_event(
            qid=obj,
            decision=classification,
            reason=f"predicate={pid}",
        ))
        self._decisions[obj] = {
            "subject_qid": subject,
            "predicate_pid": pid,
            "classification": classification,
            "basic_fetch_status": "pending",
        }

    def _reevaluate_deferred(self) -> None:
        """Promote unlikely_relevant entries whose predicate now matches updated rules (F14)."""
        for obj_qid, info in self._decisions.items():
            if info.get("classification") != "unlikely_relevant":
                continue
            if info.get("basic_fetch_status") == "complete":
                continue
            if canonical_pid(str(info.get("predicate_pid", "") or "")) in self._rule_pids:
                info["classification"] = "potentially_relevant"
                self._emit(build_fetch_decision_event(
                    qid=obj_qid,
                    decision="potentially_relevant",
                    reason="rule_changed_promotion",
                ))

    def _reload_rule_pids(self) -> None:
        from ..schemas import build_artifact_paths
        paths = build_artifact_paths(self._root)
        setup_csv = self._root / "data" / "00_setup" / "relevancy_relation_contexts.csv"
        source = setup_csv if setup_csv.exists() else paths.relevancy_relation_contexts_csv
        if not source.exists():
            return
        pids: set[str] = set()
        with source.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                # Column is "property_qid" in the CSV (not "predicate_pid")
                pid = canonical_pid(str(row.get("property_qid", "") or ""))
                if pid:
                    pids.add(pid)
        self._rule_pids = pids

    def get_potentially_relevant_pending(self) -> list[str]:
        return [
            qid for qid, info in self._decisions.items()
            if info["classification"] == "potentially_relevant" and info["basic_fetch_status"] == "pending"
        ]

    def get_unlikely_relevant_pending(self) -> list[str]:
        return [
            qid for qid, info in self._decisions.items()
            if info["classification"] == "unlikely_relevant" and info["basic_fetch_status"] == "pending"
        ]

    def _write(self, proj_dir: Path) -> None:
        header = ["object_qid", "subject_qid", "predicate_pid", "classification", "basic_fetch_status"]
        rows = [
            [obj_qid, info.get("subject_qid", ""), info.get("predicate_pid", ""),
             info.get("classification", ""), info.get("basic_fetch_status", "pending")]
            for obj_qid, info in sorted(self._decisions.items())
        ]
        self._atomic_write_csv_rows(proj_dir / "discovery_classification.csv", header, rows)
