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

## Phase 2 Wikidata Graph Store (Canonical v2 Contract)

This section describes the active canonical v2 contract for the graph-oriented
Wikidata store.

Canonical target path:

1. `data/20_candidate_generation/wikidata/`

### Naming convention

Canonical spelling is `organizations`.

### Required artifacts

Top-level:

1. `classes.csv`
2. `instances.csv`
3. `properties.csv`
4. `aliases_en.csv`
5. `aliases_de.csv`
6. `triples.csv`
7. `query_inventory.csv`
8. `summary.json`
9. `entities.json`
10. `properties.json`
11. `triple_events.json`
12. `core_classes.csv` (runtime snapshot from setup classes input)
13. `broadcasting_programs.csv` (runtime snapshot from setup seed input)
14. `graph_stage_resolved_targets.csv`
15. `graph_stage_unresolved_targets.csv`
16. `fallback_stage_candidates.csv`
17. `fallback_stage_eligible_for_expansion.csv`
18. `fallback_stage_ineligible.csv`
19. `raw_queries/` (append-only event files)
20. `checkpoints/` (append-only checkpoint manifests)
21. `archive/` (checkpoint archive snapshots)

### Core schemas

1. `classes.csv`: `id`, `label_en`, `label_de`, `description_en`, `description_de`, `alias_en`, `alias_de`, `path_to_core_class`, `subclass_of_core_class`, `discovered_count`, `expanded_count`
2. `instances.csv`: `id`, `class_id`, `class_filename`, `label_en`, `label_de`, `description_en`, `description_de`, `alias_en`, `alias_de`, `path_to_core_class`, `subclass_of_core_class`, `discovered_at_utc`, `expanded_at_utc`
3. `properties.csv`: `id`, `label_en`, `label_de`, `description_en`, `description_de`, `alias_en`, `alias_de`
4. `aliases_en.csv`: `alias`, `qid`
5. `aliases_de.csv`: `alias`, `qid`
6. `triples.csv`: `subject`, `predicate`, `object`, `discovered_at_utc`, `source_query_file`
7. `query_inventory.csv`: `endpoint`, `query_hash`, `normalized_query`, `key`, `status`, `timestamp_utc`, `source_step`
8. `graph_stage_resolved_targets.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`
9. `graph_stage_unresolved_targets.csv`: `mention_id`, `mention_type`, `mention_label`, `context`
10. `fallback_stage_candidates.csv`: `mention_id`, `mention_type`, `mention_label`, `candidate_id`, `candidate_label`, `source`, `context`
11. `fallback_stage_eligible_for_expansion.csv`: `candidate_id`
12. `fallback_stage_ineligible.csv`: `candidate_id`

JSON stores:

1. `entities.json`: top-level object with key `entities`
2. `properties.json`: top-level object with key `properties`
3. `triple_events.json`: list of triple-event records
4. `summary.json`: run summary object with current stage and row counters

JSON files are the richer source of truth; CSV files are overview/index outputs.

### Runtime semantics

1. Raw query events are canonical v2 envelopes with deterministic `query_hash` and `timestamp_utc` fields.
2. Raw event files are append-only and represent remote replies (plus explicit derived-local graph events).
3. Cache-hit and fallback-read telemetry do not create raw event files.
4. Seed filtering and materialization path resolution run cache-first without uncapped network fetches.
