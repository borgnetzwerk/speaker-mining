# Wikidata Step 4: Legacy JSON Cutover

Status: Transferred to great_rework (2026-04-09)
Owner: Candidate generation / Wikidata pipeline
Depends on: `04_core_class_output_hardening.md`

## Goal

Rewire consumers away from legacy JSON writers and remove JSON outputs that are no longer required once the new lookup infrastructure and output contracts are stable.

## What this step delivers

1. Consumer rewiring away from `entities.json`.
2. Consumer rewiring away from `properties.json`.
3. Removal of the corresponding JSON writers and checkpoint snapshots.

## Scope

In scope:

1. identify every runtime reader of `entities.json`
2. identify every runtime reader of `properties.json`
3. route those readers to the chunk/index infrastructure
4. delete legacy writer code after parity is validated
5. remove deprecated snapshotting of retired artifacts

Out of scope:

1. redesigning the chunk/index contract itself
2. changing core-class output boundary rules
3. deciding the final lifecycle of `triple_events.json`

## Implementation checklist

1. Produce consumer inventory for `entities.json` and `properties.json`.
2. Rewire all listed consumers to index/chunk-based retrieval.
3. Run parity checks before deleting writers.
4. Remove writer code and deprecated schema paths.
5. Remove deprecated checkpoint snapshot references.

## Completion criteria

This step is complete when all of the following are true:

1. No runtime path depends on `entities.json` for lookup.
2. No runtime path depends on `properties.json` for lookup.
3. Removed writers and snapshot paths are no longer referenced by active code.
4. Regression tests show lookup and output parity after cutover.

## Required completion evidence

1. Consumer inventory marked fully rewired.
2. Parity test summary before and after writer removal.
3. Grep-style proof that removed artifact paths are no longer referenced in active runtime code.

## Progress update (2026-04-09)

Transfer note:

1. Remaining scope is tracked in `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-007`.

Completed in this pass:

1. `get_item` already supports chunk/index lookup fallback when `entities.json` has no entry.
2. `iter_items` now also supports chunk/index fallback when `entities.json` is absent or empty.
3. Checkpoint runtime snapshot now includes `entity_lookup_index.csv` and `entity_chunks/*.jsonl`.
4. Tests added and passing for chunk-backed retrieval paths.

Still pending for Step 4 completion:

1. Full consumer inventory and rewiring away from `entities.json` and `properties.json`.
2. Removal of `entities.json` and `properties.json` writer code.
3. Snapshot/schema cleanup for removed legacy JSON artifacts.
4. Final parity run and grep-proof of no active legacy references.

## Notes

This step intentionally excludes the final decision for `triple_events.json`, which is handled in the next step.

When complete, mark this file complete and move to the next step file.
