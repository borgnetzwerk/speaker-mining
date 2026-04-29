from __future__ import annotations

from pathlib import Path

from . import V4Handler
from ..basic_fetch import basic_fetch_batch
from ..common import canonical_pid, canonical_qid
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
        self._info: dict[str, dict] = {}            # qid → {classification, subject_qid, predicate_pid}
        self._load_snapshot()

    def _load_snapshot(self) -> None:
        """Populate in-memory state from basic_fetch_state.csv written by previous runs."""
        import csv
        bfs = self._proj / "basic_fetch_state.csv"
        if not bfs.exists():
            return
        with bfs.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                qid = canonical_qid(str(row.get("qid", "") or ""))
                if not qid:
                    continue
                classification = str(row.get("classification", "") or "")
                status = str(row.get("status", "") or "")
                self._info[qid] = {
                    "classification": classification,
                    "predicate_pid": str(row.get("predicate_pid", "") or ""),
                    "subject_qid": str(row.get("subject_qid", "") or ""),
                }
                if status == "complete":
                    self._done.add(qid)
                elif status == "pending":
                    if qid not in self._pending_immediate:
                        self._pending_immediate.append(qid)
                elif status == "deferred":
                    if qid not in self._pending_deferred:
                        self._pending_deferred.append(qid)

    def _on_event(self, event: dict) -> None:
        etype = event.get("event_type")
        payload = event.get("payload", {}) or {}

        if etype == "fetch_decision":
            qid = canonical_qid(str(payload.get("qid", "") or ""))
            decision = str(payload.get("decision", "") or "")
            if not qid or qid in self._done:
                return
            subject = canonical_qid(str(payload.get("subject_qid", "") or ""))
            pid = canonical_pid(str(payload.get("predicate_pid", "") or ""))
            if decision == "potentially_relevant":
                if qid in self._pending_deferred:
                    self._pending_deferred.remove(qid)
                if qid not in self._pending_immediate:
                    self._pending_immediate.append(qid)
                self._info[qid] = {"classification": "potentially_relevant", "subject_qid": subject, "predicate_pid": pid}
            elif decision == "unlikely_relevant" and qid not in self._pending_immediate:
                if qid not in self._pending_deferred:
                    self._pending_deferred.append(qid)
                self._info.setdefault(qid, {"classification": "unlikely_relevant", "subject_qid": subject, "predicate_pid": pid})

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
        header = ["qid", "classification", "status", "predicate_pid", "subject_qid"]
        rows = []
        for qid in sorted(self._done):
            info = self._info.get(qid, {})
            rows.append([qid, info.get("classification", ""), "complete",
                         info.get("predicate_pid", ""), info.get("subject_qid", "")])
        for qid in self._pending_immediate:
            info = self._info.get(qid, {})
            rows.append([qid, info.get("classification", "potentially_relevant"), "pending",
                         info.get("predicate_pid", ""), info.get("subject_qid", "")])
        for qid in self._pending_deferred:
            info = self._info.get(qid, {})
            rows.append([qid, info.get("classification", "unlikely_relevant"), "deferred",
                         info.get("predicate_pid", ""), info.get("subject_qid", "")])
        self._atomic_write_csv_rows(proj_dir / "basic_fetch_state.csv", header, rows)
