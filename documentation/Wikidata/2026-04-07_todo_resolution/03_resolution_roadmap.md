# Resolution Roadmap (Dependency-Aware)

This roadmap resolves all backlog items while preserving already-working behavior and avoiding migration dead-ends.

Migration framing used throughout this roadmap:
- v2 track: logic-rework continuity and regression control.
- v3 track: event-sourcing correctness (event integrity, replayability, deterministic recovery).

## Wave 0: Baseline Lock And Scaffolding (short)

Targets:
- Preserve completed controls (`WDT-004`, `WDT-005`, `WDT-006`).
- Establish execution board and acceptance checklist templates for all open WDTs.

Deliverables:
- Baseline verification run checklist for Notebook 21 stages.
- Test plan skeleton for `WDT-003` and restore/revert checks.

Exit criteria:
- No regressions in language policy, alias handling, checkpoint restore behavior.

## Wave 1: Immediate Operational Safety

Targets:
- `WDT-007`, `WDT-018`, `WDT-019`

Implementation focus:
1. Integrate cooperative termination checks into stage loops:
   - graph expansion
   - node integrity discovery/expansion
   - fallback matching
2. Standardize stop reasons and checkpoint/log propagation (`user_interrupted` path).
3. Enforce Notebook 21 fallback config integrity:
   - derive fallback-enabled mention types once,
   - reuse the same derived value across Step 7 and Step 8,
   - never override user-configured values silently,
   - fail fast on invalid user config.

Testing:
- Simulated shutdown-file stop mid-run.
- Confirm deterministic stop boundary and checkpoint consistency.

Exit criteria:
- Operator can stop without hard interrupt.
- No partial-write corruption from cooperative stop.
- Fallback runtime configuration is deterministic and exactly matches user-defined config.

Execution status (2026-04-07):
- Core implementation landed for cooperative stop checks in Stage A / node integrity / fallback loops.
- `user_interrupted` propagation and interruption-aware checkpoint behavior were integrated into graph-stage runtime flow.
- Targeted regression suite passed (`27 passed`) for checkpoint resume, node integrity, and fallback stage tests.
- Step 6.5 now handles `KeyboardInterrupt` deterministically (discovery + expansion paths) and exits with `user_interrupted` semantics.
- Added regression test coverage for interruption during live entity refresh path in node integrity.
- WDT-019 notebook config-integrity fix is implemented in Notebook 21:
   - fallback mention types are resolved once in Step 2,
   - Step 7 and Step 8 both consume `config["fallback_enabled_mention_types_resolved"]`,
   - invalid config now fails fast with explicit `ValueError`.
- Wave 1 operational safety and config-integrity targets are now implemented; remaining work is regression monitoring in representative runtime flows.

## Wave 2: Event-Sourcing Core Unlock (Promoted)

Targets:
- `WDT-009`, `WDT-011`, `WDT-014`

Implementation focus:
1. Introduce domain events beyond `query_response` (staged rollout):
   - `entity_discovered` ✅ (Phase 1 complete)
   - `entity_expanded` ✅ (Phase 1 complete)
   - `triple_discovered` (Phase 2)
   - `class_membership_resolved` (Phase 2)
   - `expansion_decision` (Phase 1, wiring only; finalization TBD)
   - eligibility transition events (Phase 2)
2. Shift projection writes toward handler-driven replay/incremental materialization.
3. Reduce and retire non-eventsourced writes where equivalent handler projection exists.

Migration rationale:
- Prior migration reviews identified this as the dominant unlock for observability, performance, and downstream simplification.

Testing:
- Replay determinism tests from event chunks to projections.
- Invariant tests for handler progress and idempotence.

**Execution status (2026-04-07 Wave 2 Phase 1 - Domain Event Introduction)**:
- ✅ Introduced three first-promoted domain events: `entity_discovered`, `entity_expanded`, `expansion_decision` (builder only)
- ✅ Wired events into Stage A graph expansion (entity discovery/expansion during seed traversal)
- ✅ Wired events into Step 6.5 node integrity (entity discovery during node repair)
- ✅ Wired events into Stage B fallback matching (entity discovery via string match)
- ✅ All 31 tests passing (including WDT-007 integration tests and new domain event instrumentation)
- ✅ Backward compatibility verified: no breaking changes to existing checkpoint/event structures
- ✅ Notebook 21 heartbeat helper added and wired after node integrity and fallback stages
- 📋 Next: Extend event-derived heartbeat to remaining long-running stage cells, wider domain event coverage (triple_discovered, class_membership_resolved), event replay tests

Exit criteria (Phase 1):
- ✅ Domain events are defined, documented, and wired into orchestration stages
- ✅ Orchestration logs domain events alongside query_response events
- ✅ Event stream captures discovery method and expansion context
- 📋 (Phase 2) Projection updates leverage domain events for derivation
- ✅ (Phase 2 kickoff) Heartbeat and diagnostics now begin with event-derived Notebook 21 summaries

## Wave 3: Integrity Evidence Loop On Top Of Events

Targets:
- `WDT-001`, `WDT-002`, `WDT-008`

Implementation focus:
1. Keep current reclassification loop but emit explicit transition evidence as first-class events.
2. Ensure heartbeat/progress views are event-derived where possible, with stable operator fields.
3. Produce append-only diagnostics artifacts from event projections rather than ad-hoc reconstruction where feasible.

Testing:
- Deterministic fixture graphs with late class lineage appearance.
- Assert transition rows, expanded node set, and event-derived heartbeat summaries.

Exit criteria:
- Reclassification is auditable and mostly event-derived.
- Heartbeat visibility is stable across append/restart/revert.

## Wave 4: Semantics Consistency + Projection Expansion

Targets:
- `WDT-010`, `WDT-012`

Implementation focus:
1. Validate core-vs-root behavior consistency across runtime and notebook communication.
2. Add projections:
   - one per core class for instances
   - one leftovers projection for non-class/non-core-instance rows

Testing:
- Validate projection membership against class hierarchy and core class set.

Exit criteria:
- Operators can clearly reason about scope.
- Projection outputs are useful and deterministic.

## Wave 5: Query Efficiency + Storage Migration

Targets:
- `WDT-015`, `WDT-016`, `WDT-017`, `WDT-013`

Implementation focus:
1. Query efficiency:
   - Add batched minimal-entity retrieval strategy where safe.
   - Keep per-entity provenance in events despite batching.
   - Prioritize node-integrity discovery hot path.
   - Document and mitigate live-read timeout exposure in Step 6.5 / Cell 18.
   - Limit non-core subclass frontier recursion in node-integrity discovery to reduce low-value class fan-out.
2. CSV->Parquet migration:
   - Keep explicit Phase 3 CSV handoff artifact.
   - Migrate remaining projections to Parquet with compatibility period.
   - Update schema/docs/contracts/workflow references.

Testing:
- Query volume/time reduction benchmarks.
- Data-equivalence checks between old CSV and new Parquet projections.
- Representative long-run node-integrity execution with timeout tolerance/visibility checks.

Exit criteria:
- Significant query reduction and runtime improvement.
- Storage format transition complete without contract breakage.

## Wave 6: Documentation Overhaul And Clean-State Publication

Targets:
- Major TODO: Overhaul documentation.

Implementation focus:
1. Rewrite governed docs to match implemented behavior (no stale architecture or file-format claims).
2. Align terminology and execution model across:
   - workflow order
   - output contracts
   - repository/module mapping
   - Wikidata specification and tracker status
3. Publish one coherent "current truth" state for operators and contributors.

Mandatory files to update in this wave:
1. `documentation/contracts.md`
2. `documentation/workflow.md`
3. `documentation/repository-overview.md`
4. `documentation/findings.md`
5. `documentation/Wikidata/Wikidata_specification.md`
6. `documentation/Wikidata/wikidata_todo_tracker.md`

Exit criteria:
- One clean documentation state accurately represents the current code, projections, and runtime behavior.
- No conflicting instructions remain across governance docs.

## Per-WDT Resolution Matrix

- `WDT-001`: Wave 3
- `WDT-002`: Wave 3
- `WDT-003`: Cross-wave validation gate; evaluate merge/closure in tracker once event-level invariant coverage is in place
- `WDT-004`: Wave 0 regression control
- `WDT-005`: Wave 0 regression control
- `WDT-006`: Wave 0 regression control
- `WDT-007`: Wave 1
- `WDT-008`: Wave 3
- `WDT-009`: Wave 2 (promoted from deferred posture)
- `WDT-010`: Wave 4
- `WDT-011`: Wave 2
- `WDT-012`: Wave 4
- `WDT-013`: Wave 5
- `WDT-014`: Wave 2
- `WDT-015`: Wave 5 (can prototype in Wave 3/4)
- `WDT-016`: Wave 5 (timeout resilience alongside query-efficiency work)
- `WDT-017`: Wave 5 (class-frontier shaping in node-integrity discovery)
- `WDT-018`: Wave 1 (graceful interruption behavior)
- `WDT-019`: Wave 1 (notebook config integrity and no-overwrite guarantee)
- Documentation Overhaul (major TODO): Wave 6

## Governance Updates Required As Work Lands

When implementations land, update in same change set:

1. `documentation/contracts.md`
2. `documentation/workflow.md`
3. `documentation/repository-overview.md`
4. `documentation/findings.md`
5. Relevant notebook markdown guidance in Notebook 21

Program-level closeout requirement:
- Execute Wave 6 and consolidate documentation to a single accurate clean state after major fixes land.

## Immediate Next Execution Slice

Recommended first implementation slice:

1. Continue Wave 2 Phase 2 heartbeat rollout (`WDT-008`):
   - extend event-derived heartbeat summaries to remaining long-running stage cells (including Step 6 / re-entry path)
   - expose operator-facing heartbeat fields aligned to event stream (`entity_discovered`, `entity_expanded`, `expansion_decision`)
2. Continue timeout resilience (`WDT-016`) in representative runtime flow:
   - run long-running Step 6.5 scenario and verify timeout retry/continuation behavior under real network pressure
   - tune retry/backoff policy if needed based on observed runtime behavior
3. Advance Wave 2 domain coverage (`WDT-009`):
   - wire `triple_discovered` and `class_membership_resolved`
   - begin `expansion_decision` finalization at decision persistence points

This slice continues active Wave 2 work while hardening the known long-run timeout failure mode in Notebook 21.
