"""Rebuild aggregate outputs from raw per-query cache files.

Scans the raw query cache directory and aggregates candidate match records
into the final CSV outputs required by downstream phases.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .cache import _atomic_write_df, _atomic_write_text, _load_raw_record, _now_utc, _raw_dir, _wikidata_dir, _phase_dir


def rebuild_aggregates_from_raw(root: str | Path) -> dict[str, Any]:
	"""Rebuild all aggregate CSVs from raw query record files.
	
	Idempotent function that scans the raw_queries/ directory and regenerates
	candidate_index.csv, candidates.csv, query_inventory.csv, and summary.json.
	If any aggregate file is corrupted, this can rebuild everything without data loss
	since the raw files are the source of truth.
	
	The output candidates.csv is the primary output fed to Phase 3 (entity_disambiguation).
	
	Args:
		root: Repository root path.
	
	Returns:
		Dict with summary metadata:
		  - raw_files: Count of raw cache files processed
		  - candidate_rows: Count of unique candidate match rows in output CSV
		  - candidates_csv: Path to final candidates.csv
		  - candidate_index_csv: Path to candidate_index.csv (duplicate)
		  - query_inventory_csv: Path to query_inventory.csv (metadata log)
	"""
	repo_root = Path(root)
	raw_dir_path = _raw_dir(repo_root)
	raw_dir_path.mkdir(parents=True, exist_ok=True)

	candidate_rows: list[dict[str, str]] = []
	inventory_rows: list[dict[str, str | float | None]] = []

	# Scan all raw query files and aggregate metadata
	for path in sorted(raw_dir_path.glob("*.json")):
		record = _load_raw_record(path)
		if not record:
			continue

		ts = str(record.get("requested_at_utc", ""))
		age_days: float | None = None
		try:
			dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
			age_days = round((_now_utc() - dt).total_seconds() / 86400.0, 3)
		except Exception:
			pass

		inventory_rows.append(
			{
				"file": path.name,
				"query_type": record.get("query_type", ""),
				"key": record.get("key", ""),
				"requested_at_utc": ts,
				"age_days": age_days,
				"source": record.get("source", ""),
			}
		)

		# Extract candidate_match records (only these contribute to output)
		if record.get("query_type") == "candidate_match":
			rows = record.get("payload", {}).get("rows", [])
			if isinstance(rows, list):
				for row in rows:
					if isinstance(row, dict):
						candidate_rows.append(row)

	# Build candidates DataFrame with required column order
	candidate_columns = [
		"mention_id",
		"mention_type",
		"mention_label",
		"candidate_id",
		"candidate_label",
		"source",
		"context",
	]
	if candidate_rows:
		candidates_df = pd.DataFrame(candidate_rows)
		for col in candidate_columns:
			if col not in candidates_df.columns:
				candidates_df[col] = ""
		candidates_df = candidates_df[candidate_columns]
		candidates_df = candidates_df.drop_duplicates(
			subset=["mention_id", "candidate_id"]
		).reset_index(drop=True)
	else:
		candidates_df = pd.DataFrame(columns=candidate_columns)

	# Build inventory DataFrame
	inventory_df = pd.DataFrame(inventory_rows)
	if inventory_df.empty:
		inventory_df = pd.DataFrame(
			columns=["file", "query_type", "key", "requested_at_utc", "age_days", "source"]
		)

	# Write all outputs atomically
	phase_dir = _phase_dir(repo_root)
	wikidata_dir = _wikidata_dir(repo_root)
	
	_atomic_write_df(phase_dir / "candidates.csv", candidates_df)
	_atomic_write_df(wikidata_dir / "candidate_index.csv", candidates_df)
	_atomic_write_df(wikidata_dir / "query_inventory.csv", inventory_df)

	summary = {
		"raw_files": int(len(inventory_df)),
		"candidate_rows": int(len(candidates_df)),
		"candidates_csv": str(phase_dir / "candidates.csv"),
		"candidate_index_csv": str(wikidata_dir / "candidate_index.csv"),
		"query_inventory_csv": str(wikidata_dir / "query_inventory.csv"),
	}
	_atomic_write_text(
		wikidata_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2)
	)
	return summary
