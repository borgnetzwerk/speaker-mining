from __future__ import annotations

import pandas as pd

from .selection import require_manual_gate


def ingest_selected_candidates() -> pd.DataFrame:
	"""Return accepted selections for downstream phases.

	This function enforces the manual gate by requiring a validated sel.csv.
	"""
	decisions = require_manual_gate()
	accepted = decisions[decisions["decision"] == "accept"].copy()
	accepted = accepted.rename(columns={"selected_candidate_id": "candidate_id"})
	return accepted[["mention_id", "candidate_id", "reason", "reviewer", "reviewed_at"]]
