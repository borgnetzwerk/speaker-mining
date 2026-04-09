# Wikidata Step 2: Stage A Reliability

Status: Resolved (completed 2026-04-09)
Owner: Candidate generation / Wikidata pipeline
Depends on: `02_entity_lookup_and_chunk_infrastructure.md`

## Goal

Improve first-pass expansion reliability in Stage A so eligible nodes are not missed before Node Integrity reconciliation.

## What this step delivers

Canonical rule reference:

- Expansion/discovery eligibility and degree semantics are defined in `documentation/Wikidata/expansion_and_discovery_rules.md`.

1. Subclass-aware eligibility in Stage A.
2. Deterministic neighbor prioritization before cap.
3. Stable and testable expansion ordering under fixed inputs.

## Scope

In scope:

1. implement `direct_or_subclass_core_match` in Stage A eligibility
2. integrate class hierarchy fallback resolution when class nodes are missing
3. rank neighbors deterministically with a stable score then QID tie-break
4. apply cap only after ranking
5. expose counters for stop reasons and budget effects

Out of scope:

1. deleting legacy JSON writers
2. changing core-class output boundary rules
3. replay artifact decisions

## Implementation checklist

1. Add subclass-aware gate logic in `expansion_engine.py`.
2. Reuse class-path resolution via `class_resolver.py`.
3. Implement deterministic neighbor scoring and sorting.
4. Move cap application after deterministic ranking.
5. Add tests for eligibility and deterministic ordering.

## Completion criteria

This step is complete when all of the following are true:

1. Subclass-of-core episodes with direct seed link become eligible in Stage A.
2. Deterministic runs keep identical ordering and counts under same inputs.
3. Cap behavior is applied after ranking, not before.
4. Unit tests cover subclass-aware eligibility and ranking determinism.

Note:

- Eligibility correctness in item 1 is evaluated against `documentation/Wikidata/expansion_and_discovery_rules.md`.

## Required completion evidence

1. Before/after comparison for one known previously-risky case.
2. Test output showing deterministic ordering on repeated runs.
3. Metrics snapshot showing stop reasons after the change.

## Completion evidence (2026-04-09)

1. Stage A eligibility now uses `direct_or_subclass_core_match` and no longer depends on direct `P31` core match only.
2. Neighbor capping now happens after deterministic scoring and sorting by `(score desc, qid asc)`.
3. Append resume semantics now scan from program 1 and skip already completed seeds instead of hard-starting from the first unfinished seed index.
4. Stage A now writes checkpoint manifests at seed boundaries and performs expensive projection materialization once at final stage completion.
5. Tests executed:
	1. `pytest speakermining/test/process/wikidata/test_expansion_predicates.py speakermining/test/process/wikidata/test_determinism.py -q` -> 8 passed.
	2. `pytest speakermining/test/process/wikidata/test_phase1_acceptance_gate.py -q` -> 1 passed.
	3. `pytest speakermining/test/process/wikidata/test_store_buffering.py speakermining/test/process/wikidata/test_checkpoint_resume.py -q` -> 26 passed.
6. Expansion decision payload now includes `direct_or_subclass_core_match` in eligibility metadata to support operator diagnostics.

## Notes

This step should be complete before changing downstream output contracts or removing legacy artifacts.

When complete, mark this file complete and move to the next step file.
