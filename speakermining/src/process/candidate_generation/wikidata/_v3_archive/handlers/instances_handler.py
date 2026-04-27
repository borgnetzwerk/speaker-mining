"""InstancesHandler: Reads entity query_response events and maintains instances.csv."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from process.candidate_generation.wikidata.cache import _atomic_write_df
from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.event_log import get_query_event_field, get_query_event_response_data
from process.candidate_generation.wikidata.handler_registry import HandlerRegistry


class InstancesHandler(EventHandler):
    """Handler that maintains instances.csv from entity query responses.
    
    Processes query_response events where source_step="entity_fetch" and status="success",
    extracting and maintaining:
    - In-memory entity map (QID -> entity data)
    - instances.csv (denormalized entity metadata)
    """

    def __init__(self, repo_root: Path, handler_registry: Optional[HandlerRegistry] = None):
        self.repo_root = Path(repo_root)
        self.handler_registry = handler_registry
        self._last_seq = 0
        self.entities: dict[str, dict] = {}  # QID -> denormalized record (for CSV)

    def name(self) -> str:
        return "InstancesHandler"

    def last_processed_sequence(self) -> int:
        if self.handler_registry:
            return self.handler_registry.get_progress(self.name())
        return self._last_seq

    def bootstrap_from_projection(self, output_path: Path) -> bool:
        """Hydrate in-memory state from existing projection for incremental replay."""
        output_path = Path(output_path)
        if not output_path.exists() or output_path.stat().st_size == 0:
            return False
        try:
            df = pd.read_csv(output_path)
        except Exception:
            return False
        if df.empty:
            self.entities = {}
            return True
        df = df.fillna("")
        entities: dict[str, dict] = {}
        for row in df.to_dict(orient="records"):
            qid = str(row.get("qid", "") or "").strip()
            if not qid:
                continue
            entities[qid] = {
                "qid": qid,
                "label": str(row.get("label", "") or ""),
                "labels_de": str(row.get("labels_de", "") or ""),
                "labels_en": str(row.get("labels_en", "") or ""),
                "aliases": str(row.get("aliases", "") or ""),
                "description": str(row.get("description", "") or ""),
                "discovered_at": str(row.get("discovered_at", "") or ""),
                "expanded_at": str(row.get("expanded_at", "") or ""),
            }
        self.entities = entities
        return True

    def process_batch(self, events: list[dict]) -> None:
        """Process entity_fetch query responses and extract entity metadata."""
        for event in events:
            if event.get("event_type") != "query_response":
                continue
            if get_query_event_field(event, "source_step", "") != "entity_fetch":
                continue
            if get_query_event_field(event, "status", "") != "success":
                continue

            # Extract entity metadata from payload
            payload = get_query_event_response_data(event)
            key = str(get_query_event_field(event, "key", "") or "")
            qid = key.strip() if key else None
            if not qid:
                continue

            # Canonicalize QID
            if not qid.startswith("Q"):
                continue

            # Extract entity data from Wikidata response
            entities_dict = payload.get("entities", {})
            entity_data = entities_dict.get(qid, {})
            if not entity_data:
                continue

            # Build instance record
            labels = entity_data.get("labels", {})
            aliases = entity_data.get("aliases", {})
            descriptions = entity_data.get("descriptions", {})

            instance_record = {
                "qid": qid,
                "label": labels.get("en", {}).get("value", "") if labels else "",
                "labels_de": labels.get("de", {}).get("value", "") if labels else "",
                "labels_en": labels.get("en", {}).get("value", "") if labels else "",
                "aliases": json.dumps(
                    [a.get("value", "") for a in aliases.get("en", [])] if aliases else []
                ),
                "description": descriptions.get("en", {}).get("value", "") if descriptions else "",
                "discovered_at": event.get("timestamp_utc", ""),
                "expanded_at": None,
            }

            self.entities[qid] = instance_record
            self._last_seq = event.get("sequence_num", self._last_seq)

    def materialize(self, output_path: Path) -> None:
        """Write instances.csv deterministically (sorted by QID)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Sort for determinism
        sorted_qids = sorted(self.entities.keys())
        rows = [self.entities[qid] for qid in sorted_qids]

        # Write instances.csv via atomic write
        if not rows:
            df = pd.DataFrame(columns=[
                "qid", "label", "labels_de", "labels_en", "aliases", "description",
                "discovered_at", "expanded_at"
            ])
        else:
            df = pd.DataFrame(rows)

        _atomic_write_df(output_path, df)

    def update_progress(self, last_seq: int) -> None:
        """Update handler progress in registry."""
        self._last_seq = last_seq
        if self.handler_registry:
            self.handler_registry.update_progress(self.name(), last_seq)
