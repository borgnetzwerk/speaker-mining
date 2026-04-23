# Fernsehserien.de Transfer Execution Plan (Wikidata)

Date: 2026-04-09
Scope: concrete implementation slices derived from event-handling learnings

Note:

1. This file is a retained implementation detail plan.
2. Canonical planning and execution order lives in `documentation/Wikidata/2026-04-10_great_rework/00_master_rework_map.md`.

## Goal

Turn cross-pipeline learnings into coding-ready slices with explicit code touchpoints, acceptance criteria, and validation commands.

## Slice 1 (P0): Event Heartbeat Service For Long Runs

Backlog mapping:

- GRW-005 (primary)
- GRW-001 (secondary)

Code touchpoints:

1. `speakermining/src/process/candidate_generation/wikidata/event_writer.py`
2. `speakermining/src/process/candidate_generation/wikidata/event_log.py`
3. `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`

Implementation:

1. Add optional in-memory recent-event window in event writer:
   - rolling `events_in_window`
   - top event types
   - last event summary (sequence, type, compact payload)
2. Expose lightweight API to fetch recent activity without scanning chunks.
3. Add local fallback heartbeat in Notebook 21 for long waits, so progress remains visible even if callbacks stall.

Acceptance criteria:

1. Step 6 and Step 6.5 print heartbeat lines at least every 60s while running.
2. Heartbeats include event counts and top event types from recent window.
3. Long-running network delays do not create silent periods beyond heartbeat interval.

Validation:

1. Notebook dry run with cache-only mode.
2. Notebook run with non-zero network budget and simulated slow network.
3. Focused tests for heartbeat summary API behavior.

## Slice 2 (P0): Handler Progress Governance Hardening

Backlog mapping:

- GRW-003 (primary)
- GRW-001 (secondary)

Code touchpoints:

1. `speakermining/src/process/candidate_generation/wikidata/handler_registry.py`
2. `speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py`
3. `speakermining/src/process/candidate_generation/wikidata/checkpoint.py`

Implementation:

1. Add managed-handler pruning (drop stale/unknown handler rows).
2. Emit per-handler run stats:
   - pre-sequence
   - post-sequence
   - processed events
   - artifact path
3. Persist one run summary artifact under checkpoints or projections diagnostics.

Acceptance criteria:

1. `eventhandler.csv` contains only managed handlers after orchestration.
2. Every run produces deterministic per-handler stats.
3. Incremental reruns show zero processed events for already-caught-up handlers.

Validation:

1. Unit tests for registry pruning and stats generation.
2. Replay test proving no truncation when pending events are unrelated to a handler.

## Slice 3 (P1): Evented Repair Framework

Backlog mapping:

- GRW-003 (primary)
- GRW-005 (secondary)

Code touchpoints:

1. `speakermining/src/process/candidate_generation/wikidata/event_log.py`
2. `speakermining/src/process/candidate_generation/wikidata/cache.py`
3. `speakermining/src/process/candidate_generation/wikidata/checkpoint.py`
4. `speakermining/src/process/candidate_generation/wikidata/node_store.py`

Implementation:

1. Add cleanup/repair event family:
   - `cache_identity_cleanup_applied`
   - `projection_repair_applied`
2. Require repair payload fields:
   - `archive_path`
   - `diagnostics_path`
   - `affected_count`
   - `reason`
3. For destructive repairs, archive-first then repair, never silent mutation.

Acceptance criteria:

1. Every repair action is represented by an event.
2. Repair actions are auditable via artifacts and event payload.
3. Repeated repair runs are idempotent and do not duplicate side effects.

Validation:

1. Unit tests for event schema and idempotence.
2. Integration test for one real repair scenario.

## Slice 4 (P1): Phase-Contract Event Map

Backlog mapping:

- GRW-001 (primary)
- GRW-008 (secondary)

Code touchpoints:

1. `documentation/Wikidata/expansion_and_discovery_rules.md`
2. `documentation/Wikidata/Wikidata_specification.md`
3. `speakermining/src/process/candidate_generation/wikidata/event_log.py`
4. `speakermining/test/process/wikidata/test_event_schema.py`

Implementation:

1. Define allowed event families per phase:
   - discovery
   - expansion
   - integrity
   - fallback
   - projection/materialization
2. Add validation test that phase-tagged events stay inside contract.

Acceptance criteria:

1. Event phase contract is documented and test-backed.
2. New event types require explicit phase registration.

Validation:

1. Contract test failures when event type emitted from wrong phase.

## Slice 5 (P1): Incremental Materialization Default

Backlog mapping:

- GRW-003 (primary)
- GRW-007 (secondary)

Code touchpoints:

1. `speakermining/src/process/candidate_generation/wikidata/materializer.py`
2. `speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py`
3. `speakermining/src/process/candidate_generation/wikidata/checkpoint.py`

Implementation:

1. Introduce explicit modes:
   - `incremental` (default)
   - `full_rebuild` (maintenance/recovery)
2. Update only projections affected by new sequence range in incremental mode.
3. Preserve deterministic full rebuild path for parity checks.

Acceptance criteria:

1. Incremental runs avoid full rebuild for unchanged projections.
2. Full rebuild remains available and deterministic.
3. Runtime logs expose per-projection build time and changed/unmodified status.

Validation:

1. Performance regression benchmark before/after on representative graph size.
2. Parity test: incremental outputs match full rebuild outputs for same event prefix.

## Recommended Order

1. Slice 1
2. Slice 2
3. Slice 5
4. Slice 3
5. Slice 4

## Definition Of Done For Transfer

1. Slices 1 and 2 complete and used in Notebook 21 runs.
2. Slice 5 complete with benchmark evidence.
3. Slices 3 and 4 complete with documentation and regression tests.
4. GRW backlog entries updated with closure evidence links.
