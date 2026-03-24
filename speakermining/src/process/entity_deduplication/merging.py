from __future__ import annotations

import pandas as pd

from .selection import require_manual_gate


def apply_merge_decisions(entities_df: pd.DataFrame) -> pd.DataFrame:
	"""Apply human-reviewed dedup decisions to entity table.

	entities_df requires columns: entity_id, label
	"""
	required = ["entity_id", "label"]
	missing = [c for c in required if c not in entities_df.columns]
	if missing:
		raise ValueError(f"Entities missing columns for merge application: {missing}")

	decisions = require_manual_gate()
	out = entities_df.copy()

	for _, d in decisions.iterrows():
		if d["decision"] != "merge":
			continue

		left = d["entity_id_left"]
		right = d["entity_id_right"]
		merged = d["merged_entity_id"]

		out.loc[out["entity_id"].isin([left, right]), "entity_id"] = merged

	out = out.drop_duplicates().reset_index(drop=True)
	return out
