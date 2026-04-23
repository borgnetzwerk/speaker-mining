# Current Wikidata Workflow: Notebook 21

This document describes how the notebook [speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb](speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb) currently works.

## Purpose

The notebook orchestrates Phase 2 candidate generation against Wikidata:

1. Build mention targets from Phase 2 CSV outputs.
2. Expand a Wikidata graph from known seed entities (broadcasting programs).
3. Match discovered entity signatures against mention labels.
4. Persist all raw query records and rebuild aggregate CSV outputs.

The design is cache-first and append-only for raw query records, so reruns are idempotent and aggregate files are rebuildable.

## Notebook Flow

The notebook in [speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb](speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb) is structured in six operational steps.

### 1) Project setup

The notebook resolves the repository root by walking upward from the current working directory until both folders exist:

- data
- speakermining/src

Then it prepends speakermining/src to sys.path so process modules are importable inside the notebook kernel.

### 2) Runtime configuration

A config dictionary is defined in the notebook with operational limits:

- max_depth
- max_nodes
- max_queries_per_run
- max_neighbors_per_match
- query_timeout_seconds
- query_delay_seconds
- inlinks_limit
- cache_max_age_days

Important behavior:

- max_queries_per_run limits only real network calls.
- Cache hits do not consume this budget.
- query_delay_seconds applies between network requests for rate limiting.

### 3) Seed loading

Seeds are loaded via load_broadcasting_program_seeds from [speakermining/src/process/candidate_generation/broadcasting_program.py](speakermining/src/process/candidate_generation/broadcasting_program.py).

Source file:

- data/00_setup/broadcasting_programs.csv

Returned seed fields are:

- name
- wikidata_id
- wikibase_id
- fernsehserien_de_id

Only canonical Wikidata Q-IDs extracted from wikidata_id are used as BFS start nodes.

### 4) Mention target construction

Targets are built through build_targets_from_phase2_lookup in [speakermining/src/process/candidate_generation/wikidata/targets.py](speakermining/src/process/candidate_generation/wikidata/targets.py).

Input sources:

- data/20_candidate_generation/episodes.csv
- data/20_candidate_generation/broadcasting_programs.csv

Mapping policy in targets.py:

- sendungstitel -> episode
- season -> season
- publication_program_* -> organization
- guest_* -> person
- topic_* -> topic

Each target row has:

- mention_id (stable SHA1-based ID)
- mention_type
- mention_label
- context

Rows are deduplicated by (mention_type, mention_label, context).

### 5) BFS expansion and matching

The notebook calls run_bfs_expansion from [speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py](speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py).

Algorithm summary:

1. Initialize queue with seed Q-IDs at depth 0.
2. Pop nodes breadth-first while queue is not empty and max_nodes is not exceeded.
3. For each node, skip invalid/already-seen/too-deep nodes.
4. Fetch or reuse (cache-first):
	- entity payload
	- outlinks payload
	- inlinks payload
5. Update class observation cache for the entity.
6. Build text signatures and match them against normalized mention labels.
7. If matches are found:
	- write a candidate_match raw query record
	- enqueue neighbors (outlink Q-IDs + inlink source Q-IDs), capped by max_neighbors_per_match
8. On completion, rebuild aggregate outputs from raw query files.

Match-gated expansion:

- Neighbors are expanded only when the current entity produced at least one candidate match.
- This strongly reduces query volume and keeps expansion focused on productive graph regions.

Duplicate suppression:

- In-memory and persisted match index ([data/20_candidate_generation/wikidata/match_index.json](data/20_candidate_generation/wikidata/match_index.json)) is used to avoid re-emitting previously seen (mention_id, candidate_id) pairs across reruns.

### 6) Output review in notebook

The notebook reads data/20_candidate_generation/candidates.csv and prints:

- total candidate rows
- counts by mention_type
- tabular preview
- coverage metrics (mentions with at least one candidate)

## Matching Semantics

Entity-to-mention matching is exact after normalization (no fuzzy matching yet).

Normalization comes from [speakermining/src/process/candidate_generation/wikidata/common.py](speakermining/src/process/candidate_generation/wikidata/common.py):

- lowercase
- replace non-word chars with spaces
- collapse whitespace
- trim

Signatures scanned per entity in bfs_expansion.py include:

- all labels and aliases in the entity doc
- the entity Q-ID itself
- outlink linked_qids
- outlink property_ids
- inlink source_qid values
- inlink pid values

This means non-label identifiers (Q-IDs, P-IDs) can produce matches if the same normalized tokens appear in mention targets.

## Cache and Storage Model

Core cache behavior is implemented in [speakermining/src/process/candidate_generation/wikidata/cache.py](speakermining/src/process/candidate_generation/wikidata/cache.py) and [speakermining/src/process/candidate_generation/wikidata/entity.py](speakermining/src/process/candidate_generation/wikidata/entity.py).

### Raw query records

Every query result is written as a separate timestamped JSON record under:

- data/20_candidate_generation/wikidata/raw_queries

Filename schema:

- {timestamp}__{query_type}__{key}.json

Recorded query types include:

- entity
- inlinks
- outlinks
- candidate_match

### Cache retrieval

For entity/inlinks/outlinks, the latest matching raw record is reused when age <= cache_max_age_days. Otherwise, a fresh network request is made and persisted.

### Request budget and delay

Request control is process-local (begin_request_context / end_request_context):

- Hard stop when max_queries_per_run is reached (RuntimeError: Network query budget hit).
- Minimum inter-request delay via query_delay_seconds.
- Retry with exponential backoff for transient HTTP errors (429/500/502/503/504).

### User-Agent and contact policy

At import time, cache.py loads contact info from .contact-info.json using [speakermining/src/process/candidate_generation/wikidata/contact_loader.py](speakermining/src/process/candidate_generation/wikidata/contact_loader.py).

If the file is missing or invalid, initialization fails with an explicit error. This enforces Wikimedia contact disclosure in request headers.

## Aggregate Rebuild Step

After each BFS run, rebuild_aggregates_from_raw in [speakermining/src/process/candidate_generation/wikidata/aggregates.py](speakermining/src/process/candidate_generation/wikidata/aggregates.py) scans all raw JSON records and writes:

- data/20_candidate_generation/candidates.csv
- data/20_candidate_generation/wikidata/candidate_index.csv
- data/20_candidate_generation/wikidata/query_inventory.csv
- data/20_candidate_generation/wikidata/summary.json

candidate rows are deduplicated by (mention_id, candidate_id).

This makes aggregates disposable artifacts: they can always be recreated from raw query files.

## Class Tracking Side Output

During BFS, each processed entity is also passed to update_class_cache in [speakermining/src/process/candidate_generation/wikidata/classes.py](speakermining/src/process/candidate_generation/wikidata/classes.py).

It extracts P31/P279 class links, caches class entities, and updates:

- data/20_candidate_generation/wikidata/classes.csv
- data/20_candidate_generation/wikidata/class_observations.json

This is auxiliary metadata and does not directly affect candidate matching logic.

## Practical Interpretation

The notebook is an orchestration layer. The durable system behavior is defined in the process modules:

- notebook: parameterization and run order
- modules: cache-first data acquisition, BFS expansion, exact normalized matching, aggregate rebuild

In short, candidate generation currently works as a conservative, reproducible, graph-expansion matcher with strict API-budget controls and strong recoverability from raw query artifacts.
