# Wikidata Great Rework Backlog

Date: 2026-04-09

Note:

1. This file is a retained source inventory.
2. Canonical planning and execution order lives in `documentation/Wikidata/2026-04-10_great_rework/00_master_rework_map.md`.

## Priority Legend

- P0: blocks safe high-volume rerun
- P1: major efficiency/reliability gain
- P2: structural/cleanup improvement

## Migrated Unresolved Items

### GRW-001 (P1): Event-sourcing execution model simplification

Origin: WDT-011

Goal:

- Reduce notebook orchestration toward handler-driven event processing where feasible, minimizing imperative orchestration code outside setup.

Acceptance:

1. Clear target architecture for handler-first execution flow.
2. Identified notebook cells that can be replaced by event dispatch + projection readout.
3. One concrete vertical slice implemented and validated.

### GRW-002 (P1): CSV to Parquet transition completion

Origin: WDT-013

Goal:

- Finish runtime-internal transition to Parquet-first while preserving required CSV contracts for Phase 3 handoff.

Acceptance:

1. Runtime readers use Parquet by default.
2. CSV remains contract output only where required.
3. Snapshot/restore parity proven for Parquet-first runtime.

### GRW-003 (P0): Deprecate non-event-sourced rewrite paths

Origin: WDT-014

Goal:

- Remove or reduce rebuild-everything materialization paths that rewrite large projections unaffected by new events.

Acceptance:

1. Identify each non-incremental full-rebuild writer path.
2. Convert high-cost rebuild paths to incremental/event-driven projection updates.
3. Runtime logs show major reduction in repeated materialization durations.

### GRW-004 (P1): High-volume Wikidata query efficiency

Origin: WDT-015

Goal:

- Reduce network calls for minimal payload restoration at large scale.

Acceptance:

1. Benchmark baseline vs rework on representative non-zero-network run.
2. Material reduction in calls and wall-clock for Step 6.5.
3. Provenance/event semantics preserved.

### GRW-005 (P0): Long-run timeout resilience at scale

Origin: WDT-016

Goal:

- Ensure long node-integrity runs survive transient and repeated read timeouts without catastrophic failure or operator blindness.

Acceptance:

1. Reproducible stress scenario and resilience test harness.
2. Bounded retry/backoff policy validated under sustained timeout conditions.
3. Clear stop-reason and warning telemetry for operators.

### GRW-006 (P0): Final root-cause closure for mention-type overwrite concern

Origin: WDT-020

Goal:

- Prove that fallback mention-type config cannot silently revert to `person`, including notebook execution-order edge cases.

Acceptance:

1. Reproduce original reported behavior (or prove stale-cell artifact cause).
2. Add notebook-order guardrails/tests to prevent stale config leakage.
3. Operational evidence from rerun showing configured mention types are respected.

### GRW-007 (P1): Legacy JSON cutover completion

Origin: design step 05_legacy_json_cutover.md

Goal:

- Remove active runtime dependency on `entities.json` / `properties.json` after complete reader migration to chunk/index lookup.

Acceptance:

1. Consumer inventory complete and migrated.
2. Legacy writers removed.
3. Snapshot schema cleaned and verified.

### GRW-008 (P1): `triple_events.json` retain-or-remove decision

Origin: design step 06_triple_events_decision.md

Goal:

- Make explicit lifecycle decision for `triple_events.json` with replay requirements evidence.

Acceptance:

1. Consumer inventory with keep/remove disposition.
2. Decision record and implementation.
3. Tests/documentation aligned to final lifecycle.

### GRW-009 (P1): Context-aware fallback for unknown strings

Origin: rework intake 2026-04-09

Goal:

- Add a faster, class-scoped candidate acquisition path for long unknown-string sets, especially when the class is already known but the Wikidata match is not.

Acceptance:

1. Identify at least one class-scoped retrieval strategy that reduces pressure compared with the current fallback string matching stage.
2. Define how the known class context is supplied to the lookup path and how the result re-enters graph expansion.
3. Document when SPARQL-style or equivalent class-aware queries should be preferred over generic fallback matching.

### GRW-010 (P1): Notebook architecture reconsideration and consolidation

Origin: rework intake 2026-04-09

Goal:

- Re-evaluate the notebook structure as a whole and allow major consolidation, including the possibility of collapsing currently scattered orchestration into fewer cells when that improves clarity, maintainability, or event-sourcing alignment.

Acceptance:

1. Define the notebook-architecture principles that justify consolidation or decomposition.
2. Identify which existing cells remain essential and which can be deprecated or merged once full event-sourcing potential is in place.
3. Establish a decision path for future restructuring so large-scale redesign is treated as an explicit rework option, not an exception.

### GRW-011 (P1): Recover subclass logic from reverse-engineered class hierarchy

Origin: reverse_engineering_potential/class_hierarchy.csv

Goal:

- Reconstruct the lost subclass and lineage logic from preserved reverse-engineering artifacts so class-aware eligibility, rollups, and context-scoped retrieval can rely on a locally derivable hierarchy instead of ad hoc checks.

Acceptance:

1. Derive subclass closure and `path_to_core_class` behavior from the reverse-engineering hierarchy evidence.
2. Reconcile recovered lineage with the normative Wikidata contracts before any rewrite of runtime behavior.
3. Document exactly which old subclass logic is recovered, which parts remain intentionally deprecated, and which gaps still require live Wikidata evidence.

Implementation detail plan:

1. `documentation/Wikidata/2026-04-10_great_rework/05_grw_011_lineage_recovery_implementation_plan.md`

## Suggested Execution Order

1. GRW-011
2. GRW-006
3. GRW-005
4. GRW-009
5. GRW-004
6. GRW-003
7. GRW-002
8. GRW-001
9. GRW-007
10. GRW-008
11. GRW-010

## Cross-Pipeline Input

Implementation patterns reusable from fernsehserien_de are documented in:

- `documentation/Wikidata/2026-04-10_great_rework/03_fernsehserien_de_event_learnings.md`
- `documentation/Wikidata/2026-04-10_great_rework/04_fernsehserien_transfer_execution_plan.md`
