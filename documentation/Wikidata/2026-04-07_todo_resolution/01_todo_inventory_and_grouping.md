# WDT Inventory And Grouping

Source: `documentation/Wikidata/wikidata_todo_tracker.md`

## A) Runtime Safety And Observability

- `WDT-007` (P0): Graceful notebook exit without hard interrupt corruption.
  - **Important:** Very important. Independent issue and can likely be solved first.
- `WDT-008` (P0): Restore runtime heartbeat and operator progress visibility.
  - **Important:** The hearbeat is already back, the aspect of "if we just implement proper eventsourcing, we have our progress visibility for free" aspect remains.
- `WDT-009` (P1, deferred): Expand event model beyond `query_response`.
  - **Important:** This is likely the time to resolve this. This was deferred, but likely, now is the time to actually solve it, since plenty of other issues could be solved by just solving this one.

Shared thread:
- Cooperative stop boundaries, deterministic stop reasons, and event-backed operational telemetry.

## B) Eligibility Reclassification And Integrity Evidence

- `WDT-001` (P0): Re-evaluate prior eligibility when class lineage improves.
  - **Important:** Here we have to keep in mind that now that the new class hierarchy is in place, we should not question this everytime. Instead, we should process all currently known targets, then recompute the hierarchy tree if needed (likely, just a few branches will be added, 99.9 % of the tree will remain unchanged), and then see if we have new targets - if so, repeat the loop: Process all, branch all, check for targets.
- `WDT-002` (P0): Persist reclassification diagnostics for longitudinal analysis.
  - **Important:** This plays into the event-sourcing: If we did proper eventsourcing, this would not need dedicated solving. It would just be a regular byproduct of proper event logging.
- `WDT-003` (P1): Add regression tests for reclassification edge cases.
  - **Important:** WDT-003 Can likely be deleted, is a byproduct of a prior uncertainty and will no longer be relevant

Shared thread:
- Node integrity correctness loop, class-lineage re-evaluation, and auditable transitions.

## C) Domain Semantics And Projection Value

- `WDT-010`: Clear differentiation between core classes and root classes.
  - **Important:** Already done in the input csv files and also done in some of the code already. Just making sure that it's correct throughout the code.
- `WDT-012`: Add more projections (per core class + leftovers).
- `WDT-011`: Identify/define full eventsourcing target architecture.

Shared thread:
- Correct modeling boundaries (what should expand), then expose higher-value projections and converge toward handler-driven orchestration.

## D) Persistence Architecture And File Formats

- `WDT-013`: Transition from CSV to Parquet (except Phase 3 handoff CSV).
- `WDT-014`: Deprecate non-eventsourced file writing.

Shared thread:
- Projection storage migration and decommissioning mutable non-event-sourced writers.

## E) Query Efficiency And Wikidata Load

- `WDT-015`: Query easier for Wikidata (reduce high-volume minimal payload fetches).

Shared thread:
- Batch-aware and cache-amortized retrieval strategy, especially in node integrity.

## F) Completed Baseline Controls (Keep Stable)

- `WDT-004` (completed): language fetch policy (`de`, `en`, `mul`) is explicit and enforced.
- `WDT-005` (completed): alias cross-language leakage fixed.
- `WDT-006` (completed): checkpoint snapshot includes eventstore artifacts and restore path.

Role in plan:
- These are not active backlog items, but they are regression controls and must remain green while other changes land.

## G) Cross-Cutting Major TODO: Documentation Overhaul

- Major TODO (new): overhaul Wikidata documentation after implementation waves land.

Scope of overhaul:
- Align all Wikidata docs to post-fix runtime behavior.
- Reflect both migration axes explicitly:
	- v2 logic-rework behavior continuity
	- v3 event-sourcing architecture and operational model
- Remove stale references (for example CSV-only assumptions after Parquet migration decisions).
- Ensure docs, workflow order, contracts, and notebook guidance are mutually consistent.

Primary files expected to be part of this overhaul:
- `documentation/workflow.md`
- `documentation/contracts.md`
- `documentation/repository-overview.md`
- `documentation/findings.md`
- `documentation/Wikidata/Wikidata_specification.md`
- `documentation/Wikidata/wikidata_todo_tracker.md` (status closure/update)

## Dependency Order (Reworked With Current Context)

1. Solve `WDT-007` first as an independent operational safety fix.
2. Promote event-model work immediately after (`WDT-009` + `WDT-011` + `WDT-014`), because this unlocks or simplifies multiple downstream items.
3. Then resolve integrity and diagnostics (`WDT-001`, `WDT-002`), with transition evidence emitted as domain events where possible.
4. Treat `WDT-003` as a validation gate integrated into each wave, not as a large independent stream. If dedicated edge-case tests become redundant after event-level invariants are in place, close or merge it explicitly in tracker governance.
5. Confirm core-vs-root correctness end-to-end (`WDT-010`) and only then add projections (`WDT-012`).
6. Execute query-efficiency redesign (`WDT-015`) with event provenance preserved, then storage transition (`WDT-013`) to avoid churn and duplicate migration work.
7. Documentation overhaul closes the program: publish one clean, accurate state after code/data-contract changes stabilize.

## Migration-Learning Inputs Used For This Rework

From `documentation/Wikidata/2026-04-03_eventsourcing_potential_unlock`:
- Domain events were identified as a major unlock, not a minor deferred task.
- Incremental event-backed runtime behavior reduces pressure on ad-hoc diagnostics and progress reporting.

From `documentation/Wikidata/2026-04-02_jsonl_eventsourcing`:
- v3 is already established as the active runtime direction.
- Deterministic replay, handler progress, and event integrity are explicit quality gates and should drive sequencing decisions.

## Planning Note On Current "Important" Context

- `WDT-008`: heartbeat baseline exists; remaining value is event-derived visibility.
- `WDT-009`: moved from deferred posture to near-term architecture focus.
- `WDT-002`: should converge toward being largely produced by proper domain-event emission.
- `WDT-003`: likely reducible/mergeable into wave-level invariant testing and governance gates.
- `WDT-010`: mostly verification and consistency sweep, not greenfield build.
