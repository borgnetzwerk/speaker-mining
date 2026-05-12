# Analysis Review — 2026-05-11

Scope: `speakermining/src/process/notebooks/50_analysis.ipynb` and the `process.analysis` modules it orchestrates.

This review focuses on inconsistencies, duplicated logic, protocol violations, and related maintenance risks. The notebook is compared against the Phase 5 analysis requirements and the binding review principles in `documentation/50_Analysis/2026-05-04_finalization/03_intermediate_review.md` and `documentation/50_Analysis/2026-04-30_restructuring/00_requirements.md`.

## Overall Assessment

The notebook currently does more than orchestration. It contains several stateful transformations, writes the same summary artifact twice with different schemas, and reuses variable names across unrelated stages in ways that can change downstream outputs. The most important risks are the calculation paths: one analysis path counts from expanded appearance rows instead of the episode matrix, and another duplicates core logic inside the notebook instead of centralizing it in modules. The second-stage pass also found a visualization cache mismatch and a show-registry boundary issue in the final-viz layer. The most important risks are not stylistic: they affect the final JSON summary, the visualization bundle, and the README generation step.

## Key Findings

1. Age-at-appearance statistics are computed with the age values themselves as the appearance measure, which inflates `appearance_count` and makes the age distribution wrong.
2. The notebook performs substantial data processing and file-writing work that should live in analysis modules, and it duplicates logic that already exists in `process.analysis`.
3. `analysis_summary.json` is written twice with incompatible schemas, so the later cell overwrites earlier summary data.
4. `per_show_stats` is reused for two unrelated tables; by the time README generation runs, it no longer contains the per-show guest table that the README generator expects.
5. The shared visualization exporter skips on PNG existence only, which is weaker than the documented checksum-based cache contract.
6. The final show-color registry accepts placeholder show IDs, so staging rows like `NONE` can leak into published ordering and colors.
7. The notebook’s section numbering is duplicated and out of order, which makes references fragile and complicates review and maintenance.

See [findings.md](findings.md) for the detailed evidence and recommendations.

Implementation plan: [code_update_plan.md](code_update_plan.md)

## Review Status

This review now covers both the notebook pass and the follow-up visualization/output-validation pass. The documented findings are concrete and reproducible from the current notebook and module code.