"""QueryInventoryHandler: Reads all query_response events and maintains query_inventory.csv."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.event_log import get_query_event_field
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


def _status_rank(status: str) -> int:
    """Return preference rank for query status (higher is better)."""
    status = str(status or "").strip()
    if status == "success":
        return 4
    if status == "cache_hit":
        return 3
    if status in {"fallback_cache"}:
        return 2
    if status in {"http_error", "timeout"}:
        return 1
    return 0


class QueryRecord:
    """Tracks a single unique query (by query_hash)."""

    def __init__(
        self,
        query_hash: str = "",
        endpoint: str = "",
        normalized_query: str = "",
        status: str = "unknown",
        first_seen: str = "",
        source_step: str = "",
        key: str = "",
        count: int = 1,
    ):
        self.query_hash = query_hash
        self.endpoint = endpoint
        self.normalized_query = normalized_query
        self.status = status
        self.first_seen = first_seen
        self.last_seen = first_seen
        self.source_step = source_step
        self.key = key
        self.count = count

    def to_dict(self) -> dict:
        return {
            "query_hash": self.query_hash,
            "endpoint": self.endpoint,
            "normalized_query": self.normalized_query,
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": self.count,
        }


class QueryInventoryHandler(EventHandler):
    """Handler that maintains query_inventory.csv from query_response events.
    
    Deduplicates queries by query_hash and maintains status for each unique query.
    Status preference: success > cache_hit > fallback_cache > http_error/timeout > other.
    """

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self.queries: dict[str, QueryRecord] = {}  # query_hash -> record

    def name(self) -> str:
        return "QueryInventoryHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def bootstrap_from_projection(self, output_path: Path) -> bool:
        """Hydrate query inventory from existing projection for incremental replay."""
        output_path = Path(output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            return False
        try:
            df = pd.read_csv(output_path)
        except Exception:
            return False
        if df.empty:
            self.queries = {}
            return True
        df = df.fillna("")
        hydrated: dict[str, QueryRecord] = {}
        for row in df.to_dict(orient="records"):
            query_hash = str(row.get("query_hash", "") or "").strip()
            if not query_hash:
                continue
            record = QueryRecord(
                query_hash=query_hash,
                endpoint=str(row.get("endpoint", "") or ""),
                normalized_query=str(row.get("normalized_query", "") or ""),
                status=str(row.get("status", "") or ""),
                first_seen=str(row.get("first_seen", "") or ""),
                source_step="",
                key="",
                count=int(row.get("count", 0) or 0),
            )
            record.last_seen = str(row.get("last_seen", "") or "")
            hydrated[query_hash] = record
        self.queries = hydrated
        return True

    def process_batch(self, events: list[dict]) -> None:
        """Process all query_response events and deduplicate by query_hash."""
        for event in events:
            if event.get("event_type") != "query_response":
                continue

            query_hash = str(get_query_event_field(event, "query_hash", "") or "")
            if not query_hash:
                continue

            endpoint = str(get_query_event_field(event, "endpoint", "") or "")
            normalized_query = str(get_query_event_field(event, "normalized_query", "") or "")
            status = str(get_query_event_field(event, "status", "") or "")
            timestamp = event.get("timestamp_utc", "")
            source_step = str(get_query_event_field(event, "source_step", "") or "")
            key = str(get_query_event_field(event, "key", "") or "")

            if query_hash not in self.queries:
                # New query; create record
                self.queries[query_hash] = QueryRecord(
                    query_hash=query_hash,
                    endpoint=endpoint,
                    normalized_query=normalized_query,
                    status=status,
                    first_seen=timestamp,
                    source_step=source_step,
                    key=key,
                    count=1,
                )
            else:
                # Update existing record
                record = self.queries[query_hash]
                record.count += 1
                record.last_seen = timestamp
                
                # Update status to highest-preference version
                if _status_rank(status) > _status_rank(record.status):
                    record.status = status

            self._last_seq = event.get("sequence_num", self._last_seq)

    def materialize(self, output_path: Path) -> None:
        """Write query_inventory.csv deterministically (sorted by endpoint, then query)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Sort for determinism: by endpoint, then normalized_query
        sorted_records = sorted(
            self.queries.values(),
            key=lambda r: (r.endpoint, r.normalized_query, r.query_hash),
        )

        rows = [r.to_dict() for r in sorted_records]

        columns = ["query_hash", "endpoint", "normalized_query", "status", "first_seen", "last_seen", "count"]
        
        if not rows:
            df = pd.DataFrame(columns=columns)
        else:
            df = pd.DataFrame(rows)[columns]

        _atomic_write_df(output_path, df)

    def update_progress(self, last_seq: int) -> None:
        """Update handler progress in registry."""
        self._last_seq = last_seq
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), last_seq)
