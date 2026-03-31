# Migration Evaluation Report

Date: 2026-03-31  
Evaluator role: Migration evaluator (Step-contract compliance review)

## Remediation Update (Post-Final Verification)

This report reflects a full remediation pass over the previously identified migration findings.

Result summary:
- Previously open critical/high behavioral findings were implemented in code.
- Final verification identified three additional gaps and all three were remediated in this pass:
  - Stage A resolved-target handoff was not populated.
  - Fallback stage could not discover candidates outside local discovered nodes.
  - Legacy entrypoints still exposed compatibility semantics in a v2-only policy context.
- Migration test slice was re-run after final remediation.

Validation executed:
- pytest speakermining/test/process/wikidata -q
- Result: 14 passed

## Scope and Method

Authoritative contract baseline:
- documentation/Wikidata/2026-03-31_transition/migration_sequence.md
- documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md
- documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md
- documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md
- documentation/Wikidata/2026-03-31_transition/step_4_separate_graph_expansion_from_candidate_matching.md

Primary implementation review scope:
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
- speakermining/src/process/candidate_generation/broadcasting_program.py
- speakermining/src/process/candidate_generation/wikidata/*
- speakermining/test/process/wikidata/*

## Executive Verdict

Status: **Substantially compliant with the migration sequence implementation phase**.

The implementation-phase code findings are now remediated and re-validated. Remaining gate work is documentation synchronization listed in migration_sequence.md.

## Findings Resolution Log

### Resolved Critical 1: Fallback re-entry eligibility disabled

Previous issue:
- Stage B candidates were evaluated with empty seed context and forced no direct link, making re-entry practically unreachable.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py
  - Added seed-aware fallback evaluation input (`seeds`).
  - Re-entry eligibility now computes direct-link-to-seed from persisted triples.
- speakermining/src/process/candidate_generation/wikidata/triple_store.py
  - Added `has_direct_link_to_any_seed` helper.

Validation:
- speakermining/test/process/wikidata/test_fallback_stage.py
  - Added test asserting seed-linked fallback candidate becomes eligible.

### Resolved Critical 2: Resume decision not orchestrated in notebook flow

Previous issue:
- No explicit resume decision stage before Stage A execution.

Fixes:
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
  - Added explicit resume decision cell using `checkpoint.decide_resume_mode`.
  - Stage A call now passes `requested_mode` to graph expansion.
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - Added `requested_mode` handling (`append`, `restart`, `revert`) and seed start index behavior.

### Resolved High 1: Legacy conflicting runtime paths

Previous issue:
- Legacy modules still contained match-gated assumptions and candidate-era aggregation semantics.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/bfs_expansion.py
  - Converted to fail-fast v2-only deprecation entrypoint.
- speakermining/src/process/candidate_generation/wikidata/aggregates.py
  - Converted to fail-fast v2-only deprecation entrypoint.

Outcome:
- Legacy entrypoints no longer execute any compatibility behavior and explicitly direct callers to canonical v2 modules.

Validation:
- speakermining/test/process/wikidata/test_fallback_stage.py
  - Added fail-fast assertions for both legacy entrypoints.

### Resolved High 2: Expandability direct-link approximation divergence

Previous issue:
- Runtime fallback used a P31-based approximation that is not a direct-link check.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - Removed the P31-to-seed approximation from direct-link determination.
  - Expansion decisions now rely on observed item-item direct-link context.

### Resolved High 3: Class descriptive metadata unpopulated in classes.csv

Previous issue:
- class rollups had counts but label/description/alias fields remained empty.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/materializer.py
  - Enriched class rollups from discovered class entity metadata when available.

### Resolved Medium 1: Property node discovery flow incomplete

Previous issue:
- Property persistence path existed but was not wired in expansion runtime.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/entity.py
  - Added `get_or_fetch_property` with canonical v2 event logging.
- speakermining/src/process/candidate_generation/wikidata/cache.py
  - Added property mapping support in cache lookup/event compatibility.
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - Persists discovered property nodes from outlinks property IDs.

### Resolved Medium 2: Crash checkpoint incompleteness flag semantics

Previous issue:
- Crash-recovery stop reason could be emitted without explicit incomplete checkpoint semantics.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - Crash path sets stop reason `crash_recovery`.
  - Checkpoint manifest now sets `incomplete=True` on crash recovery.

### Resolved Critical 3: Stage A handoff resolved-target set remained empty

Previous issue:
- Stage A discovered graph nodes but did not map them back to mention targets, leaving `resolved_target_ids` and `discovered_candidates` effectively empty and pushing all targets into unresolved handoff.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - Added deterministic target resolution against discovered node-store entities using normalized labels/aliases.
  - Added mention-type scope checks using core-class filename mapping.
  - `discovered_candidates`, `resolved_target_ids`, and `unresolved_targets` are now computed from actual Stage A discoveries.

Validation:
- speakermining/test/process/wikidata/test_graph_stage_resolution.py
  - Added test asserting discovered-node resolution populates resolved/unresolved handoff correctly.

### Resolved High 4: Fallback could not discover non-local candidates

Previous issue:
- Fallback matching only indexed local discovered nodes and could not discover a candidate when label did not already exist in local node store.

Fixes:
- speakermining/src/process/candidate_generation/wikidata/entity.py
  - Added cache-first `get_or_search_entities_by_label` using Wikidata `wbsearchentities` with canonical event logging.
- speakermining/src/process/candidate_generation/wikidata/cache.py
  - Added cache mapping for fallback search events (`source_step=fallback_search`).
- speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py
  - Added bounded endpoint-assisted discovery path for unresolved labels.
  - Newly discovered search hits are fetched, persisted into node store, indexed, and then matched under class-scope filters.

Validation:
- speakermining/test/process/wikidata/test_fallback_stage.py
  - Added test asserting fallback can discover and match candidates via endpoint-search path.

## Current Gate Status Against migration_sequence.md

1. Freeze design contracts: **Pass**  
- Step 1-4 design artifacts remain present and authoritative.

2. Implement frozen contracts (single rollout phase): **Pass (code scope)**  
- Core runtime contracts for graph expansion, canonical events, materialization, fallback separation, re-entry, and Stage A/Stage B handoff are implemented.

3. Validate and publish as one gated change set: **Partial (non-code gate pending)**  
- Testing gate: pass for current migration suite (14 passed).
- Documentation gate: workflow/contracts/repository-overview/open-tasks/findings synchronization remains an explicit follow-up documentation pass.

## Final Evaluation Outcome

Status: **Ready for migration code acceptance, pending documentation-gate synchronization tasks**.
