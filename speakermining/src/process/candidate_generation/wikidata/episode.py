"""Load episode and publication mention targets from Phase 1 output.

These mention targets are extracted by the Phase 1 (mention_detection) pipeline
and will be used to match against Wikidata entities discovered through tree expansion.
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


def load_episode_targets(root: str | Path) -> list[dict[str, str]]:
	"""Load episode mentions extracted in Phase 1.
	
	Reads episodes.csv from the mention_detection output. Each row represents
	an episode mention with a normalized label for matching.
	
	Args:
		root: Repository root path.
	
	Returns:
		List of dicts with keys: mention_id, mention_type, mention_label, context.
	"""
	path = Path(root) / "data" / "10_mention_detection" / "episodes.csv"
	if not path.exists():
		return []

	df = pd.read_csv(path)
	if df.empty:
		return []

	rows: list[dict[str, str]] = []
	for _, r in df.iterrows():
		rows.append(
			{
				"mention_id": _safe_str(r.get("episode_id", "")),
				"mention_type": "episode",
				"mention_label": _safe_str(r.get("sendungstitel", "")),
				"context": _safe_str(r.get("infos", "")),
			}
		)
	return rows


def load_publication_targets(root: str | Path) -> list[dict[str, str]]:
	"""Load publication mentions extracted in Phase 1.
	
	Reads publications.csv from the mention_detection output. Each row represents
	a publication (broadcast occurrence) with program, date, and time information.
	
	Args:
		root: Repository root path.
	
	Returns:
		List of dicts with keys: mention_id, mention_type, mention_label, context.
	"""
	path = Path(root) / "data" / "10_mention_detection" / "publications.csv"
	if not path.exists():
		return []

	df = pd.read_csv(path)
	if df.empty:
		return []

	rows: list[dict[str, str]] = []
	for _, r in df.iterrows():
		label_parts = [_safe_str(r.get("program", "")), _safe_str(r.get("date", "")), _safe_str(r.get("time", ""))]
		label = " ".join([part for part in label_parts if part]).strip()
		rows.append(
			{
				"mention_id": _safe_str(r.get("publikation_id", "")),
				"mention_type": "publication",
				"mention_label": label,
				"context": _safe_str(r.get("raw_line", "")),
			}
		)
	return rows
