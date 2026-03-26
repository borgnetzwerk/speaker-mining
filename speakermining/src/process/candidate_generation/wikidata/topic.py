"""Load topic mention targets from Phase 1 output.

Topic mentions extracted by the Phase 1 pipeline are used for matching
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


def load_topic_targets(root: str | Path) -> list[dict[str, str]]:
	"""Load topic mentions extracted in Phase 1.
	
	Reads topics.csv from the mention_detection output. Each row represents
	a topic (subject) mentioned in an episode with source context.
	
	Args:
		root: Repository root path.
	
	Returns:
		List of dicts with keys: mention_id, mention_type, mention_label, context.
	"""
	path = Path(root) / "data" / "10_mention_detection" / "topics.csv"
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
				"mention_type": "topic",
				"mention_label": _safe_str(r.get("topic", "")),
				"context": _safe_str(r.get("source_context", "")),
			}
		)
	return rows
