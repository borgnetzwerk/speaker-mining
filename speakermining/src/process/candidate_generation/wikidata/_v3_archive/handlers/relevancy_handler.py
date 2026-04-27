"""RelevancyHandler: builds relevancy.csv from relevance_assigned events."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.common import canonical_qid
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


class RelevancyHandler(EventHandler):
    """Maintains the monotonic relevancy projection for core instances."""

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self._rows: dict[str, dict] = {}

    @staticmethod
    def _to_bool(value: object) -> bool:
        token = str(value or "").strip().lower()
        return token in {"1", "true", "yes", "y", "on"}

    def name(self) -> str:
        return "RelevancyHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def bootstrap_from_projection(self, output_path: Path) -> bool:
        output_path = Path(output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            return False
        try:
            df = pd.read_csv(output_path)
        except Exception:
            return False
        if df.empty:
            self._rows = {}
            return True

        rows: dict[str, dict] = {}
        for row in df.fillna("").to_dict(orient="records"):
            qid = canonical_qid(str(row.get("qid", "") or ""))
            if not qid:
                continue
            rows[qid] = {
                "qid": qid,
                "is_core_class_instance": self._to_bool(row.get("is_core_class_instance", False)),
                "relevant": self._to_bool(row.get("relevant", False)),
                "relevant_seed_source": str(row.get("relevant_seed_source", "") or ""),
                "relevance_first_assigned_at": str(row.get("relevance_first_assigned_at", "") or ""),
                "relevance_last_updated_at": str(row.get("relevance_last_updated_at", "") or ""),
                "relevance_inherited_from_qid": str(row.get("relevance_inherited_from_qid", "") or ""),
                "relevance_inherited_via_property_qid": str(row.get("relevance_inherited_via_property_qid", "") or ""),
                "relevance_inherited_via_direction": str(row.get("relevance_inherited_via_direction", "") or ""),
                "relevance_evidence_event_sequence": int(row.get("relevance_evidence_event_sequence", 0) or 0),
            }
        self._rows = rows
        return True

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                self._last_seq = max(self._last_seq, seq)
            if event.get("event_type") != "relevance_assigned":
                continue

            payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
            qid = canonical_qid(str(payload.get("entity_qid", "") or ""))
            if not qid:
                continue

            current = self._rows.get(qid, {"qid": qid})
            already_relevant = bool(current.get("relevant", False))
            if already_relevant:
                continue

            assigned_at = str(payload.get("relevance_first_assigned_at", "") or event.get("timestamp_utc", "") or "")
            current.update(
                {
                    "qid": qid,
                    "is_core_class_instance": bool(payload.get("is_core_class_instance", True)),
                    "relevant": bool(payload.get("relevant", False)),
                    "relevant_seed_source": str(payload.get("relevant_seed_source", "") or ""),
                    "relevance_first_assigned_at": assigned_at,
                    "relevance_last_updated_at": str(event.get("timestamp_utc", "") or assigned_at),
                    "relevance_inherited_from_qid": str(payload.get("relevance_inherited_from_qid", "") or ""),
                    "relevance_inherited_via_property_qid": str(payload.get("relevance_inherited_via_property_qid", "") or ""),
                    "relevance_inherited_via_direction": str(payload.get("relevance_inherited_via_direction", "") or ""),
                    "relevance_evidence_event_sequence": int(seq or 0),
                }
            )
            self._rows[qid] = current

    def materialize(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        columns = [
            "qid",
            "is_core_class_instance",
            "relevant",
            "relevant_seed_source",
            "relevance_first_assigned_at",
            "relevance_last_updated_at",
            "relevance_inherited_from_qid",
            "relevance_inherited_via_property_qid",
            "relevance_inherited_via_direction",
            "relevance_evidence_event_sequence",
        ]
        if not self._rows:
            df = pd.DataFrame(columns=columns)
        else:
            rows = [self._rows[qid] for qid in sorted(self._rows)]
            df = pd.DataFrame(rows, columns=columns)

        _atomic_write_df(output_path, df)

    def update_progress(self, last_seq: int) -> None:
        self._last_seq = last_seq
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), last_seq)
