# Migration Evaluation Report

Date: 2026-03-31
Evaluator role: Migration evaluator
Authoritative baseline: documentation/Wikidata/2026-03-31_transition/migration_sequence.md plus Step 1-4 specs

## Findings (ordered by severity)

### Critical

1. Resume semantics can skip incomplete seeds after budget stop
- Requirement: deterministic resume with correct seed continuity and checkpoint semantics (migration_sequence.md, Step 2 checkpoint/resume contract, wikidata_future_V2.md resume semantics).
- Evidence:
	- `run_graph_expansion_stage` resumes from `seeds_completed` (`start_seed_index = max(0, int(latest.get("seeds_completed", 0) or 0))`) in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:454`.
	- `seeds_done` is incremented unconditionally after each `run_seed_expansion` call in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:466`.
	- `run_seed_expansion` can exit early with `per_seed_budget_exhausted` in the middle of a seed.
- Impact: a partially processed seed can be counted as completed and skipped on append resume.

2. Inlinks cursor is persisted but not used to resume paging continuity
- Requirement: deterministic resume including inlinks cursor state (migration_sequence.md, Step 2, Step 3 section on inlinks paging contract and resume behavior).
- Evidence:
	- cursor is written into manifest (`inlinks_cursor=last_cursor`) in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:492`.
	- expansion always starts with `offset = 0` in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:276`.
	- no code path reads checkpoint `inlinks_cursor` and re-enters paging at saved offset.
- Impact: Step 3 paging continuity and deterministic crash-resume are not fully implemented.

3. Neighbor cap contract is declared but not enforced
- Requirement: enforce per-node neighbor cap and stop precedence behavior (migration_sequence.md Step 2/Step 4, wikidata_future_V2.md stop conditions).
- Evidence:
	- `ExpansionConfig` defines `max_neighbors_per_node` in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:40`.
	- neighbor loop iterates all neighbors without cap in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:332`.
- Impact: violates bounded expansion contract and can inflate endpoint pressure.

### High

1. Node merge policy can downgrade expanded payload back to minimal claims
- Requirement: discovered/expanded merge semantics must preserve expanded data as authoritative (Step 2 node_store contract; wikidata_future_V2 node storage model).
- Evidence:
	- `upsert_discovered_item` uses `merged = {**current, **minimal}` in `speakermining/src/process/candidate_generation/wikidata/node_store.py:70`.
	- `minimal` stores only P31/P279 claims, so later rediscovery can overwrite richer expanded `claims` content.
- Impact: expanded payload can be lost over time, breaking source-of-truth expectations.

2. Checkpoint filename can collide within the same second
- Requirement: append-only checkpoints, never overwrite during run (wikidata_future_V2 checkpoint policy).
- Evidence:
	- filename is derived only from run_id and second-precision timestamp in `_manifest_filename` at `speakermining/src/process/candidate_generation/wikidata/checkpoint.py:27` and `:28`.
- Impact: two checkpoints created in same second can overwrite a manifest path, violating append-only guarantee.

3. Seed validation does not enforce "seed must be broadcasting program instance"
- Requirement: seed instance policy from production spec: only valid broadcasting program seed instances should be roots.
- Evidence:
	- loader validates only QID regex in `speakermining/src/process/candidate_generation/wikidata/bootstrap.py:11` and `:48`.
	- no class-instance check against broadcasting program type in bootstrap loading path.
- Impact: class/entity type mis-seeding remains possible if setup data is malformed.

### Medium

1. Class path BFS only uses local store and does not fetch missing parent classes
- Requirement: path resolution BFS to core classes with cycle protection (Step 1 and Step 2 class resolver intent).
- Evidence:
	- resolver BFS uses `get_entity_fn(node_qid) or {}` in `speakermining/src/process/candidate_generation/wikidata/class_resolver.py:69`.
	- materializer passes `get_item` from local node store only; no fetch fallback.
- Impact: path_to_core_class can remain blank when parents are not yet discovered locally.

2. Fallback search events are mapped to `materialization_support` source step
- Requirement: canonical source-step taxonomy should reflect process semantics (Step 3 schema contract).
- Evidence:
	- wbsearch event writes use `source_step="materialization_support"` in `speakermining/src/process/candidate_generation/wikidata/entity.py:308`, `:332`, `:346`.
- Impact: inventory/provenance semantics are less explicit for fallback matching calls.

3. Runtime bootstrap files are rewritten every stage run
- Requirement: deterministic orchestration with stable bootstrap references.
- Evidence:
	- `initialize_bootstrap_files(...)` is called unconditionally in `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:405`.
	- function overwrites `core_classes.csv` and `broadcasting_programs.csv` each invocation in `speakermining/src/process/candidate_generation/wikidata/bootstrap.py:84-86`.
- Impact: while deterministic, this can unexpectedly mutate runtime artifacts when replaying/reverting.

## What Is Compliant / Improved

1. Legacy prototype modules were removed and replaced with v2-oriented modules
- Removed: `bfs_expansion.py`, `aggregates.py`, `classes.py`, `targets.py`.
- Added: `schemas.py`, `bootstrap.py`, `event_log.py`, `node_store.py`, `triple_store.py`, `query_inventory.py`, `materializer.py`, `checkpoint.py`, `expansion_engine.py`, `candidate_targets.py`, `fallback_matcher.py`.

2. Stage separation (graph-first then fallback) is implemented in notebook orchestration
- Notebook now has explicit Stage A, unresolved handoff, Stage B, and fallback re-entry expansion flow in `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`.

3. Canonical v2 event envelope is implemented
- Event writer enforces event_version v2, endpoint/source_step/status enums, normalized query, hash, timestamp, payload in `speakermining/src/process/candidate_generation/wikidata/event_log.py`.

4. Query inventory dedup now keys on `query_hash + endpoint` and prefers successful events
- Implemented in `speakermining/src/process/candidate_generation/wikidata/query_inventory.py`.

5. Deterministic inlinks query ordering and paging parameters were introduced
- `ORDER BY ?source ?prop`, `LIMIT`, `OFFSET` in `speakermining/src/process/candidate_generation/wikidata/inlinks.py`.

6. `broadcasting_program.py` correctly adapts to setup schema using `label` fallback
- Seed loader now reads `label` before `name`.

## Changed-Since-Last-Commit Scope Reviewed

Primary implementation scope reviewed:
- `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`
- `speakermining/src/process/candidate_generation/broadcasting_program.py`
- All changed files under `speakermining/src/process/candidate_generation/wikidata/`
- Added tests under `speakermining/test/process/wikidata/`

Migration docs reviewed for contract alignment:
- `documentation/Wikidata/2026-03-31_transition/migration_sequence.md`
- `documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md`
- `documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md`
- `documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md`
- `documentation/Wikidata/2026-03-31_transition/step_4_separate_graph_expansion_from_candidate_matching.md`
- `documentation/Wikidata/2026-03-31_transition/wikidata_future_V2.md`
- `documentation/Wikidata/2026-03-31_transition/v2_only_policy.md`

## Test Evidence

Executed:
- `pytest speakermining/test/process/wikidata -q`

Result:
- 19 passed, 0 failed.

Interpretation:
- The added tests validate core scaffolding and selected contracts.
- Several migration-sequence-critical behaviors remain untested and currently non-compliant (resume cursor continuity, per-node cap enforcement, no-downgrade node merge).

## Recommended Remediation Order

1. Fix resume semantics first:
- track partial-seed state correctly,
- avoid incrementing completed seed count on mid-seed budget stop,
- resume same seed using checkpoint cursor.

2. Enforce `max_neighbors_per_node` deterministically before queueing neighbors.

3. Protect expanded payload from rediscovery downgrade in `node_store.upsert_discovered_item`.

4. Make checkpoint manifest naming collision-proof (subsecond or monotonic suffix).

5. Tighten seed instance validation to enforce broadcasting program instance policy.

## Overall Evaluation Verdict

Status: Partially compliant, not yet ready to be marked fully complete against the authoritative migration sequence.

Rationale:
- Architecture direction is correct and substantial migration work is present.
- Critical resume/paging and contract-enforcement gaps remain and must be addressed before treating the migration wave as complete.
