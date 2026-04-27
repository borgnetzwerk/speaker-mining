from __future__ import annotations

from pathlib import Path

from . import V4Handler
from ..common import canonical_pid, canonical_qid
from ..event_log import build_entity_discovered_event
from ..full_fetch import full_fetch


class FullFetchHandler(V4Handler):
    """Execute full_fetch for seeds and eligible candidates.

    Manages a fetch queue. Seeds enter at depth 0. Discovered objects enter at
    parent depth + 1 (up to depth_limit). Only QIDs matching the full_fetch_rules
    are enqueued.

    Reacts to: seed_registered, entity_discovered, entity_fetched,
               entity_marked_relevant, full_fetch_rule_registered
    Emits: (via full_fetch.py) entity_fetched, triple_discovered
    Writes: full_fetch_state.csv
    """

    def name(self) -> str:
        return "FullFetchHandler"

    def __init__(self, repo_root: Path, event_store=None, depth_limit: int = 2):
        super().__init__(repo_root, event_store)
        self._depth_limit = depth_limit
        self._queue: list[tuple[str, int]] = []  # (qid, depth)
        self._done: set[str] = set()
        self._rules: list[dict] = []  # full_fetch_rule_registered payloads

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}

        if etype == "seed_registered":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid and qid not in self._done:
                self._enqueue(qid, depth=0)

        elif etype == "full_fetch_rule_registered":
            self._rules.append(dict(payload))

        elif etype == "entity_fetched":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._done.add(qid)
                self._queue = [(q, d) for q, d in self._queue if q != qid]

        elif etype == "triple_discovered":
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            obj = canonical_qid(str(payload.get("object_qid", "") or ""))
            depth = int(payload.get("depth", 0))
            if not (subject and pid and obj):
                return
            obj_depth = depth + 1
            if obj_depth > self._depth_limit:
                return
            if obj in self._done or any(q == obj for q, _ in self._queue):
                return
            if self._passes_rules(subject, pid, obj):
                self._enqueue(obj, depth=obj_depth)

    def _enqueue(self, qid: str, depth: int) -> None:
        if qid not in self._done and not any(q == qid for q, _ in self._queue):
            self._queue.append((qid, depth))

    def _passes_rules(self, subject_qid: str, pid: str, obj_qid: str) -> bool:
        """Evaluate full_fetch_rules (permit/exclude) for the given triple."""
        if not self._rules:
            return False

        # Group rules by type
        permit_groups: dict[int, list[dict]] = {}
        exclude_groups: dict[int, list[dict]] = {}
        for rule in self._rules:
            rtype = str(rule.get("rule_type", ""))
            gid = int(rule.get("group_id", 0))
            if rtype == "permit":
                permit_groups.setdefault(gid, []).append(rule)
            elif rtype == "exclude":
                exclude_groups.setdefault(gid, []).append(rule)

        # Phase 1: exclude groups are absolute vetoes
        for gid, conditions in exclude_groups.items():
            if self._group_matches(conditions, subject_qid, pid, obj_qid):
                return False

        # Phase 2: permit — any matching group allows
        for gid, conditions in permit_groups.items():
            if self._group_matches(conditions, subject_qid, pid, obj_qid):
                return True

        return False

    def _group_matches(self, conditions: list[dict], subject_qid: str, pid: str, obj_qid: str) -> bool:
        """AND: all conditions in the group must match."""
        for cond in conditions:
            s = str(cond.get("subject", "*"))
            p = str(cond.get("predicate", "*"))
            o = str(cond.get("object", "*"))
            if not self._spo_matches(s, p, o, subject_qid, pid, obj_qid):
                return False
        return True

    @staticmethod
    def _spo_matches(s: str, p: str, o: str, subject_qid: str, pid: str, obj_qid: str) -> bool:
        """Match a single SPO condition against a triple."""
        # subject position
        if s == "CANDIDATE":
            pass  # candidate is always the object in the discovering triple context
        elif s != "*":
            pass  # source core class match — not evaluated here (ClassHierarchyHandler needed)

        # predicate position
        if p != "*" and p != pid:
            return False

        # object position
        if o == "CANDIDATE":
            pass  # always matches — candidate is by definition the object
        elif o != "*" and o != obj_qid:
            return False

        return True

    def has_pending(self) -> bool:
        return bool(self._queue)

    def do_next(self, *, languages: list[str] | None = None) -> int:
        """Full-fetch the next queued entity. Returns 1 if fetched, 0 if queue empty."""
        if not self._queue:
            return 0
        qid, depth = self._queue.pop(0)
        if qid in self._done:
            return 0
        # F5: emit entity_discovered before full_fetch (architecture §6.1 step 1)
        self._emit(build_entity_discovered_event(
            qid=qid,
            label="",
            source_step="entity_fetch",
            discovery_method="full_fetch",
        ))
        full_fetch(
            qid,
            repo_root=self._root,
            depth=depth,
            languages=languages or ["de", "en"],
            event_store=self._store,
        )
        return 1

    def _write(self, proj_dir: Path) -> None:
        rows = [[qid, "complete", ""] for qid in sorted(self._done)]
        rows += [[qid, "pending", depth] for qid, depth in self._queue]
        self._atomic_write_csv_rows(proj_dir / "full_fetch_state.csv", ["qid", "status", "depth"], rows)
