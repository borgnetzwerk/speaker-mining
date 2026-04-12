from __future__ import annotations

from pathlib import Path


# ============================================================================
# Paths & Directories (Step 311 Event-Sourced Disambiguation)
# ============================================================================

# Resolve repository root from this file location so paths are stable
# regardless of notebook/terminal working directory.
REPO_ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = REPO_ROOT / "data"
INPUT_PHASE_DIR = DATA_DIR / "20_candidate_generation"
PHASE_DIR = DATA_DIR / "31_entity_disambiguation"
PROJECTIONS_DIR = PHASE_DIR / "projections"

# Event-sourcing infrastructure
EVENTS_DIR = PHASE_DIR / "events"
CHECKPOINTS_DIR = PHASE_DIR / "checkpoints"
HANDLER_PROGRESS_DB = PHASE_DIR / "handler_progress.db"

# Historical archive (for rollback / audit)
HISTORY_DIR = PHASE_DIR / "history"

# Input data paths
BROADCASTING_PROGRAMS_CSV = DATA_DIR / "00_setup" / "broadcasting_programs.csv"
CORE_CLASSES_CSV = DATA_DIR / "00_setup" / "core_classes.csv"

# Mention detection inputs (Layer 3: persons in episodes)
MENTION_DETECTION_DIR = DATA_DIR / "10_mention_detection"
EPISODES_CSV = MENTION_DETECTION_DIR / "episodes.csv"
PERSONS_CSV = MENTION_DETECTION_DIR / "persons.csv"
PUBLICATIONS_CSV = MENTION_DETECTION_DIR / "publications.csv"
SEASONS_CSV = MENTION_DETECTION_DIR / "seasons.csv"
TOPICS_CSV = MENTION_DETECTION_DIR / "topics.csv"

# Candidate generation inputs (Layer 2 episodes, Layer 3 persons)
WIKIDATA_PROJECTIONS_DIR = INPUT_PHASE_DIR / "wikidata" / "projections"
FERNSEHSERIEN_PROJECTIONS_DIR = INPUT_PHASE_DIR / "fernsehserien_de" / "projections"
CANDIDATE_EPISODES_CSV = INPUT_PHASE_DIR / "episodes.csv"

# Wikidata projection files (JSON-first policy for Phase 31)
WD_BROADCASTING_PROGRAMS = WIKIDATA_PROJECTIONS_DIR / "instances_core_broadcasting_programs.json"
WD_SERIES = WIKIDATA_PROJECTIONS_DIR / "instances_core_series.json"
WD_EPISODES = WIKIDATA_PROJECTIONS_DIR / "instances_core_episodes.json"
WD_PERSONS = WIKIDATA_PROJECTIONS_DIR / "instances_core_persons.json"
WD_TOPICS = WIKIDATA_PROJECTIONS_DIR / "instances_core_topics.json"
WD_ROLES = WIKIDATA_PROJECTIONS_DIR / "instances_core_roles.json"
WD_ORGANIZATIONS = WIKIDATA_PROJECTIONS_DIR / "instances_core_organizations.json"

# Fernsehserien.de projection files
FS_EPISODE_GUESTS = FERNSEHSERIEN_PROJECTIONS_DIR / "episode_guests_normalized.csv"
FS_EPISODE_METADATA = FERNSEHSERIEN_PROJECTIONS_DIR / "episode_metadata_normalized.csv"
FS_EPISODE_BROADCASTS = FERNSEHSERIEN_PROJECTIONS_DIR / "episode_broadcasts_normalized.csv"


# ============================================================================
# Core Class Definitions & Output Files
# ============================================================================

CORE_CLASSES = [
    "broadcasting_programs",
    "series",
    "episodes",
    "persons",
    "topics",
    "roles",
    "organizations",
]

def get_aligned_csv_path(core_class: str) -> Path:
    """Return path to aligned_{core_class}.csv output file."""
    return PROJECTIONS_DIR / f"aligned_{core_class}.csv"


# ============================================================================
# Baseline Column Contract (Section 3 of 313_disambiguation_artifact_contract_draft.md)
# ============================================================================
# Every aligned_*.csv must include these columns as minimum:

BASELINE_COLUMNS = [
    "alignment_unit_id",      # Unique identifier for this alignment row
    "core_class",             # e.g. "persons", "episodes"
    "broadcasting_program_key", # Reference to broadcasting program
    "episode_key",            # Reference to episode (None for layer 1)
    "source_zdf_value",       # Evidence from ZDF mention detection
    "source_wikidata_value",  # Evidence from Wikidata projection
    "source_fernsehserien_value", # Evidence from Fernsehserien.de projection
    "deterministic_alignment_status",  # "aligned", "unresolved", "conflict"
    "deterministic_alignment_score",   # 0.0 to 1.0 confidence
    "deterministic_alignment_method",  # e.g. "name_exact_multi_source"
    "deterministic_alignment_reason",  # Human-readable explanation
    "requires_human_review",   # Boolean: needs Step 312 review?
]

# Extended columns per core class (beyond baseline)
EVENT_METADATA_COLUMNS = [
    "source_entity_ids_json",   # JSON object of source-specific stable IDs
    "action_type",              # Action performed on the IDs
    "action_status",            # emitted|updated|skipped|failed
    "action_reason",            # Human-readable reason
    "wikidata_claim_properties",
    "wikidata_claim_property_count",
    "wikidata_claim_statement_count",
    "wikidata_property_counts_json",
    "wikidata_p31_qids",
    "wikidata_p179_qids",
    "wikidata_p106_qids",
    "wikidata_p39_qids",
    "wikidata_p921_qids",
    "wikidata_p527_qids",
    "wikidata_p361_qids",
]

PERSONS_EXTENDED_COLUMNS = [
    "mention_id",
    "person_name",
    "person_episode_publication_date",
    "person_episode_publication_time",
    "wikidata_id",
    "wikidata_label",
    "fernsehserien_url",
    "fernsehserien_label",
    "occupation_evidence",
    "affiliation_evidence",
    "matched_on_fields",
    "candidate_count",
    "evidence_sources",
] + EVENT_METADATA_COLUMNS

EPISODES_EXTENDED_COLUMNS = [
    "episode_id",
    "publication_date",
    "publication_time",
    "duration_seconds",
    "season_number",
    "episode_number",
    "matched_on_fields",
    "candidate_count",
    "evidence_sources",
] + EVENT_METADATA_COLUMNS

SERIES_EXTENDED_COLUMNS = [
    "series_id",
    "series_label",
    "matched_on_fields",
    "candidate_count",
    "evidence_sources",
] + EVENT_METADATA_COLUMNS

ROLES_EXTENDED_COLUMNS = [
    "role_id",
    "role_label",
    "confidence_role",
    "matched_on_fields",
    "evidence_sources",
] + EVENT_METADATA_COLUMNS

ORGANIZATIONS_EXTENDED_COLUMNS = [
    "org_id",
    "org_label",
    "confidence_org",
    "matched_on_fields",
    "evidence_sources",
] + EVENT_METADATA_COLUMNS

TOPICS_EXTENDED_COLUMNS = [
    "topic_id",
    "topic_label",
    "matched_on_fields",
    "evidence_sources",
] + EVENT_METADATA_COLUMNS

BROADCASTING_PROGRAMS_EXTENDED_COLUMNS = [
    "program_label",
    "matched_on_fields",
] + EVENT_METADATA_COLUMNS


# ============================================================================
# Event Schema (Append-Only Event Log)
# ============================================================================

EVENT_LOG_FIELDS = [
    "timestamp_utc",
    "event_id",
    "phase",
    "event_type",  # "alignment_attempt", "handler_checkpoint", etc.
    "core_class",
    "message",
    "alignment_unit_id",
    "alignment_result",  # JSON: the AlignmentResult
    "source_entity_ids",  # Stable IDs (mention_id, wikidata_qid, fs guest/url)
    "action",  # Action taken on IDs: type/status/reason
    "extra.source_import_id",  # Stable import fingerprint used for incremental ingest
    "handler_name",  # For projection handlers
    "last_processed_sequence",  # For resumable handlers
]


# ============================================================================
# Handler Progress Tracking
# ============================================================================

HANDLER_PROGRESS_FIELDS = [
    "handler_name",
    "last_processed_sequence",
    "artifact_path",
    "updated_at",
    "total_events_processed",
]


# ============================================================================
# Checkpoint Structure
# ============================================================================

CHECKPOINT_STRUCTURE = """
checkpoints/
  [timestamp]-checkpoint/
    events/
      chunk_001.jsonl
      chunk_002.jsonl
      ...
      chunk_catalog.csv  (schema: chunk_id, eventstore_path, chunk_size, checksum)
      eventstore_checksums.txt
    projections/
      aligned_*.csv (current state of projections)
    handler_progress.db
  [timestamp]-checkpoint.zip
"""

CHECKPOINT_RETENTION = {
    "unzipped_newest": 3,
    "daily_latest_zip": "one per day",
    "additional_zipped": 7,
}


# ============================================================================
# Legacy file names (kept for compatibility if needed)
# ============================================================================

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