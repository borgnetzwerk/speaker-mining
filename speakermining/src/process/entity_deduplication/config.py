from __future__ import annotations

from pathlib import Path


DATA_DIR = Path("data")
INPUT_PHASE_DIR = DATA_DIR / "30_entity_disambiguation"
PHASE_DIR = DATA_DIR / "31_entity_deduplication"
HISTORY_DIR = PHASE_DIR / "history"


FILE_ENTITY_SCORES = "similarity.csv"
FILE_MERGE_RECOMMENDATIONS = "recommendations.csv"
FILE_MERGE_SELECTIONS = "selections.csv"


ENTITY_SCORE_COLUMNS = [
    "entity_id_left",
    "entity_id_right",
    "score",
    "method",
    "explanation",
]

MERGE_RECOMMENDATION_COLUMNS = [
    "entity_id_left",
    "entity_id_right",
    "recommended_action",
    "confidence",
    "reasons",
]

MERGE_SELECTION_COLUMNS = [
    "entity_id_left",
    "entity_id_right",
    "decision",
    "merged_entity_id",
    "reason",
    "reviewer",
    "reviewed_at",
]


ALLOWED_DECISIONS = ["merge", "keep_separate", "skip"]