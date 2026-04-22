"""Load person mention targets from Phase 1 output.

Person mentions extracted by the Phase 1 pipeline are used for matching
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


def load_persons_context(root: str | Path) -> pd.DataFrame:
	"""Load and reduce persons.csv to required context columns."""
	path = Path(root) / "data" / "10_mention_detection" / "persons.csv"
	if not path.exists():
		return pd.DataFrame(columns=["mention_id", "episode_id", "name", "beschreibung"])

	df = pd.read_csv(path)
	return _select_existing_columns(df, ["mention_id", "episode_id", "name", "beschreibung"])


def clean_mixed_uppercase_name(name: object) -> str:
	"""Lowercase uppercase tails within words while preserving first character.

	Examples:
		Elmar THEVEßEN -> Elmar Theveßen
		Robin ALEXANDER -> Robin Alexander
	"""
	if pd.isna(name):
		return ""
	text = str(name).strip()
	if not text:
		return ""
	words = text.split()
	cleaned_words: list[str] = []
	for word in words:
		if not word:
			cleaned_words.append(word)
			continue
		cleaned_words.append(word[0] + word[1:].lower())
	return " ".join(cleaned_words)


_UMLAUT_PAIRS = [("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")]


def normalize_name_for_matching(name: object) -> str:
    """Return a lowercase ASCII-ish key for matching ZDF names against Wikidata labels.

    Applies mixed-case cleanup then umlaut digraph substitution so that
    "Elmar THEVEßEN" and "Elmar Thevessen" both resolve to "elmar thevessen".
    Apply to both sides before comparison — not suitable for display.
    """
    text = clean_mixed_uppercase_name(name)
    for umlaut, digraph in _UMLAUT_PAIRS:
        text = text.replace(umlaut, digraph)
    return text.lower()


def _normalize_description(value: object) -> str:
	"""Normalize description text for duplicate comparisons."""
	if pd.isna(value):
		return ""
	text = str(value).strip()
	if not text:
		return ""
	return re.sub(r"\s+", " ", text).lower()


def split_duplicate_person_mentions(
	persons_lookup_df: pd.DataFrame,
	episodes_lookup_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
	"""Split person mentions into cleaned rows and duplicate-feedback rows.

	Duplicate rule:
	- same episode_id + name_cleaned and
	- same description, or at least one side has no description.
	
	Rows flagged as duplicates are excluded from downstream guest columns.
	"""
	if persons_lookup_df.empty:
		return persons_lookup_df.copy(), pd.DataFrame(columns=[
			"mention_id",
			"episode_id",
			"name",
			"name_cleaned",
			"beschreibung",
			"kept_mention_id",
			"kept_beschreibung",
			"duplicate_reason",
			"sendungstitel",
			"season",
		])

	df = persons_lookup_df.copy()
	if "mention_id" not in df.columns:
		df["mention_id"] = [f"generated_{i}" for i in range(len(df))]

	df["beschreibung_norm"] = df["beschreibung"].apply(_normalize_description)
	df["_has_desc"] = df["beschreibung_norm"] != ""
	df["_desc_len"] = df["beschreibung_norm"].map(len)

	kept_rows: list[pd.Series] = []
	duplicate_rows: list[dict[str, object]] = []

	for (_, _), group in df.groupby(["episode_id", "name_cleaned"], dropna=False, sort=False):
		if len(group) == 1:
			kept_rows.append(group.iloc[0])
			continue

		sorted_group = group.sort_values(by=["_has_desc", "_desc_len", "mention_id"], ascending=[False, False, True])
		keeper = sorted_group.iloc[0]
		kept_rows.append(keeper)

		for _, row in sorted_group.iloc[1:].iterrows():
			same_description = row["beschreibung_norm"] == keeper["beschreibung_norm"]
			missing_description = row["beschreibung_norm"] == "" or keeper["beschreibung_norm"] == ""
			if same_description or missing_description:
				reason = "same_description" if same_description else "missing_description"
				duplicate_rows.append(
					{
						"mention_id": row.get("mention_id", ""),
						"episode_id": row.get("episode_id", ""),
						"name": row.get("name", ""),
						"name_cleaned": row.get("name_cleaned", ""),
						"beschreibung": row.get("beschreibung", ""),
						"kept_mention_id": keeper.get("mention_id", ""),
						"kept_beschreibung": keeper.get("beschreibung", ""),
						"duplicate_reason": reason,
					}
				)
			else:
				kept_rows.append(row)

	cleaned_df = pd.DataFrame(kept_rows).drop(columns=["beschreibung_norm", "_has_desc", "_desc_len"], errors="ignore")
	duplicates_df = pd.DataFrame(duplicate_rows)

	if not duplicates_df.empty:
		episode_context = episodes_lookup_df[[c for c in ["episode_id", "sendungstitel", "season"] if c in episodes_lookup_df.columns]].drop_duplicates()
		duplicates_df = duplicates_df.merge(episode_context, on="episode_id", how="left")

	return cleaned_df.reset_index(drop=True), duplicates_df.reset_index(drop=True)


def append_persons_to_episodes(
	episodes_lookup_df: pd.DataFrame, persons_ctx_df: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
	"""Append guest_{index} and guest_{index}_description columns to episodes.

	Returns:
		Tuple of (merged episodes df, persons lookup df, guest long df, guest wide df, duplicate guests df).
	"""
	persons_lookup_df = persons_ctx_df.copy()
	if "name" not in persons_lookup_df.columns:
		persons_lookup_df["name"] = ""
	if "beschreibung" not in persons_lookup_df.columns:
		persons_lookup_df["beschreibung"] = ""

	persons_lookup_df["name_cleaned"] = persons_lookup_df["name"].apply(clean_mixed_uppercase_name)
	persons_lookup_df, duplicate_guests_df = split_duplicate_person_mentions(persons_lookup_df, episodes_lookup_df)

	guest_long_df = persons_lookup_df[["episode_id", "name_cleaned", "beschreibung"]].copy()
	guest_long_df["guest_index"] = guest_long_df.groupby("episode_id").cumcount()

	guest_wide_df = (
		guest_long_df.pivot(index="episode_id", columns="guest_index", values=["name_cleaned", "beschreibung"])
		.sort_index(axis=1, level=1)
		.copy()
	)

	guest_wide_rename_map: dict[tuple[str, int], str] = {}
	for field_name, idx in guest_wide_df.columns.to_flat_index():
		out_name = f"guest_{idx}" if field_name == "name_cleaned" else f"guest_{idx}_description"
		guest_wide_rename_map[(field_name, idx)] = out_name

	guest_wide_df.columns = [guest_wide_rename_map[key] for key in guest_wide_df.columns.to_flat_index()]
	guest_wide_df = guest_wide_df.reset_index()

	# Make the merge idempotent when this cell is rerun by removing prior guest_* columns.
	existing_guest_cols = [
		c
		for c in episodes_lookup_df.columns
		if re.match(r"^guest_\d+(_description)?(_[xy])?$", str(c))
	]
	base_episodes_df = episodes_lookup_df.drop(columns=existing_guest_cols, errors="ignore")
	merged_df = base_episodes_df.merge(guest_wide_df, on="episode_id", how="left")
	return merged_df, persons_lookup_df, guest_long_df, guest_wide_df, duplicate_guests_df


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
