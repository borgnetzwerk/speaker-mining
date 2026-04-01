"""Persistence helpers for Phase 2 candidate generation outputs.

This module centralizes CSV output writing so notebooks stay orchestration-only.
All writes target data/20_candidate_generation and overwrite previous versions.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv


def phase2_output_dir(root: str | Path) -> Path:
	"""Return and ensure the Phase 2 output directory exists."""
	out_dir = Path(root) / "data" / "20_candidate_generation"
	out_dir.mkdir(parents=True, exist_ok=True)
	return out_dir


def persist_dataframe(root: str | Path, df: pd.DataFrame, filename: str) -> Path:
	"""Write a DataFrame to Phase 2 output as CSV (overwrite mode)."""
	path = phase2_output_dir(root) / filename
	atomic_write_csv(path, df, index=False)
	return path


def persist_setup_outputs(
	root: str | Path,
	classes_df: pd.DataFrame,
	properties_df: pd.DataFrame,
	broadcasting_programs_df: pd.DataFrame,
) -> dict[str, Path]:
	"""Persist setup reference tables used by candidate generation."""
	return {
		"classes": persist_dataframe(root, classes_df, "classes.csv"),
		"properties": persist_dataframe(root, properties_df, "properties.csv"),
		"broadcasting_programs": persist_dataframe(root, broadcasting_programs_df, "broadcasting_programs.csv"),
	}


def persist_seasons_output(root: str | Path, seasons_df: pd.DataFrame) -> Path:
	"""Persist the current season lookup table to seasons.csv."""
	return persist_dataframe(root, seasons_df, "seasons.csv")


def persist_episodes_output(root: str | Path, episodes_df: pd.DataFrame) -> Path:
	"""Persist the current episode lookup table to episodes.csv."""
	return persist_dataframe(root, episodes_df, "episodes.csv")


def persist_guest_duplicate_feedback(root: str | Path, duplicates_df: pd.DataFrame) -> Path:
	"""Persist duplicate guest rows as feedback for Phase 1 mining improvements."""
	return persist_dataframe(root, duplicates_df, "person_duplicates_for_phase1_feedback.csv")
