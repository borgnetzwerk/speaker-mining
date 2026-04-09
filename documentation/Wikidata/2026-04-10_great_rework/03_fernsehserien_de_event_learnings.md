# Fernsehserien.de Event Handling Learnings For Wikidata Rework

Date: 2026-04-09
Scope: transfer of event-sourcing and handler-orchestration patterns only (not traversal semantics)

Note:

1. This file is a retained source inventory.
2. Canonical planning and execution order lives in `documentation/Wikidata/2026-04-10_great_rework/00_master_rework_map.md`.

## Executive Summary

The fernsehserien_de implementation validates a practical, restart-safe event workflow where:

1. event emission is explicit and fine-grained,
2. projection handlers are sequence-driven with persisted progress,
3. observability is derived from event activity windows,
4. data hygiene repairs are also evented,
5. checkpoint snapshots are first-class and include eventstore payload.

Wikidata already implements many building blocks. The largest improvement opportunities are incremental projection updates, clearer handler-progress governance, and stronger event-driven hygiene/repair workflows.

## What Fernsehserien.de Does Well

### 1) Real-time event activity windows for operator heartbeat

Observed in:

- `speakermining/src/process/candidate_generation/fernsehserien_de/event_store.py`
- `speakermining/src/process/candidate_generation/fernsehserien_de/notebook_runtime.py`

Pattern:

1. Event store keeps an in-memory recent-event deque and `last_event` snapshot.
2. Notebook heartbeat shows event counts per window and top event types.
3. Fallback local heartbeat thread prevents silent stalls even when callback cadence drops.

Transfer to Wikidata:

1. Keep event-based heartbeat but add an optional in-memory recent-window cache in the event writer for low-cost heartbeat summaries.
2. Add local fallback heartbeat in Notebook 21 for long network waits.

### 2) Incremental handler progress with explicit per-handler state

Observed in:

- `speakermining/src/process/candidate_generation/fernsehserien_de/handler_progress.py`
- `speakermining/src/process/candidate_generation/fernsehserien_de/projection.py`

Pattern:

1. `eventhandler.csv` records `handler_name`, `last_processed_sequence`, `artifact_path`, `updated_at`.
2. Projection build reads existing rows and applies only events beyond handler progress.
3. Stale/unknown handlers are removed (`keep_only_handlers`).

Transfer to Wikidata:

1. Continue using `eventhandler.csv` but enforce stale-handler pruning and per-handler processed-event counters in summary output.
2. Ensure each handler summary reports before/after sequence and processed count every run.

### 3) Event-driven cleanup/repair is explicit and auditable

Observed in:

- `speakermining/src/process/candidate_generation/fernsehserien_de/fragment_cleanup.py`

Pattern:

1. Detects corrupted/undesired cache identities (URL fragments).
2. Archives affected files and writes diagnostics manifest.
3. Emits a dedicated cleanup event with counts and artifact paths.

Transfer to Wikidata:

1. Add explicit repair events for runtime hygiene operations (cache repair, projection reconciliation, fragment/identity cleanup equivalents).
2. Archive-first for destructive repairs and emit one summarized cleanup event.

### 4) Clear phase boundaries: discovered events first, normalized events second

Observed in:

- `speakermining/src/process/candidate_generation/fernsehserien_de/orchestrator.py`

Pattern:

1. Extraction emits only discovered events.
2. Normalization phase consumes discovered events and emits normalized events.
3. Projections are rebuilt at phase boundaries and checkpointed.

Transfer to Wikidata:

1. Formalize and document event phases: discovery, expansion, integrity, fallback, normalization/materialization.
2. Avoid mixing normalization with discovery in same hot loop when possible.

### 5) Strong checkpoint snapshot payload and timeline

Observed in:

- `speakermining/src/process/candidate_generation/fernsehserien_de/checkpoint.py`

Pattern:

1. Snapshot includes projections, raw query cache, chunks, chunk catalog, checksums.
2. Timeline appends checkpoint_created events.
3. Retention policy balances unzipped speed and zipped history.

Transfer to Wikidata:

1. Continue parity with this model (already mostly aligned).
2. Add explicit checkpoint health summary to notebook output after checkpoint operations.

## What Not To Copy Directly

1. Single-file event chunk (`chunk_000001.jsonl`) in fernsehserien_de event store:
   - Wikidata requires multi-chunk scale and should keep chunk rotation strategy.
2. Full projection rebuild every pass:
   - For Wikidata this is too expensive at current graph size; incremental projection strategy is preferred.
3. Domain-specific traversal/fallback behavior:
   - fernsehserien_de crawl priorities are website-structure specific and not transferable to Wikidata graph exploration semantics.

## Recommended Wikidata Rework Actions

### Action A (P0): Event heartbeat service in writer/runtime

1. Add recent-window activity cache (`events_in_window`, top event types, last event payload summary).
2. Expose this through notebook helper API and print every minute + network milestones.

### Action B (P0): Handler progress governance hardening

1. Add managed-handler pruning equivalent to `keep_only_handlers`.
2. Emit per-handler run stats: processed events, pre/post sequence, artifact path.

### Action C (P1): Evented repair framework

1. Introduce cleanup event family (for example `projection_repair_applied`, `cache_identity_cleanup_applied`).
2. Require archive path + diagnostics artifact path in cleanup payload.

### Action D (P1): Phase-contract event map

1. Define allowed event types per phase in documentation.
2. Add lightweight validation tests to ensure no phase emits out-of-contract event families.

### Action E (P1): Incremental materialization strategy

1. Retain full rebuild mode only for explicit maintenance/recovery.
2. Default to incremental projection updates keyed by event sequence progression.

## Suggested Backlog Mapping

1. Supports GRW-003 directly (non-event-sourced rewrite reduction).
2. Supports GRW-005 directly (timeout/stall observability and graceful long-run monitoring).
3. Supports GRW-001 directly (handler-first execution simplification).
4. Supports GRW-007/GRW-008 indirectly (clearer projection lifecycle and event boundaries).
