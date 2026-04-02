# Execution Checklist, Gates, and Benchmark Protocol

Date: 2026-04-03

---

## Delivery Plan (Commit-Sized)

### Commit A - Cache index and lookup acceleration

Scope:

- Implement latest query cache index and invalidation.
- Preserve existing cache_max_age_days and language coverage semantics.

Must pass:

- Existing cache and entity fetch tests.
- New tests for stale-index avoidance after append.

Exit criterion:

- At least 2x speedup in synthetic repeated lookup benchmark.

---

### Commit B - Event writer reuse

Scope:

- Stage-scoped EventStore writer reuse.
- No behavior change in sequence numbering and chunk rotation.

Must pass:

- Event writer tests for sequence continuity.
- Chunk boundary tests and checksum compatibility.

Exit criterion:

- Append microbenchmark at least 5x faster for 1k appends.

---

### Commit C - Mutable store write buffering

Scope:

- Buffer node and triple updates in-memory.
- Seed-boundary atomic flush.

Must pass:

- Crash recovery tests for .recovery behavior.
- Functional tests for discovered and expanded node counts.

Exit criterion:

- Write count during one seed reduced by at least 80 percent.

Status:

- Completed and notebook-validated.

---

### Commit D - Checkpoint-lite materialization policy

Scope:

- Add configurable full materialization interval.
- Keep final materialization mandatory.

Must pass:

- Resume and checkpoint tests.
- Notebook integration run for Step 6 and Step 10.

Exit criterion:

- Step 6 wall time reduced by at least 30 percent on benchmark run.

Status:

- Completed via incremental query-inventory materialization and stage boundary flushing.

---

### Commit E - Incremental handlers in Stage A

Scope:

- Trigger handlers orchestrator with sequence progress.
- Remove per-seed full rebuild dependency where safe.

Must pass:

- Determinism tests across repeated reruns.
- eventhandler progress correctness tests.

Exit criterion:

- Handler run time scales with new event volume, not total history.

Status:

- Not yet required for this unlock wave; deferred to the next architectural pass.

---

### Commit F - Domain event emission rollout

Scope:

- Introduce domain event types and update handlers to consume them.
- Keep query_response for provenance and debugging.

Must pass:

- Replay tests on mixed streams.
- Backward compatibility checks on existing chunks.

Exit criterion:

- Event mix includes new domain events for Step 6 operations.

Status:

- Not yet required for this unlock wave; deferred to the next architectural pass.

---

### Commit G - Remove mutable JSON sidecars

Scope:

- Move every remaining consumer to event-backed or handler-backed projections.
- Remove `entities.json`, `properties.json`, and any other mutable JSON sidecar compatibility writes from the runtime path.
- Keep only replayable event logs and deterministic projections as runtime state.

Must pass:

- Restore/revert tests with no sidecar compatibility assumptions.
- Projection determinism tests on repeated reruns.
- Notebook 21 end-to-end validation with a clean runtime root.

Exit criterion:

- No mutable JSON sidecar is required for normal runtime operation.

Status:

- In progress: the handler-level entities.json compatibility output has been removed; the runtime store sidecars are the remaining consumer path.

---

## Notebook 21 Benchmark Protocol

Use identical configuration and data snapshot before and after each commit.

### Benchmark config

- same seeds and target rows
- max_queries_per_run set to a fixed value, for example 200
- same cache state for A/B pair (cold or warm, never mixed)

### Metrics to record

1. Time to first progress heartbeat in Step 6
2. Calls per minute reported in progress logs
3. Total Step 6 elapsed time
4. Total materialization time share
5. Cache hit ratio for entity, property, inlinks
6. Number of full file rewrites for entities.json and triples_events.json

### Required instrumentation additions

- Timers around _latest_cached_record
- Timers around EventStore initialization
- Counters for node_store and triple_store flush operations
- Materializer stage breakdown already present should be retained

---

## Risk Register

1. Stale cache index serving old query_response
- Mitigation: strict invalidation on append and sequence-aware freshness checks.

2. Writer reuse causing lifecycle or shutdown conflicts
- Mitigation: explicit close/flush lifecycle and graceful shutdown integration tests.

3. Buffer flush bugs causing data loss
- Mitigation: forced flush on seed completion and on exception path.

4. Checkpoint-lite confusing downstream cells
- Mitigation: documented projection freshness contract and final materialization guarantee.

5. Handler incremental drift
- Mitigation: deterministic replay validation and byte-level projection diff on sampled runs.

---

## Acceptance Gates For Production Merge

All must be true:

1. Step 6 speedup at least 5x versus current baseline on benchmark profile.
2. No regression in discovered candidate counts and unresolved target counts.
3. Resume mode append and revert semantics still pass.
4. Projection files remain deterministic across two identical reruns.
5. Event stream contains domain events beyond query_response after Commit F.
