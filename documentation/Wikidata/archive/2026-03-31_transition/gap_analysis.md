# Gap Analysis (new production spec vs. current implementation)

## Related files

### Documentation
* `documentation`
* `documentation/Wikidata`
* `documentation/Wikidata/wikidata_future_V2.md`
* `documentation/Wikidata.md`
* `documentation/contracts.md`
* `documentation/workflow.md`

* `documentation/Wikidata/wikidata_current.md`
* `documentation/Wikidata/wikidata_future_V1.md`

* `documentation/coding-principles.md`
* `documentation/open-tasks.md`
* `documentation/repository-overview.md`

* `documentation/README.md`

### Implementation
Map where behavior already complies versus where the new spec requires structural redesign.
* `speakermining/src/process/candidate_generation/wikidata`
* `speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py`
* `speakermining/src/process/candidate_generation/wikidata/cache.py`
* `speakermining/src/process/candidate_generation/wikidata/aggregates.py`
* `speakermining/src/process/candidate_generation/wikidata/classes.py`
* `speakermining/src/process/candidate_generation/wikidata/entity.py`
* `speakermining/src/process/candidate_generation/wikidata/targets.py`
* `speakermining/src/process/candidate_generation/broadcasting_program.py`

### Data
* `data/20_candidate_generation/wikidata/query_inventory.csv`
* `data/20_candidate_generation/wikidata/classes.csv`
* `data/20_candidate_generation/wikidata/summary.json`
* `data/20_candidate_generation/wikidata/raw_queries/20260326T145224278856Z__entity__Q1499182.json`

* `speakermining/src/process/candidate_generation/wikidata/common.py`

## Executive Verdict
The production spec is strong and internally coherent, but the current implementation is still a prototype of a different strategy: match-gated candidate discovery, not full graph-store materialization. The repository already has useful building blocks (cache-first requests, request pacing, raw event logging, aggregate rebuild), but it does not yet implement the core semantics and artifacts required by the new production workflow.

### Highest-Risk Gaps (Spec vs Current Behavior)
1. Expansion semantics are fundamentally different.
- Spec requires expansion eligibility as defined by the canonical contract in `documentation/Wikidata/expansion_and_discovery_rules.md` (historically documented in `wikidata_future_V2.md`).
- Current code expands neighbors only when a node produced mention matches, then enqueues discovered QIDs without enforcing the canonical eligibility contract: `bfs_expansion.py`.

2. Seed ordering rule is not implemented as specified.
- Spec says each seed must be expanded fully before the next seed: `wikidata_future_V2.md`.
- Current queue initializes all seeds at once, so BFS interleaves seed-level traversal by depth: `bfs_expansion.py`.

3. Required graph artifacts are not produced by current pipeline.
- Spec requires `triples.csv`, class and instance csv/json partitions, properties json/csv, and materialization from node/triple events: `wikidata_future_V2.md`.
- Current aggregate rebuild only regenerates candidates, candidate_index, query_inventory, summary: `aggregates.py`.

4. Query event schema does not meet spec/policy metadata requirements.
- Spec and policy require endpoint, normalized query/canonical descriptor, query hash, timestamp, source step: `wikidata_future_V2.md`, `Wikidata.md`.
- Current raw record stores query_type, key, requested_at_utc, source, payload only: `cache.py`, `20260326T145224278856Z__entity__Q1499182.json`.

5. Checkpointing/resume/rollback model is absent.
- Spec defines run_id, stop_reason taxonomy, incomplete checkpoint handling, resume semantics: `wikidata_future_V2.md`.
- Current summary is minimal and has no run-state continuity metadata: `summary.json`.

### Important Gaps
1. Bootstrap guarantees are incomplete.
- Spec requires creating multiple directories and required files on empty target path: `wikidata_future_V2.md`.
- Current directory bootstrap only ensures raw_queries exists: `cache.py`.

2. Class/instance path resolution to core classes is not implemented.
- Spec requires BFS shortest path to core classes with cycle protection and path persistence: `wikidata_future_V2.md`.
- Current class module tracks P31/P279 counts only and writes a flat classes.csv: `classes.py`.

3. Query inventory dedup semantics differ.
- Spec wants dedup by query hash + endpoint and latest successful response: `wikidata_future_V2.md`.
- Current query_inventory is append-derived per raw file row with no hash-based dedup: `aggregates.py`, `query_inventory.csv`.

4. Inlink retrieval strategy is not chunk-stable for very large result sets.
- Policy points toward deterministic chunking and checkpoints for large pulls: `Wikidata.md`.
- Current inlinks query is a single LIMIT N without ordering/cursor checkpoints: `inlinks.py`.

5. Seed loading has a schema mismatch against setup csv.
- Setup file uses label, not name: `broadcasting_programs.csv`.
- Loader reads/returns name; this can silently blank seed names in logs and diagnostics: `broadcasting_program.py`.

### What Is Already Strong and Reusable
1. Contact-policy enforcement and request identification are implemented robustly: `cache.py`, `contact_loader.py`.
2. Cache-first with age threshold and fallback behavior is in place: `entity.py`.
3. Request pacing and retry backoff exist and are policy-aligned: `cache.py`.
4. Atomic writes and rebuild-from-raw mindset are already present: `cache.py`, `aggregates.py`.

### Architectural Tension in Goal Statement
You currently optimize for candidate discovery under strict API budget, while the new spec optimizes for complete graph capture around seeds with controlled expansion predicates. These are compatible only if candidate matching becomes downstream of graph materialization, not the gate for graph traversal. Right now matching is the gate: `bfs_expansion.py`, `21_candidate_generation_wikidata.ipynb`.

### Current Repository State vs Migration Target
1. Dual-structure state exists.
- Old/current outputs under `data/20_candidate_generation/wikidata` and partial new graph outputs under `data/20_candidate_generation/wikidata/new` both exist.
- This matches a transition phase but violates the final state expectation that old structure is replaced: `wikidata_future_V2.md`.

2. New folder appears incomplete relative to spec.
- Some expected json partition files are missing in current tree (for example many classes and instances json pairs), while spec requires full csv/json pairs per core class.