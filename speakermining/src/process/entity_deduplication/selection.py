from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import (
	ALLOWED_DECISIONS,
	FILE_MERGE_SELECTIONS,
	HISTORY_DIR,
	MERGE_SELECTION_COLUMNS,
	PHASE_DIR,
)


def load_manual_merge_selections(output_dir: str | Path | None = None) -> pd.DataFrame:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	path = out_dir / FILE_MERGE_SELECTIONS
	if not path.exists():
		return pd.DataFrame(columns=MERGE_SELECTION_COLUMNS)
	return pd.read_csv(path)


def build_review_sheet(scores_df: pd.DataFrame, recommendations_df: pd.DataFrame) -> pd.DataFrame:
	required_scores = ["entity_id_left", "entity_id_right", "score", "method", "explanation"]
	missing = [c for c in required_scores if c not in scores_df.columns]
	if missing:
		raise ValueError(f"Scores missing columns for dedup review sheet: {missing}")

	merged = scores_df[required_scores].merge(
		recommendations_df,
		on=["entity_id_left", "entity_id_right"],
		how="left",
	)
	merged = merged.sort_values(by="score", ascending=False).reset_index(drop=True)
	merged["human_decision"] = ""
	merged["merged_entity_id"] = ""
	merged["human_reason"] = ""
	merged["reviewer"] = ""
	merged["reviewed_at"] = ""
	return merged


def validate_manual_merge_selections(df: pd.DataFrame) -> None:
	missing = [c for c in MERGE_SELECTION_COLUMNS if c not in df.columns]
	if missing:
		raise ValueError(f"Manual merge selection file missing columns: {missing}")

	if df.empty:
		raise ValueError("Manual merge selection file is empty. Human decisions are required.")

	invalid = sorted(set(df[~df["decision"].isin(ALLOWED_DECISIONS)]["decision"].tolist()))
	if invalid:
		raise ValueError(f"Invalid merge decisions: {invalid}")

	if (df["reviewer"].astype(str).str.strip() == "").any():
		raise ValueError("Every merge decision must contain reviewer.")
	if (df["reviewed_at"].astype(str).str.strip() == "").any():
		raise ValueError("Every merge decision must contain reviewed_at.")


def backup_manual_merge_selections(df: pd.DataFrame, history_dir: str | Path | None = None) -> Path:
	out_dir = Path(history_dir) if history_dir else HISTORY_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	path = out_dir / f"mg_{stamp}.csv"
	df.to_csv(path, index=False)
	return path


def require_manual_gate(output_dir: str | Path | None = None) -> pd.DataFrame:
	df = load_manual_merge_selections(output_dir)
	validate_manual_merge_selections(df)
	backup_manual_merge_selections(df)
	return df[MERGE_SELECTION_COLUMNS]
