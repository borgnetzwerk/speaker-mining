# T06: Consolidate documentation/50_Analysis/ Temporal Structure

## Problem

`documentation/50_Analysis/` has 40 tracked files organized by date (temporal working-area pattern):

```
50_Analysis/
├── 2026-04-29_Initialization/    9 files — initial planning
├── 2026-04-30_restructuring/     8 files — restructuring notes  
├── 2026-05-04_finalization/     13 files — active working state
└── 2026-05-11_review/            4 files — recent code review
```

A GitHub visitor sees a folder structure that looks like a lab notebook, not project documentation. The valuable content is buried inside temporal layers.

## What each dir contains

### 2026-04-29_Initialization/
Design spec, open tasks, analysis angle structure, implementation context, existing context snapshot. **Historical — superseded by later work.**

### 2026-04-30_restructuring/
Plan, requirements, design docs, closed tasks archive, open tasks. **Historical — restructuring was executed.**

### 2026-05-04_finalization/
The most recent and richest working state:
- `visualization-design.md` — active design decisions for viz
- `10_final_visualizations.md` — finalization plan
- `03_intermediate_review.md` — code review notes (recently updated)
- `reference/Priority_Visualizations.html`, `reference/Visualizations_Critique.html` — reference HTML (tracked)
- `open-tasks.md` — open items for phase 50
- Various implementation and review files

### 2026-05-11_review/
Code update plan, findings, test plan. **Recent and active.**

## Proposed target structure

```
documentation/50_analysis/
├── README.md                     ← What this phase does (from Initialization/00_immutable_input.md)
├── design.md                     ← Merged from visualization-design.md + design spec
├── open-tasks.md                 ← Single merged open task list
├── code-review-2026-05-11.md     ← From 2026-05-11_review/ (preserve as dated snapshot)
└── archive/
    ├── 2026-04-29_Initialization/   ← Move as-is
    ├── 2026-04-30_restructuring/    ← Move as-is
    └── 2026-05-04_finalization/     ← Move residual files (the active ones extracted above)
```

## Git actions required

```bash
# Create the consolidated structure via git mv
# This is a large series of git mv commands — plan carefully before executing
# All paths under documentation/50_Analysis/ need renaming to documentation/50_analysis/
# (lowercase 'a' in analysis for consistency)
```

## Acceptance criteria

- A new GitHub visitor can find the analysis design in one file, not by navigating 4 dated directories
- Historical context preserved in archive/
- Lowercase folder name `50_analysis/` consistent with convention
- Open tasks in one place

## Notes

- `documentation/50_Analysis/2026-05-04_finalization/reference/` contains two tracked HTML files (`Priority_Visualizations.html`, `Visualizations_Critique.html`) — these are reference docs, keep them
- Two additional untracked HTML files exist in the same folder (Chart audit.html, Table audit.html) — handle separately
- The folder rename from `50_Analysis/` to `50_analysis/` is case-only on Windows (case-insensitive FS) — use `git mv` with an intermediate name to avoid issues
