# Future Wikidata Workflow (Production Spec)

This document defines the new comprehensive graph workflow that starts from seed
broadcasting programs and discovers relevant connected Wikidata data under
deterministic, cache-first, and policy-compliant controls.

## Scope and migration target

Current development path:

- data/20_candidate_generation/wikidata/new

Final target path after rollout:

- data/20_candidate_generation/wikidata

After rollout, the old Wikidata structure is removed and replaced by the new
graph-oriented structure.

## Normative vocabulary

- discovered node: a node ID (QID or PID) observed in fetched data and persisted
  with a discovery snapshot.
- expanded node: a discovered QID whose neighbors are actively fetched.
- seed instance: a QID from data/00_setup/broadcasting_programs.csv that is an
   instance of broadcasting program (Q11578774); only these seed instances are
   root expansion starts.
- exportable node: any discovered node included in persisted output artifacts.
- direct link: an item-to-item edge where A references B or B references A,
  regardless of property.
- class node: an entity with at least one P279 statement.
- stale cache entry: a cached record older than cache_max_age_days.

## Policy constraints

### Naming freeze

Canonical spelling is organizations.

All class and instance artifacts must use organizations (not organisations).

### Cache and query event policy

Query means cache-first lookup, then network only when cache is missing or
stale.

Raw query results are append-only event records, one file per remote reply.
Number of raw query files equals number of remote replies received.

Each raw record must include:

- endpoint
- normalized query text (or canonical request descriptor)
- query hash
- timestamp UTC
- source process step
- response payload

Long-term storage may move to an event-sourced database with equivalent
properties (append safety, reconstructability, flexible payload shape).

## Data model and artifacts

JSON is the source of truth for rich payloads. CSV files are redundant overview
and indexing tables derived from JSON and raw query events.

### Input sources

- data/00_setup/classes.csv
- data/00_setup/broadcasting_programs.csv

Seed loading rule:

- Only rows with a valid wikidata_id matching ^Q[1-9][0-9]*$ are seed instances.
- Rows with NONE, blanks, or non-QID placeholders are skipped and recorded in
   run diagnostics.
- Classes are never used as a seed.

Core classes schema:

wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id

### Bootstrap requirement

A run must be able to start from an empty target output path and create all
required folders and files automatically.

This does not apply to setup input files in data/00_setup.

Required folders:

- data/20_candidate_generation/wikidata/raw_queries
- data/20_candidate_generation/wikidata/classes
- data/20_candidate_generation/wikidata/instances
- data/20_candidate_generation/wikidata/properties

Required top-level files:

- data/20_candidate_generation/wikidata/classes.csv
- data/20_candidate_generation/wikidata/triples.csv
- data/20_candidate_generation/wikidata/summary.json
- data/20_candidate_generation/wikidata/query_inventory.csv

Required class overview pairs per core class filename:

- classes/<filename>.csv
- classes/<filename>.json
- instances/<filename>.csv
- instances/<filename>.json

Required properties pair:

- properties/properties.csv
- properties/properties.json

## Node storage model

### Discovered and stored nodes

Default: every found node is discovered and stored immediately.

When an entity node is discovered (but not yet expanded), store basic fields only:

- label (en, de)
- description (en, de)
- alias (en, de)
- instance of (P31)
- subclass of (P279)

When a property node is discovered (but not yet expanded), store basic fields:

- label (en, de)
- description (en, de)
- alias (en, de)
- instance of (P31)
- subproperty of (P1647)

All discovered nodes are persisted and never re-queried without an explicit stale override.

### Expanded nodes

Expanded nodes are discovered QIDs whose relationships have been recursively explored.

Expansion on item A means:

1. Fetch all properties for A beyond basic context (outlinks).
2. Collect newly discovered IDs from outlinks.
3. Fetch all links referencing A (inlinks).
4. Collect newly discovered IDs from inlinks.
5. Store the expanded payload (all fetched properties and relationships).
6. Evaluate discovered IDs against the expandable target rule.

Expanded nodes overwrite their discovered-only records with complete payloads.

## Expansion predicates and graph semantics

### Edge domain

Expansion graph edges are item-to-item only.

Item outlink edge:

- A --P*--> B, where A and B are QIDs and P* is any property PID.

Item inlink edge:

- X --P*--> A, where X and A are QIDs and P* is any property PID.

Literal/time/quantity/string values are persisted as node attributes, not queue
neighbors.

No property allowlist is enforced in this version. Property blacklisting may be
added later after empirical analysis.

### Direct link definition

Two items A and B have a direct link if at least one stored item-to-item edge
exists where:

- subject = A and object = B, or
- subject = B and object = A.

Property identity does not affect direct-link validity in this version.

### Expandable target rule

A node N is expandable if either condition holds:

1. N is one of the listed seed instances from
   data/00_setup/broadcasting_programs.csv.
2. N has a direct link to at least one listed seed instance and N is
   instance of one of the core classes in data/00_setup/classes.csv.

Additional guard:

- inlinks to class nodes are discovered and persisted, but never used for
  expansion recursion.

#### Expandability decision table

1. Class: expandable = no 
2. Seed node: expandable = yes.
3. Non-seed, no direct link to any seed: expandable = no.
4. Non-seed, direct link to seed, but P31 not in core classes: expandable = no.
5. Non-seed, direct link to seed, and P31 in core classes: expandable = yes.

### Canonical queue ordering

For reproducible reruns:

1. Seed instances (valid QIDs only) are enqueued in the exact order they appear
   in data/00_setup/broadcasting_programs.csv (not sorted by QID).
2. Each seed is expanded fully before the next seed is processed.
3. Per expanded node, candidate neighbors are deduplicated, canonicalized, sorted by QID,
   then enqueued.
4. Within each seed's expansion, queue discipline is FIFO BFS.
5. Tie-breaking uses lexical QID order.

### Stop conditions and precedence

If multiple stop conditions become true, apply this precedence order:

1. total_query_budget exhausted.
2. current seed per_seed_query_budget exhausted.
3. queue exhausted.
4. candidate neighbors pruned by per-node caps (continue if queue still non-empty).

Run summary should record both final stop reason and active limit counters.

## Class and instance discovery policy

Class detection:

- if entity has any P279 statement, treat as class-capable and track as class
  candidate.

Instance detection:

- if no P279 statements exist, treat as instance and classify via P31 paths.

Path resolution:

- for discovered classes, run BFS over subclass relations to shortest path to a
  core class.
- persist resolved path in class and instance overview rows.
- if no path is found, keep path blank.
- use seen-set cycle protection during path BFS.

## Materialization and dedup policy

Materialization rebuilds CSV views from persisted node and triple events.

Node table dedup:

- Dedup key: ID
- For nodes discovered multiple times: keep all timestamps, merge all observed fields.
- When a discovered node is later expanded, merge expansion payload fields into existing record.

Triple table dedup:

- Dedup key: (subject, predicate, object)
- Immutable facts keep first observed timestamp.

Query inventory dedup:

- Dedup key: query hash + endpoint
- Keep latest successful response and timestamp.

Materialization outputs:

- classes.csv and partition csv/json files (deduplicated node records per class)
- instances.csv and partition csv/json files (deduplicated node records per class)
- triples.csv (deduplicated relationship records)
- summary.json (run metadata)
- query_inventory.csv (query log)

## End-to-end execution outline

### Step 1: graph setup

1. Load classes and seed instances from data/00_setup.
2. Create missing folders/files for target schema.
3. Ensure core class rows exist in bootstrap outputs.
4. Backfill missing labels/descriptions/aliases from cache or query as needed.

### Step 2: seed expansion

For each broadcasting program in data/00_setup/broadcasting_programs.csv (in order):

1. If wikidata_id is not a valid QID, skip row and record skip reason.
2. Initialize BFS queue with the current seed instance QID.
3. Expand queue under budgets and degree caps.
4. For each expanded node, process outlinks and inlinks under edge-domain rules.
5. Discover and store new nodes (basic fields for discovered-only, full payload for expanded).
6. Persist triples (item-to-item relationships).
7. Continue until stop condition is reached (seed budget, total budget, or queue exhausted).
8. After seed is complete or budget limit is reached, proceed to materialization checkpoint.

### Step 3: materialization checkpoints

Materialization occurs at three trigger points:

**After each seed broadcasting program instance completes:**

1. Rebuild CSV indices from JSON/event sources.
2. Rebuild triples.csv from persisted relationship events.
3. Update summary.json with per-seed statistics and cumulative totals.
4. Update query_inventory.csv.
5. Output human-readable summary: nodes discovered, expanded, queries used, stop reason.

**When network query limit is hit:**

1. Perform same materialization as above.
2. Record stop reason (per_seed_budget or total_query_budget exhausted).
3. Output is ready for human review and decision to resume or stop.

**Final materialization (all seeds processed or run terminated):**

1. Perform same materialization as above.
2. Record final stop reason and complete run statistics.
3. Output includes total nodes by type, total triples, total queries, time elapsed.

## Checkpoint policy

Each materialization produces a timestamped checkpoint at the target output path
(data/20_candidate_generation/wikidata).

### Checkpoint safety rules

1. Each checkpoint is self-contained: all CSV files, JSON files, and raw query
   events are independently readable and reconstructable from that point forward.

2. Checkpoints are never deleted or overwritten during a run. If a run is resumed
   or restarted at the same output path, a new checkpoint is appended (new
   folder or suffix).

3. Partial checkpoints (incomplete after a crash) are marked with a `_incomplete`
   flag in the checkpoint manifest so they can be identified during recovery.

4. Checkpoint metadata includes:

   - run_id (UUID or timestamp-based identifier)
   - start_timestamp (UTC when this run started)
   - latest_checkpoint_timestamp (UTC of last materialized state)
   - stop_reason (one of: seed_complete, per_seed_budget_exhausted,
     total_query_budget_exhausted, user_interrupted, crash_recovery)
   - seeds_completed (count)
   - seeds_remaining (count)
   - total_nodes_discovered (count by type)
   - total_nodes_expanded (count by type)
   - total_queries (count)

### Resume and rollback semantics

On resume or restart after interruption:

1. Read latest checkpoint metadata.
2. If run_id and output path match: continue from last seed + 1.
3. If run_id differs or recovery mode is manual: create new run_id and decide
   whether to:
   - **Append**: continue from last completed seed
   - **Restart**: clear target path and start over
   - **Revert**: discard latest checkpoint and resume from second-to-last

4. Node cache (discovered records) is never invalidated between checkpoints in
   the same run_id. Expansion cache (expanded payloads) is similarly immutable.

5. Any query already recorded in query_inventory.csv is never re-issued; edges
   are synced from cache.

## Worked examples

### Example A: direct-link truth table

1. A -> B exists: direct link = true.
2. B -> A exists: direct link = true.
3. A <-> B both directions exist: direct link = true.
4. A -> literal only: direct link = false.
5. A -> B -> C exists, but no A -> C or C -> A: no direct AC link, only an indirect link over one hop: B

### Example B: reproducible neighbor ordering

Discovered neighbors before normalization: Q1499182, Q42, Q100, Q42.

After canonicalization, dedup, sort: Q42, Q100, Q1499182.

Queue receives neighbors exactly in that order.

### Example C: one seed expansion trace

1. Seed Q1499182 is dequeued and expanded.
2. Outlinks produce new nodes Q56418119 and Q56418136.
3. Inlinks produce QID set including Q56418119.
4. Combined candidate set is deduped and sorted.
5. Each candidate is checked against expandable target rule.
6. Eligible nodes are enqueued; ineligible nodes remain discovered-only.

## Notes for later iterations

- property blacklists/allowlists are intentionally out of scope for this
  version.
- final candidate-generation export schema for downstream phases is intentionally
  not fixed yet and may iterate after graph-store stabilization.