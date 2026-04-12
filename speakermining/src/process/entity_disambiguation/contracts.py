from __future__ import annotations

from pathlib import Path

DATA_DIR = Path("data")
SETUP_DIR = DATA_DIR / "00_setup"
MENTION_DIR = DATA_DIR / "10_mention_detection"
CANDIDATE_DIR = DATA_DIR / "20_candidate_generation"
PHASE31_DIR = DATA_DIR / "31_entity_disambiguation"

RAW_IMPORT_DIR = PHASE31_DIR / "raw_import"
NORMALIZED_DIR = PHASE31_DIR / "normalized"
ALIGNED_DIR = PHASE31_DIR / "aligned"

RAW_EXAMPLES_DIR = RAW_IMPORT_DIR / "examples"
NORMALIZED_EXAMPLES_DIR = NORMALIZED_DIR / "examples"
SCHEMA_EXAMPLES_DIR = ALIGNED_DIR / "examples" / "schema_harmonization"
LAYERED_EXAMPLES_DIR = ALIGNED_DIR / "examples" / "layered_alignment"

INPUT_FILES = {
    "setup_broadcasting_programs": SETUP_DIR / "broadcasting_programs.csv",
    "zdf_episodes": MENTION_DIR / "episodes.csv",
    "zdf_persons": MENTION_DIR / "persons.csv",
    "zdf_publications": MENTION_DIR / "publications.csv",
    "zdf_topics": MENTION_DIR / "topics.csv",
    "zdf_seasons": MENTION_DIR / "seasons.csv",
    "wikidata_programs": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_broadcasting_programs.json",
    "wikidata_series": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_series.json",
    "wikidata_episodes": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_episodes.json",
    "wikidata_persons": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_persons.json",
    "wikidata_topics": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_topics.json",
    "wikidata_roles": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_roles.json",
    "wikidata_organizations": CANDIDATE_DIR / "wikidata" / "projections" / "instances_core_organizations.json",
    "wikidata_triples": CANDIDATE_DIR / "wikidata" / "projections" / "triples.csv",
    "wikidata_properties": CANDIDATE_DIR / "wikidata" / "projections" / "properties.csv",
    "wikidata_classes": CANDIDATE_DIR / "wikidata" / "projections" / "classes.csv",
    "wikidata_aliases_en": CANDIDATE_DIR / "wikidata" / "projections" / "aliases_en.csv",
    "wikidata_aliases_de": CANDIDATE_DIR / "wikidata" / "projections" / "aliases_de.csv",
    "fs_episode_metadata": CANDIDATE_DIR / "fernsehserien_de" / "projections" / "episode_metadata_normalized.csv",
    "fs_episode_broadcasts": CANDIDATE_DIR / "fernsehserien_de" / "projections" / "episode_broadcasts_normalized.csv",
    "fs_episode_guests": CANDIDATE_DIR / "fernsehserien_de" / "projections" / "episode_guests_normalized.csv",
}

SHARED_COLUMNS = [
    "alignment_unit_id",
    "wikidata_id",
    "fernsehserien_de_id",
    "mention_id",
    "canonical_label",
    "entity_class",
    "match_confidence",
    "match_tier",
    "match_strategy",
    "evidence_summary",
    "unresolved_reason_code",
    "unresolved_reason_detail",
    "inference_flag",
    "inference_basis",
    "notes",
]

BASIC_SUFFIX_COLUMNS = [
    "label_wikidata",
    "label_fernsehserien_de",
    "label_zdf",
    "description_wikidata",
    "description_fernsehserien_de",
    "description_zdf",
    "alias_wikidata",
    "alias_fernsehserien_de",
    "alias_zdf",
]

COMMON_BASE_COLUMNS = SHARED_COLUMNS + BASIC_SUFFIX_COLUMNS

OUTPUT_FILES = {
    "aligned_broadcasting_programs": ALIGNED_DIR / "aligned_broadcasting_programs.csv",
    "aligned_seasons": ALIGNED_DIR / "aligned_seasons.csv",
    "aligned_episodes": ALIGNED_DIR / "aligned_episodes.csv",
    "aligned_persons": ALIGNED_DIR / "aligned_persons.csv",
    "aligned_topics": ALIGNED_DIR / "aligned_topics.csv",
    "aligned_roles": ALIGNED_DIR / "aligned_roles.csv",
    "aligned_organizations": ALIGNED_DIR / "aligned_organizations.csv",
    "match_evidence": ALIGNED_DIR / "match_evidence.csv",
    "source_schema_mapping": ALIGNED_DIR / "source_schema_mapping.csv",
    "run_summary": ALIGNED_DIR / "run_summary.json",
}

REQUIRED_ALIGNED_FILES = [
    "aligned_broadcasting_programs",
    "aligned_seasons",
    "aligned_episodes",
    "aligned_persons",
    "aligned_topics",
    "aligned_roles",
    "aligned_organizations",
]

EXACT_TIER = "exact"
HIGH_TIER = "high"
MEDIUM_TIER = "medium"
UNRESOLVED_TIER = "unresolved"

UNRESOLVED_REASON_CODES = {
    "no_candidate",
    "low_confidence",
    "contradiction",
    "insufficient_context",
}
