"""Append-only event log for deterministic alignment tracking.

Events are immutable, append-only records of alignment attempts.
This serves as the source of truth for reproducible runs and recovery.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .alignment import AlignmentResult
from .config import EVENTS_DIR


class AlignmentEventLog:
    """Append-only JSONL event log for Step 311 alignment events.
    
    Handles:
    - Atomic appends with corruption tolerance
    - Chunking strategy for large runs
    - Recovery and resumption support
    """
    
    CHUNK_SIZE_BYTES = 10 * 1024 * 1024  # Rotate chunk at 10MB
    
    def __init__(self, *, core_class: str):
        """Initialize event log for a specific core class.
        
        Args:
            core_class: One of the core classes (e.g. "persons", "episodes")
        """
        self.core_class = str(core_class)
        self.base_path = EVENTS_DIR / f"{self.core_class}.jsonl"
        self.chunk_dir = EVENTS_DIR / f"{self.core_class}_chunks"
        self._event_counter = 0
        self._current_chunk_size = 0
        self._current_chunk_num = 1
        
        # Ensure directories exist
        self.base_path.parent.mkdir(parents=True, exist_ok=True)
        self.chunk_dir.mkdir(parents=True, exist_ok=True)
    
    def _iso_now(self) -> str:
        """ISO 8601 UTC timestamp."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def _next_event_id(self) -> str:
        """Generate unique event ID."""
        self._event_counter += 1
        return f"{self.core_class[:4]}_{self._event_counter:08d}"
    
    def _get_current_chunk_path(self) -> Path:
        """Return path to current chunk file."""
        return self.chunk_dir / f"chunk_{self._current_chunk_num:03d}.jsonl"
    
    def append_alignment_event(
        self,
        *,
        alignment_result: AlignmentResult,
        handler_name: str = "",
        source_mention_data: Optional[dict] = None,
        source_entity_ids: Optional[dict] = None,
        action: Optional[dict] = None,
        extra_context: Optional[dict] = None,
    ) -> str:
        """Append an alignment attempt event to the log.
        
        Returns the event_id.
        """
        event_id = self._next_event_id()
        event = {
            "timestamp_utc": self._iso_now(),
            "event_id": event_id,
            "phase": "31",
            "event_type": "alignment_attempt",
            "core_class": self.core_class,
            "handler_name": str(handler_name or ""),
            "alignment_unit_id": alignment_result.alignment_unit_id,
            "broadcasting_program_key": alignment_result.broadcasting_program_key,
            "episode_key": alignment_result.episode_key,
            "source_zdf_value": alignment_result.source_zdf_value,
            "source_wikidata_value": alignment_result.source_wikidata_value,
            "source_fernsehserien_value": alignment_result.source_fernsehserien_value,
            "alignment_status": alignment_result.deterministic_alignment_status.value,
            "alignment_score": float(alignment_result.deterministic_alignment_score),
            "alignment_method": str(alignment_result.deterministic_alignment_method),
            "alignment_reason": str(alignment_result.deterministic_alignment_reason),
            "requires_human_review": bool(alignment_result.requires_human_review),
            "matched_on_fields": list(alignment_result.matched_on_fields),
            "candidate_count": int(alignment_result.candidate_count),
            "evidence_sources": list(alignment_result.evidence_sources),
        }
        
        if source_mention_data:
            event["source_data"] = dict(source_mention_data)

        if source_entity_ids:
            event["source_entity_ids"] = dict(source_entity_ids)

        if action:
            event["action"] = {
                "type": str(action.get("type", "")),
                "status": str(action.get("status", "")),
                "reason": str(action.get("reason", "")),
            }
        
        if extra_context:
            event["extra"] = dict(extra_context)
        
        line = json.dumps(event, ensure_ascii=False) + "\n"
        self._append_line(line)
        return event_id
    
    def append_handler_checkpoint(
        self,
        *,
        handler_name: str,
        last_processed_sequence: int,
        artifact_path: str,
        total_events_processed: int,
        extra_context: Optional[dict] = None,
    ) -> str:
        """Append a handler checkpoint event."""
        event_id = self._next_event_id()
        event = {
            "timestamp_utc": self._iso_now(),
            "event_id": event_id,
            "phase": "31",
            "event_type": "handler_checkpoint",
            "core_class": self.core_class,
            "handler_name": str(handler_name),
            "last_processed_sequence": int(last_processed_sequence),
            "artifact_path": str(artifact_path),
            "total_events_processed": int(total_events_processed),
        }
        
        if extra_context:
            event["extra"] = dict(extra_context)
        
        line = json.dumps(event, ensure_ascii=False) + "\n"
        self._append_line(line)
        return event_id
    
    def _append_line(self, line: str) -> None:
        """Append line atomically with chunk rotation."""
        chunk_path = self._get_current_chunk_path()
        
        # Check if we need to rotate
        line_bytes = len(line.encode("utf-8"))
        if self._current_chunk_size + line_bytes > self.CHUNK_SIZE_BYTES:
            self._rotate_chunk()
            chunk_path = self._get_current_chunk_path()
            self._current_chunk_size = 0
        
        # Append line
        try:
            with chunk_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
            self._current_chunk_size += line_bytes
        except PermissionError as exc:
            raise RuntimeError(
                f"Permission denied appending to event log {chunk_path}. "
                "Close any process locking the file and rerun."
            ) from exc
    
    def _rotate_chunk(self) -> None:
        """Rotate to next chunk file."""
        self._current_chunk_num += 1
    
    def read_events(self, *, start_event_id: Optional[str] = None) -> list[dict]:
        """Read all events from all chunks.
        
        If start_event_id provided, resume from that point.
        Handles corruption gracefully.
        
        Returns list of event dicts.
        """
        events = []
        started = start_event_id is None
        
        # Read all chunks in order
        chunk_files = sorted(self.chunk_dir.glob("chunk_*.jsonl"))
        
        for chunk_path in chunk_files:
            try:
                lines = chunk_path.read_text(encoding="utf-8").splitlines()
            except Exception:
                # Skip corrupted chunk, log a warning
                continue
            
            for raw in lines:
                line = raw.strip()
                if not line:
                    continue
                
                try:
                    event = json.loads(line)
                    if not started:
                        if event.get("event_id") == start_event_id:
                            started = True
                        else:
                            continue
                    events.append(event)
                except json.JSONDecodeError:
                    # Skip malformed line
                    continue
        
        return events
    
    def get_last_event_id(self) -> Optional[str]:
        """Get the most recent event_id in the log."""
        events = self.read_events()
        if events:
            return events[-1].get("event_id")
        return None
