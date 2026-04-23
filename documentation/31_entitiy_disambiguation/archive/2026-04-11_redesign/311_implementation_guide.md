# Phase 31 Step 311 Implementation Guide

Date: 2026-04-09
Status: Active implementation guide

This guide explains how to extend Step 311 automated disambiguation logic while staying compliant with repository governance and event-sourcing standards.

Authoritative references:

1. Specification: [311_automated_disambiguation_specification.md](311_automated_disambiguation_specification.md)
2. Manual handoff: [312_manual_reconciliation_specification.md](312_manual_reconciliation_specification.md)
3. Artifact contract: [313_disambiguation_artifact_contract_draft.md](313_disambiguation_artifact_contract_draft.md)
4. Repository coding rules: [../coding-principles.md](../coding-principles.md)

## 1. Current Runtime Topology

Step 311 implementation modules:

1. `speakermining/src/process/entity_disambiguation/alignment.py`
2. `speakermining/src/process/entity_disambiguation/event_log.py`
3. `speakermining/src/process/entity_disambiguation/event_handlers.py`
4. `speakermining/src/process/entity_disambiguation/checkpoints.py`
5. `speakermining/src/process/entity_disambiguation/orchestrator.py`
6. `speakermining/src/process/entity_disambiguation/config.py`
7. Notebook orchestrator: `speakermining/src/process/notebooks/31_entity_disambiguation.ipynb`

Execution model:

1. Notebook does bootstrap/import/orchestration only.
2. Process modules contain all transformation logic.
3. Alignment decisions are appended as immutable events.
4. Replayable handlers build aligned projections from event logs.
5. Checkpoints preserve event chunks, projections, and handler progress.

## 2. Extension Rules (Do Not Break)

1. Never write to upstream phase folders from Step 311.
2. Never force low-confidence matches; unresolved rows are valid output.
3. Keep outputs deterministic for unchanged inputs.
4. Keep aligned CSV baseline columns stable across reruns.
5. Add logic in process modules, not directly in notebook execution cells.
6. Preserve append-only event semantics for alignment decisions.
7. Keep checkpoint format backward-compatible when possible.

## 3. Where To Extend Alignment Logic

### 3.1 Episode Alignment (Layer 2)

Primary file: `alignment.py`, class `EpisodeAligner`

Additions typically include:

1. Stronger time-window matching (date + start + duration tolerance)
2. Season/episode-number fallback matching
3. Publication metadata normalization before comparison

Requirements:

1. Every rule must produce a clear method label and reason text.
2. Confidence scoring must be explicit and reproducible.
3. Ambiguous matches must produce `unresolved` or `conflict`, not guessed links.

### 3.2 Person Alignment (Layer 3)

Primary file: `alignment.py`, class `PersonAligner`

Additions typically include:

1. Candidate loading from Wikidata projections
2. Candidate loading from Fernsehserien projections
3. Better deterministic name normalization rules
4. Deterministic tie-breaking based on episode-local evidence

Requirements:

1. Matching unit remains one person mention in one episode.
2. Score/rule logic must be explainable in output fields.
3. Keep `requires_human_review` true where uncertainty remains.

### 3.3 Role/Organization Context (Layer 4)

Primary files:

1. `alignment.py` for deterministic context scoring
2. `orchestrator.py` for loading and passing Layer 4 signals

Guideline:

1. Layer 4 may increase confidence but must not overwrite stronger Layer 1/2 evidence.

## 4. Event-Sourced Contract For New Logic

When adding any new deterministic rule:

1. Emit or enrich alignment events, do not mutate projection rows directly.
2. Keep event payload backward-compatible when possible.
3. Ensure handlers can replay from clean state and produce same result.
4. Track handler progress (`handler_name`, `last_processed_sequence`, `artifact_path`, `updated_at`).

Event compatibility checklist:

1. Existing fields unchanged or explicitly versioned.
2. New fields optional for older handlers.
3. Replay still succeeds on historic event logs.

## 5. Projection Extension Pattern

Primary file: `event_handlers.py`

To add new output fields safely:

1. Add column names in `config.py` extended column lists.
2. Add extraction mapping in `ReplayableHandler._event_to_row`.
3. Keep baseline columns first and unchanged.
4. Preserve stable column order for deterministic CSV contracts.

## 5.1 Projection Ordering Rules

Ordering is part of the projection contract and must remain deterministic.

Global rule for time-aware projections:

1. Sort chronologically oldest-first (first season/first episode at top).
2. Use publication date/time first where available.
3. Use season and episode numbers as deterministic secondary tie-breakers where available.
4. Keep unresolved rows in output; ordering must not filter records.

Persons-specific rule (two-pass stable ordering):

1. First pass: sort chronologically by episode appearance (oldest episode appearance first).
2. Second pass: stable alphabetical sort by person name.
3. Resulting behavior: names are grouped alphabetically, and repeated names keep chronological show appearance order within each name group.

Implementation ownership:

1. Sorting logic belongs in `event_handlers.py` after replay deduplication.
2. If ordering rules change, update this section and artifact contract docs in the same PR.

## 6. Input Integration Pattern (Phase 20 -> Phase 31)

Primary file: `orchestrator.py`

Recommended sequence:

1. Load projection inputs from `data/20_candidate_generation/...`.
2. Normalize relevant join keys before matching.
3. Build in-memory candidate indexes for deterministic lookup.
4. Run aligners and emit one event per alignment attempt.
5. Build projections from events only.

Failure handling:

1. Missing optional inputs should degrade to unresolved rows.
2. Missing required inputs should fail fast with a clear error message.

## 7. Checkpoint & Retention Expectations

Primary file: `checkpoints.py`

Every checkpoint should include:

1. Event chunk files
2. `chunk_catalog.csv`
3. `eventstore_checksums.txt`
4. Current `aligned_*.csv` projections
5. Handler progress database

Retention minimum:

1. Keep 3 newest unzipped checkpoints.
2. Keep zipped history according to retention policy.

## 8. Notebook Orchestrator Expectations

Notebook file: `speakermining/src/process/notebooks/31_entity_disambiguation.ipynb`

Must remain:

1. Bootstrap/setup oriented in first code cell
2. Process-module orchestration only (no heavy business logic)
3. Safe to run with a single Run All
4. Graceful interruption handling and resumable flow

## 9. Definition Of Done For Any Step 311 Extension

1. Notebook Run All completes without import/path errors.
2. New logic emits deterministic events with clear reasons.
3. `aligned_*.csv` files are produced with baseline columns intact.
4. At least one recovery run is validated from checkpoint.
5. Documentation updated when contracts or outputs change.
6. Changes remain compliant with [../coding-principles.md](../coding-principles.md).

## 10. Practical Next Extension Sequence

1. Integrate Wikidata and Fernsehserien candidate loading in `orchestrator.py`.
2. Pass real candidate dictionaries into `PersonAligner`.
3. Add episode time-window matching rule in `EpisodeAligner`.
4. Emit episode-level events and include them in projection builds.
5. Validate OpenRefine import quality for `aligned_persons.csv` and `aligned_episodes.csv`.
