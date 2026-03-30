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

## Phase 2 Wikidata Graph Store (Provisional New Contract)

This section describes the provisional contract for the new graph-oriented
Wikidata store.

Current development path:

1. `data/20_candidate_generation/wikidata/new/`

Final target path after rollout:

1. `data/20_candidate_generation/wikidata/`

After rollout, old Wikidata artifacts are replaced by the new structure.

### Naming convention

Canonical spelling is `organizations`.

### Provisional required artifacts

Top-level:

1. `classes.csv`
2. `triples.csv`
3. `summary.json`
4. `query_inventory.csv`
5. `raw_queries/` (append-only remote query events)

Class partitions (`<class_filename>` from setup classes):

1. `classes/<class_filename>.csv`
2. `classes/<class_filename>.json`
3. `instances/<class_filename>.csv`
4. `instances/<class_filename>.json`

Properties:

1. `properties/properties.csv`
2. `properties/properties.json`

### Provisional schemas

1. `classes.csv`: `wikibase_id`, `filename`, `label`, `description`, `alias`, `label_de`, `description_de`, `alias_de`, `wikidata_id`, `fernsehserien_de_id`
2. `triples.csv`: `subject`, `predicate`, `object`, `more_info_path`
3. `classes/<class_filename>.csv`: `ID`, `label`, `description`, `alias`, `label_de`, `description_de`, `alias_de`, `path`
4. `instances/<class_filename>.csv`: `ID`, `label`, `description`, `alias`, `label_de`, `description_de`, `alias_de`, `path`
5. `properties/properties.csv`: `ID`, `label`, `description`, `alias`, `label_de`, `description_de`, `alias_de`, `path`

JSON files are the richer source of truth; CSV files are overview/index outputs.

### Compatibility note

How the new graph store will feed final candidate-generation exports for
downstream phases is intentionally not fixed yet and remains an iterative design
step.
