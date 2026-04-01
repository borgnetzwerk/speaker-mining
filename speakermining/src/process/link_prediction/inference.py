from __future__ import annotations

from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv


REL_COLUMNS = ["source_id", "property", "target_id", "confidence", "reason"]


def infer_episode_person_links(person_mentions_df: pd.DataFrame) -> pd.DataFrame:
	required = ["episode_id", "name"]
	missing = [c for c in required if c not in person_mentions_df.columns]
	if missing:
		raise ValueError(f"Person mentions missing columns for inference: {missing}")

	rows = []
	for _, r in person_mentions_df.iterrows():
		rows.append(
			{
				"source_id": r["episode_id"],
				"property": "talk_show_guest",
				"target_id": str(r["name"]),
				"confidence": 0.8,
				"reason": "direct_mention_in_episode",
			}
		)

	if not rows:
		return pd.DataFrame(columns=REL_COLUMNS)
	return pd.DataFrame(rows)[REL_COLUMNS].drop_duplicates().reset_index(drop=True)


def save_relations(df: pd.DataFrame, output_dir: str | Path = "data/40_link_prediction") -> Path:
	out_dir = Path(output_dir)
	out_dir.mkdir(parents=True, exist_ok=True)
	path = out_dir / "rel.csv"
	atomic_write_csv(path, df[REL_COLUMNS], index=False)
	return path
