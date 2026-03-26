"""Load season mention targets from Phase 1 output.

Season mentions extracted by the Phase 1 pipeline are used for matching
against Wikidata entities discovered through tree expansion.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def _safe_str(value: object) -> str:
	"""Safely convert a value to string, handling None and NaN."""
	if value is None:
		return ""
	text = str(value)
	return "" if text == "nan" else text


def load_season_targets(root: str | Path) -> list[dict[str, str]]:
	"""Load season mentions extracted in Phase 1.
	
	Reads seasons.csv from the mention_detection output. Each row represents
	a season (series/staffel) with temporal and episode count information.
	
	Args:
		root: Repository root path.
	
	Returns:
		List of dicts with keys: mention_id, mention_type, mention_label, context.
	"""
	path = Path(root) / "data" / "10_mention_detection" / "seasons.csv"
	if not path.exists():
		return []

	df = pd.read_csv(path)
	if df.empty:
		return []

	rows: list[dict[str, str]] = []
	for _, r in df.iterrows():
		rows.append(
			{
				"mention_id": _safe_str(r.get("season_id", "")),
				"mention_type": "season",
				"mention_label": _safe_str(r.get("season_label", "")),
				"context": " ".join(
					[
						_safe_str(r.get("start_time", "")),
						_safe_str(r.get("end_time", "")),
						_safe_str(r.get("episode_count", "")),
					]
				).strip(),
			}
		)
	return rows
