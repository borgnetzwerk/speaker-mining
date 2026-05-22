# data-lineage-trace

**Identified by:** Data Engineer (review 05), task 9

## Problem

When a person entity in the final Phase 50 output appears with unexpected values (wrong Wikidata QID, missing properties, wrong gender attribution), there is no tool to trace that entity back through the pipeline stages to find where the value was introduced or last modified. A developer must manually grep logs, check intermediate CSVs for each phase, and reconstruct the chain of transformations by hand.

This is a significant debugging cost that grows with each additional pipeline phase, and it means data quality issues are expensive to reproduce and fix.

## Action (code-scope, deferred)

Implement a `trace_entity(canonical_entity_id)` function in `speakermining/src/` (exact module TBD based on pipeline structure) that:

1. Accepts a canonical entity ID (QID or internal person ID) as input
2. Walks the pipeline stage outputs in order (Phase 1 → 2 → 3 → 31/32 → 50) and collects every row or record touching that entity
3. Returns a structured trace object: `{stage: str, file: str, row: dict, transformation: str}` per stage
4. Has a human-readable print mode suitable for debugging (`trace_entity(qid, verbose=True)`)

The function should work on the output CSVs/JSONs already present in the data directory — it is a read-only diagnostic tool, not a reprocessing step.

Document the function's existence and usage in `documentation/data_reference.md` under a "Debugging and traceability" section.

## Definition of done

1. `trace_entity(canonical_entity_id)` exists and works on a complete pipeline run.
2. It covers all phases from 1 through 50.
3. Its usage is documented in `documentation/data_reference.md`.
4. A `verbose=True` mode produces a human-readable output suitable for debugging.
