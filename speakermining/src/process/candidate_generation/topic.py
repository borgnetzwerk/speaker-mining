"""Load topic mention targets from Phase 1 output.

Topic mentions extracted by the Phase 1 pipeline are used for matching
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


def load_topics_context(root: str | Path) -> pd.DataFrame:
	"""Load and reduce topics.csv to required context columns."""
	path = Path(root) / "data" / "10_mention_detection" / "topics.csv"
	if not path.exists():
		return pd.DataFrame(columns=["episode_id", "topic"])

	df = pd.read_csv(path)
	return _select_existing_columns(df, ["episode_id", "topic"])


def append_topics_to_episodes(
	episodes_lookup_df: pd.DataFrame, topics_ctx_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
	"""Append topic_{index} columns to episodes.

	Returns:
		Tuple of (merged episodes df, topics lookup df, topic long df, topic wide df).
	"""
	topics_lookup_df = topics_ctx_df.copy()
	if "topic" not in topics_lookup_df.columns:
		topics_lookup_df["topic"] = ""

	topic_long_df = topics_lookup_df[["episode_id", "topic"]].copy()
	topic_long_df["topic_index"] = topic_long_df.groupby("episode_id").cumcount()

	topic_wide_df = (
		topic_long_df.pivot(index="episode_id", columns="topic_index", values="topic")
		.sort_index(axis=1)
		.copy()
	)

	topic_wide_df.columns = [f"topic_{idx}" for idx in topic_wide_df.columns]
	topic_wide_df = topic_wide_df.reset_index()

	# Make the merge idempotent when this cell is rerun by removing prior topic_* columns.
	existing_topic_cols = [
		c
		for c in episodes_lookup_df.columns
		if re.match(r"^topic_\d+(_[xy])?$", str(c))
	]
	base_episodes_df = episodes_lookup_df.drop(columns=existing_topic_cols, errors="ignore")
	merged_df = base_episodes_df.merge(topic_wide_df, on="episode_id", how="left")
	return merged_df, topics_lookup_df, topic_long_df, topic_wide_df


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
