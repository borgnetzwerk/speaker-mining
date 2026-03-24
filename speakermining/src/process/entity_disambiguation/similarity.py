from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from .config import SCORE_COLUMNS


def _norm(value: str) -> str:
	return " ".join(str(value or "").lower().split())


def label_similarity(a: str, b: str) -> float:
	return float(SequenceMatcher(None, _norm(a), _norm(b)).ratio())


def context_overlap(mention_context: str, candidate_context: str) -> float:
	a = set(_norm(mention_context).split())
	b = set(_norm(candidate_context).split())
	if not a or not b:
		return 0.0
	inter = len(a.intersection(b))
	union = len(a.union(b))
	return float(inter / union)


def score_candidates(candidates_df: pd.DataFrame) -> pd.DataFrame:
	"""Precision-first scoring for mention/candidate pairs.

	Required columns in candidates_df:
	mention_id, mention_label, candidate_id, candidate_label, context
	"""
	required = ["mention_id", "mention_label", "candidate_id", "candidate_label", "context"]
	missing = [c for c in required if c not in candidates_df.columns]
	if missing:
		raise ValueError(f"Missing candidate columns for scoring: {missing}")

	rows: list[dict[str, str | float]] = []
	for _, r in candidates_df.iterrows():
		label_score = label_similarity(r["mention_label"], r["candidate_label"])
		ctx_score = context_overlap(r.get("mention_label", ""), r.get("context", ""))

		# Precision-first: label match dominates.
		score = 0.85 * label_score + 0.15 * ctx_score

		rows.append(
			{
				"mention_id": r["mention_id"],
				"candidate_id": r["candidate_id"],
				"score": round(score, 6),
				"method": "label85_context15",
				"explanation": f"label={label_score:.3f};context={ctx_score:.3f}",
			}
		)

	if not rows:
		return pd.DataFrame(columns=SCORE_COLUMNS)

	return pd.DataFrame(rows)[SCORE_COLUMNS]
