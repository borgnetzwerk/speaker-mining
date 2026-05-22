# notebook-module-duplication

* priority: medium
* scope: pipeline
* legacy-finding: F-03 (2026-05-11 review)

## Summary

`50_analysis.ipynb` contains inline implementations of logic (occurrence matrix computation, co-occurrence matrix) that already exists in the pipeline's Python modules. This duplication means the notebook and the modules can diverge, and bugs fixed in one place are silently not applied in the other.

## Evidence

Source: `documentation/archive/50_Analysis/2026-05-11_review/code_update_plan.md` (F-03) and `findings.md`.

The occurrence matrix and co-occurrence matrix computations are defined directly in notebook cells rather than imported from the appropriate module functions.

## Definition of done

1. Occurrence matrix computation in the notebook calls the module function, not a local reimplementation.
2. Co-occurrence matrix computation in the notebook calls the module function.
3. Any module function changes are automatically reflected when the notebook is re-run.
