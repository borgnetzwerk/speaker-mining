# Node Integrity Pass: Code-Level Analysis And Bottleneck Map

## Purpose
The node integrity pass is a post Stage-A repair and expansion step inside Notebook 21. It has two goals:

1. Repair discovery completeness for known nodes (minimal payload and local outlinks).
2. Expand nodes that are eligible but still not expanded, before fallback matching.

The implementation lives primarily in:

- speakermining/src/process/candidate_generation/wikidata/node_integrity.py
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
- speakermining/src/process/candidate_generation/wikidata/triple_store.py
- speakermining/src/process/candidate_generation/wikidata/node_store.py
- speakermining/src/process/candidate_generation/wikidata/cache.py


## End-To-End Flow

### 1) Resolve runtime seed/core classes
Function: _resolve_runtime_seed_and_core_classes

- Uses explicit input when passed from notebook.
- Falls back to setup files when omitted.
- Core classes are normalized through effective_core_class_qids.

### 2) Build known QID universe
Function: _known_qids

- Starts from seed + core classes.
- Adds every node from iter_items (entities store).
- Adds subject/object from iter_unique_triples (deduped edge projection over triples events).

Implication:
- Known universe size is sensitive to historical event volume, not only current frontier.

### 3) Discovery repair loop
Function: run_node_integrity_pass, discovery section

Data structure:
- BFS queue over known_qids, with additional class frontier expansion from P31/P279.

For each qid:
- get_item from node store.
- _has_minimal_discovery_payload check.
- If incomplete: get_or_fetch_entity then upsert_discovered_item then _record_outlinks_for_node.
- Add newly seen class nodes from P31/P279 to queue.

Network governance:
- Wrapped in begin_request_context / end_request_context.
- Budget and pacing controlled by discovery_query_budget, query_delay_seconds.

### 4) Eligibility detection for unexpanded nodes
Function: run_node_integrity_pass, eligibility section

Canonical rule reference:

- Eligibility semantics come from `documentation/Wikidata/expansion_and_discovery_rules.md`.
- This section documents how the pass implements that contract.

For each item in iter_items:
- Skip non-QIDs and already expanded items.
- Evaluate is_expandable_target using:
	- Seed membership.
	- has_direct_link_to_seed equivalent via precomputed set from _qids_directly_linked_to_seeds.
	- p31_core_match with subclass traversal via _p31_core_match_with_subclass_resolution.
	- Class-node exclusion.

Important recent optimization already present:
- Direct seed link is now precomputed in one triple scan, avoiding repeated full scans per candidate.

### 5) Expansion of eligible unexpanded nodes
Function: run_node_integrity_pass, expansion section

Config used for per-node expansion:
- max_depth=0
- max_nodes=1
- inlinks_limit from notebook config
- per-node budget via per_node_expansion_query_budget

Loop behavior:
- For each eligible qid, call run_seed_expansion with seed={wikidata_id: qid}.
- Aggregate returned network_queries and expanded_qids.
- Periodically flush node/triple stores (currently every 100 qids), final flush in finally.

### 6) Final materialization
Function: materialize_final

- Flushes stores.
- Rebuilds projections (instances/classes/properties/aliases/triples/query_inventory).
- Writes CSV + summary artifacts.


## Internals Of run_seed_expansion Relevant To Performance

Inside expansion_engine.run_seed_expansion:

1. For current qid, fetch entity, upsert discovered + expanded.
2. Build outlinks from entity and write edges.
3. For each property in outlinks, fetch property payload.
4. Pull inlinks pages in a while loop until page size < inlinks_limit.
5. For each inlink row, append edge events.
6. For each neighbor (capped), fetch neighbor entity, upsert, derive outlinks/class chain.
7. Evaluate each neighbor with is_expandable_target for queueing.

With max_depth=0 and max_nodes=1, the queue does not recurse deeply, but steps 1-6 still execute for each seed qid, including inlinks paging.


## Why The Current Run Is Still Slow

Observed runtime pattern from notebook output:

- ~1219 eligible unexpanded qids.
- Expansion progresses slowly even after write-batching fix.
- Some seeds consume dozens of calls (example: 53 calls for one qid).

This indicates the dominant cost shifted from local JSON serialization to network-bound expansion work.

### Bottleneck A: High query volume per integrity-expanded node
Root cause:

- Node integrity uses full run_seed_expansion semantics per eligible qid.
- Even with depth=0/max_nodes=1, each qid can still trigger:
	- entity fetch
	- one or more inlinks page fetches
	- many neighbor entity fetches
	- property fetches

Effect:
- Total calls can grow to thousands for a 1000+ qid eligible set.
- query_delay_seconds amplifies wall-clock linearly.

### Bottleneck B: Inlinks pagination can dominate per qid
Root cause:

- get_or_fetch_inlinks loop continues until a short page arrives.
- High-degree nodes can require many pages (offset stepping by inlinks_limit).

Effect:
- Long-tail nodes produce large call spikes (as seen in heartbeat examples).

### Bottleneck C: Re-evaluating subclass chains repeatedly during eligibility pass
Root cause:

- _p31_core_match_with_subclass_resolution calls resolve_class_path per item.
- resolve_class_path traverses P279 ancestors via get_item repeatedly.
- No memoized class ancestry verdict cache at pass scope.

Effect:
- CPU overhead increases with item count and class graph density.
- Less dominant than network, but still material for large stores.

### Bottleneck D: Large in-memory triples events list growth
Root cause:

- triple_store keeps events list in memory and appends continuously.
- flush_triple_events serializes whole list when dirty.
- Batching improved write frequency, but each flush still serializes full payload.

Effect:
- For very large event logs, periodic flushes remain expensive and memory-heavy.

### Bottleneck E: Integrity and Stage A share expensive expansion logic
Root cause:

- Integrity currently calls generic run_seed_expansion designed for graph expansion richness, not minimal repair pass.

Effect:
- Integrity pass does more than minimally required to unblock downstream stages.


## What Was Already Mended

1. Direct-seed-link eligibility check optimized from repeated triple scans to one precomputed set.
2. Per-seed persistence flush disabled during node integrity expansion calls.
3. Periodic + final flush strategy added in node integrity expansion.
4. Split-aware setup semantics introduced:
	- `data/00_setup/core_classes.csv` is now authoritative for expansion-qualifying core classes.
	- `data/00_setup/root_class.csv` is now tracked separately as root taxonomy context.
	- `data/00_setup/other_interesting_classes.csv` is tracked separately for analysis-only classes.
5. New persistent projection `class_hierarchy.csv` added under `data/20_candidate_generation/wikidata/projections`.
6. Node integrity eligibility now uses projection-backed + pass-local memoized subclass resolution.

These fixes removed two algorithmic and one I/O hotspot, but they do not reduce network work volume itself.


## Implemented Projection Infrastructure (2026-04-07)

### New persistent asset: class hierarchy projection
Materialization now writes:

- `data/20_candidate_generation/wikidata/projections/class_hierarchy.csv`

Columns:

- `class_id`
- `class_filename`
- `path_to_core_class`
- `subclass_of_core_class`
- `is_core_class`
- `is_root_class`
- `parent_count`
- `parent_qids`

How it helps:

- Captures class lineage decisions as replayable projection state.
- Enables future passes to reuse prior lineage outcomes instead of recomputing every class walk.

### Node integrity uses projected lineage decisions
Eligibility step now:

1. Loads projected `class_hierarchy.csv` decisions (`class_id -> subclass_of_core_class`).
2. Reuses them before performing any fresh subclass traversal.
3. Caches uncached results in a pass-local memo for remaining classes.

This directly addresses repeated subclass-resolution work across items and across runs.


## Recommended Mends For The Current Bottleneck

## Priority 1: Add a lightweight integrity expansion mode
Goal:
- Keep integrity semantics but drastically reduce queries per eligible qid.

Approach:
- Add a specialized function (example name: run_integrity_seed_touch) instead of calling run_seed_expansion.
- For each qid:
	- Ensure entity is present and minimal.
	- Materialize local outlinks from entity payload.
	- Skip inlinks pagination by default.
	- Skip neighbor candidate fetch/enqueue.
	- Mark expanded_at_utc only when minimum integrity contract is satisfied.

Expected impact:
- Largest runtime reduction.
- Converts per-qid work from graph expansion to minimal integrity completion.

Risk:
- Must align definition of expanded_at_utc with downstream assumptions.


## Priority 2: Cap or disable inlinks during integrity expansion
Goal:
- Control long-tail high-degree nodes.

Approach options:

1. Add NodeIntegrityConfig.inlinks_pages_cap (for example 0, 1, 2).
2. Add NodeIntegrityConfig.include_inlinks_during_expansion (bool).
3. In run_seed_expansion call path, pass mode flag that bypasses inlinks loop.

Expected impact:
- Strong reduction in high-variance node runtimes.
- More predictable total runtime.

Risk:
- Reduced graph completeness in this specific pass; usually acceptable for integrity-focused runs.


## Priority 3: Add subclass resolution memoization
Goal:
- Remove repeated class ancestry traversal cost in eligibility screening.

Approach:
- Add pass-local cache:
	- class_subclass_of_core_cache: dict[qid, bool]
	- optional class_doc_cache: dict[qid, dict]
- Cache outcomes for class_qid checks within _p31_core_match_with_subclass_resolution.

Expected impact:
- Medium CPU savings in large item stores.

Risk:
- Low; deterministic cache keyed by class qid and core class set.


## Priority 4: Move triples events to append-only JSONL
Goal:
- Avoid full-file JSON reserialization cost.

Approach:
- Write new edge events as line-delimited records.
- Build dedup/triples projection from JSONL on materialization.
- Keep existing JSON format for backward compatibility via one-time migration or dual-read adapter.

Expected impact:
- Significant reduction in flush overhead and memory pressure.

Risk:
- Medium implementation complexity and migration handling.


## Priority 5: Add coarse-grained integrity run controls in notebook config
Goal:
- Provide operational guard rails for long runs.

Suggested knobs:

- max_nodes_to_expand set to bounded incremental values (example 100-300).
- dedicated integrity_query_budget independent from Stage A budget.
- integrity_skip_previously_attempted_qids from prior run logs.

Expected impact:
- Better operator control and faster iterative runs.

Risk:
- Low; mostly orchestration-level change.


## Suggested Immediate Implementation Order

1. Implement lightweight integrity expansion mode and route Step 6.5 to it.
2. Add explicit inlinks disable/cap for integrity path.
3. Add subclass memoization in eligibility screening.
4. If still needed, migrate triple events persistence to JSONL.


## Validation Plan After Mends

Metrics to capture per run:

- eligible_unexpanded_qids count
- network_queries_expansion total
- p50/p95 queries per expanded qid
- wall-clock for Step 6.5
- flush time split (node store vs triple store)

Success criteria:

- At least 3x reduction in Step 6.5 wall-clock on same dataset.
- Eliminate large per-qid spikes from inlinks-heavy nodes.
- No regression in downstream fallback and final materialization outputs.


## Key Takeaway
Current slow behavior is no longer dominated by local serialization. The dominant bottleneck is that node integrity still executes near-full graph expansion semantics for each eligible qid. The highest-value fix is to introduce a dedicated minimal integrity expansion path with explicit inlinks controls.
