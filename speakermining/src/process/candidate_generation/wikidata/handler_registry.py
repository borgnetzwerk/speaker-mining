"""Handler progress registry (eventhandler.csv).

Maintains a CSV file tracking the progress of all event handlers:
- handler_name (unique identifier)
- last_processed_sequence (highest sequence number processed by this handler)
- artifact_path (where this handler stores its projection)
- updated_at (ISO 8601 timestamp of last update)
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from process.io_guardrails import atomic_write_csv


def _iso_now() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HandlerProgress:
    """Tracks progress of a single event handler."""

    def __init__(self, handler_name: str, last_seq: int = 0, artifact_path: Optional[str] = None, updated_at: Optional[str] = None):
        self.handler_name = handler_name
        self.last_seq = last_seq
        self.artifact_path = artifact_path or ""
        self.updated_at = updated_at or _iso_now()

    def to_dict(self) -> dict:
        return {
            "handler_name": self.handler_name,
            "last_processed_sequence": self.last_seq,
            "artifact_path": self.artifact_path,
            "updated_at": self.updated_at,
        }


class HandlerRegistry:
    """Registry for tracking event handler progress.
    
    Maintains eventhandler.csv with one row per registered handler.
    Provides atomic read-modify-write semantics for progress updates.
    """

    def __init__(self, registry_path: Path):
        """Initialize handler registry.
        
        Args:
            registry_path: Path to eventhandler.csv file
        
        Creates the file if it doesn't exist (with header row).
        """
        self.registry_path = Path(registry_path)
        self.handlers: dict[str, HandlerProgress] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load handlers from eventhandler.csv."""
        self.handlers.clear()
        
        if not self.registry_path.exists():
            # New registry; no handlers yet
            self._write_registry()
            return
        
        try:
            with self.registry_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    # Empty file; reinit
                    self._write_registry()
                    return
                for row in reader:
                    if not row.get("handler_name"):
                        continue
                    progress = HandlerProgress(
                        handler_name=row["handler_name"],
                        last_seq=int(row.get("last_processed_sequence", "0") or "0"),
                        artifact_path=row.get("artifact_path", ""),
                        updated_at=row.get("updated_at", _iso_now()),
                    )
                    self.handlers[progress.handler_name] = progress
        except Exception as e:
            # On read error, start fresh
            self.handlers.clear()
            self._write_registry()

    def _write_registry(self) -> None:
        """Atomically write handlers to eventhandler.csv."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = ["handler_name", "last_processed_sequence", "artifact_path", "updated_at"]
        rows = [handler.to_dict() for handler in sorted(self.handlers.values(), key=lambda h: h.handler_name)]
        frame = pd.DataFrame(rows, columns=fieldnames)
        atomic_write_csv(self.registry_path, frame, index=False)

    def register_handler(self, handler_name: str, artifact_path: str = "") -> None:
        """Register a new handler (or update its artifact_path).
        
        Args:
            handler_name: Unique handler identifier
            artifact_path: Path to output artifact (optional)
        """
        if handler_name not in self.handlers:
            self.handlers[handler_name] = HandlerProgress(handler_name, last_seq=0, artifact_path=artifact_path)
        else:
            if artifact_path:
                self.handlers[handler_name].artifact_path = artifact_path
        self._write_registry()

    def get_progress(self, handler_name: str) -> int:
        """Return last_processed_sequence for a handler.
        
        Args:
            handler_name: Handler identifier
        
        Returns:
            Last processed sequence number (0 if not found or never processed).
        """
        if handler_name not in self.handlers:
            return 0
        return self.handlers[handler_name].last_seq

    def update_progress(self, handler_name: str, last_seq: int) -> None:
        """Atomically update handler progress.
        
        Args:
            handler_name: Handler identifier
            last_seq: Highest sequence number just processed
        
        Creates handler entry if it doesn't exist.
        """
        if handler_name not in self.handlers:
            self.handlers[handler_name] = HandlerProgress(handler_name, last_seq=last_seq)
        else:
            self.handlers[handler_name].last_seq = last_seq
            self.handlers[handler_name].updated_at = _iso_now()
        self._write_registry()

    def all_handlers_caught_up(self, latest_sequence: int) -> bool:
        """Check if all registered handlers have processed up to latest_sequence.
        
        Args:
            latest_sequence: The highest sequence number available in the eventstore
        
        Returns:
            True if all handlers have last_seq >= latest_sequence.
        """
        if not self.handlers:
            return True
        return all(h.last_seq >= latest_sequence for h in self.handlers.values())

    def list_handlers(self) -> list[str]:
        """Return sorted list of registered handler names."""
        return sorted(self.handlers.keys())

    def snapshot(self) -> list[dict]:
        """Return deterministic snapshot rows for governance/audit artifacts."""
        return [self.handlers[name].to_dict() for name in sorted(self.handlers)]

    def prune_to_managed_handlers(self, managed_handler_names: set[str]) -> list[str]:
        """Remove unmanaged/stale handlers from the registry.

        Returns a sorted list of removed handler names.
        """
        managed = {str(name or "").strip() for name in (managed_handler_names or set()) if str(name or "").strip()}
        stale = sorted(name for name in self.handlers if name not in managed)
        if not stale:
            return []
        for name in stale:
            self.handlers.pop(name, None)
        self._write_registry()
        return stale
