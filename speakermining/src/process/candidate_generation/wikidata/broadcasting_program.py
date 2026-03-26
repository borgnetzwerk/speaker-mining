"""Load broadcasting program seed entities from setup data.

Reads the broadcasting_programs.csv file from the setup directory and returns a list
of seed entities (broadcasting programs like "Markus Lanz") that will serve as the
starting points for Wikidata tree expansion.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_broadcasting_program_seeds(root: str | Path) -> list[dict[str, str]]:
	"""Load broadcasting program seed entities from setup data.
	
	Reads the broadcasting_programs.csv file (data/00_setup/broadcasting_programs.csv)
	and returns structured records. Each record contains the program name and its
	Wikidata Q-ID, which will be used as starting points for tree expansion.
	
	Args:
		root: Repository root path.
	
	Returns:
		List of dicts with keys: name, wikidata_id, wikibase_id, fernsehserien_de_id.
		Empty list if file does not exist.
	"""
	path = Path(root) / "data" / "00_setup" / "broadcasting_programs.csv"
	if not path.exists():
		return []

	df = pd.read_csv(path)
	if df.empty:
		return []

	for col in ["name", "wikidata_id", "wikibase_id", "fernsehserien_de_id"]:
		if col not in df.columns:
			df[col] = ""

	records: list[dict[str, str]] = []
	for _, row in df.iterrows():
		records.append(
			{
				"name": str(row.get("name", "") or ""),
				"wikidata_id": str(row.get("wikidata_id", "") or ""),
				"wikibase_id": str(row.get("wikibase_id", "") or ""),
				"fernsehserien_de_id": str(row.get("fernsehserien_de_id", "") or ""),
			}
		)
	return records
