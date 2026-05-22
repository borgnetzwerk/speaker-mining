# phase-orchestration-drift

* priority: high
* scope: pipeline
* legacy-id: TODO-036

## Summary

`run_phase31` in `entity_disambiguation/orchestrator.py` and `run_phase32` in `entity_deduplication/orchestrator.py` wrap all logic in single functions, violating the notebook-first principle in `documentation/coding-principles.md`. Notebooks should be the orchestrators with step-by-step cells and intermediate output; modules should expose granular functions.

## Evidence

`speakermining/src/process/entity_disambiguation/orchestrator.py`, `speakermining/src/process/entity_deduplication/orchestrator.py`, `documentation/coding-principles.md`. TODO-017 column trimming was implemented in `run_phase31` instead of in the notebook (see archive/additional_input.md batch 5).

## Definition of done

1. Audit Notebooks 31 and 32 to identify all steps currently delegated to `run_phase31`/`run_phase32` and not represented as notebook cells.
2. Each logical step becomes a notebook cell calling a granular module function, with visible output after each step. The `run_phase3x` wrappers are removed or deprecated.
3. TODO-017 column trimming is applied inside `build_aligned_*` functions, not inside `run_phase31` (completed 2026-04-24).
4. Notebooks 31 and 32 can be run cell-by-cell with intermediate results visible.

## Context

This was likely introduced when Claude Code generated code without following notebook-first conventions. Fix before any further Phase 31/32 work. Related: `claude-md-coding-conventions` task, which extends CLAUDE.md to explicitly prevent this pattern recurring.
