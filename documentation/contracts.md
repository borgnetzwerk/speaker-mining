# Data Contracts

This document describes current output contracts based on active notebooks and generated CSV headers.

## Canonical Contract Sources

1. `speakermining/src/process/mention_detection/config.py`
2. candidate-generation module functions in `speakermining/src/process/candidate_generation/*.py`
3. actual generated CSV headers in `data/*`

## Phase Output Locations

1. `data/10_mention_detection/`
2. `data/20_candidate_generation/`
3. `data/30_entity_disambiguation/`
4. `data/31_entity_deduplication/`
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

## Phase 3/4

These phases are present in workflow structure but no stable, repository-wide schema contract is documented yet from generated files in this repository state.

When Phase 3/4 schemas are finalized, extend this document and add explicit headers for each produced file.

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

1. `classes.csv`
2. `core_classes.csv`
3. `instances.csv`
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
16. `summary.json`

Legacy note:

1. `raw_queries/` is a legacy v2 artifact set kept only for archive/migration reference.

### Core schemas

1. `classes.csv`: `id`, `class_filename`, `label_en`, `label_de`, `description_en`, `description_de`, `alias_en`, `alias_de`, `path_to_core_class`, `subclass_of_core_class`, `discovered_count`, `expanded_count`
2. `core_classes.csv`: same columns as `classes.csv`
3. `instances.csv`: `qid`, `label`, `labels_de`, `labels_en`, `aliases`, `description`, `discovered_at`, `expanded_at`
4. `entities.json`: object keyed by QID with full entity payloads
5. `triples.csv`: `subject`, `predicate`, `object`, `discovered_at_utc`, `source_query_file`
6. `query_inventory.csv`: `query_hash`, `endpoint`, `normalized_query`, `status`, `first_seen`, `last_seen`, `count`
7. `fallback_stage_candidates.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`
8. `fallback_stage_eligible_for_expansion.csv`: `candidate_id`
9. `fallback_stage_ineligible.csv`: `candidate_id`
10. `graph_stage_resolved_targets.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`
11. `graph_stage_unresolved_targets.csv`: `mention_id`, `mention_type`, `mention_label`, `context`

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
