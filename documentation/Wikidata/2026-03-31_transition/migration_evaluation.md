# Migration Evaluation Report

Date: 2026-03-31
Evaluator role: Migration evaluator
Authoritative baseline: documentation/Wikidata/2026-03-31_transition/migration_sequence.md

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
	 - Result: 25 passed.
4. Contract-level manual audit for gaps not necessarily covered by tests.

## Executive Verdict

The migration is substantially implemented and directionally aligned with the Step 1-4 architecture (graph-first stage, fallback stage separation, new canonical stores, checkpointing, new notebook orchestration, and new tests).

However, the migration is not yet fully compliant with the authoritative contracts due to several high-impact runtime policy deviations and an incomplete publication gate.

Overall status: PARTIALLY COMPLIANT (implementation advanced, release gate not yet satisfied).

## Findings (Severity Ordered)

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
2. Implement frozen contracts: MOSTLY SATISFIED (major architecture landed, with noted policy deviations).
3. Testing gate: PARTIALLY SATISFIED (tests pass, but not yet full contract matrix coverage).
4. Documentation gate: NOT SATISFIED (required governance docs not synchronized in observed change set).

## Recommended Next Actions Before Declaring Migration Complete

1. Correct raw event emission semantics to keep raw_queries authoritative for remote replies (and approved derived events only).
2. Fix direct-link marking logic so expandability is evaluated correctly for both edge directions.
3. Reconcile source_step taxonomy with Step 3 schema contract (either code or spec update, but must be explicit and consistent).
4. Bring all network-capable operations under budgeted request context or explicitly redesign with documented policy.
5. Complete documentation synchronization gate in the required governance files.
6. Add missing contract tests to close acceptance-plan gaps.

## Final Evaluation Statement

The migration is technically substantial and near target architecture, but should not be treated as fully closed under the authoritative migration sequence until critical policy deviations and gate incompleteness are resolved.
