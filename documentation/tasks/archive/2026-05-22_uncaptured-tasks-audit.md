# uncaptured-tasks-audit

* priority: high
* scope: documentation

## Summary

The 2026-05-22 migration captured all tasks from `documentation/open-tasks.md`, but several other archived files may contain open items that were never migrated. Each file below must be read and any actionable items either added to `documentation/tasks/00_index.md` or confirmed as already captured.

## Files to check

### High-risk — likely to have open items

- `documentation/archive/50_Analysis/2026-04-30_restructuring/open-tasks.md` — a separate open-tasks file from the restructuring session; unknown overlap with the migrated set
- `documentation/archive/50_Analysis/2026-05-11_review/` — a review session from after finalization (`findings.md`, `code_update_plan.md`, `test_plan.md`); likely contains new findings and action items
- `documentation/archive/task_archive/additional_input.md` — raw scratchpad batches 1–7; each batch was archived with an "Archived → TODO-XXX" marker but the full content should be spot-checked for items that may have been summarized away
- `documentation/archive/closed-tasks.md` — should contain only resolved items; verify nothing was moved here prematurely

### Medium-risk — may contain tasks embedded in prose

- `documentation/archive/phases/PHASE_ANALYSIS_INDEX.md` and `PHASE_ANALYSIS_P*.md` — pipeline status tables and open issues; the synthesis pass noted these were captured but they should be spot-checked
- `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` — earlier open-tasks file; the Phase 50 backlog (TODO-057–073) was recovered from here, but other items may remain
- `documentation/archive/speaker_mining_code.md` — original code overview; may contain TODO-like observations
- `documentation/archive/TASK_EXECUTION_PLAN.md` — an older execution plan; any open items should be in the index or explicitly closed

### Lower-risk — context/design files

- `documentation/archive/context/` — six files (alias, eventsourcing notes, JSONL potential, mention-detection diagnostics); likely no tasks but worth scanning
- `documentation/archive/31_entity_disambiguation/post-processing.md` — already referenced by `reconciliation-csv-integration`; verify no additional items
- `documentation/archive/documentation_synthesis/` — synthesis planning artifacts; likely fully extracted already
- `documentation/archive/paper/` — paper materials; any tasks should already be in the index

## Phase 2 — Task consolidation review

After the archive audit, review `documentation/tasks/00_index.md` for tasks that are really sub-steps of a shared effort and would work better grouped under a parent large task. Two cases to handle:

**Case A — Current medium tasks that belong together.** If a set of medium tasks share a common parent (e.g. all Phase 50 implementation sub-steps, all Wikidata V4 sub-steps), consider: does a large task folder already exist that should own them? If not, is the grouping valuable enough to create one? Candidate clusters to evaluate:
- Phase 50 analysis implementation (~16 medium tasks: dynamic-analysis-pipeline, class-hierarchy-walk, property-stats-tables, visualization-infrastructure, cross-property-charts, hierarchical-item-visualizations, scalar-extended-plot-families, person-level-analysis, data-quality-followups, analysis-taxonomy-compliance, exploratory-analysis-angles, quality-tier-classification, output-folder-readmes, gitignore-analysis-outputs, appearance-totals-validation, unclassified-persons-fs-links)
- Wikidata V4 sub-tasks: roles-projection-fix, instances-csv-dual-write, node-integrity-pass-performance, property-hydration-config-alignment, seed-removal-propagation may belong inside `wikidata-v4-rework/` as tracked sub-tasks rather than standalone medium tasks
- Transcript/NLP chain: transcript-acquisition-pipeline (already large) with guest-speaking-time, named-entity-co-mention, topic-demographic-correlation as explicit sub-tasks within it

**Case B — Large tasks found in the archive that should be moved, not unwrapped.** If an archived file is itself a large-task structure (mission doc, progress log, design spec), do not decompose it into individual medium tasks. Move or transform it into a `documentation/tasks/2026-MM-DD_<slug>/` folder, preserving its internal structure, and add a single large-task entry to `00_index.md`.

## Definition of done

1. Every file in the Phase 1 list above has been read.
2. Any open item found is either: (a) already in `documentation/tasks/00_index.md` (noted as confirmed), or (b) added as a new task entry.
3. A short verdict (confirmed captured / X new tasks added) is written next to each file in this task's Notes section.
4. `documentation/archive/closed-tasks.md` is verified: every item there is genuinely resolved.
5. Phase 2 consolidation review complete: each candidate cluster evaluated; decision (group / keep separate / move into existing large task) documented per cluster.
6. Any restructuring from Phase 2 is reflected in `00_index.md`.

## Notes

### Phase 1 — Per-file verdicts

**High-risk files:**

- `documentation/archive/50_Analysis/2026-04-30_restructuring/open-tasks.md` — TASK-B series (TASK-B02–B28, ~25 items): all overlap with the 16 medium tasks already in the index (TODO-057–073 range). The TASK-B items are more granular sub-steps within those tasks. No additional tasks needed; TASK-B dependency graph captured in `phase-50-analysis-implementation/README.md`. **Verdict: covered by existing tasks + large task README.**
- `documentation/archive/50_Analysis/2026-05-11_review/` (code_update_plan.md, findings.md, test_plan.md) — 7 concrete bugs (F-01–F-07) in `50_analysis.ipynb`. **7 new bug-fix sub-tasks added** to `phase-50-analysis-implementation/`.
- `documentation/archive/task_archive/additional_input.md` — All 7 batches properly archived with TODO cross-references. **Verdict: confirmed captured.**
- `documentation/archive/closed-tasks.md` — 20+ genuinely resolved items. No premature archiving found. **Verdict: confirmed clean.**

**Medium-risk files:**

- `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` — TASK-A02/A03/A04/A05/A09/A11/A12/A13: all covered by existing migrated tasks. TASK-A10 (numbers in top-X lists + "most relevant person" metric) partially captured in `person-level-analysis`; items 3 and 4 added to that task's definition of done. **Verdict: confirmed captured (with person-level-analysis update).**
- `documentation/archive/phases/PHASE_ANALYSIS_INDEX.md` — No new tasks; all referenced TODOs already migrated. **Verdict: confirmed captured.**
- `documentation/archive/phases/PHASE_ANALYSIS_P2.md` — F-012 (season misclassification Q3464665 in broadcasting_program path, LOW) is not a standalone task; the `v4-architecture-documentation` task covers governance documentation. `wikidata_roles empty` covered by `roles-projection-fix`. **Verdict: confirmed captured.**
- `documentation/archive/phases/PHASE_ANALYSIS_P31_P32.md` — OpenRefine questions covered by `reconciliation-csv-integration`; TODO-004 covered by `mention-category-propagation`; wikidata_roles covered by `roles-projection-fix`. **Verdict: confirmed captured.**
- `documentation/archive/phases/PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md` — All open tasks reference already-migrated TODOs. **Verdict: confirmed captured.**
- `documentation/archive/phases/PHASE_ANALYSIS_PRE_P1.md` — All Phase 1 tasks are already migrated. **Verdict: confirmed captured.**
- `documentation/archive/speaker_mining_code.md` — "Forbidden Features catalogue / Data Privacy catalogue" (Future Work) was not previously captured. **1 new task added:** `data-privacy-catalogue`.
- `documentation/archive/TASK_EXECUTION_PLAN.md` — All tasks reference already-migrated TODOs; Wave 2b wired correctly. **Verdict: confirmed captured.**

**Lower-risk files:**

- `documentation/archive/context/` (6 files) — No TODO or TASK patterns found. **Verdict: confirmed clean.**
- `documentation/archive/31_entity_disambiguation/post-processing.md` — OpenRefine workflow all covered by `reconciliation-csv-integration`. **Verdict: confirmed captured.**
- `documentation/archive/documentation_synthesis/` — Steps 4–7 explicitly superseded by GitHub-ready restructuring (note in PLAN.md). **Verdict: confirmed superseded.**
- `documentation/archive/paper/` — LaTeX compilation artifacts; no TODO patterns. **Verdict: confirmed clean.**

### Phase 2 — Consolidation review

**Phase 50 analysis cluster (~16 medium tasks):** Grouped into new large task `phase-50-analysis-implementation/`. All 16 `.md` files moved into the folder; 7 bug-fix sub-tasks added; dependency order documented in README. **Decision: grouped.**

**Wikidata V4 satellites (roles-projection-fix, instances-csv-dual-write, node-integrity-pass-performance, property-hydration-config-alignment, seed-removal-propagation):** Kept as standalone medium tasks in `00_index.md` for visibility (roles-projection-fix is in-progress/high priority). The `wikidata-v4-rework/README.md` updated to list all 6 related tasks with links. **Decision: keep standalone, document relationship in large task README.**

**Transcript/NLP chain (guest-speaking-time, named-entity-co-mention, topic-demographic-correlation):** Kept as standalone medium tasks. `transcript-acquisition-pipeline/README.md` updated to reference all 3 downstream tasks with links. **Decision: keep standalone, document relationship in large task README.**
