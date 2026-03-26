from __future__ import annotations

from pathlib import Path


DATA_DIR = Path("data")
INPUT_PHASE_DIR = DATA_DIR / "20_candidate_generation"
PHASE_DIR = DATA_DIR / "30_entity_disambiguation"
HISTORY_DIR = PHASE_DIR / "history"


FILE_SCORES = "similarity.csv"
FILE_RECOMMENDATIONS = "recommendations.csv"
FILE_SELECTIONS = "selections.csv"


SCORE_COLUMNS = [
    "mention_id",
    "candidate_id",
    "score",
    "method",
    "explanation",
]

RECOMMENDATION_COLUMNS = [
    "mention_id",
    "recommended_candidate_id",
    "confidence",
    "reasons",
]

SELECTION_COLUMNS = [
    "mention_id",
    "selected_candidate_id",
    "decision",
    "reason",
    "reviewer",
    "reviewed_at",
]


ALLOWED_DECISIONS = ["accept", "reject", "skip"]