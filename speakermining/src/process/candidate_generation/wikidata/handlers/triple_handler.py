"""TripleHandler: builds triples projection from events carrying entity claim payloads."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.common import canonical_pid, canonical_qid
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.event_log import get_query_event_field, get_query_event_response_data
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


def _extract_item_triples(subject_qid: str, claims: dict) -> list[tuple[str, str, str]]:
    triples: list[tuple[str, str, str]] = []
    if not isinstance(claims, dict):
        return triples
    subj = canonical_qid(subject_qid)
    if not subj:
        return triples
    for pid_raw, claim_list in claims.items():
        pid = canonical_pid(pid_raw)
        if not pid:
            continue
        for claim in claim_list or []:
            mainsnak = claim.get("mainsnak", {}) if isinstance(claim, dict) else {}
            value = (mainsnak.get("datavalue", {}) or {}).get("value")
            if isinstance(value, dict) and value.get("entity-type") == "item":
                obj = canonical_qid(value.get("id", ""))
                if obj:
                    triples.append((subj, pid, obj))
    return triples


def _iter_entities_from_event(event: dict) -> list[tuple[str, dict]]:
    """Return entity docs found in common event payload shapes.

    This allows replay from historical logs that predate specialized triple events.
    """
    if not isinstance(event, dict):
        return []

    containers: list[dict] = []

    response_payload = get_query_event_response_data(event)
    if isinstance(response_payload, dict):
        containers.append(response_payload)

    payload = event.get("payload")
    if isinstance(payload, dict):
        containers.append(payload)
        nested = payload.get("response_data")
        if isinstance(nested, dict):
            containers.append(nested)

    entities: list[tuple[str, dict]] = []
    seen_keys: set[str] = set()
    for container in containers:
        raw_entities = container.get("entities")
        if not isinstance(raw_entities, dict):
            continue
        for qid, doc in raw_entities.items():
            qid_norm = canonical_qid(qid)
            if not qid_norm or not isinstance(doc, dict):
                continue
            dedupe_key = f"{qid_norm}:{id(doc)}"
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            entities.append((qid_norm, doc))

    return entities


class TripleHandler(EventHandler):
    """Maintains deduplicated `triples.csv` from any event carrying entity claims."""

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self._triples: dict[tuple[str, str, str], dict] = {}

    def name(self) -> str:
        return "TripleHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def bootstrap_from_projection(self, output_path: Path) -> bool:
        """Hydrate in-memory triples from existing projection for incremental replay."""
        output_path = Path(output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            return False
        try:
            df = pd.read_csv(output_path)
        except Exception:
            return False
        if df.empty:
            self._triples = {}
            return True
        df = df.fillna("")
        triples: dict[tuple[str, str, str], dict] = {}
        for row in df.to_dict(orient="records"):
            subject = canonical_qid(str(row.get("subject", "") or ""))
            predicate = canonical_pid(str(row.get("predicate", "") or ""))
            obj = canonical_qid(str(row.get("object", "") or ""))
            if not subject or not predicate or not obj:
                continue
            key = (subject, predicate, obj)
            triples[key] = {
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "discovered_at_utc": str(row.get("discovered_at_utc", "") or ""),
                "source_query_file": str(row.get("source_query_file", "") or ""),
            }
        self._triples = triples
        return True

    def process_batch(self, events: list[dict]) -> None:
        for event in events:
            discovered_at = str(event.get("timestamp_utc", "") or "")
            source_query_file = str(get_query_event_field(event, "query_hash", "") or "")
            for qid, doc in _iter_entities_from_event(event):
                claims = doc.get("claims", {}) if isinstance(doc, dict) else {}
                for subj, pred, obj in _extract_item_triples(qid, claims):
                    key = (subj, pred, obj)
                    if key in self._triples:
                        continue
                    self._triples[key] = {
                        "subject": subj,
                        "predicate": pred,
                        "object": obj,
                        "discovered_at_utc": discovered_at,
                        "source_query_file": source_query_file,
                    }
            seq = event.get("sequence_num")
            if isinstance(seq, int):
                self._last_seq = max(self._last_seq, seq)

    def materialize(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        columns = ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"]
        if not self._triples:
            df = pd.DataFrame(columns=columns)
        else:
            rows = [self._triples[key] for key in sorted(self._triples)]
            df = pd.DataFrame(rows)[columns]
        
        _atomic_write_df(output_path, df)

    def update_progress(self, last_seq: int) -> None:
        self._last_seq = last_seq
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), last_seq)
