# Code Update Plan

This plan turns the verified findings in [findings.md](findings.md) into a concrete edit sequence for `speakermining/src/process/notebooks/50_analysis.ipynb` and the affected analysis modules.

Priority is based on correctness risk: fix calculation bugs first, then boundary/validation issues, then cleanup.

## 1. Fix the age aggregation bug first

### Problem
The age summary cell in `50_analysis.ipynb` passes `appearance_age` into `compute_carrier_stats` as the appearance measure. That helper sums the supplied column, so the resulting `appearance_count` and percentages are age totals instead of counts.

### Target files
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)
- [speakermining/src/process/analysis/universal_stats.py](../../../../speakermining/src/process/analysis/universal_stats.py)
- [speakermining/src/process/analysis/viz_scalar.py](../../../../speakermining/src/process/analysis/viz_scalar.py)

### Concrete edit sequence
1. Update the age summary path in the notebook so the age table uses a true count column for `compute_carrier_stats`.
1. Prefer `appearance_count=1` on the age frame and pass that column into the helper, or add a dedicated age-summary helper if the summary needs separate count/value semantics.
1. Verify the age chart output still uses `appearance_age` only for the value axis and not for counting.
1. If `viz_scalar.py` reuses the same age summary logic, update it to share the corrected count/value split instead of rebuilding the old pattern.

### Validation
- Re-run the age-summary cell and confirm the published `appearance_count` values are counts, not sums of ages.
- Confirm the age distribution percentages remain within expected bounds.
- Run the narrow notebook slice or a targeted module test for the age distribution path.

## 2. Consolidate the notebook/module boundary

### Problem
The notebook still performs manual occurrence matrix construction, co-occurrence counting, property aggregation, exports, and README generation in places where modules already exist.

### Target files
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)
- [speakermining/src/process/analysis/occurrence_matrix.py](../../../../speakermining/src/process/analysis/occurrence_matrix.py)
- [speakermining/src/process/analysis/person_analysis.py](../../../../speakermining/src/process/analysis/person_analysis.py)
- [speakermining/src/process/analysis/readme_generator.py](../../../../speakermining/src/process/analysis/readme_generator.py)
- [speakermining/src/process/analysis/universal_stats.py](../../../../speakermining/src/process/analysis/universal_stats.py)

### Concrete edit sequence
1. Keep the notebook as the orchestration layer and move repeated transformation code into modules where the module already has an equivalent or near-equivalent helper.
1. Replace any inline duplicates with module calls, starting with occurrence-matrix logic and co-occurrence logic.
1. Make the notebook variables explicit and stable: split `per_show_stats` into semantic names so the guest table cannot be overwritten by coverage data.
1. Ensure summary generation reads the intended table and the intended summary schema only once.

### Validation
- Compare notebook outputs before and after refactoring for the affected CSV/JSON artifacts.
- Re-run the notebook slice that produces occurrence matrices, per-show statistics, and README outputs.
- Check that the README generator receives the guest stats table, not the coverage table.

## 3. Repair the summary artifact collision

### Problem
`analysis_summary.json` is written twice with incompatible schemas.

### Target files
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)

### Concrete edit sequence
1. Choose a single canonical schema for `analysis_summary.json`.
1. Remove the duplicate write, or rename one of the two outputs to a separate, clearly scoped file.
1. Update the README-generation cell so it reads the canonical summary file only.

### Validation
- Re-run the export cell and confirm only one JSON artifact is written for the canonical summary path.
- Verify downstream README generation reads the intended summary structure.

## 4. Separate guest stats from coverage stats

### Problem
`per_show_stats` is reused for unrelated DataFrames and the later reassignment can corrupt README generation.

### Target files
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)
- [speakermining/src/process/analysis/readme_generator.py](../../../../speakermining/src/process/analysis/readme_generator.py)

### Concrete edit sequence
1. Rename the guest per-show table to something explicit, such as `guest_per_show_stats`.
1. Rename the coverage table to something separate, such as `coverage_per_show_stats`.
1. Pass the guest table into `generate_all_readmes()` and the coverage table into the coverage dashboards only.
1. Add a defensive shape check in `readme_generator.py` so the generator fails fast if the required guest columns are missing.

### Validation
- Confirm the guest README output still shows `episode_count`, `guest_appearances`, `unique_guests`, and `avg_guests_per_episode`.
- Confirm coverage dashboards continue to use their own table.

## 5. Harden the visualization cache contract

### Problem
The shared visualization cache currently skips based on PNG existence plus figure checksum, which is weaker than the documented triple-check contract.

### Target files
- [speakermining/src/process/analysis/viz_base.py](../../../../speakermining/src/process/analysis/viz_base.py)
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)

### Concrete edit sequence
1. Extend the cache metadata so each visualization tracks the input checksum and the emitted output bundle, not just the figure JSON.
1. Make the skip logic require all three conditions from REQ-A02 before it short-circuits.
1. Keep the default behavior as regenerate-unless-cached, not cache-as-permanent-bypass.
1. Make sure the notebook logging still clearly says whether a chart was regenerated or reused.

### Validation
- Delete one artifact from a previously cached visualization bundle and confirm the next run regenerates it.
- Confirm a clean rerun still produces identical outputs and then reuses the cache on the second run.

## 6. Reject placeholder show IDs in the final color registry

### Problem
`build_show_color_registry()` accepts any non-empty `show_id`, so placeholder rows such as `NONE` can consume palette slots and alter ordering.

### Target files
- [speakermining/src/process/analysis/viz_final.py](../../../../speakermining/src/process/analysis/viz_final.py)
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)

### Concrete edit sequence
1. Filter sentinel values like `NONE` inside `build_show_color_registry()` rather than trusting callers.
1. Sanitize the staging table in the notebook before building the final visualizations.
1. Keep the show ordering derived from real show rows only.

### Validation
- Re-run the final visualization prep and confirm placeholder rows do not appear in the registry output.
- Confirm the published show ordering and legend colors stay stable.

## 7. Clean up section naming and follow-up wiring

### Problem
The notebook has duplicated section numbers and out-of-order headings.

### Target files
- [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb)
- [documentation/50_Analysis/2026-05-11_review/README.md](README.md)
- [documentation/50_Analysis/2026-05-11_review/findings.md](findings.md)

### Concrete edit sequence
1. Renumber the notebook sections that are duplicated or out of order.
1. Keep the review README linked to this plan and the findings file.
1. Leave the findings unchanged unless a follow-up edit promotes a newly verified bug.

### Validation
- Confirm the notebook headings read in stable order.
- Confirm the review README still points to the findings and this plan.

## Suggested execution order

1. F-04: age aggregation bug.
1. F-01 and F-02 together if the related notebook cells are already open, because they are both artifact-collision bugs in the same area.
1. F-03: module boundary consolidation.
1. F-06: cache contract hardening.
1. F-07: show registry sanitization.
1. F-05: numbering cleanup.

## Done criteria

- The age distribution uses counts, not age totals.
- The notebook no longer overwrites a summary artifact with a different schema.
- `readme_generator.py` receives the correct guest per-show table.
- Visualization caching respects the documented checksum contract.
- Placeholder show IDs do not enter the final color registry.
- The notebook remains the orchestrator; reusable logic lives in modules.