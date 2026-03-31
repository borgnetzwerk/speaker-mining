"""Build Wikidata mention targets from Phase 2 lookup outputs.

This module keeps notebook orchestration thin by centralizing target construction.
Current policy:
- Main target source is data/20_candidate_generation/episodes.csv.
- Broadcasting program targets are additionally loaded from
  data/20_candidate_generation/broadcasting_programs.csv.
- publication_program_* values are modeled as organizations.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd


EPISODES_TARGET_PATTERNS: list[tuple[str, str]] = [
	("sendungstitel", "episode"),
	("season", "season"),
	("publication_program_", "organization"),
	("guest_", "person"),
	("topic_", "topic"),
]


def _stable_mention_id(
	episode_id: str,
	mention_type: str,
	source_column: str,
	mention_label: str,
) -> str:
	raw = f"{episode_id}|{mention_type}|{source_column}|{mention_label}".encode("utf-8")
	return "cgm_" + hashlib.sha1(raw).hexdigest()[:12]


def _stable_program_mention_id(mention_type: str, source_column: str, mention_label: str) -> str:
	raw = f"{mention_type}|{source_column}|{mention_label}".encode("utf-8")
	return "cgm_" + hashlib.sha1(raw).hexdigest()[:12]


def _column_to_type(column: str, patterns: list[tuple[str, str]]) -> str | None:
	for prefix, mention_type in patterns:
		if column == prefix or column.startswith(prefix):
			if prefix == "guest_" and column.endswith("_description"):
				return None
			return mention_type
	return None


def build_targets_from_phase2_lookup(root: str | Path) -> tuple[list[dict[str, str]], pd.Series, pd.DataFrame]:
	"""Build mention targets for Wikidata matching from Phase 2 outputs.

	Args:
		root: Repository root path.

	Returns:
		Tuple:
		- all_target_rows: list of target rows for BFS matching.
		- mention_stats: Series with counts per mention_type.
		- targets_df: full DataFrame of target rows for notebook display/inspection.
	"""
	root_path = Path(root)
	phase2_dir = root_path / "data" / "20_candidate_generation"

	episodes_path = phase2_dir / "episodes.csv"
	programs_path = phase2_dir / "broadcasting_programs.csv"

	episodes_df = pd.read_csv(episodes_path)

	target_rows: list[dict[str, str]] = []

	for _, row in episodes_df.iterrows():
		episode_id = str(row.get("episode_id", "")).strip()
		episode_title = str(row.get("sendungstitel", "")).strip()
		context_base = f"episode_id={episode_id}; sendungstitel={episode_title}"

		for column in episodes_df.columns:
			mention_type = _column_to_type(column, EPISODES_TARGET_PATTERNS)
			if mention_type is None:
				continue

			value = row.get(column)
			if pd.isna(value):
				continue

			mention_label = str(value).strip()
			if not mention_label:
				continue

			target_rows.append(
				{
					"mention_id": _stable_mention_id(episode_id, mention_type, column, mention_label),
					"mention_type": mention_type,
					"mention_label": mention_label,
					"context": f"{context_base}; source_column={column}",
				}
			)

	# Add broadcasting program entities from dedicated phase-2 table.
	if programs_path.exists():
		programs_df = pd.read_csv(programs_path)
		if "label" in programs_df.columns or "name" in programs_df.columns:
			for _, row in programs_df.iterrows():
				program_name = str(row.get("label", row.get("name", "")) or "").strip()
				if not program_name:
					continue
				target_rows.append(
					{
						"mention_id": _stable_program_mention_id(
							"broadcasting_program", "broadcasting_programs.label", program_name
						),
						"mention_type": "broadcasting_program",
						"mention_label": program_name,
						"context": "source=data/20_candidate_generation/broadcasting_programs.csv; source_column=label",
					}
				)

	seen: set[tuple[str, str, str]] = set()
	all_target_rows: list[dict[str, str]] = []
	for row in target_rows:
		key = (row["mention_type"], row["mention_label"], row["context"])
		if key in seen:
			continue
		seen.add(key)
		all_target_rows.append(row)

	if all_target_rows:
		mention_stats = pd.Series([r["mention_type"] for r in all_target_rows]).value_counts().sort_index()
		targets_df = pd.DataFrame(all_target_rows)
	else:
		mention_stats = pd.Series(dtype="int64")
		targets_df = pd.DataFrame(columns=["mention_id", "mention_type", "mention_label", "context"])

	return all_target_rows, mention_stats, targets_df


__all__ = ["build_targets_from_phase2_lookup"]
