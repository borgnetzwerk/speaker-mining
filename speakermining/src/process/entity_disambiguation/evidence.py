from __future__ import annotations

from typing import Any

import pandas as pd


def combine_evidence_rows(*evidence_sets: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for evidence_set in evidence_sets:
        rows.extend(evidence_set)

    if not rows:
        return pd.DataFrame(
            columns=[
                "alignment_unit_id",
                "entity_class",
                "match_strategy",
                "match_tier",
                "match_confidence",
                "evidence_summary",
                "unresolved_reason_code",
            ]
        )

    return pd.DataFrame(rows).sort_values(by=["entity_class", "alignment_unit_id"]).reset_index(drop=True)
