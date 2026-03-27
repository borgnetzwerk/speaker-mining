"""Load episode and publication mention targets from Phase 1 output.

These mention targets are extracted by the Phase 1 (mention_detection) pipeline
and will be used to match against Wikidata entities discovered through tree expansion.
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


def load_episodes_context(root: str | Path) -> pd.DataFrame:
	"""Load and reduce episodes.csv to required context columns."""
	path = Path(root) / "data" / "10_mention_detection" / "episodes.csv"
	if not path.exists():
		return pd.DataFrame(columns=["episode_id", "sendungstitel", "season", "staffel", "folge", "folgennr"])

	df = pd.read_csv(path)
	return _select_existing_columns(df, ["episode_id", "sendungstitel", "season", "staffel", "folge", "folgennr"])


def load_publications_context(root: str | Path) -> pd.DataFrame:
	"""Load and reduce publications.csv to required context columns."""
	path = Path(root) / "data" / "10_mention_detection" / "publications.csv"
	if not path.exists():
		return pd.DataFrame(columns=["episode_id", "date", "time", "duration", "program", "prod_nr_sendung", "prod_nr_secondary"])

	df = pd.read_csv(path)
	return _select_existing_columns(df, ["episode_id", "date", "time", "duration", "program", "prod_nr_sendung", "prod_nr_secondary"])


def _normalize_season_token(value: object) -> str:
	"""Normalize season tokens for redundancy checks between season and staffel."""
	if pd.isna(value):
		return ""
	text = str(value).strip().lower()
	if not text:
		return ""

	match = re.search(r"staffel\s*([0-9]+(?:[\.,][0-9]+)?)", text)
	if match:
		text = match.group(1)
	else:
		text = re.sub(r"(?i)^staffel\s*", "", text).strip()

	text = text.replace(",", ".")
	if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
		number = float(text)
		if number.is_integer():
			return str(int(number))
		return str(number)

	return re.sub(r"\s+", " ", text)


def build_episodes_lookup(episodes_ctx_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
	"""Reduce episode context and report non-redundant season/staffel rows.
	
	Returns:
		Tuple of (episodes_lookup_df, season_staffel_mismatches_df).
	"""
	episodes_lookup_df = _select_existing_columns(
		episodes_ctx_df, ["episode_id", "sendungstitel", "season", "staffel", "folge", "folgennr"]
	).copy()

	if "staffel" in episodes_lookup_df.columns and "season" in episodes_lookup_df.columns:
		season_norm = episodes_lookup_df["season"].apply(_normalize_season_token)
		staffel_norm = episodes_lookup_df["staffel"].apply(_normalize_season_token)
		mismatch_mask = (staffel_norm != "") & (season_norm != "") & (staffel_norm != season_norm)
		season_staffel_mismatches_df = episodes_lookup_df.loc[
			mismatch_mask, ["episode_id", "sendungstitel", "staffel", "season"]
		].copy()
	else:
		season_staffel_mismatches_df = pd.DataFrame()

	if "staffel" in episodes_lookup_df.columns:
		episodes_lookup_df = episodes_lookup_df.drop(columns=["staffel"])

	episodes_lookup_df = _select_existing_columns(
		episodes_lookup_df, ["episode_id", "sendungstitel", "season", "folge", "folgennr"]
	)
	return episodes_lookup_df, season_staffel_mismatches_df


def append_publications_to_episodes(
	episodes_lookup_df: pd.DataFrame, publications_ctx_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
	"""Append publication_{field}_{index} columns to episodes by episode_id.
	
	Returns:
		Tuple of (merged episodes df, publication long df, publication wide df).
	"""
	publication_fields = ["date", "time", "duration", "program", "prod_nr_sendung", "prod_nr_secondary"]
	publications_df = publications_ctx_df.copy()
	for col in publication_fields:
		if col not in publications_df.columns:
			publications_df[col] = ""

	pub_long_df = publications_df[["episode_id"] + publication_fields].copy()
	pub_long_df["publication_index"] = pub_long_df.groupby("episode_id").cumcount()

	pub_wide_df = (
		pub_long_df.pivot(index="episode_id", columns="publication_index", values=publication_fields)
		.sort_index(axis=1, level=1)
		.copy()
	)

	rename_map: dict[tuple[str, int], str] = {}
	for field_name, idx in pub_wide_df.columns.to_flat_index():
		if field_name == "date":
			out_name = f"publication_data_{idx}"
		else:
			out_name = f"publication_{field_name}_{idx}"
		rename_map[(field_name, idx)] = out_name

	pub_wide_df.columns = [rename_map[key] for key in pub_wide_df.columns.to_flat_index()]
	pub_wide_df = pub_wide_df.reset_index()
	merged_df = episodes_lookup_df.merge(pub_wide_df, on="episode_id", how="left")
	return merged_df, pub_long_df, pub_wide_df


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
