from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data")
PHASE31_DIR = DATA_DIR / "31_entity_disambiguation"
PHASE32_DIR = DATA_DIR / "32_entity_deduplication"

ALIGNED_DIR = PHASE31_DIR / "aligned"

INPUT_FILES = {
    "aligned_persons": ALIGNED_DIR / "aligned_persons.csv",
}

OUTPUT_DIR = PHASE32_DIR
OUTPUT_FILES = {
    "dedup_persons": PHASE32_DIR / "dedup_persons.csv",
    "dedup_cluster_members": PHASE32_DIR / "dedup_cluster_members.csv",
    "dedup_summary": PHASE32_DIR / "dedup_summary.json",
}

DEDUP_PERSONS_COLUMNS = [
    "canonical_entity_id",
    "entity_class",
    "cluster_size",
    "cluster_strategy",
    "cluster_confidence",
    "wikidata_id",
    "canonical_label",
    "open_refine_name",
    "cluster_key",
    "evidence_summary",
    "representative_alignment_unit_id",
]

DEDUP_CLUSTER_MEMBERS_COLUMNS = [
    "canonical_entity_id",
    "alignment_unit_id",
    "mention_id",
    "canonical_label",
    "wikidata_id",
    "match_tier",
    "cluster_key",
    "is_representative",
]

STRATEGY_WIKIDATA_QID = "wikidata_qid_match"
STRATEGY_NORMALIZED_NAME = "normalized_name_match"
STRATEGY_SINGLETON = "singleton"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
