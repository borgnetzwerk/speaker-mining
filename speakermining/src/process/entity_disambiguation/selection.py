from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import (
	ALLOWED_DECISIONS,
	FILE_RECOMMENDATIONS,
	FILE_SELECTIONS,
	HISTORY_DIR,
	PHASE_DIR,
	RECOMMENDATION_COLUMNS,
	SELECTION_COLUMNS,
)


def save_recommendations(df: pd.DataFrame, output_dir: str | Path | None = None) -> Path:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	path = out_dir / FILE_RECOMMENDATIONS
	df[RECOMMENDATION_COLUMNS].to_csv(path, index=False)
	return path


def build_review_sheet(
	candidates_df: pd.DataFrame,
	scores_df: pd.DataFrame,
	recommendations_df: pd.DataFrame,
	top_k: int = 5,
) -> pd.DataFrame:
	"""Build a human-friendly sheet with ranked options and compact context."""
	required_candidates = [
		"mention_id",
		"mention_label",
		"candidate_id",
		"candidate_label",
		"source",
		"context",
	]
	missing = [c for c in required_candidates if c not in candidates_df.columns]
	if missing:
		raise ValueError(f"Candidates missing columns for review sheet: {missing}")

	s = scores_df[["mention_id", "candidate_id", "score", "explanation"]].copy()
	c = candidates_df[required_candidates].copy()
	merged = c.merge(s, on=["mention_id", "candidate_id"], how="left")
	merged = merged.merge(recommendations_df, on="mention_id", how="left")
	merged = merged.sort_values(by=["mention_id", "score"], ascending=[True, False])
	merged["rank"] = merged.groupby("mention_id").cumcount() + 1
	merged = merged[merged["rank"] <= top_k].copy()

	merged["is_recommended"] = (
		merged["candidate_id"].astype(str) == merged["recommended_candidate_id"].astype(str)
	)
	merged["human_decision"] = ""
	merged["human_reason"] = ""
	merged["reviewer"] = ""
	merged["reviewed_at"] = ""
	return merged


def load_manual_selections(output_dir: str | Path | None = None) -> pd.DataFrame:
	out_dir = Path(output_dir) if output_dir else PHASE_DIR
	path = out_dir / FILE_SELECTIONS
	if not path.exists():
		return pd.DataFrame(columns=SELECTION_COLUMNS)
	return pd.read_csv(path)


def validate_manual_selections(df: pd.DataFrame) -> None:
	missing = [c for c in SELECTION_COLUMNS if c not in df.columns]
	if missing:
		raise ValueError(f"Manual selection file missing columns: {missing}")

	if df.empty:
		raise ValueError("Manual selection file is empty. Human decisions are required.")

	invalid = sorted(set(df[~df["decision"].isin(ALLOWED_DECISIONS)]["decision"].tolist()))
	if invalid:
		raise ValueError(f"Invalid decisions in manual selection file: {invalid}")

	if (df["reviewer"].astype(str).str.strip() == "").any():
		raise ValueError("Every row must contain reviewer.")
	if (df["reviewed_at"].astype(str).str.strip() == "").any():
		raise ValueError("Every row must contain reviewed_at.")


def backup_manual_selections(df: pd.DataFrame, history_dir: str | Path | None = None) -> Path:
	out_dir = Path(history_dir) if history_dir else HISTORY_DIR
	out_dir.mkdir(parents=True, exist_ok=True)
	stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
	path = out_dir / f"sel_{stamp}.csv"
	df.to_csv(path, index=False)
	return path


def require_manual_gate(output_dir: str | Path | None = None) -> pd.DataFrame:
	df = load_manual_selections(output_dir)
	validate_manual_selections(df)
	backup_manual_selections(df)
	return df[SELECTION_COLUMNS]
