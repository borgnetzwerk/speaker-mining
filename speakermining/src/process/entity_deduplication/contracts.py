from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data")
PHASE31_DIR = DATA_DIR / "31_entity_disambiguation"
PHASE32_DIR = DATA_DIR / "32_entity_deduplication"

ALIGNED_DIR = PHASE31_DIR / "aligned"

INPUT_FILES = {
    "aligned_persons": ALIGNED_DIR / "aligned_persons.csv",
    # Optional — present only after manual OpenRefine reconciliation is complete.
    # Phase 32 will use it as the highest-confidence tier when it exists.
    "reconciliation_csv": PHASE31_DIR / "reconciliation_export.csv",
}

RECONCILIATION_CSV_COLUMNS = [
    "alignment_unit_id",
    "wikibase_id",
    "wikidata_id",
    "fernsehserien_de_id",
    "mention_id",
    "canonical_label",
]

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

STRATEGY_MANUAL_RECONCILIATION = "manual_reconciliation"
STRATEGY_WIKIDATA_QID = "wikidata_qid_match"
STRATEGY_NORMALIZED_NAME = "normalized_name_match"
STRATEGY_SINGLETON = "singleton"

# Confidence levels in descending order: authoritative > high > medium > low
CONFIDENCE_AUTHORITATIVE = "authoritative"
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"
