# Wikidata Step 3: Core-Class Output Hardening

Status: Resolved (completed 2026-04-09)
Owner: Candidate generation / Wikidata pipeline
Depends on: `02_entity_lookup_and_chunk_infrastructure.md`, `03_stage_a_reliability.md`

## Goal

Make the core-class output projections explicitly contract-driven and stable for downstream phases.

## What this step delivers

1. Explicit two-hop boundary enforcement for all `instances_core_*` projections.
2. Stable output schemas across reruns.
3. Validation that output generation is deterministic from runtime state.

## Scope

In scope:

1. enforce and test the two-hop discovery boundary in output materialization
2. align output schema fields across all core classes
3. validate CSV and Parquet parity for the same output family
4. document schema stability expectations

Out of scope:

1. removing legacy JSON writers
2. replay artifact decisions
3. redesigning runtime lookup infrastructure

## Implementation checklist

1. Add boundary filter tests to materializer outputs.
2. Verify all `instances_core_*` writers apply the same boundary rule.
3. Validate schema consistency and deterministic field ordering.
4. Confirm CSV and Parquet outputs remain aligned.

## Completion criteria

This step is complete when all of the following are true:

1. Core-class instance outputs satisfy the two-hop neighbor boundary contract.
2. Output schemas remain stable across reruns.
3. CSV/Parquet outputs are equivalent for the same data slice.
4. Integration tests verify boundary rules across all core-class families.

## Required completion evidence

1. Output diff summary across two deterministic reruns.
2. Boundary test results for each core-class family.
3. One schema snapshot confirming field stability.

## Completion evidence (2026-04-09)

1. Two-hop boundary filter is now explicitly applied during core-instance materialization using configured broadcasting program seeds.
2. Boundary enforcement test added and passing: `test_materializer_core_projections_enforce_two_hop_boundary` in `test_class_path_resolution.py`.
3. Validation tests executed:
	1. `pytest speakermining/test/process/wikidata/test_class_path_resolution.py -q` -> 5 passed.
	2. `pytest speakermining/test/process/wikidata/test_contract_matrix_closure.py speakermining/test/process/wikidata/test_fallback_stage.py speakermining/test/process/wikidata/test_node_integrity.py -q` -> 26 passed.
4. Existing write path still uses shared CSV/Parquet writer helper (`_write_tabular_artifact`) so schema and cross-format alignment remain on the same code path.

## Notes

This step should be complete before any broad legacy-artifact cutover to avoid shifting consumers during schema churn.

When complete, mark this file complete and move to the next step file.
