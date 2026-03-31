# Migration Evaluation Report

Date: 2026-03-31  
Evaluator role: Migration evaluator (Step-contract compliance review)

## Scope and Method

Authoritative contract baseline:
- documentation/Wikidata/2026-03-31_transition/migration_sequence.md
- documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md
- documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md
- documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md
- documentation/Wikidata/2026-03-31_transition/step_4_separate_graph_expansion_from_candidate_matching.md

Implementation and changed-file review scope:
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
- speakermining/src/process/candidate_generation/broadcasting_program.py
- speakermining/src/process/candidate_generation/wikidata/*
- speakermining/test/process/wikidata/*

Validation executed:
- pytest speakermining/test/process/wikidata -q
- Result: 7 passed

## Executive Verdict

The migration is partially implemented and currently not compliant with the authoritative migration sequence as a gated rollout.

What is complete or strongly progressed:
- Canonical v2 event envelope infrastructure exists (event_log, query hashing, normalized query descriptors).
- Consolidated stores and projections exist in first usable form (entities.json, properties.json, triples.csv, query inventory, aliases CSVs).
- Bootstrap/checkpoint/materializer skeletons were introduced.
- Seed label/name schema mismatch fix in broadcasting program seed loader was implemented.

What blocks acceptance:
- Graph expansion semantics are still match-gated via legacy BFS behavior and therefore violate the Step 4 graph-first contract.
- Two-stage orchestration (Stage A -> unresolved handoff -> Stage B fallback -> eligibility re-entry) is not implemented in notebook flow.
- Core expandability decision contract (direct-link + core-class) is not enforced in runtime expansion.
- Inlinks paging cursor/resume contract is only partially represented in signatures but not implemented end-to-end.
- Mandatory test gate and documentation gate are incomplete relative to migration_sequence.md.

## Findings (Ordered by Severity)

### Critical 1: Expansion remains literal/match-gated instead of graph-authoritative

Contract violated:
- step_4_separate_graph_expansion_from_candidate_matching.md (Stage A must be independent of literal matching)
- step_2_implementation_blueprint.md (expansion_engine must enforce graph semantics)

Evidence:
- speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py
	- Neighbor enqueueing happens only inside `if candidate_rows:` block.
	- Inline comment explicitly states: "Match-driven recursion: expand neighbors only if current node produced candidates".
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
	- `run_graph_expansion_stage` delegates to `run_bfs_expansion` per seed, inheriting match-gated recursion.

Impact:
- Graph coverage is biased by text matches and no longer represents authoritative graph-first discovery.
- Stage separation promise is not fulfilled.

### Critical 2: Expandability rule (direct-link + core class) is not enforced

Contract violated:
- step_4_separate_graph_expansion_from_candidate_matching.md (explicit decision rules)
- step_2_implementation_blueprint.md (`is_expandable_target` decision table semantics)

Evidence:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
	- `core_class_qids` is accepted but not used in `run_graph_expansion_stage`.
	- `is_expandable_target` exists but is never invoked by runtime queueing path.
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
	- Graph expansion call passes `core_class_qids=set()`.

Impact:
- Expansion can include/exclude nodes for the wrong reasons.
- Step 4 core predicate contract is functionally bypassed.

### Critical 3: Stage B fallback and re-entry expansion are not operational

Contract violated:
- step_4_separate_graph_expansion_from_candidate_matching.md sections 4, 5, 7, 8, 9

Evidence:
- speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py
	- `run_fallback_string_matching_stage` returns deterministic empty outputs (stub behavior).
	- `enqueue_eligible_fallback_qids` returns metadata only and performs no expansion.
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
	- No Stage B cell sequence exists.
	- No unresolved handoff, class-scope hints, fallback run, or eligibility re-check cells are present.

Impact:
- Two-stage architecture is not implemented despite renamed Stage A markdown/title language.

### Critical 4: Inlinks paging + checkpoint cursor resume contract not implemented

Contract violated:
- step_3_canonical_event_schema.md section 7 (paging and cursor schema)
- step_2_implementation_blueprint.md (checkpoint and inlinks paging acceptance criteria)

Evidence:
- speakermining/src/process/candidate_generation/wikidata/entity.py
	- Inlinks call is hardwired to `offset=0` and one page.
- speakermining/src/process/candidate_generation/wikidata/checkpoint.py
	- Dataclass supports `inlinks_cursor`, but no runtime paging loop persists cursor progression.
- speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py
	- Manifest always writes `inlinks_cursor=None`.

Impact:
- Large inlinks result sets cannot be resumed deterministically per contract.
- Crash recovery at page boundary is not available.

### Critical 5: Migration gates in migration_sequence are not satisfied

Contract violated:
- migration_sequence.md (testing gate and documentation gate required in same change set)

Evidence:
- Tests present are only:
	- test_bootstrap_outputs.py
	- test_checkpoint_resume.py
	- test_event_schema.py
	- test_inlinks_paging.py
	- test_query_inventory.py
- Missing major contract test families from Step 2/4 blueprint:
	- expansion predicates, queue ordering, stop conditions, class resolution, triple dedup, materialization outputs breadth, end-to-end determinism, Stage A/B separation tests.
- Documentation synchronization files listed in migration_sequence.md were not updated in this change wave:
	- documentation/workflow.md
	- documentation/contracts.md
	- documentation/repository-overview.md
	- documentation/open-tasks.md
	- documentation/findings.md

Impact:
- Rollout cannot be considered publish-ready under the defined migration gates.

### High 1: `run_graph_expansion_stage` result contract is structurally present but functionally empty

Contract violated:
- step_4_separate_graph_expansion_from_candidate_matching.md (GraphExpansionResult as actual stage output)

Evidence:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
	- `discovered_candidates`, `resolved_target_ids`, `newly_discovered_qids`, `expanded_qids` are initialized and returned without population.
	- `unresolved_targets` is effectively all targets.

Impact:
- Handoff semantics are declared but not produced.

### High 2: Class resolution module contract is missing; materialization placeholders remain

Contract violated:
- step_2_implementation_blueprint.md section 4.8 (class_resolver.py)
- step_1_graph_artifacts_design.md (path_to_core_class/subclass_of_core_class visibility)

Evidence:
- No class_resolver.py module exists in speakermining/src/process/candidate_generation/wikidata.
- speakermining/src/process/candidate_generation/wikidata/materializer.py
	- `class_filename` and `path_to_core_class` remain blank.
	- `subclass_of_core_class` defaults to False.
	- Class grouping uses joined P31 text in `class_id`, not resolved nearest-core semantics.

Impact:
- Class/instance outputs are incomplete for downstream graph policy reasoning.

### High 3: Checkpoint semantics are only partially implemented and not deterministic across full run state

Contract violated:
- step_2_implementation_blueprint.md section 4.12
- wikidata_future_V2.md checkpoint and resume semantics

Evidence:
- speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py
	- `run_id` regenerated per invocation.
	- `seeds_completed` fixed at 0.
	- `seeds_remaining` set from total seed count, not actual progression.
	- stop reason collapses to queue_exhausted or total budget only.
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
	- Per-seed loop repeatedly calls run_bfs_expansion with fresh context; no shared global run-level checkpoint progression.

Impact:
- Resume/apply/revert behaviors are not implementable as specified at orchestration level.

### High 4: Potential append-only violation via filename collision risk in event log

Contract risk:
- step_3_canonical_event_schema.md append-only event policy

Evidence:
- speakermining/src/process/candidate_generation/wikidata/event_log.py
	- filename built from second-resolution timestamp + source_step + key.
	- multiple same-key events in same second can collide and overwrite.

Impact:
- One-file-per-event integrity may be violated under burst traffic.

### Medium 1: Legacy archive-and-remove migration procedure not implemented

Contract violated:
- step_3_canonical_event_schema.md section 8

Evidence:
- No utility or migration code found for legacy raw event archive manifests, external backup handoff markers, or cleanup workflow.

Impact:
- Existing non-v2 raw files are ignored by readers, but migration lifecycle procedure remains incomplete.

### Medium 2: Old prototype artifacts and contracts remain active

Contract tension:
- migration_sequence.md requests removal of deprecated conflicting assumptions

Evidence:
- speakermining/src/process/candidate_generation/wikidata/aggregates.py still rebuilds old candidates.csv pipeline artifacts.
- speakermining/src/process/candidate_generation/wikidata/classes.py still maintains legacy observation outputs.

Impact:
- Operational ambiguity between legacy and migrated outputs.

## Positive Progress

1. Canonical event schema implementation exists and is materially aligned:
- speakermining/src/process/candidate_generation/wikidata/event_log.py
- speakermining/src/process/candidate_generation/wikidata/entity.py
- speakermining/src/process/candidate_generation/wikidata/cache.py

2. Query inventory dedup basis (query_hash + endpoint) is implemented:
- speakermining/src/process/candidate_generation/wikidata/query_inventory.py

3. Consolidated stores and projection materializer are present:
- speakermining/src/process/candidate_generation/wikidata/node_store.py
- speakermining/src/process/candidate_generation/wikidata/triple_store.py
- speakermining/src/process/candidate_generation/wikidata/materializer.py

4. Seed setup schema fix was addressed:
- speakermining/src/process/candidate_generation/broadcasting_program.py now prioritizes `label` while preserving fallback behavior.

5. Basic migration test scaffold is present and passing:
- speakermining/test/process/wikidata/* (current 7-test slice)

## Gate Status (Migration Sequence)

1. Freeze design contracts: Pass
- Authoritative Step 1-4 documents exist and are coherent.

2. Implement frozen contracts (single rollout phase): Partial Fail
- Core scaffolding implemented.
- Critical behavioral contracts (graph-first, Stage B fallback, eligibility re-entry, paging resume, class resolution semantics) not fully implemented.

3. Validate and publish as one gated change set: Fail
- Testing gate: Partial only; required acceptance breadth not implemented.
- Documentation gate: Not synchronized across required governance files.

## Recommendations to Reach Compliance

1. Replace match-gated BFS recursion with strict graph-first expansion predicate evaluation.
2. Wire and use `core_class_qids` end-to-end from setup loading through expandability checks.
3. Implement Stage B fallback in notebook orchestration with unresolved-only input and eligibility re-entry expansion.
4. Implement paged inlinks loop with cursor persistence and retry/partial checkpoint semantics.
5. Complete class_resolver path BFS and populate class_filename/path/subclass flags in materializer outputs.
6. Harden event file naming to guaranteed unique append behavior (monotonic suffix or higher precision token).
7. Expand test suite to full Step 2/3/4 acceptance matrix and re-run gate.
8. Complete documentation synchronization required by migration_sequence.md in same change set.

## Final Evaluation Outcome

Status: Not ready to ship as a completed migration.

Rationale:
- The change set demonstrates strong structural progress but does not yet satisfy the authoritative behavioral and gating requirements defined in migration_sequence.md and Step 2-4 contracts.

