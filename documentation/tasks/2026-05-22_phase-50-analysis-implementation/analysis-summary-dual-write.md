# analysis-summary-dual-write

* priority: medium
* scope: pipeline
* legacy-finding: F-01 (2026-05-11 review)

## Summary

`analysis_summary.json` is written twice in `50_analysis.ipynb` with incompatible schemas. The second write overwrites the first, silently discarding summary data produced earlier in the notebook.

## Evidence

Source: `documentation/archive/50_Analysis/2026-05-11_review/code_update_plan.md` (F-01) and `findings.md`.

Two separate notebook cells write to the same `analysis_summary.json` path. The schemas differ between the two writes, so the final file reflects only the second write's structure.

## Definition of done

1. `analysis_summary.json` is written exactly once, combining all required fields in a single schema.
2. No notebook cell overwrites a previously written summary file.
3. The summary schema is documented in `documentation/contracts.md` or a Phase 50 contracts section.
