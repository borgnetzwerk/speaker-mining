from __future__ import annotations

import pandas as pd

from .config import MERGE_RECOMMENDATION_COLUMNS


def _action(score: float) -> tuple[str, str]:
	if score >= 0.96:
		return "merge", "high"
	if score >= 0.92:
		return "review", "medium"
	return "keep_separate", "low"


def build_merge_recommendations(scores_df: pd.DataFrame) -> pd.DataFrame:
	required = ["entity_id_left", "entity_id_right", "score", "method", "explanation"]
	missing = [c for c in required if c not in scores_df.columns]
	if missing:
		raise ValueError(f"Missing score columns for merge recommendations: {missing}")

	if scores_df.empty:
		return pd.DataFrame(columns=MERGE_RECOMMENDATION_COLUMNS)

	rows = []
	for _, r in scores_df.iterrows():
		action, conf = _action(float(r["score"]))
		rows.append(
			{
				"entity_id_left": r["entity_id_left"],
				"entity_id_right": r["entity_id_right"],
				"recommended_action": action,
				"confidence": conf,
				"reasons": f"score={r['score']:.3f}; {r['method']}; {r['explanation']}",
			}
		)

	return pd.DataFrame(rows)[MERGE_RECOMMENDATION_COLUMNS]
