# Wikidata TODO Resolution Plan (2026-04-07)

This folder is the working plan for clearing the Wikidata backlog from `documentation/Wikidata/wikidata_todo_tracker.md`.

## Scope

- Source backlog items: WDT-001 through WDT-019.
- Orchestration anchor: `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`.
- Main implementation surface: `speakermining/src/process/candidate_generation/wikidata/`.

## Planning Goals

1. Carry over all WDT items into a grouped execution plan.
2. Identify cross-cutting dependencies and resolve items in dependency-aware waves.
3. Attach each item to concrete code touchpoints and expected test/documentation updates.
4. Separate completed baseline items from unresolved work while preserving migration policy across both migration tracks:
  - v2 logic-rework continuity: preserve working behavior from v2
  - v3 event-sourcing continuity: preserve event integrity, determinism, replay/recovery guarantees
  - apply low-risk improvements quickly
  - do not block rollout on known legacy-unsolved issues unless they are regressions
5. Treat documentation overhaul as a first-class deliverable so the final state is accurate, current, and internally consistent.

## Documents

- `01_todo_inventory_and_grouping.md`
  Full WDT inventory and grouping by shared implementation thread.
- `02_issue_analysis.md`
  Thorough codebase analysis per WDT item (current state, gaps, affected modules, risks).
- `03_resolution_roadmap.md`
  Sequenced implementation roadmap with waves, acceptance criteria, and deliverables.
- `04_execution_progress.md`
  Wave 1 (WDT-007) execution log with implemented changes, validation evidence, and completion.
- `05_wave2_domain_events_progress.md`
  Wave 2 Phase 1 (WDT-009) domain event introduction with architecture impact and next steps.
- `06_complete_session_summary.md`
  Complete session summary covering WDT-007 closure and Wave 2 Phase 1 domain events.

## Notes

- Existing completed items (`WDT-004`, `WDT-005`, `WDT-006`) are retained as baseline controls and include verification tasks to prevent regressions while solving remaining items.
- This plan intentionally assumes documentation can lag code; contract and workflow docs must be refreshed as storage and projection formats change (especially for `WDT-013` and `WDT-014`).
- Plan sequencing was reworked with lessons from:
  - `documentation/Wikidata/2026-04-02_jsonl_eventsourcing`
  - `documentation/Wikidata/2026-04-03_eventsourcing_potential_unlock`
- Latest tracker integration includes WDT-019 implementation (Notebook 21 fallback config integrity now uses single-source derivation + fail-fast validation).
- Final delivery target: one clean documentation state that accurately represents the implemented runtime behavior and data contracts.
