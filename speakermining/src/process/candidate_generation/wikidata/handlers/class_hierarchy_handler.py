from __future__ import annotations

import csv
from pathlib import Path

from . import V4Handler
from ..basic_fetch import basic_fetch_batch
from ..common import canonical_qid
from ..event_log import build_class_resolved_event


class ClassHierarchyHandler(V4Handler):
    """Incrementally resolves the P279 class hierarchy.

    For each new class QID encountered, walks P279 upward until a core class
    or the depth limit is reached. Only NEW class QIDs trigger a walk — previously
    resolved classes are no-ops (O(new classes) per run).

    Reacts to: entity_basic_fetched, core_class_registered
    Emits: class_resolved
    Writes: class_resolution_map.csv (class_qid, parent_qids_csv, depth, core_class_ancestor)
    """

    def name(self) -> str:
        return "ClassHierarchyHandler"

    def __init__(self, repo_root: Path, event_store=None, depth_limit: int = 8):
        super().__init__(repo_root, event_store)
        self._depth_limit = depth_limit
        self._resolved: dict[str, dict] = {}  # class_qid → {parent_qids, depth, core_class_ancestor}
        self._core_classes: set[str] = set()
        self._pending: list[str] = []  # class QIDs waiting to be walked

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
        """Iterative upward P279 walk from start_qid."""
        to_resolve = [start_qid]
        emitted = 0

        while to_resolve:
            batch = [q for q in to_resolve if q not in self._resolved]
            if not batch:
                break

            fetch_results = basic_fetch_batch(batch, repo_root=self._root, languages=languages)
            to_resolve = []

            for qid, info in fetch_results.items():
                parent_qids = info.get("p279_qids", [])
                event = build_class_resolved_event(
                    class_qid=qid,
                    parent_qids=parent_qids,
                    depth=depth,
                )
                self._emit(event)
                emitted += 1

                core = self._find_core_ancestor(parent_qids)
                self._resolved[qid] = {
                    "parent_qids": parent_qids,
                    "depth": depth,
                    "core_class_ancestor": core,
                }

                if depth < self._depth_limit and not core:
                    for parent in parent_qids:
                        if parent not in self._resolved:
                            to_resolve.append(parent)

            depth += 1
            if depth > self._depth_limit:
                break

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

    def resolve_class(self, qid: str) -> str:
        """Return core_class_ancestor for qid, or '' if unresolved."""
        return self._resolved.get(qid, {}).get("core_class_ancestor", "")

    def is_class_node(self, qid: str) -> bool:
        return qid in self._resolved

    def _write(self, proj_dir: Path) -> None:
        out = proj_dir / "class_resolution_map.csv"
        with out.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["class_qid", "parent_qids", "depth", "core_class_ancestor"])
            for class_qid, info in sorted(self._resolved.items()):
                writer.writerow([
                    class_qid,
                    "|".join(info.get("parent_qids", [])),
                    info.get("depth", 0),
                    info.get("core_class_ancestor", ""),
                ])
