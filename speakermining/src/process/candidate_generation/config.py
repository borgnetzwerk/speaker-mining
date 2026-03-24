from __future__ import annotations

from pathlib import Path


DATA_DIR = Path("data")
INPUT_PHASE_DIR = DATA_DIR / "10_mention_detection"
PHASE_DIR = DATA_DIR / "20_canidate_generation"
CACHE_DIR = PHASE_DIR / "cache"


FILE_CANDIDATES = "candidates.csv"
FILE_LINKS = "links.csv"

SOURCE_PRIORITY = [
    "wikibase",
    "wikidata",
    "fernsehserien_de",
    "youtube",
    "other",
]


MANDATORY_SOURCES = ["wikibase", "wikidata"]
OPTIONAL_SOURCES = ["fernsehserien_de", "youtube", "other"]


CANDIDATE_COLUMNS = [
    "mention_id",
    "mention_label",
    "candidate_id",
    "candidate_label",
    "source",
    "score",
    "context",
]

LINK_COLUMNS = [
    "src_candidate_id",
    "property",
    "value",
    "target_candidate_id",
    "source",
]
