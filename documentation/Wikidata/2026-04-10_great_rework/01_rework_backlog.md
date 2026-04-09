# Wikidata Great Rework Backlog

Date: 2026-04-09

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

## Suggested Execution Order

1. GRW-006
2. GRW-005
3. GRW-004
4. GRW-003
5. GRW-007
6. GRW-008
7. GRW-002
8. GRW-001
