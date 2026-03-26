"""Load person mention targets from Phase 1 output.

Person mentions extracted by the Phase 1 pipeline are used for matching
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


def load_person_targets(root: str | Path) -> list[dict[str, str]]:
	"""Load person mentions extracted in Phase 1.
	
	Reads persons.csv from the mention_detection output. Each row represents
	a person mentioned in an episode with extracted name and source context.
	
	Args:
		root: Repository root path.
	
	Returns:
		List of dicts with keys: mention_id, mention_type, mention_label, context.
	"""
	path = Path(root) / "data" / "10_mention_detection" / "persons.csv"
	if not path.exists():
		return []

	df = pd.read_csv(path)
	if df.empty:
		return []

	rows: list[dict[str, str]] = []
	for _, r in df.iterrows():
		rows.append(
			{
				"mention_id": _safe_str(r.get("mention_id", "")),
				"mention_type": "person",
				"mention_label": _safe_str(r.get("name", "")),
				"context": _safe_str(r.get("source_context", "")),
			}
		)
	return rows
