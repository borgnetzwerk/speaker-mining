"""Base class and registry for event handlers in the v3 event-sourcing pipeline.

Handlers are responsible for:
1. Reading events from the chunk chain starting from (last_processed_sequence + 1)
2. Maintaining in-memory state during batch processing
3. Writing derived projections (CSV/JSON files) atomically
4. Tracking progress in eventhandler.csv
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class EventHandler(ABC):
    """Abstract base class for event handlers.
    
    A handler reads events and maintains a derived projection (e.g., instances.csv, classes.csv).
    Handlers are deterministic and idempotent: reprocessing the same events produces identical output.
    """

    @abstractmethod
    def name(self) -> str:
        """Return unique handler identifier (e.g., 'InstancesHandler').
        
        Used as primary key in eventhandler.csv.
        """
        ...

    @abstractmethod
    def last_processed_sequence(self) -> int:
        """Return the last event sequence number processed by this handler.
        
        Default: 0 (no events processed yet).
        Used to determine where to resume after interruption.
        """
        ...

    @abstractmethod
    def process_batch(self, events: list[dict]) -> None:
        """Process a batch of unhandled events.
        
        Args:
            events: List of event dicts with keys: sequence_num, event_type, event_version, etc.
        
        Updates in-memory state but does NOT write projections yet.
        """
        ...

    @abstractmethod
    def materialize(self, output_path: Path) -> None:
        """Write in-memory state to projection file(s) atomically.
        
        Called after all events in the batch are processed.
        Must guarantee atomic writes (no partial/corrupted outputs).
        """
        ...

    def update_progress(self, last_seq: int) -> None:
        """Update handler progress in eventhandler.csv.
        
        Called by the orchestrator after materialization.
        Default implementation does nothing (subclasses may override for custom tracking).
        """
        ...
