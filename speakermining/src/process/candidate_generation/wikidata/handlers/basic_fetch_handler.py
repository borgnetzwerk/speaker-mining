from __future__ import annotations

from pathlib import Path

from . import V4Handler
from ..basic_fetch import basic_fetch_batch
from ..common import canonical_qid
from ..event_log import build_entity_basic_fetched_event


class BasicFetchHandler(V4Handler):
    """Execute basic_fetch batches for potentially_relevant discovered objects.

    Reads fetch_decision events to populate its queue, then drains the queue
    by calling basic_fetch_batch. Emits entity_basic_fetched for each result.

    Reacts to: fetch_decision, entity_basic_fetched
    Emits: entity_basic_fetched
    Writes: basic_fetch_state.csv
    """

    def name(self) -> str:
        return "BasicFetchHandler"

    def __init__(self, repo_root: Path, event_store=None):
        super().__init__(repo_root, event_store)
        self._pending_immediate: list[str] = []     # potentially_relevant
        self._pending_deferred: list[str] = []      # unlikely_relevant
        self._done: set[str] = set()

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}

        if etype == "fetch_decision":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            decision = str(payload.get("decision", "") or "")
            if not qid or qid in self._done:
                return
            if decision == "potentially_relevant" and qid not in self._pending_immediate:
                self._pending_immediate.append(qid)
            elif decision == "unlikely_relevant" and qid not in self._pending_deferred:
                self._pending_deferred.append(qid)

        elif etype == "entity_basic_fetched":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            if qid:
                self._done.add(qid)
                if qid in self._pending_immediate:
                    self._pending_immediate.remove(qid)
                if qid in self._pending_deferred:
                    self._pending_deferred.remove(qid)

    def has_immediate_pending(self) -> bool:
        return bool(self._pending_immediate)

    def has_deferred_pending(self) -> bool:
        return bool(self._pending_deferred)

    def do_next_batch(self, *, languages: list[str] | None = None, batch_size: int = 50) -> int:
        """Fetch the next batch of immediately-pending QIDs. Returns count emitted."""
        batch = self._pending_immediate[:batch_size]
        if not batch:
            return 0
        return self._fetch_and_emit(batch, languages=languages or ["de", "en"])

    def do_next_deferred_batch(self, *, languages: list[str] | None = None, batch_size: int = 50) -> int:
        """Fetch the next batch of deferred QIDs. Returns count emitted."""
        batch = self._pending_deferred[:batch_size]
        if not batch:
            return 0
        return self._fetch_and_emit(batch, languages=languages or ["de", "en"])

    def _fetch_and_emit(self, qids: list[str], languages: list[str]) -> int:
        results = basic_fetch_batch(qids, repo_root=self._root, languages=languages)
        emitted = 0
        for qid, info in results.items():
            self._emit(build_entity_basic_fetched_event(
                qid=qid,
                label=info.get("label", ""),
                p31_qids=info.get("p31_qids", []),
                p279_qids=info.get("p279_qids", []),
                source=info.get("source", "network"),
            ))
            emitted += 1
        return emitted

    def _write(self, proj_dir: Path) -> None:
        rows = [[qid, "complete"] for qid in sorted(self._done)]
        rows += [[qid, "pending_immediate"] for qid in self._pending_immediate]
        rows += [[qid, "pending_deferred"] for qid in self._pending_deferred]
        self._atomic_write_csv_rows(proj_dir / "basic_fetch_state.csv", ["qid", "status"], rows)
