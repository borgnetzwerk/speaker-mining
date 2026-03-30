# Future Wikidata Workflow (Production Spec)

This document defines the new comprehensive graph workflow that starts from
seed broadcasting programs and discovers all relevant connected Wikidata data
under deterministic, cache-first, and policy-compliant controls.

## Scope and migration target

Current development happens in:

- data/20_candidate_generation/wikidata/new

Final target location (after rollout) is:

- data/20_candidate_generation/wikidata

After rollout, the old Wikidata structure is removed and replaced by the new
graph-oriented structure.

## Naming freeze

The canonical spelling is organizations.

All class and instance artifacts must use organizations (not organisations).

## Data model

JSON is the source of truth for rich payloads. CSV files are redundant overview
and indexing tables derived from JSON and raw query events.

### Core classes file

The core class index is loaded from data/00_setup/classes.csv and uses this
schema:

wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id

Seed broadcasting programs are loaded from data/00_setup/broadcasting_programs.csv.

### Required folder and file bootstrap

A run must be able to start from an empty data directory and create all
required folders and files automatically.

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

## Cache and query event policy

Query means cache-first lookup, then network only if entry is missing or stale.

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
properties (append safety, reconstructability, and flexible payload shape).

## Node types and relevance policy

### Discoverable nodes

Default: every found node is discoverable.

When a node is discovered, store basic context only:

- label (en, de)
- description (en, de)
- alias (en, de)
- instance of (P31)
- subclass of (P279)

For properties (PID), store:

- label (en, de)
- description (en, de)
- alias (en, de)
- instance of (P31)
- subproperty of (P1647)

### Expandable nodes

Expandable nodes are a subset of discovered nodes allowed to recurse into
neighbors.

Expansion on instance A means:

1. Fetch all properties beyond the basic context fields for A (outlinks of A).
2. Collect all newly discovered IDs from those outlinks.
3. Fetch all links that reference A (inlinks to A).
4. Collect all newly discovered IDs from those inlinks.
5. Evaluate discovered IDs against expansion predicates.

### Exportable nodes

Every discovered node is exportable.

Rule: always export everything fetched so known nodes are never queried again
without an explicit stale/override reason.

## Expansion predicates

### Edge families used during expansion

This workflow currently treats all properties as valid edges for discovery and
direct-link checks.

Edge family 1, outlinks:

- A --P*--> B, where A and B are item QIDs and P* is any property PID.

Edge family 2, inlinks:

- X --P*--> A, where A and X are item QIDs and P* is any property PID.

No property allowlist is enforced in this version. Property blacklisting may be
added later after empirical analysis.

### Direct link definition (unambiguous)

Two items A and B have a direct link if at least one claim exists where:

- subject = A and object = B, or
- subject = B and object = A,

with any property PID.

Property identity does not affect direct-link validity in this version.

### Expandable target rule

A node N is expandable if either condition holds:

1. N is one of the listed broadcasting program seeds, or
2. N has a direct link to at least one listed broadcasting program seed and N is
    instance of one of the core classes from data/00_setup/classes.csv.

Additional guard:

- inlinks to class nodes are discovered but never used for expansion recursion.

## Deterministic controls

The workflow must expose and enforce these controls:

- per_node_outlink_cap
- per_node_inlink_cap
- class_node_inlink_expansion_ban (true by default)
- per_seed_query_budget
- total_query_budget
- max_depth_by_node_type

Recommended depth policy:

- broadcasting_program: configurable, default 3
- episode/series/person/organization/topic/role: configurable, default 2
- class nodes: configurable, default 1
- properties: configurable, default 0 for expansion

### Canonical queue ordering

For reproducible reruns:

1. Seeds are enqueued in ascending canonical QID order.
2. For each expanded node, candidate neighbors are deduplicated and sorted by
    canonical QID before enqueue.
3. Queue mode is FIFO BFS.
4. Tie-breaking always uses canonical QID lexical order.

## Class and instance discovery policy

Class detection rule:

- If an entity has any P279 statement, treat it as class-capable and track as a
   class candidate.

Instance detection rule:

- If no P279 statements are present, treat as instance and classify via P31
   paths.

Path resolution:

- For discovered classes, run BFS over subclass relations to find shortest path
   to any core class.
- Persist the resolved path in class and instance overview rows.
- If no path is found, keep path blank.
- Use seen-set cycle protection during path BFS to avoid loops and duplicate
   branch exploration.

## End-to-end execution outline

### Step 1, graph setup

1. Load classes and broadcasting program seeds from data/00_setup.
2. Create missing folders/files for the full target schema.
3. Ensure core class rows are present in entities/class bootstrap outputs.
4. Backfill missing labels/descriptions/aliases from cached entity payloads.

### Step 2, seed expansion

1. Initialize BFS queue from all seed QIDs using canonical ordering.
2. Expand queue under budgets, node-type depth limits, and degree caps.
3. For each expansion, process outlinks and inlinks per rules above.
4. Store all discovery payloads and update class/instance/property tables.
5. Continue until queue empty or budget limit reached.

### Step 3, materialization

1. Rebuild CSV indices from JSON/event sources.
2. Rebuild triples.csv from persisted relationship events.
3. Update summary.json and query_inventory.csv.

## Notes for later iterations

- Property blacklists/allowlists are intentionally out of scope for this
   version.
- Candidate-generation export schema for downstream phases is intentionally not
   finalized yet and may iterate after graph-store stabilization.