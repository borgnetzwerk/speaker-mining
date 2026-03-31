# Migration Evaluation Report

Date: 2026-03-31
Evaluator role: Migration evaluator
Authoritative baseline: documentation/Wikidata/2026-03-31_transition/migration_sequence.md plus Step 1-4 specs

## Remediation Status Update

Status: All previously listed findings have been remediated in code and revalidated.

### Closed Findings

1. Resume semantics for partial seed stops (Closed)
- Fixed in `expansion_engine.py`:
  - `seeds_completed` now increments only when a seed fully completes.
  - append resume starts from the correct seed index and preserves partial-seed continuity.

2. Inlinks cursor paging continuity (Closed)
- Fixed in `expansion_engine.py`:
  - checkpoint `inlinks_cursor` is now consumed on resume.
  - inlinks paging resumes from the next deterministic page offset for the saved target node.

3. Neighbor cap enforcement (Closed)
- Fixed in `expansion_engine.py`:
  - `max_neighbors_per_node` is applied before neighbor fetch/enqueue.

4. Expanded payload downgrade on rediscovery (Closed)
- Fixed in `node_store.py`:
  - discovered upsert now preserves previously expanded payload fields as authoritative.

5. Checkpoint filename collision risk (Closed)
- Fixed in `checkpoint.py`:
  - manifest filename now includes a unique suffix to guarantee append-only writes.

6. Seed instance policy enforcement (Closed)
- Fixed in `expansion_engine.py`:
  - seeds are filtered against the broadcasting program core class via P31 instance validation.

7. Class-path resolution missing-parent limitation (Closed)
- Fixed in `materializer.py`:
  - class-path resolver now fetches missing parent class docs when absent from local node store.

8. Fallback search provenance source-step specificity (Closed)
- Fixed in `entity.py`, `cache.py`, and `schemas.py`:
  - fallback label search events now use explicit `fallback_search` source step.

9. Runtime bootstrap reference file rewrites (Closed)
- Fixed in `bootstrap.py`:
  - bootstrap runtime reference files are created once and no longer overwritten on each stage run.

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

7. Additional contract hardening completed in this remediation pass
- deterministic partial-seed resume accounting
- checkpoint filename uniqueness guarantees
- explicit fallback-search provenance taxonomy
- class-path parent fetch fallback in materialization

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
- 25 passed, 0 failed.

Interpretation:
- Regression coverage now includes the previously open findings: resume accounting, inlinks cursor continuation, checkpoint filename uniqueness, seed instance filtering, bootstrap file stability, and class-path parent fetch fallback.
- No remaining failing findings from the prior evaluation list.

## Overall Evaluation Verdict

Status: Findings remediated for the evaluated implementation scope.

Rationale:
- Previously reported contract gaps were implemented and verified with passing tests.
- Remaining publish gate work is documentation synchronization required by `migration_sequence.md`.
