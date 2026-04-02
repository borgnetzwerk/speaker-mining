# Event-Sourcing Potential Unlock: Done vs Remaining

Date: 2026-04-03

This file is the single handoff for the unlock folder.
It separates what has already been completed and documented from what still must be done to finish Commit G.

## What Is Done

These items are already implemented and documented in the existing unlock files:

- Cache lookup indexing now avoids repeated full event-history scans.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md) and [02_EXECUTION_CHECKLIST.md](02_EXECUTION_CHECKLIST.md).
- Event writes reuse a cached EventStore per repository root.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md).
- Node and triple store updates are buffered and flushed at stage boundaries.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md) and [02_EXECUTION_CHECKLIST.md](02_EXECUTION_CHECKLIST.md).
- Query inventory is maintained incrementally instead of being rebuilt from all events.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md).
- Empty JSON sidecar bootstrap has been removed; the stores are now lazy.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md).
- InstancesHandler no longer writes a compatibility entities.json sidecar.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md), [02_EXECUTION_CHECKLIST.md](02_EXECUTION_CHECKLIST.md), and [03_OLD_BAGGAGE_INDEX.md](03_OLD_BAGGAGE_INDEX.md).
- Handler output tests now pass with InstancesHandler writing only instances.csv.
  - Documented in [00_OVERVIEW.md](00_OVERVIEW.md).

Validation already completed for the done work:

- Notebook 21 ran end-to-end with `max_queries_per_run = 5` after the cleanup.
- Regression tests passed for buffering, checkpoint reset, bootstrap, append-only event writing, and handler output contracts.

## What Is Still Required

The remaining work is the runtime-side sidecar removal for Commit G.
This is the part that still has to be done before the repo can say that mutable JSON sidecars are gone entirely.

### Remaining task 1: remove runtime JSON sidecar state from the hot path

Current runtime-side files still exist and are actively used as mutable state:

- [speakermining/src/process/candidate_generation/wikidata/node_store.py](../../../speakermining/src/process/candidate_generation/wikidata/node_store.py)
- [speakermining/src/process/candidate_generation/wikidata/triple_store.py](../../../speakermining/src/process/candidate_generation/wikidata/triple_store.py)
- [speakermining/src/process/candidate_generation/wikidata/checkpoint.py](../../../speakermining/src/process/candidate_generation/wikidata/checkpoint.py)
- [speakermining/src/process/candidate_generation/wikidata/schemas.py](../../../speakermining/src/process/candidate_generation/wikidata/schemas.py)

Required change:

- Remove `entities.json`, `properties.json`, and `triple_events.json` as mutable runtime sidecars.
- Replace them with replayable event-log reads and handler-backed or projection-backed state.
- Eliminate compatibility writes and fallback restore logic that depend on those JSON files.

### Remaining task 2: move checkpoint and restore logic off mutable sidecars

Required change:

- Update snapshot/restore/revert behavior so it no longer depends on copying mutable JSON sidecars as authoritative runtime state.
- Keep checkpointing only for replayable event logs and deterministic projections.
- Ensure restart, append, and revert modes still work without JSON-sidecar assumptions.

### Remaining task 3: replace the remaining projection reads with event-backed or handler-backed sources

Required change:

- Update any code paths that still read item or triple state from `entities.json`, `properties.json`, or `triple_events.json`.
- Keep `instances.csv`, `classes.csv`, `properties.csv`, `triples.csv`, and `query_inventory.csv` as deterministic projections.
- Preserve notebook behavior and ordering semantics.

### Remaining task 4: update the tests that still assert runtime sidecar presence

Required change:

- Replace tests that currently assert `entities.json` or `properties.json` existence with tests against replayable projections or handler output.
- Keep regression coverage for checkpoint restore, determinism, and notebook execution.
- Confirm no test requires mutable JSON sidecars for normal runtime operation.

## Required Exit Criteria

Commit G is only complete when all of the following are true:

- No mutable JSON sidecar is required for normal runtime operation.
- Runtime state is derived from replayable event logs and deterministic projections only.
- Restore/revert tests pass without sidecar compatibility assumptions.
- Projection determinism still passes on repeated reruns.
- Notebook 21 still runs end-to-end from a clean runtime root.

## Notes For The Next Pass

- The handler-side `entities.json` cut is already done and should not be reintroduced.
- The remaining work is broader than a one-file refactor because `node_store.py`, `triple_store.py`, and `checkpoint.py` still define the active runtime contract.
- The existing unlock docs remain the historical record; this file is the current action boundary.
