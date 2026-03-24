from __future__ import annotations

import pandas as pd

from .config import RECOMMENDATION_COLUMNS


def _confidence_bucket(score: float) -> str:
	if score >= 0.92:
		return "high"
	if score >= 0.80:
		return "medium"
	return "low"


def build_recommendations(scores_df: pd.DataFrame, top_n: int = 1) -> pd.DataFrame:
	required = ["mention_id", "candidate_id", "score", "method", "explanation"]
	missing = [c for c in required if c not in scores_df.columns]
	if missing:
		raise ValueError(f"Missing score columns for recommendations: {missing}")

	if scores_df.empty:
		return pd.DataFrame(columns=RECOMMENDATION_COLUMNS)

	ranked = scores_df.sort_values(by=["mention_id", "score"], ascending=[True, False])
	picked = ranked.groupby("mention_id", as_index=False).head(top_n)

	rows = []
	for _, r in picked.iterrows():
		conf = _confidence_bucket(float(r["score"]))
		rows.append(
			{
				"mention_id": r["mention_id"],
				"recommended_candidate_id": r["candidate_id"],
				"confidence": conf,
				"reasons": f"score={r['score']:.3f}; {r['method']}; {r['explanation']}",
			}
		)

	return pd.DataFrame(rows)[RECOMMENDATION_COLUMNS]
