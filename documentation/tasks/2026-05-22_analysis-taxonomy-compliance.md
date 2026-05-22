# analysis-taxonomy-compliance

* priority: low
* scope: documentation
* legacy-id: TODO-066

## Summary

The analysis angle taxonomy (property types A/B/C/D, function types F1–F5) and its visualization mapping must be consistently applied across all documentation and all notebook cells, but this has not been audited.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F13; `2026-04-29_Initialization/open-tasks.md` TASK-A12.

## Definition of done

1. `documentation/analysis/README.md` lists all analysis angles by property type (A/B/C/D) and function type (F1–F5).
2. `50_analysis.ipynb`: each Step C cell opens with a comment identifying its F-type (e.g. `# F1 — gender distribution`).
3. The §6 visualization mapping table (in `documentation/analysis/`) covers every F-type and matches `visualization-principles.md`.
4. No analysis angle is described only in narrative terms — all reference their property type and function type.
