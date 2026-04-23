# Wikidata Step 1: Entity Lookup and Chunk Infrastructure

Status: Resolved (completed 2026-04-09)
Owner: Candidate generation / Wikidata pipeline
Depends on: `01_entity_dossier_and_expansion_reliability_design.md`

## Goal

Build the scalable QID lookup layer that replaces the need for monolithic JSON as the primary runtime lookup surface.

## Entry gate

Start this step only when all are true:

1. The immutable constraints in `00_immutable_input.md` are accepted as fixed.
2. The data contract in `01_entity_dossier_and_expansion_reliability_design.md` is the source of truth.
3. No downstream cutover work has started.

## What this step delivers

1. `entity_lookup_index.csv` as the constant-time QID locator.
2. `entity_chunks/` as the chunked record store.
3. A compact record format that can answer "everything we know about QID X" without scanning all runtime artifacts.
4. Runtime wiring for entity-backed lookup, with deterministic chunk assignment.

## Scope

In scope:

1. entity lookup index creation and refresh
2. entity chunk record writing
3. chunk rotation policy
4. lookup-by-QID plumbing in runtime consumers
5. validation that one QID resolves through index plus one chunk read

Out of scope:

1. deleting legacy JSON writers
2. consumer rewiring for all downstream readers
3. `triple_events.json` replacement decisions

## Implementation checklist

1. Add schema paths for `entity_lookup_index.csv` and `entity_chunks/`.
2. Initialize index and chunk directory during bootstrap.
3. Implement deterministic chunk writing order with sequential size-based rotation.
4. Add chunk writer with rotation threshold (target: about 50 MB, configurable).
5. Persist and read lookup rows that resolve a QID without scanning all records.
6. Add at least one runtime consumer path that uses index plus chunk read for QID diagnostics.

## Completion criteria

This step is complete when all of the following are true:

1. A QID can be resolved through `entity_lookup_index.csv` to exactly one chunk record.
2. The lookup path is deterministic across reruns with the same config and record ordering.
3. The runtime pipeline can answer the existing diagnostics use case without a full event-store scan.
4. Tests cover index determinism and chunk record retrieval.

## Required completion evidence

1. Example lookup trace for one known QID (for example Q130638552) from index row to chunk record.
2. Test results for index determinism and chunk retrieval.
3. A short note confirming chunk rotation config used for validation.

## Completion evidence (2026-04-09)

1. Lookup trace implemented and validated in tests: `Q130638552 -> entity_lookup_index.csv -> entity_chunks/entities_*.jsonl -> entity payload` using byte offset and byte length addressing.
2. Test execution:
	1. `pytest speakermining/test/process/wikidata/test_bootstrap_outputs.py speakermining/test/process/wikidata/test_store_buffering.py -q` -> 9 passed.
	2. `pytest speakermining/test/process/wikidata/test_determinism.py speakermining/test/process/wikidata/test_checkpoint_resume.py -q` -> 18 passed.
3. Rotation config validated with default `WIKIDATA_ENTITY_CHUNK_MAX_BYTES=52428800` (about 50 MB), configurable via environment variable.
4. Chunk fan-out behavior updated: chunk files now rotate sequentially by size and no longer pre-split into up to 256 hash buckets for small datasets.

## Notes

This step is the prerequisite for any later deprecation of `entities.json` or `properties.json`.

When complete, mark this file complete and move to the next step file.
