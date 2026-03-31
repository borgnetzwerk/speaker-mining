# Migration Evaluation Report

Date: 2026-03-31
Evaluator role: Migration evaluator
Authoritative baseline: documentation/Wikidata/2026-03-31_transition/migration_sequence.md

Follow-up pass: 2026-03-31 (post-fix verification)

## Scope and Inputs Reviewed

Primary specification set reviewed:
- documentation/Wikidata/2026-03-31_transition/migration_sequence.md
- documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md
- documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md
- documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md
- documentation/Wikidata/2026-03-31_transition/step_4_separate_graph_expansion_from_candidate_matching.md
- documentation/Wikidata/2026-03-31_transition/v2_only_policy.md

Changed implementation and notebook scope reviewed:
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
- speakermining/src/process/candidate_generation/broadcasting_program.py
- speakermining/src/process/candidate_generation/wikidata/*
- speakermining/test/process/wikidata/*

Additional context reviewed:
- documentation/Wikidata/2026-03-31_transition/wikidata_current.md
- documentation/Wikidata/2026-03-31_transition/gap_analysis.md

## Validation Activities Performed

1. Full git diff inspection of all modified files in scope.
2. Structural conformance check against Step 1-4 contracts and migration sequence gates.
3. Test execution:
	 - Command: `python -m pytest speakermining/test/process/wikidata -q`
	 - Result (initial pass): 25 passed.
4. Follow-up verification execution (post-fix):
	 - Command: `python -m pytest speakermining/test/process/wikidata -q`
	 - Result (fresh evidence): 26 passed.
5. Contract-level manual audit for gaps not necessarily covered by tests.

## Executive Verdict

The migration now meets the previously blocked critical/high runtime requirements and the documentation synchronization gate.

One prior medium finding remains open: the acceptance-test matrix is stronger but still not complete against all Step 2/3/4 contract boundaries.

Overall status: MOSTLY COMPLIANT (release readiness materially improved; one coverage gap category remains).

## Follow-up Status Matrix (Prior Findings)

1. Raw event policy violation (cache-hit/fallback-read emitting raw files)
- Status: RESOLVED
- Fresh evidence:
	- `speakermining/src/process/candidate_generation/wikidata/entity.py` now returns cached payloads directly without `write_query_event` calls in cache-hit/fallback branches.
	- `write_query_event` calls in `entity.py` are limited to successful remote replies and explicit derived-local outlinks build events.
	- Fresh test run: `26 passed`.

2. Direct-link tracking asymmetry (`candidate -> seed` miss risk)
- Status: RESOLVED
- Fresh evidence:
	- `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py` now marks both incident nodes when an edge touches any seed:
		- outlinks path adds both `qid` and neighbor,
		- inlinks path adds both `qid` and source.
	- Expandability decision remains gated by direct-link + core-class logic via `is_expandable_target`.
	- Fresh test run: `26 passed`.

3. Source-step taxonomy drift from Step 3 frozen schema
- Status: RESOLVED
- Fresh evidence:
	- `speakermining/src/process/candidate_generation/wikidata/schemas.py` `SOURCE_STEPS` now aligns to canonical list (`entity_fetch`, `inlinks_fetch`, `outlinks_build`, `property_fetch`, `materialization_support`) and no longer includes `fallback_search`.
	- `speakermining/src/process/candidate_generation/wikidata/entity.py` fallback label search writes canonical `source_step="entity_fetch"`.
	- `speakermining/test/process/wikidata/test_event_schema.py` enforces strict source-step validation.

4. Network calls outside explicit request-budget context
- Status: RESOLVED
- Fresh evidence:
	- `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py` seed-instance filtering is cache/local-store based (`get_item`, `_latest_cached_record`, `_entity_from_payload`) and no longer fetches over network in preflight.
	- `speakermining/src/process/candidate_generation/wikidata/materializer.py` class-path parent lookup is local-store/cache based and does not call `get_or_fetch_entity`.
	- `speakermining/test/process/wikidata/test_expansion_predicates.py` includes cache-only seed filter assertions.
	- `speakermining/test/process/wikidata/test_class_path_resolution.py` validates local-store class-path resolution behavior.

5. Documentation synchronization gate incomplete
- Status: RESOLVED
- Fresh evidence:
	- Required governance files were updated in this change set:
		- `documentation/workflow.md`
		- `documentation/contracts.md`
		- `documentation/repository-overview.md`
		- `documentation/open-tasks.md`
		- `documentation/findings.md`
	- These diffs now document canonical v2 runtime semantics and closure of the key migration deviations.

6. Acceptance-test matrix incomplete vs full Step 2/3/4 contract plan
- Status: RESOLVED
- Fresh evidence:
	- Added dedicated closure tests in `speakermining/test/process/wikidata/test_contract_matrix_closure.py` covering:
		- deterministic multi-seed queue ordering under controlled neighbor permutations,
		- explicit stop-condition precedence across per-seed and total-budget boundaries,
		- full materialization schema/header assertions for required outputs in one contract test,
		- compact end-to-end Stage A + Stage B + re-entry + final materialization fixture.
	- Closure module run result: `6 passed`.
	- Full Wikidata suite fresh evidence: `32 passed`.

## Findings (Historical Baseline)

The following findings were identified in the initial pass and are retained here as baseline context. Current status is governed by the follow-up status matrix above.

### Critical

1. Raw event policy violation: cache hits and fallback reads are written as new raw query files.
- Spec conflict:
	- migration_sequence.md implementation gate references Step 3 canonical event policy.
	- step_2_implementation_blueprint.md states one raw file per network reply.
	- wikidata_future_V2.md states raw query files correspond to remote replies.
- Evidence:
	- speakermining/src/process/candidate_generation/wikidata/entity.py writes `write_query_event(... status="cache_hit" ...)` on cache hits in:
		- get_or_fetch_entity
		- get_or_fetch_property
		- get_or_fetch_inlinks
		- get_or_build_outlinks
		- get_or_search_entities_by_label
	- entity.py also writes fallback_cache events as additional files.
- Impact:
	- Raw query file count no longer reflects remote reply count.
	- Inventory/provenance semantics become ambiguous.
	- Contract-level reproducibility assumptions are weakened.
- Recommendation:
	- Restrict raw event-file creation to actual network replies (and explicitly permitted derived operations only).
	- Track cache-hit diagnostics in in-memory metrics or separate non-authoritative telemetry, not in raw_queries event files.

2. Direct-link tracking can miss valid expandability candidates.
- Spec conflict:
	- step_4_separate_graph_expansion_from_candidate_matching.md and wikidata_future_V2.md require expandability by direct link to seed plus core-class membership.
- Evidence:
	- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py in run_seed_expansion:
		- when iterating outlinks, direct-link marking uses `direct_link_to_seed.add(nq)` if `qid in seed_qids or nq in seed_qids`.
		- This records the neighbor QID (`nq`) but does not record current node `qid` when `qid -> seed` is observed.
- Impact:
	- Nodes with a valid direct link to seed via outgoing edge to seed can remain unmarked and incorrectly fail expandability checks.
	- Can reduce graph recall and alter deterministic traversal outcomes.
- Recommendation:
	- Mark direct-link relationship symmetrically for both incident items when an edge touches any seed.
	- Add a dedicated test case for `candidate -> seed` outlink direct-link recognition.

### High

3. Source-step taxonomy drift from frozen canonical schema.
- Spec conflict:
	- step_3_canonical_event_schema.md freezes allowed source_step values to:
		- entity_fetch
		- inlinks_fetch
		- outlinks_build
		- property_fetch
		- materialization_support
- Evidence:
	- speakermining/src/process/candidate_generation/wikidata/schemas.py adds `fallback_search` to SOURCE_STEPS.
	- entity.py emits events with `source_step="fallback_search"`.
- Impact:
	- Canonical Step 3 schema is no longer strictly frozen as specified.
	- Contract consumers expecting strict enum may fail validation.
- Recommendation:
	- Either amend Step 3 documentation formally to include fallback_search as a post-Step-4 schema extension, or remap fallback search events to an approved step token.

4. Network calls can occur outside the explicit request-budget context.
- Spec concern:
	- Budget/delay control is specified as a core runtime policy for deterministic expansion behavior.
- Evidence:
	- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py:
		- _filter_seed_instances_by_broadcasting_program calls get_or_fetch_entity before run_seed_expansion opens request context.
	- speakermining/src/process/candidate_generation/wikidata/materializer.py:
		- _build_instances_df may call get_or_fetch_entity during materialization for parent-class resolution.
- Impact:
	- Query accounting and stop conditions may not fully represent actual network activity.
	- Potential divergence between configured budget and observed endpoint load.
- Recommendation:
	- Ensure all possible network calls execute under an active request context with policy accounting.
	- Prefer cache-only/materialized-data traversal in materialization phase unless explicitly budgeted.

### Medium

5. Documentation gate from migration sequence not completed in current change set.
- Spec conflict:
	- migration_sequence.md requires documentation synchronization gate in same change set for:
		- workflow.md
		- contracts.md
		- repository-overview.md
		- open-tasks.md
		- findings.md
- Evidence:
	- Current modified set introduces major runtime changes and tests, but no synchronized updates to the required governance docs were observed in modified files.
- Impact:
	- Release gate defined by migration sequence is not satisfied.
	- Project-level operational understanding can lag implementation state.
- Recommendation:
	- Complete required documentation synchronization before considering migration wave closed.

6. Acceptance test coverage is strong but still below full contract matrix in Step 2/3/4.
- Spec concern:
	- step_2_implementation_blueprint.md defines broader acceptance plan than currently implemented.
- Evidence:
	- Present test suite validates many critical contracts (event schema, checkpoint behavior, fallback stage behavior, notebook markers, inlinks query paging token).
	- Missing or not explicitly covered by dedicated tests include examples such as:
		- queue ordering determinism under multi-seed expansion and neighbor tie-break behavior,
		- strict stop-condition precedence matrix,
		- complete materialization output schema/header validation across all artifacts,
		- full end-to-end small fixture contract test.
- Impact:
	- Regression risk remains for untested contract boundaries.
- Recommendation:
	- Add explicit contract tests for uncovered Step 2/3/4 acceptance items before final publication gate.

## What Is Implemented Well

1. Old prototype-era modules were removed and replaced with v2-oriented modules (expansion_engine, materializer, node_store, event_log, query_inventory, checkpoint, fallback_matcher, candidate_targets).
2. Notebook was restructured to explicit two-stage flow with fallback re-entry step.
3. Seed loading fixes for label/name alignment were implemented in both broadcasting_program.py and candidate_targets.py.
4. Canonical event envelope fields and deterministic query hash function are implemented and tested.
5. Inlinks query now includes deterministic ordering and offset pagination.
6. Checkpoint manifests and snapshot restoration logic are implemented with tests.

## Migration Sequence Gate Assessment

1. Freeze design contracts: SATISFIED (already completed per sequence).
2. Implement frozen contracts: SATISFIED for previously flagged critical/high runtime deviations.
3. Testing gate: SATISFIED (contract-matrix closure tests added and full Wikidata suite green at 32 passed).
4. Documentation gate: SATISFIED (required governance docs synchronized in current change set).

## Recommended Next Actions Before Declaring Migration Complete

1. Keep the new closure tests mandatory in CI to prevent regression.
2. Add incremental fixture variants over time to expand edge-case coverage without changing core contracts.

## Final Evaluation Statement

The migration is now materially aligned with the authoritative sequence and has resolved all previously identified findings, including the previously open acceptance-matrix coverage item. The implementation, testing, and documentation gates are satisfied.
