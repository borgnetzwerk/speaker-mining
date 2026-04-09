"""Replayable event handlers for alignment projections.

Each handler:
- Consumes alignment events for its core class
- Maintains reproducible progress state
- Builds deterministic projections (aligned_*.csv)
- Supports resumption from checkpoints
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from process.io_guardrails import atomic_write_csv
from .config import (
    BASELINE_COLUMNS,
    CORE_CLASSES,
    HANDLER_PROGRESS_DB,
    PERSONS_EXTENDED_COLUMNS,
    EPISODES_EXTENDED_COLUMNS,
    SERIES_EXTENDED_COLUMNS,
    ROLES_EXTENDED_COLUMNS,
    ORGANIZATIONS_EXTENDED_COLUMNS,
    TOPICS_EXTENDED_COLUMNS,
    BROADCASTING_PROGRAMS_EXTENDED_COLUMNS,
    get_aligned_csv_path,
)
from .event_log import AlignmentEventLog


class HandlerProgressDB:
    """SQLite DB for handler resumption state."""
    
    def __init__(self, db_path: Path):
        """Initialize handler progress DB."""
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
    
    def _init_schema(self) -> None:
        """Initialize DB schema if needed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS handler_progress (
                    handler_name TEXT PRIMARY KEY,
                    last_processed_sequence INTEGER,
                    artifact_path TEXT,
                    updated_at TEXT,
                    total_events_processed INTEGER
                )
            """)
            conn.commit()
    
    def get_progress(self, handler_name: str) -> Optional[dict]:
        """Get handler progress or None if not started."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT last_processed_sequence, artifact_path, updated_at, total_events_processed FROM handler_progress WHERE handler_name = ?",
                (handler_name,)
            ).fetchone()
            if row:
                return {
                    "last_processed_sequence": row[0],
                    "artifact_path": row[1],
                    "updated_at": row[2],
                    "total_events_processed": row[3],
                }
        return None
    
    def update_progress(
        self,
        handler_name: str,
        last_processed_sequence: int,
        artifact_path: str,
        total_events_processed: int,
    ) -> None:
        """Update handler progress."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO handler_progress
                (handler_name, last_processed_sequence, artifact_path, updated_at, total_events_processed)
                VALUES (?, ?, ?, ?, ?)
            """, (handler_name, last_processed_sequence, artifact_path, now, total_events_processed))
            conn.commit()


class ReplayableHandler:
    """Base handler for building deterministic projections from alignment events."""
    
    def __init__(self, *, core_class: str, progress_db: HandlerProgressDB):
        """Initialize handler.
        
        Args:
            core_class: One of the CORE_CLASSES
            progress_db: HandlerProgressDB instance for resumption
        """
        self.core_class = str(core_class)
        self.handler_name = f"handler_{self.core_class}"
        self.progress_db = progress_db
        self.event_log = AlignmentEventLog(core_class=self.core_class)
        self.output_path = get_aligned_csv_path(self.core_class)
        self._rows: list[dict] = []
    
    def run(self) -> pd.DataFrame:
        """Run handler: replay events and build projection.
        
        Returns the computed projection DataFrame.
        """
        # Always rebuild projections from full event history.
        # This keeps output deterministic even when event IDs repeat across runs.
        events = self.event_log.read_events(start_event_id=None)

        # Reset in-memory rows per run so repeated invocations do not accumulate state.
        self._rows = []
        
        # Replay events
        for event in events:
            self._process_event(event)
        
        # Build projection DataFrame
        projection = self._build_projection()
        
        # Save output for every core class, even if empty, to satisfy the contract
        # of stable aligned_*.csv artifacts.
        atomic_write_csv(self.output_path, projection, index=False)
        
        # Update progress
        last_event_id = self.event_log.get_last_event_id()
        if last_event_id:
            self.progress_db.update_progress(
                self.handler_name,
                last_processed_sequence=last_event_id,
                artifact_path=str(self.output_path),
                total_events_processed=len(events),
            )
        
        return projection
    
    def _process_event(self, event: dict) -> None:
        """Process a single alignment event."""
        if event.get("event_type") == "alignment_attempt":
            row = self._event_to_row(event)
            if row:
                self._rows.append(row)
    
    def _event_to_row(self, event: dict) -> Optional[dict]:
        """Convert alignment event to projection row."""
        # Base row from event
        row = {
            "alignment_unit_id": event.get("alignment_unit_id", ""),
            "core_class": self.core_class,
            "broadcasting_program_key": event.get("broadcasting_program_key", ""),
            "episode_key": event.get("episode_key", ""),
            "source_zdf_value": event.get("source_zdf_value", ""),
            "source_wikidata_value": event.get("source_wikidata_value", ""),
            "source_fernsehserien_value": event.get("source_fernsehserien_value", ""),
            "deterministic_alignment_status": event.get("alignment_status", "unresolved"),
            "deterministic_alignment_score": event.get("alignment_score", 0.0),
            "deterministic_alignment_method": event.get("alignment_method", ""),
            "deterministic_alignment_reason": event.get("alignment_reason", ""),
            "requires_human_review": event.get("requires_human_review", True),
            "source_entity_ids_json": json.dumps(event.get("source_entity_ids", {}), ensure_ascii=False),
            "action_type": str(event.get("action", {}).get("type", "")),
            "action_status": str(event.get("action", {}).get("status", "")),
            "action_reason": str(event.get("action", {}).get("reason", "")),
        }
        
        # Add core-class-specific columns
        if "source_data" in event:
            source = event["source_data"]
            if self.core_class == "persons":
                row["mention_id"] = source.get("mention_id", "")
                row["person_name"] = source.get("mention_name", "")
                row["person_episode_publication_date"] = source.get("person_episode_publication_date", "")
                row["person_episode_publication_time"] = source.get("person_episode_publication_time", "")
                row["wikidata_id"] = source.get("wikidata_id", "")
                row["fernsehserien_url"] = source.get("fernsehserien_url", "")
            elif self.core_class == "episodes":
                row["episode_id"] = source.get("episode_id", "")
                row["publication_date"] = source.get("publication_date", "")
                row["publication_time"] = source.get("publication_time", "")
                row["duration_seconds"] = source.get("duration_seconds", "")
                row["season_number"] = source.get("season_number", "")
                row["episode_number"] = source.get("episode_number", "")
        
        return row
    
    def _build_projection(self) -> pd.DataFrame:
        """Build final projection DataFrame from rows."""
        if not self._rows:
            return pd.DataFrame(columns=self._get_columns())
        
        df = pd.DataFrame(self._rows)
        
        # Fill missing columns
        for col in self._get_columns():
            if col not in df.columns:
                df[col] = ""
        
        # Keep the latest event per alignment unit to make replay idempotent even
        # when multiple runs append duplicate units.
        if "alignment_unit_id" in df.columns:
            df = df.drop_duplicates(subset=["alignment_unit_id"], keep="last")

        df = self._apply_projection_sorting(df)

        # Select only defined columns in order
        return df[self._get_columns()]

    def _parse_datetime_from_columns(
        self,
        df: pd.DataFrame,
        *,
        date_col: str,
        time_col: str,
    ) -> pd.Series:
        if date_col in df.columns:
            date_vals = df[date_col].fillna("").astype(str).str.strip()
        else:
            date_vals = pd.Series([""] * len(df), index=df.index, dtype="object")

        if time_col in df.columns:
            time_vals = df[time_col].fillna("").astype(str).str.strip()
        else:
            time_vals = pd.Series([""] * len(df), index=df.index, dtype="object")

        dt_combined = (date_vals + " " + time_vals).str.strip()
        parsed = pd.to_datetime(dt_combined, errors="coerce", dayfirst=True)
        parsed = parsed.fillna(pd.to_datetime(date_vals, errors="coerce", dayfirst=True))
        parsed = parsed.fillna(pd.to_datetime(dt_combined, errors="coerce", dayfirst=False))
        parsed = parsed.fillna(pd.to_datetime(date_vals, errors="coerce", dayfirst=False))
        return parsed

    def _apply_projection_sorting(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        if self.core_class == "persons":
            df = df.copy()
            # Persons rule pass 1: chronological by episode appearance.
            df["_sort_dt"] = self._parse_datetime_from_columns(
                df,
                date_col="person_episode_publication_date",
                time_col="person_episode_publication_time",
            )
            df = df.sort_values(
                by=["_sort_dt", "episode_key", "alignment_unit_id"],
                ascending=[True, True, True],
                kind="mergesort",
                na_position="last",
            )

            # Persons rule pass 2: alphabetical by person name while preserving
            # chronology ordering among same-name rows.
            if "person_name" in df.columns:
                df["_sort_person_name"] = df["person_name"].fillna("").astype(str).str.casefold()
                df = df.sort_values(
                    by=["_sort_person_name"],
                    ascending=[True],
                    kind="mergesort",
                    na_position="last",
                )

            return df.drop(columns=[c for c in ["_sort_dt", "_sort_person_name"] if c in df.columns])

        # Generic rule: chronological oldest-first where publication fields exist.
        if "publication_date" in df.columns or "publication_time" in df.columns:
            df = df.copy()
            df["_sort_dt"] = self._parse_datetime_from_columns(
                df,
                date_col="publication_date",
                time_col="publication_time",
            )
            if "season_number" in df.columns:
                df["_sort_season"] = pd.to_numeric(df["season_number"], errors="coerce")
            else:
                df["_sort_season"] = pd.NA
            if "episode_number" in df.columns:
                df["_sort_episode"] = pd.to_numeric(df["episode_number"], errors="coerce")
            else:
                df["_sort_episode"] = pd.NA

            df = df.sort_values(
                by=["_sort_dt", "_sort_season", "_sort_episode", "alignment_unit_id"],
                ascending=[True, True, True, True],
                kind="mergesort",
                na_position="last",
            )
            return df.drop(columns=["_sort_dt", "_sort_season", "_sort_episode"], errors="ignore")

        return df
    
    def _get_columns(self) -> list[str]:
        """Get columns for this projection."""
        cols = BASELINE_COLUMNS.copy()
        
        if self.core_class == "persons":
            cols.extend(PERSONS_EXTENDED_COLUMNS)
        elif self.core_class == "episodes":
            cols.extend(EPISODES_EXTENDED_COLUMNS)
        elif self.core_class == "series":
            cols.extend(SERIES_EXTENDED_COLUMNS)
        elif self.core_class == "roles":
            cols.extend(ROLES_EXTENDED_COLUMNS)
        elif self.core_class == "organizations":
            cols.extend(ORGANIZATIONS_EXTENDED_COLUMNS)
        elif self.core_class == "topics":
            cols.extend(TOPICS_EXTENDED_COLUMNS)
        elif self.core_class == "broadcasting_programs":
            cols.extend(BROADCASTING_PROGRAMS_EXTENDED_COLUMNS)
        
        return cols


class AlignmentProjectionBuilder:
    """Orchestrator for building all core-class projections."""
    
    def __init__(self):
        """Initialize projection builder."""
        self.progress_db = HandlerProgressDB(HANDLER_PROGRESS_DB)
        self.handlers: dict[str, ReplayableHandler] = {}
        
        for core_class in CORE_CLASSES:
            self.handlers[core_class] = ReplayableHandler(
                core_class=core_class,
                progress_db=self.progress_db,
            )
    
    def build_all_projections(self) -> dict[str, pd.DataFrame]:
        """Build all core-class projections.
        
        Returns dict mapping core_class -> DataFrame.
        """
        projections = {}
        for core_class, handler in self.handlers.items():
            try:
                projections[core_class] = handler.run()
            except Exception as e:
                # Log error but continue with other classes
                print(f"Error building {core_class} projection: {e}")
                projections[core_class] = pd.DataFrame()
        
        return projections
