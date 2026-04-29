from __future__ import annotations

from pathlib import Path

from . import V4Handler
from ..basic_fetch import basic_fetch_batch
from ..common import canonical_pid, canonical_qid
from ..event_log import build_class_resolved_event


class ClassHierarchyHandler(V4Handler):
    """Incrementally resolves the P279 class hierarchy.

    For each new class QID encountered, walks P279 upward until a core class
    or the depth limit is reached. Only NEW class QIDs trigger a walk — previously
    resolved classes are no-ops (O(new classes) per run).

    Reacts to: entity_basic_fetched, triple_discovered, core_class_registered
    Emits: class_resolved (with core_class_qid field)
    Writes: class_resolution_map.csv (class_qid, parent_qids, depth, core_class_qid)
    """

    # D3: explicit walk terminators — Q35120 (entity) and Q1 (universe of discourse)
    _ROOT_CLASSES: frozenset[str] = frozenset({"Q35120", "Q1"})

    def name(self) -> str:
        return "ClassHierarchyHandler"

    def __init__(self, repo_root: Path, event_store=None, depth_limit: int = 8):
        super().__init__(repo_root, event_store)
        self._depth_limit = depth_limit
        self._resolved: dict[str, dict] = {}  # class_qid → {parent_qids, depth, core_class_ancestor}
        self._core_classes: set[str] = set()
        self._pending: list[str] = []  # class QIDs waiting to be walked
        self._load_snapshot()

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}

        if etype == "core_class_registered":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._core_classes.add(qid)
                # Core classes are resolved trivially — no walk needed
                if qid not in self._resolved:
                    self._resolved[qid] = {"parent_qids": [], "depth": 0, "core_class_ancestor": qid}

        elif etype == "triple_discovered":
            # Discover class nodes from P31 (instance-of) and P279 (subclass-of) triples (F20)
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            if pid == "P31":
                class_qid = canonical_qid(str(payload.get("object_qid", "") or ""))
                if class_qid and class_qid not in self._resolved and class_qid not in self._ROOT_CLASSES:
                    self._pending.append(class_qid)
            elif pid == "P279":
                for pos in ("subject_qid", "object_qid"):
                    qid = canonical_qid(str(payload.get(pos, "") or ""))
                    if qid and qid not in self._resolved and qid not in self._ROOT_CLASSES:
                        self._pending.append(qid)

        elif etype == "entity_rewired":
            # Synthetic triple added via rewiring_catalogue.csv (F11)
            if str(payload.get("rule", "add") or "add").lower() == "add":
                pid = canonical_qid(str(payload.get("predicate_pid", "") or ""))
                if pid == "P279":
                    subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
                    obj = canonical_qid(str(payload.get("object_qid", "") or ""))
                    if subject and subject not in self._resolved:
                        self._pending.append(subject)
                    if obj and obj not in self._resolved:
                        self._pending.append(obj)

        elif etype == "entity_basic_fetched":
            # Any P279 QIDs are class nodes; queue them for resolution
            p279_qids = payload.get("p279_qids", []) or []
            for qid in p279_qids:
                qid = canonical_qid(str(qid or ""))
                if qid and qid not in self._resolved:
                    self._pending.append(qid)

            # The entity itself is a class node if it has P279 claims
            subject_qid = canonical_qid(str(payload.get("qid", "") or ""))
            if subject_qid and p279_qids and subject_qid not in self._resolved:
                self._pending.append(subject_qid)

        elif etype == "class_resolved":
            class_qid = canonical_qid(str(payload.get("class_qid", "") or ""))
            if class_qid:
                parent_qids = list(payload.get("parent_qids", []) or [])
                depth = int(payload.get("depth", 0))
                core = self._find_core_ancestor(parent_qids)
                self._resolved[class_qid] = {
                    "parent_qids": parent_qids,
                    "depth": depth,
                    "core_class_ancestor": core,
                }
                if class_qid in self._pending:
                    self._pending.remove(class_qid)

    def _load_snapshot(self) -> None:
        """Populate in-memory state from projection CSVs written by previous runs."""
        import csv
        reg = self._proj / "core_class_registry.csv"
        if reg.exists():
            with reg.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    qid = canonical_qid(str(row.get("qid", "") or ""))
                    if qid:
                        self._core_classes.add(qid)
                        self._resolved.setdefault(qid, {"parent_qids": [], "depth": 0, "core_class_ancestor": qid})

        crm = self._proj / "class_resolution_map.csv"
        if crm.exists():
            with crm.open(newline="", encoding="utf-8") as fh:
                for row in csv.DictReader(fh):
                    class_qid = canonical_qid(str(row.get("class_qid", "") or ""))
                    if not class_qid:
                        continue
                    parent_str = str(row.get("parent_qids", "") or "")
                    parent_qids = [p for p in parent_str.split("|") if p] if parent_str else []
                    depth_val = row.get("depth", "0") or "0"
                    try:
                        depth = int(depth_val)
                    except (ValueError, TypeError):
                        depth = 0
                    core = str(row.get("core_class_qid", "") or "")
                    self._resolved[class_qid] = {
                        "parent_qids": parent_qids,
                        "depth": depth,
                        "core_class_ancestor": core,
                    }

        # Repair any entries with empty core that can be resolved from the loaded graph.
        self._backpropagate_cores()

    def has_pending(self) -> bool:
        return bool(self._pending)

    def resolve_next(self, *, languages: list[str] | None = None) -> int:
        """Walk the next pending class QID upward via P279. Returns count of events emitted."""
        if not self._pending:
            return 0

        qid = self._pending.pop(0)
        if qid in self._resolved:
            return 0

        return self._walk(qid, depth=0, languages=languages or ["de", "en"])

    def _walk(self, start_qid: str, depth: int, languages: list[str]) -> int:
        """Iterative upward P279 walk from start_qid.

        Collects all newly resolved nodes before emitting events, then
        backpropagates core_class_ancestor from child to ancestor (F32 fix).
        This ensures nodes whose parents are resolved later in the same walk
        still receive a correct core_class_qid in their emitted event.
        """
        to_resolve = [start_qid]
        # Walk-local staging area — not committed to _resolved until after backprop
        new_nodes: dict[str, dict] = {}  # qid → {parent_qids, depth, core_class_ancestor}

        while to_resolve:
            batch = [q for q in to_resolve if q not in self._resolved and q not in new_nodes]
            if not batch:
                break

            fetch_results = basic_fetch_batch(batch, repo_root=self._root, languages=languages)
            to_resolve = []

            for qid, info in fetch_results.items():
                parent_qids = info.get("p279_qids", [])
                core = self._find_core_ancestor_extended(parent_qids, new_nodes)
                new_nodes[qid] = {"parent_qids": parent_qids, "depth": depth, "core_class_ancestor": core}

                # Only walk further if core is still unknown
                if depth < self._depth_limit and not core:
                    for parent in parent_qids:
                        if parent not in self._resolved and parent not in new_nodes and parent not in self._ROOT_CLASSES:
                            to_resolve.append(parent)

            depth += 1
            if depth > self._depth_limit:
                break

        # Backpropagate: nodes fetched early may now find cores via later-fetched parents.
        changed = True
        while changed:
            changed = False
            for info in new_nodes.values():
                if info["core_class_ancestor"]:
                    continue
                core = self._find_core_ancestor_extended(info["parent_qids"], new_nodes)
                if core:
                    info["core_class_ancestor"] = core
                    changed = True

        # Commit to in-memory state and emit events with correct cores.
        emitted = 0
        for qid, info in new_nodes.items():
            core = info["core_class_ancestor"]
            self._resolved[qid] = {
                "parent_qids": info["parent_qids"],
                "depth": info["depth"],
                "core_class_ancestor": core,
            }
            event = build_class_resolved_event(
                class_qid=qid,
                parent_qids=info["parent_qids"],
                depth=info["depth"],
                core_class_qid=core,
            )
            self._emit(event)
            emitted += 1

        return emitted

    def _find_core_ancestor(self, parent_qids: list[str]) -> str:
        """Return the first core class QID found in parent_qids, or ''."""
        for qid in parent_qids:
            if qid in self._core_classes:
                return qid
            ancestor = self._resolved.get(qid, {}).get("core_class_ancestor", "")
            if ancestor:
                return ancestor
        return ""

    def _find_core_ancestor_extended(self, parent_qids: list[str], new_nodes: dict) -> str:
        """Like _find_core_ancestor but also checks walk-local new_nodes."""
        for qid in parent_qids:
            if qid in self._core_classes:
                return qid
            ancestor = self._resolved.get(qid, {}).get("core_class_ancestor", "")
            if ancestor:
                return ancestor
            ancestor = new_nodes.get(qid, {}).get("core_class_ancestor", "")
            if ancestor:
                return ancestor
        return ""

    def _backpropagate_cores(self) -> None:
        """Multi-pass core propagation over _resolved until stable.

        Repairs entries with core_class_ancestor='' from snapshots written
        before F32 was fixed.
        """
        changed = True
        while changed:
            changed = False
            for info in self._resolved.values():
                if info.get("core_class_ancestor"):
                    continue
                for parent in info.get("parent_qids", []):
                    if parent in self._core_classes:
                        info["core_class_ancestor"] = parent
                        changed = True
                        break
                    ancestor = self._resolved.get(parent, {}).get("core_class_ancestor", "")
                    if ancestor:
                        info["core_class_ancestor"] = ancestor
                        changed = True
                        break

    def resolve_class(self, qid: str) -> str:
        """Return core_class_ancestor for qid, or '' if unresolved."""
        return self._resolved.get(qid, {}).get("core_class_ancestor", "")

    def is_class_node(self, qid: str) -> bool:
        return qid in self._resolved

    def _write(self, proj_dir: Path) -> None:
        rows = [
            [class_qid, "|".join(info.get("parent_qids", [])), info.get("depth", 0), info.get("core_class_ancestor", "")]
            for class_qid, info in sorted(self._resolved.items())
        ]
        self._atomic_write_csv_rows(proj_dir / "class_resolution_map.csv", ["class_qid", "parent_qids", "depth", "core_class_qid"], rows)
