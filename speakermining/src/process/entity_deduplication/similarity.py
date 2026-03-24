from __future__ import annotations

from difflib import SequenceMatcher

import pandas as pd

from .config import ENTITY_SCORE_COLUMNS


def _norm(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _score(a: str, b: str) -> float:
    return float(SequenceMatcher(None, _norm(a), _norm(b)).ratio())


def score_entity_pairs(entities_df: pd.DataFrame, min_score: float = 0.9) -> pd.DataFrame:
    required = ["entity_id", "label"]
    missing = [c for c in required if c not in entities_df.columns]
    if missing:
        raise ValueError(f"Missing entity columns for dedup scoring: {missing}")

    rows: list[dict[str, str | float]] = []
    data = entities_df[required].drop_duplicates().reset_index(drop=True)

    for i in range(len(data)):
        left = data.iloc[i]
        for j in range(i + 1, len(data)):
            right = data.iloc[j]
            s = _score(left["label"], right["label"])
            if s < min_score:
                continue
            rows.append(
                {
                    "entity_id_left": left["entity_id"],
                    "entity_id_right": right["entity_id"],
                    "score": round(s, 6),
                    "method": "label_seq_ratio",
                    "explanation": f"label_similarity={s:.3f}",
                }
            )

    if not rows:
        return pd.DataFrame(columns=ENTITY_SCORE_COLUMNS)
    return pd.DataFrame(rows)[ENTITY_SCORE_COLUMNS]