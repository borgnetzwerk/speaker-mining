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

Primary implementation review scope (as requested):
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
- speakermining/src/process/candidate_generation/broadcasting_program.py
- speakermining/src/process/candidate_generation/wikidata/*

Validation executed:
- pytest speakermining/test/process/wikidata -q
- Result: 10 passed

## Executive Verdict

Status: **Partially compliant; not yet publish-ready as a fully gated migration sequence completion**.

Current implementation demonstrates strong structural progress and passes the available migration test slice. However, several contract-level behaviors remain incomplete or inconsistent with the Step 2-4 implementation contracts and the migration gate requirements in migration_sequence.md.

## Findings (Ordered by Severity)

### Critical 1: Fallback re-entry eligibility is effectively disabled

Contract violated:
- Step 4 requires newly discovered fallback candidates to be re-checked for expansion eligibility and expanded when eligible.

Evidence:
- speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py
  - run_fallback_string_matching_stage calls is_expandable_target with:
	 - seed_qids=set()
	 - has_direct_link_to_seed=False
  - Under the Step 4 decision table, this makes fallback candidates non-expandable in practice (except impossible edge-cases), so eligible_for_expansion_qids remains empty.

Impact:
- Stage B cannot practically feed Stage A re-entry expansion as required by the two-stage architecture.

### Critical 2: Resume decision and deterministic resume flow are not orchestrated in notebook contract flow

Contract violated:
- Step 2 notebook orchestration contract requires explicit resume decision stage before per-seed expansion execution.

Evidence:
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
  - Contains Stage A, unresolved handoff, Stage B, and re-entry cells.
  - Does not contain a dedicated resume decision execution step using checkpoint.decide_resume_mode semantics.

Impact:
- Resume/restart/revert behavior is not operationalized at notebook orchestration level as specified.

### High 1: Deprecated prototype paths remain in active codebase and still conflict with migration intent

Contract tension:
- migration_sequence.md requires removal of deprecated development-era contracts where conflicting assumptions remain (notably candidates.csv-era assumptions).

Evidence:
- speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py still contains match-gated recursion and candidate_match-driven queueing.
- speakermining/src/process/candidate_generation/wikidata/aggregates.py still rebuilds legacy candidates.csv/candidate_index.csv artifacts from raw materialization_support events.

Impact:
- Operational ambiguity persists between migrated graph-store path and older match-gated candidate path.

### High 2: Expandability direct-link determination is only partially represented and may diverge from strict direct-link contract

Contract scope:
- Step 4 and wikidata_future_V2 direct-link semantics are item-to-item edge based, independent of P31.

Evidence:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - direct_link_to_seed is maintained incrementally from currently observed neighbor relationships.
  - Fallback branch uses has_direct = bool(_claim_qids(candidate_doc, "P31") & seed_qids), which is not a direct-link check and is semantically unrelated.

Impact:
- Expandability outcomes can diverge from strict direct-link semantics in edge cases.

### High 3: Class rollup metadata is structurally present but class descriptive fields remain unpopulated

Contract scope:
- Step 1 Option B artifacts include classes.csv with descriptive fields and class-level rollups.

Evidence:
- speakermining/src/process/candidate_generation/wikidata/class_resolver.py
  - compute_class_rollups initializes label/description/alias fields as empty strings.
- speakermining/src/process/candidate_generation/wikidata/materializer.py
  - classes.csv is generated from these rollups without enrichment.

Impact:
- classes.csv is usable for counts/path flags but incomplete for human inspection and metadata parity expected by design.

### Medium 1: Property node discovery pipeline is incomplete in runtime flow

Contract scope:
- Step 2 includes property store handling and properties projections.

Evidence:
- speakermining/src/process/candidate_generation/wikidata/node_store.py exposes upsert_discovered_property.
- No observed runtime call path in expansion/materialization flow that populates properties.json from discovered property IDs.

Impact:
- properties.csv/properties.json may remain sparse or empty relative to graph expansion observations.

### Medium 2: Inlinks cursor persistence exists, but crash-path checkpoint semantics are not fully explicit

Contract scope:
- Step 3 defines incomplete checkpoint behavior on paging failure/retry exhaustion.

Evidence:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py records inlinks_cursor after successful page processing and writes checkpoint manifests after each seed.
- No explicit crash-recovery checkpoint write path with incomplete=true was identified inside inlinks paging failure branches.

Impact:
- Recovery metadata on hard paging failure may be weaker than contract intent.

## Positive Progress

1. Canonical v2 event envelope is implemented and used in runtime fetch/build paths.
	- speakermining/src/process/candidate_generation/wikidata/event_log.py
	- speakermining/src/process/candidate_generation/wikidata/entity.py
	- speakermining/src/process/candidate_generation/wikidata/cache.py

2. Event append-only collision safety is improved with unique filename suffixing.
	- speakermining/src/process/candidate_generation/wikidata/event_log.py
	- speakermining/test/process/wikidata/test_event_append_only.py

3. Graph-first expansion module exists and is wired into notebook Stage A.
	- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
	- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb

4. Inlinks query now supports deterministic ordering and offset paging.
	- speakermining/src/process/candidate_generation/wikidata/inlinks.py
	- speakermining/src/process/candidate_generation/wikidata/entity.py

5. Consolidated artifact materialization exists for instances/classes/properties/aliases/triples/inventory.
	- speakermining/src/process/candidate_generation/wikidata/materializer.py

6. Seed loader schema mismatch (label vs name) was corrected.
	- speakermining/src/process/candidate_generation/broadcasting_program.py

7. Migration-focused test slice currently passes.
	- speakermining/test/process/wikidata/*
	- 10 tests passed in local run

## Gate Status Against migration_sequence.md

1. Freeze design contracts: **Pass**
- Step 1-4 design artifacts are present and coherent.

2. Implement frozen contracts (single rollout phase): **Partial**
- Major scaffolding and substantial runtime implementation are present.
- Remaining gaps persist in fallback re-entry eligibility logic, resume orchestration, and lingering legacy conflicting paths.

3. Validate and publish as one gated change set: **Partial Fail**
- Testing gate: improved and currently green on available migration test slice (10 passed), but still not a full blueprint-level acceptance matrix.
- Documentation gate: governance synchronization in workflow/contracts/repository-overview/open-tasks/findings is not included in this implementation slice.

## Recommendations to Reach Full Compliance

1. Fix fallback eligibility re-check to use real direct-link-to-seed semantics and non-empty seed set context during Stage B.
2. Add explicit resume decision stage to notebook orchestration and wire checkpoint.decide_resume_mode behavior into execution flow.
3. Remove or quarantine legacy conflicting runtime modules (especially match-gated bfs_expansion/aggregates paths) to enforce single canonical migration behavior.
4. Replace P31-based fallback direct-link approximation with triple-backed direct-link checks.
5. Enrich classes.csv descriptive columns from resolved class entities during materialization.
6. Wire discovered property persistence from outlink/property observations into node_store and verify properties projections.
7. Add explicit crash-recovery checkpoint write path with incomplete=true for paging failure branches.
8. Complete migration_sequence documentation gate updates in the same rollout set.

## Final Evaluation Outcome

Status: **Not yet ready to ship as a fully completed migration sequence under current gate definitions**.

Rationale:
- The migration is substantially advanced and materially improved (including passing tests and strong module coverage), but the remaining contract-critical behavior gaps prevent full acceptance against the authoritative sequence and Step contracts.
