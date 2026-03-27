"""Load season mention targets from Phase 1 output.

Season mentions extracted by the Phase 1 pipeline are used for matching
against Wikidata entities discovered through tree expansion.
"""
from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


def _safe_str(value: object) -> str:
	"""Safely convert a value to string, handling None and NaN."""
	if value is None:
		return ""
	text = str(value)
	return "" if text == "nan" else text


def _select_existing_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
	"""Return a copy with only columns present in the DataFrame."""
	existing = [c for c in columns if c in df.columns]
	return df.loc[:, existing].copy()


def load_seasons_context(root: str | Path) -> pd.DataFrame:
	"""Load and reduce seasons.csv to the required context columns."""
	path = Path(root) / "data" / "10_mention_detection" / "seasons.csv"
	if not path.exists():
		return pd.DataFrame(columns=["season_id", "season_label", "start_time", "end_time", "episode_count"])

	df = pd.read_csv(path)
	return _select_existing_columns(df, ["season_id", "season_label", "start_time", "end_time", "episode_count"])


def build_seasons_lookup(seasons_ctx_df: pd.DataFrame) -> pd.DataFrame:
	"""Create season lookup data with chunked season labels."""
	def split_season_label_chunks(label: object) -> list[str]:
		if pd.isna(label):
			return []
		text = str(label).strip()
		if not text:
			return []
		return [part.strip() for part in re.split(r"[,;|/\\-]+", text) if part and part.strip()]

	seasons_lookup_df = seasons_ctx_df.copy()
	if "season_label" not in seasons_lookup_df.columns:
		return seasons_lookup_df

	season_chunks = seasons_lookup_df["season_label"].apply(split_season_label_chunks)
	max_chunks = int(season_chunks.map(len).max() or 0)
	for i in range(max_chunks):
		seasons_lookup_df[f"season_label_chunk{i + 1}"] = season_chunks.apply(
			lambda parts: parts[i] if i < len(parts) else ""
		)
	return seasons_lookup_df


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
