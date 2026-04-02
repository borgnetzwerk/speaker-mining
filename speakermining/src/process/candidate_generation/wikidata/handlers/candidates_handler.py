"""CandidatesHandler stub for Phase 1.

Phase 1 behavior: accept events, no-op unless candidate_matched events are present.
Materialization writes an empty CSV with stable headers when no candidates exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


class CandidatesHandler(EventHandler):
    """Phase-1 stub handler for candidate matching events."""

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self._candidates: list[dict] = []

    def name(self) -> str:
        return "CandidatesHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                self._last_seq = max(self._last_seq, seq)
            if event.get("event_type") != "candidate_matched":
                continue
            payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}

            def _field(name: str) -> str:
                if name in payload:
                    return str(payload.get(name, "") or "")
                return str(event.get(name, "") or "")

            mention_id = _field("mention_id")
            candidate_id = _field("candidate_id")
            if mention_id and candidate_id:
                self._candidates.append({
                    "mention_id": mention_id,
                    "mention_type": _field("mention_type"),
                    "mention_label": _field("mention_label"),
                    "candidate_id": candidate_id,
                    "candidate_label": _field("candidate_label"),
                    "source": _field("source"),
                    "context": _field("context"),
                })

    def materialize(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        columns = ["mention_id", "mention_type", "mention_label", "candidate_id", "candidate_label", "source", "context"]
        if not self._candidates:
            df = pd.DataFrame(columns=columns)
        else:
            df = pd.DataFrame(self._candidates, columns=columns)
            df = df.drop_duplicates(subset=["mention_id", "candidate_id"]).sort_values(["mention_id", "candidate_id"])
        
        _atomic_write_df(output_path, df)

    def update_progress(self, last_seq: int) -> None:
        self._last_seq = last_seq
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), last_seq)
