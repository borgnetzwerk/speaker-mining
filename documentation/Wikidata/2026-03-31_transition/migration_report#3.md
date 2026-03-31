# Migration Evaluation Report (Third Pass)

Date: 2026-03-31
Evaluator role: Migration evaluator (contract-compliance and change-set audit)

## Scope and Sources

Authoritative migration baseline reviewed:
- documentation/Wikidata/2026-03-31_transition/migration_sequence.md
- documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md
- documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md
- documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md
- documentation/Wikidata/2026-03-31_transition/step_4_separate_graph_expansion_from_candidate_matching.md
- documentation/Wikidata/2026-03-31_transition/v2_only_policy.md

Implementation scope reviewed:
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
- speakermining/src/process/candidate_generation/broadcasting_program.py
- speakermining/src/process/candidate_generation/wikidata/*
- speakermining/test/process/wikidata/*

Validation executed:
- pytest speakermining/test/process/wikidata -q
- Result: 19 passed

## Executive Verdict

Status: Code contracts compliant in third pass.

The change set resolves the majority of previously identified findings (event schema enforcement, bootstrap wiring, stage handoff artifacts, query inventory preference, target ingestion schema alignment, timestamp history, notebook stage order checks, and expanded test coverage).

Revert semantics are now state-correct through checkpoint snapshot restore: reverting removes the latest checkpoint and restores runtime artifacts (including raw query cache and materialized stores) to the previous checkpoint snapshot before continuation.

Conclusion: Code-level migration findings from this evaluation are closed. Final publish gate still depends on documentation-gate synchronization.

## Third-Pass Closure Matrix

1. Critical 1: Resume/restart/revert semantics
- Status: Fixed.
- Fixed:
  - restart clears runtime artifacts before continuing.
  - append reuses prior run_id/start_timestamp when checkpoint exists.
  - revert removes latest checkpoint file, restores previous checkpoint snapshot, then resumes from prior checkpoint metadata.
  - checkpoint write now persists runtime snapshots used for deterministic restore.
- Evidence:
  - speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - speakermining/src/process/candidate_generation/wikidata/checkpoint.py
  - speakermining/test/process/wikidata/test_checkpoint_resume.py

2. Critical 2: Canonical Step 3 source_step taxonomy enforcement
- Status: Fixed.
- Evidence:
  - SOURCE_STEPS added and enforced at event build time.
  - fallback_search usage removed from runtime emission paths.
- Files:
  - speakermining/src/process/candidate_generation/wikidata/schemas.py
  - speakermining/src/process/candidate_generation/wikidata/event_log.py
  - speakermining/src/process/candidate_generation/wikidata/entity.py
  - speakermining/src/process/candidate_generation/wikidata/cache.py
  - speakermining/test/process/wikidata/test_event_schema.py

3. High 1: Notebook orchestration contract
- Status: Fixed (practical contract intent), with one caveat.
- Fixed:
  - explicit resume decision cell.
  - explicit bootstrap cell with load_seed_instances + initialize_bootstrap_files.
  - graph stage before fallback stage ordering.
  - stage numbering corrected (no duplicate 3).
- Caveat:
  - notebook now contains 10 sections, while earlier analysis referenced a 9-step pair wording; if strict cardinality is required in governance text, docs should clarify this.
- Files:
  - speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
  - speakermining/test/process/wikidata/test_notebook_contract.py

4. High 2: Bootstrap API wiring into runtime
- Status: Fixed.
- Evidence:
  - runtime now calls load_core_classes/load_seed_instances/initialize_bootstrap_files.
  - bootstrap output creation is validated by tests.
- Files:
  - speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - speakermining/src/process/candidate_generation/wikidata/bootstrap.py
  - speakermining/test/process/wikidata/test_bootstrap_outputs.py

5. High 3: Step 4 stage-handoff artifacts missing
- Status: Fixed.
- Evidence:
  - graph stage resolved/unresolved target CSVs are written.
  - fallback stage candidate/eligible/ineligible CSVs are written.
- Files:
  - speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py
  - speakermining/src/process/candidate_generation/wikidata/schemas.py
  - speakermining/test/process/wikidata/test_graph_stage_resolution.py

6. High 4: Query inventory success preference
- Status: Fixed.
- Evidence:
  - success now outranks cache_hit/fallback_cache in dedup selection.
- Files:
  - speakermining/src/process/candidate_generation/wikidata/query_inventory.py
  - speakermining/test/process/wikidata/test_query_inventory.py

7. Medium 1: Node dedup timestamp history
- Status: Fixed.
- Evidence:
  - discovered_at_utc_history and expanded_at_utc_history maintained.
- File:
  - speakermining/src/process/candidate_generation/wikidata/node_store.py

8. Medium 2: Candidate target ingestion name-only bias
- Status: Fixed.
- Evidence:
  - label preferred with name fallback for broadcasting_programs input.
- File:
  - speakermining/src/process/candidate_generation/wikidata/candidate_targets.py

9. Medium 3: Testing gate coverage incomplete
- Status: Fixed for originally identified gaps.
- Added coverage includes:
  - determinism rerun behavior,
  - graph/fallback stage ordering contract,
  - graph-authoritative merge behavior,
  - restart/revert behavior checks,
  - source_step schema rejection.
- Files:
  - speakermining/test/process/wikidata/test_determinism.py
  - speakermining/test/process/wikidata/test_notebook_contract.py
  - speakermining/test/process/wikidata/test_fallback_stage.py
  - speakermining/test/process/wikidata/test_checkpoint_resume.py
  - speakermining/test/process/wikidata/test_event_schema.py

## Remaining Required Action

No remaining code-level action from this migration evaluation.

## Gate Assessment Against migration_sequence.md

1. Freeze design contracts: Pass
2. Implement frozen contracts: Pass
3. Validate and publish as one gated change set: Partial
- Testing gate: Pass for identified code-level gaps (19 passing tests in current suite).
- Documentation gate: Pending broader repository synchronization (workflow/contracts/repository-overview/open-tasks/findings), not re-evaluated in this third-pass code check.
