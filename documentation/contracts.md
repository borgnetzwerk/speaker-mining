# Data Contracts

This document describes current output contracts based on active notebooks and generated CSV headers.

## Canonical Contract Sources

1. `speakermining/src/process/mention_detection/config.py`
2. candidate-generation module functions in `speakermining/src/process/candidate_generation/*.py`
3. actual generated CSV headers in `data/*`

## Phase Output Locations

1. `data/10_mention_detection/`
2. `data/20_candidate_generation/`
3. `data/31_entity_disambiguation/` (Phase 31: Step 311 automated, Step 312 manual)
4. `data/32_entity_deduplication/` (Phase 32: Step 321 automated, Step 322 manual)
5. `data/40_link_prediction/`

## Phase 1: Mention Detection (`data/10_mention_detection`)

### Primary outputs

1. `episodes.csv`
2. `publications.csv`
3. `seasons.csv`
4. `persons.csv`
5. `topics.csv`

### Duplicate reports

1. `duplicates_episodes.csv`
2. `duplicates_publications.csv`
3. `duplicates_seasons.csv`
4. `duplicates_persons.csv`
5. `duplicates_topics.csv`

### Core columns

1. `episodes.csv`: `episode_id`, `sendungstitel`, `publikation_id`, `publikationsdatum`, `dauer`, `archivnummer`, `prod_nr_beitrag`, `zeit_tc_start`, `zeit_tc_end`, `season`, `staffel`, `folge`, `folgennr`, `infos`
2. `publications.csv`: `publikation_id`, `episode_id`, `publication_index`, `date`, `time`, `duration`, `program`, `prod_nr_sendung`, `prod_nr_secondary`, `is_primary`, `raw_line`
3. `seasons.csv`: `season_id`, `season_label`, `start_time`, `end_time`, `episode_count`
4. `persons.csv`: `mention_id`, `episode_id`, `name`, `beschreibung`, `source_text`, `source_context`, `parsing_rule`, `confidence`, `confidence_note`
5. `topics.csv`: `mention_id`, `episode_id`, `topic`, `source_text`, `source_context`, `parsing_rule`, `confidence`, `confidence_note`

Note: `institutions.csv` is not currently produced by active Phase 1 workflow.

## Phase 2: Candidate Generation (`data/20_candidate_generation`)

### Current outputs

1. `classes.csv`
2. `properties.csv`
3. `broadcasting_programs.csv`
4. `seasons.csv`
5. `episodes.csv`
6. `person_duplicates_for_phase1_feedback.csv`
7. `candidates.csv`

### Core columns

1. `classes.csv`: `name`, `alias`, `wikibase_id`, `wikidata_id`
2. `properties.csv`: `name`, `wikibase_id`, `wikidata_id`, `data_type`
3. `broadcasting_programs.csv`: `name`, `wikibase_id`, `wikidata_id`, `fernsehserien_de_id`
4. `seasons.csv`: `season_id`, `season_label`, `start_time`, `end_time`, `episode_count`, `season_label_chunk1`, `season_label_chunk2`
5. `episodes.csv`: reduced episode keys plus `publication_*`, `guest_*`, and `topic_*` wide columns
6. `person_duplicates_for_phase1_feedback.csv`: `mention_id`, `episode_id`, `name`, `name_cleaned`, `beschreibung`, `kept_mention_id`, `kept_beschreibung`, `duplicate_reason`, `sendungstitel`, `season`
7. `candidates.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`

## Phase 2 Fernsehserien Runtime Contract (Stage-2)

Canonical target path:

1. `data/20_candidate_generation/fernsehserien_de/`

Required runtime artifacts:

1. `chunks/chunk_000001.jsonl`
2. `eventhandler.csv`
3. `cache/pages/*.html`
4. `projections/summary.json`
5. `checkpoints/checkpoint_timeline.jsonl`
6. `checkpoints/snapshots/` (unzipped snapshot directories and/or zipped snapshot archives)
7. `chunk_catalog.csv`
8. `eventstore_checksums.txt`

Required projection artifacts (`projections/`):

1. `program_pages.csv`
2. `episode_index_pages.csv`
3. `episode_urls.csv`
4. `episode_metadata_discovered.csv`
5. `episode_guests_discovered.csv`
6. `episode_broadcasts_discovered.csv`
7. `episode_metadata_normalized.csv`
8. `episode_guests_normalized.csv`
9. `episode_broadcasts_normalized.csv`

Required minimum event families:

1. lifecycle: `eventstore_opened`, `eventstore_closed`, `projection_checkpoint_written`
2. discovery: `program_root_discovered`, `episode_index_page_discovered`, `episode_url_discovered`
3. network: `network_request_skipped_cache_hit`, `network_request_performed`
4. extraction/normalization: `episode_description_discovered`, `episode_guest_discovered`, `episode_broadcast_discovered`, `episode_description_normalized`, `episode_guest_normalized`, `episode_broadcast_normalized`

Operational semantics:

1. `max_network_calls=0` is cache-only execution.
2. `max_network_calls>0` is bounded network execution.
3. `max_network_calls<0` is unlimited network execution.

## Phase 31: Entity Disambiguation (`data/31_entity_disambiguation`)

### Output location

`data/31_entity_disambiguation/aligned/`

### Core files

1. `aligned_persons.csv`
2. `aligned_episodes.csv`
3. `aligned_seasons.csv`
4. `aligned_broadcasting_programs.csv`
5. `aligned_topics.csv`
6. `aligned_roles.csv`
7. `aligned_organizations.csv`
8. `match_evidence.csv`
9. `source_schema_mapping.csv`
10. `run_summary.json`

### Shared columns (all aligned files)

`alignment_unit_id`, `wikidata_id`, `fernsehserien_de_id`, `mention_id`, `canonical_label`, `open_refine_name`, `entity_class`, `match_confidence`, `match_tier`, `match_strategy`, `evidence_summary`, `unresolved_reason_code`, `unresolved_reason_detail`, `inference_flag`, `inference_basis`, `notes`

Plus `label_wikidata`, `label_fernsehserien_de`, `label_zdf`, `description_wikidata`, `description_fernsehserien_de`, `description_zdf`, `alias_wikidata`, `alias_fernsehserien_de`, `alias_zdf`

### Match tiers

`exact` > `high` > `medium` > `unresolved`

## Phase 32: Entity Deduplication (`data/32_entity_deduplication`)

### Purpose

Clusters Phase 31 alignment units (one row per mention × entity) into canonical entities (one row per real-world person). Reduces 31,811 person alignment rows to a smaller set of deduplicated canonical entities.

### Output files

1. `dedup_persons.csv` — one row per canonical entity
2. `dedup_cluster_members.csv` — membership mapping (alignment_unit_id → canonical_entity_id)
3. `dedup_summary.json` — run statistics

### `dedup_persons.csv` columns

`canonical_entity_id`, `entity_class`, `cluster_size`, `cluster_strategy`, `cluster_confidence`, `wikidata_id`, `canonical_label`, `open_refine_name`, `cluster_key`, `evidence_summary`, `representative_alignment_unit_id`

### `dedup_cluster_members.csv` columns

`canonical_entity_id`, `alignment_unit_id`, `mention_id`, `canonical_label`, `wikidata_id`, `match_tier`, `cluster_key`, `is_representative`

### Cluster strategies

| Strategy | Confidence | Description |
|----------|-----------|-------------|
| `wikidata_qid_match` | high | Rows sharing the same non-empty `wikidata_id` |
| `normalized_name_match` | medium | Rows sharing the same `normalize_name_for_matching(canonical_label)` key |
| `singleton` | low | No cluster partner found |

### Normalization note

`normalize_name_for_matching` is applied symmetrically to all `canonical_label` values being compared (see TODO-016 and `documentation/normalization-policy.md` when written).

## Phase 40

Not yet implemented. Schema contract to be added when Phase 40 is designed.

## Phase 2 Wikidata Graph Store (Canonical v3 Contract)

This section describes the active canonical v3 contract for the graph-oriented
Wikidata store.

Canonical target path:

1. `data/20_candidate_generation/wikidata/`

### Naming convention

Canonical spelling is `organizations`.

### Required artifacts

Top-level runtime state:

1. `chunks/` (append-only JSONL eventstore chunks)
2. `eventhandler.csv` (per-handler progress checkpoints)
3. `chunk_catalog.csv` (derived chunk summary)
4. `eventstore_checksums.txt` (closed-chunk checksums)
5. `checkpoints/` (append-only checkpoint manifests)
6. `archive/` (checkpoint archive snapshots)
7. `projections/` (materialized deterministic artifacts)

Projection artifacts (`projections/`):

1. Tabular projections keep CSV compatibility files during the migration period and now also emit matching `.parquet` sidecars for internal/runtime use.

2. `classes.csv`
3. `core_classes.csv`
4. `instances.csv`
4. `entities.json` (lazy runtime sidecar; created on first write or snapshot restore)
5. `triples.csv`
6. `query_inventory.csv`
7. `fallback_stage_candidates.csv`
8. `fallback_stage_eligible_for_expansion.csv`
9. `fallback_stage_ineligible.csv`
10. `graph_stage_resolved_targets.csv`
11. `graph_stage_unresolved_targets.csv`
12. `properties.csv`
13. `properties.json` (lazy runtime sidecar; created on first write or snapshot restore)
14. `aliases_en.csv`
15. `aliases_de.csv`
16. `instances_leftovers.csv`
17. `instances_core_<core_filename>.json` (one file per configured core class; e.g. `instances_core_persons.json`)
18. `summary.json`
19. `summary_profiles/<run_profile>/summary_latest.json` (profile-isolated latest summary)
20. `relevancy.csv`
21. `relevancy_relation_contexts.csv`
22. `not_relevant_instance_core_<core_filename>.json` (one file per configured core class)

Legacy note:

1. `raw_queries/` is a legacy v2 artifact set kept only for archive/migration reference.

### Core schemas

Parquet sidecar policy note:

1. CSV is the canonical required tabular persistence format for runtime projections.
2. Parquet files are optional sidecars controlled by `WIKIDATA_WRITE_PARQUET`.
3. `WIKIDATA_WRITE_PARQUET=0|false|no|off` disables parquet sidecars and checkpoint parquet inclusion.
4. Any other value (or unset) keeps parquet sidecars enabled.

Summary profile isolation note:

1. `summary.json` is the operational baseline summary artifact.
2. Materialization always writes profile-isolated summaries under `projections/summary_profiles/<run_profile>/`.
3. `WIKIDATA_RUN_PROFILE` controls run profile classification (`operational`, `smoke`, `cache_only`; default `operational`).
4. Non-operational runs do not overwrite `summary.json` unless `WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE=1` is explicitly set.

1. `classes.csv`: `id`, `class_filename`, `label_en`, `label_de`, `description_en`, `description_de`, `alias_en`, `alias_de`, `path_to_core_class`, `subclass_of_core_class`, `discovered_count`, `expanded_count`
2. `core_classes.csv`: same columns as `classes.csv`
3. `instances.csv`: `id`, `class_id`, `class_filename`, `label_de`, `label_en`, `description_de`, `description_en`, `alias_de`, `alias_en`, `wikidata_claim_properties`, `wikidata_claim_property_count`, `wikidata_claim_statement_count`, `wikidata_property_counts_json`, `wikidata_p31_qids`, `wikidata_p279_qids`, `wikidata_p179_qids`, `wikidata_p106_qids`, `wikidata_p39_qids`, `wikidata_p921_qids`, `wikidata_p527_qids`, `wikidata_p361_qids`, `relevant`, `relevant_seed_source`, `relevance_first_assigned_at`, `relevance_last_updated_at`, `relevance_inherited_from_qid`, `relevance_inherited_via_property_qid`, `relevance_inherited_via_direction`, `path_to_core_class`, `subclass_of_core_class`, `discovered_at_utc`, `expanded_at_utc`
	- Parquet sidecar: `instances.parquet`
4. `entities.json`: object keyed by QID with full entity payloads
5. `properties.csv`: `id`, `label_de`, `label_en`, `description_de`, `description_en`, `alias_de`, `alias_en`
	- Parquet sidecar: `properties.parquet`
6. `aliases_en.csv`: `alias`, `qid`
	- Parquet sidecar: `aliases_en.parquet`
7. `aliases_de.csv`: `alias`, `qid`
	- Parquet sidecar: `aliases_de.parquet`
8. `triples.csv`: `subject`, `predicate`, `object`, `discovered_at_utc`, `source_query_file`
	- Parquet sidecar: `triples.parquet`
9. `query_inventory.csv`: `query_hash`, `endpoint`, `normalized_query`, `status`, `first_seen`, `last_seen`, `count`
	- Parquet sidecar: `query_inventory.parquet`
10. `fallback_stage_candidates.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`
11. `fallback_stage_eligible_for_expansion.csv`: `candidate_id`
12. `fallback_stage_ineligible.csv`: `candidate_id`
13. `graph_stage_resolved_targets.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`
14. `graph_stage_unresolved_targets.csv`: `mention_id`, `mention_type`, `mention_label`, `context`
15. `instances_leftovers.csv`: same columns as `instances.csv`; contains non-class rows with no resolved core-class mapping
	- Parquet sidecar: `instances_leftovers.parquet`
16. `relevancy.csv`: `qid`, `is_core_class_instance`, `relevant`, `relevant_seed_source`, `relevance_first_assigned_at`, `relevance_last_updated_at`, `relevance_inherited_from_qid`, `relevance_inherited_via_property_qid`, `relevance_inherited_via_direction`, `relevance_evidence_event_sequence`
17. `relevancy_relation_contexts.csv`: `subject_class_qid`, `subject_class_label`, `property_qid`, `property_label`, `object_class_qid`, `object_class_label`, `decision_last_updated_at`, `can_inherit`

Projection ownership note:

1. `query_inventory.csv` is handler-owned and materialized by `QueryInventoryHandler`.
2. `fallback_stage_candidates.csv` is handler-owned and materialized from `candidate_matched` events.
3. `relevancy.csv` is handler-owned and materialized from `relevance_assigned` events.
4. Runtime/materializer code must not dual-write projections that have a handler owner.

Per-core handoff note:

1. `instances_core_<core_filename>.json` is the handoff for future phases. It is a QID-keyed object whose values are the full entity payloads we have for that core class.
2. `instances_core_<core_filename>.csv` and `instances_core_<core_filename>.parquet` are deprecated legacy artifacts and must not be produced by Phase 20 materialization.
3. `not_relevant_instance_core_<core_filename>.json` contains core-class instances that are not relevant and therefore excluded from `instances_core_<core_filename>.json`.
4. Duplicate top-level class JSON outputs (for example `persons.json`, `episodes.json`, `organizations.json`, `series.json`, `topics.json`, `broadcasting_programs.json`) are deprecated and must not be produced by Phase 20 materialization.

Lazy sidecar note:

1. `entities.json`, `properties.json`, and `triple_events.json` are runtime sidecars that are created on first write or when a checkpoint snapshot restores them.
2. Bootstrap must not eagerly create empty copies of those sidecars.

Eventstore envelope requirements (JSONL chunks):

1. Required fields: `sequence_num`, `event_version`, `event_type`, `timestamp_utc`, `recorded_at`, `payload`
2. `event_version` must be `v3`
3. Chunk boundary events must be represented by `eventstore_opened` and `eventstore_closed`

Checkpoint snapshot retention policy:

1. Checkpoint snapshots are written under `checkpoints/snapshots/<checkpoint_stem>/`.
2. Each snapshot directory contains a copy of its manifest file (`checkpoint__...json`) so the manifest is preserved in the same lifecycle as the snapshot and included in any zip archive.
2. The 3 most recent snapshots remain unzipped directories.
3. When a new snapshot would increase unzipped snapshots above 3, the oldest unzipped snapshot is compressed into `checkpoints/snapshots/<checkpoint_stem>.zip`.
4. Zipped snapshots keep one protected "daily latest" snapshot per creation day with no hard cap.
5. Additional zipped snapshots (those that are not the protected daily latest) are capped to the 7 most recent; older ones are deleted.
6. Restore/revert must work from either an unzipped snapshot directory or a zipped snapshot archive.
7. Snapshot payload must include runtime projections, legacy raw query snapshot content, and eventstore artifacts (`chunks/`, `chunk_catalog.csv`, `eventstore_checksums.txt`).
8. Checkpoint creation history is append-only JSONL in `checkpoints/checkpoint_timeline.jsonl`.

### Runtime semantics

1. `chunks/` is the canonical append-only runtime event log.
2. Projections are deterministic handler outputs rebuilt from eventstore events.
3. Cache-hit and fallback-read telemetry do not create legacy v2 raw query files.
4. Seed filtering and materialization path resolution run cache-first without uncapped network fetches.
5. Runtime sidecars are allowed to be absent immediately after bootstrap; first write or restore creates them.
