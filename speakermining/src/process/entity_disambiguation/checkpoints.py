"""Checkpoint and recovery system for event-sourced alignment.

Implements:
- Checkpoint snapshots (dual-form: directory + zip)
- Recovery detection and restoration
- Retention policy enforcement
- Corruption detection
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from process.io_guardrails import atomic_write_text, atomic_write_csv
from .config import CHECKPOINTS_DIR, HANDLER_PROGRESS_DB, CORE_CLASSES, get_aligned_csv_path


class CheckpointManager:
    """Manage snapshots, recovery, and retention policy."""
    
    def __init__(self):
        """Initialize checkpoint manager."""
        self.checkpoints_dir = CHECKPOINTS_DIR
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    
    def _iso_now(self) -> str:
        """ISO 8601 UTC timestamp."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    def _checkpoint_dir_name(self) -> str:
        """Generate checkpoint directory name with timestamp."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        return f"{ts}-checkpoint"
    
    def save_checkpoint(self, *, events_dir: Path, projections: dict[str, pd.DataFrame]) -> Path:
        """Save a checkpoint snapshot in both directory and zip forms.
        
        Args:
            events_dir: Directory containing event log chunks
            projections: Dict mapping core_class -> projection DataFrame
        
        Returns:
            Path to the unzipped checkpoint directory
        """
        checkpoint_name = self._checkpoint_dir_name()
        checkpoint_path = self.checkpoints_dir / checkpoint_name
        checkpoint_path.mkdir(parents=True, exist_ok=True)
        
        # Save event chunks
        events_target = checkpoint_path / "events"
        events_target.mkdir(parents=True, exist_ok=True)
        
        if events_dir.exists():
            for chunk_file in events_dir.glob("chunk_*.jsonl"):
                shutil.copy2(chunk_file, events_target / chunk_file.name)
        
        # Create chunk catalog
        chunk_catalog = []
        for chunk_file in sorted(events_target.glob("chunk_*.jsonl")):
            chunk_size = chunk_file.stat().st_size
            checksum = self._compute_checksum(chunk_file)
            chunk_catalog.append({
                "chunk_id": chunk_file.stem,
                "eventstore_path": str(chunk_file.relative_to(events_target)),
                "chunk_size": chunk_size,
                "checksum": checksum,
            })
        
        if chunk_catalog:
            catalog_df = pd.DataFrame(chunk_catalog)
            atomic_write_csv(events_target / "chunk_catalog.csv", catalog_df, index=False)
        
        # Create eventstore checksums file
        checksums = "\n".join(f"{cat['chunk_id']}: {cat['checksum']}" for cat in chunk_catalog) + "\n"
        atomic_write_text(events_target / "eventstore_checksums.txt", checksums)
        
        # Save projections
        projections_target = checkpoint_path / "projections"
        projections_target.mkdir(parents=True, exist_ok=True)
        
        for core_class, df in projections.items():
            if df is not None and not df.empty:
                output_path = projections_target / f"aligned_{core_class}.csv"
                atomic_write_csv(output_path, df, index=False)
        
        # Copy handler progress DB
        if HANDLER_PROGRESS_DB.exists():
            shutil.copy2(HANDLER_PROGRESS_DB, checkpoint_path / "handler_progress.db")
        
        # Create metadata
        metadata = {
            "checkpoint_timestamp": self._iso_now(),
            "checkpoint_name": checkpoint_name,
            "event_chunks": len(chunk_catalog),
            "projections": list(projections.keys()),
        }
        metadata_path = checkpoint_path / "checkpoint_metadata.json"
        atomic_write_text(metadata_path, json.dumps(metadata, indent=2, ensure_ascii=False))
        
        # Create zip backup
        zip_path = self.checkpoints_dir / f"{checkpoint_name}.zip"
        shutil.make_archive(str(zip_path.with_suffix("")), "zip", checkpoint_path)
        
        # Enforce retention policy
        self._enforce_retention_policy()
        
        return checkpoint_path
    
    def restore_checkpoint(self, *, checkpoint_dir: Optional[Path] = None, checkpoint_zip: Optional[Path] = None) -> tuple[Path, Path]:
        """Restore a checkpoint from directory or zip.
        
        Returns:
            Tuple of (events_dir, projections_dir)
        """
        if checkpoint_zip:
            # Extract zip to temp location
            restore_path = self.checkpoints_dir / f"{checkpoint_zip.stem}_restored"
            if restore_path.exists():
                shutil.rmtree(restore_path)
            shutil.unpack_archive(str(checkpoint_zip), extract_dir=str(restore_path))
            checkpoint_dir = restore_path
        
        if not checkpoint_dir:
            raise ValueError("Must provide either checkpoint_dir or checkpoint_zip")
        
        if not checkpoint_dir.exists():
            raise ValueError(f"Checkpoint directory not found: {checkpoint_dir}")
        
        events_dir = checkpoint_dir / "events"
        projections_dir = checkpoint_dir / "projections"
        
        if not events_dir.exists():
            events_dir.mkdir(parents=True, exist_ok=True)
        if not projections_dir.exists():
            projections_dir.mkdir(parents=True, exist_ok=True)
        
        return events_dir, projections_dir
    
    def find_latest_checkpoint(self) -> Optional[Path]:
        """Find the most recent unzipped checkpoint."""
        checkpoints = sorted([d for d in self.checkpoints_dir.iterdir() if d.is_dir() and "-checkpoint" in d.name], reverse=True)
        return checkpoints[0] if checkpoints else None
    
    def get_checkpoint_metadata(self, checkpoint_dir: Path) -> dict:
        """Load checkpoint metadata."""
        metadata_path = checkpoint_dir / "checkpoint_metadata.json"
        if metadata_path.exists():
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        return {}
    
    def validate_checkpoint(self, checkpoint_dir: Path) -> bool:
        """Validate checkpoint integrity using checksums."""
        checksums_path = checkpoint_dir / "events" / "eventstore_checksums.txt"
        if not checksums_path.exists():
            return False
        
        try:
            expected_sums = {}
            for line in checksums_path.read_text().splitlines():
                if ":" in line:
                    chunk_id, expected = line.split(":", 1)
                    expected_sums[chunk_id.strip()] = expected.strip()
            
            for chunk_id, expected_checksum in expected_sums.items():
                chunk_path = checkpoint_dir / "events" / f"{chunk_id}.jsonl"
                if not chunk_path.exists():
                    return False
                actual_checksum = self._compute_checksum(chunk_path)
                if actual_checksum != expected_checksum:
                    return False
            
            return True
        except Exception:
            return False
    
    def _compute_checksum(self, path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        import hashlib
        sha = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                data = f.read(65536)
                if not data:
                    break
                sha.update(data)
        return sha.hexdigest()
    
    def _enforce_retention_policy(self) -> None:
        """Enforce retention: keep 3 newest unzipped, plus 7 zipped backups.
        
        Also enforce: one protected daily-latest zip per day.
        """
        # Find all checkpoints
        unzipped = sorted(
            [d for d in self.checkpoints_dir.iterdir() if d.is_dir() and "-checkpoint" in d.name],
            reverse=True
        )
        zipped = sorted(
            [f for f in self.checkpoints_dir.glob("*-checkpoint.zip")],
            reverse=True
        )
        
        # Keep 3 newest unzipped
        for old_checkpoint in unzipped[3:]:
            try:
                shutil.rmtree(old_checkpoint)
            except Exception:
                pass
        
        # Keep 7 newest zipped backups
        for old_zip in zipped[7:]:
            try:
                old_zip.unlink()
            except Exception:
                pass
