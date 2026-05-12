# Detailed Findings

Priority order: findings are listed by likelihood of producing wrong calculations or wrong published totals, not just by architectural cleanliness.

## F-04 — Age-at-appearance statistics are calculated from age values, not appearance counts

**Severity:** High

The age chart path computes `appearance_age` correctly per appearance, but then passes that numeric age column into `compute_carrier_stats` as the `appearance_column`. That helper sums the chosen appearance column, so the resulting `appearance_count` and `pct_by_appearance` values become sums of ages instead of counts of appearances.

Evidence:
- `compute_carrier_stats` sums the selected appearance column rather than counting rows: [speakermining/src/process/analysis/universal_stats.py](../../../speakermining/src/process/analysis/universal_stats.py#L26)
- The age summary builds `appearance_age` as a numeric difference in years: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L993)
- The same cell passes `appearance_age` into `compute_carrier_stats` as the `appearance_column`: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L999)
- Age is defined as a per-appearance derived property, so the summary should report appearance counts rather than age totals: [documentation/50_Analysis/2026-04-30_restructuring/00_requirements.md](../2026-04-30_restructuring/00_requirements.md#REQ-P05)

Impact:
- The age distribution table reports inflated `appearance_count` values that are not counts at all.
- Any percentages derived from those values are also wrong, so the published age chart can misstate the distribution.
- Because the bug lives in a shared helper call, the wrong aggregation is systematic, not a one-off display issue.

Recommendation:
- Pass a true count column such as `appearance_count` into `compute_carrier_stats`, or use a dedicated age summary helper that separates value aggregation from appearance counting.

## F-03 — The notebook violates the module-orchestration boundary and duplicates core logic

**Severity:** Medium

The current notebook does substantial computation itself: it manually builds occurrence matrices, computes co-occurrence pairs, runs per-property aggregation, performs JSON exports, and generates README content. Some of this logic already exists in `process.analysis`, but the notebook repeats it or reimplements it inline.

Evidence:
- Manual occurrence-matrix construction and sorting logic in the notebook: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L546)
- The notebook also invokes `build_role_occurrence_matrices` from the module later, so both handwritten and module-backed implementations coexist: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L643)
- Manual co-occurrence computation appears again in the notebook: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2701)
- Module-side helpers already exist for occurrence matrices: [speakermining/src/process/analysis/occurrence_matrix.py](../../../speakermining/src/process/analysis/occurrence_matrix.py#L381)
- The binding review principle says modules compute and the notebook orchestrates: [documentation/50_Analysis/2026-05-04_finalization/03_intermediate_review.md](../2026-05-04_finalization/03_intermediate_review.md)

Impact:
- Logic divergence becomes likely because there is no single canonical implementation.
- Changes to the module path can leave the notebook path stale, or vice versa.
- The notebook becomes harder to reason about because it mixes orchestration, transformation, and export responsibilities.

Recommendation:
- Consolidate the transformation logic in `process.analysis` and keep the notebook focused on loading inputs, invoking module functions, and reporting results.

## F-01 — `analysis_summary.json` is overwritten with a different schema

**Severity:** High

The notebook writes `analysis_summary.json` in two different cells with two different payload shapes. The first write happens in the analysis summary cell, and the second write happens later in the export section. Because both writes target the same path, the later cell silently replaces the earlier summary.

Evidence:
- First write: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L1089)
- Second write: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2827)
- Later read before README generation: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2890)

Impact:
- The earlier summary structure is lost.
- Any downstream consumer that expects the first schema will see the second schema instead.
- The overwrite also makes the notebook output order-sensitive: re-running a later cell changes the artifact without changing the earlier computation.

Recommendation:
- Keep a single canonical `analysis_summary.json` schema, or split the two payloads into distinct files with explicit names.

## F-02 — `per_show_stats` is reused for incompatible DataFrames

**Severity:** High

The variable `per_show_stats` is first used for the per-show guest statistics table, then later reassigned to the source-coverage table returned by `compute_per_show_coverage`. The README-generation cell then passes the overwritten variable into `generate_all_readmes`.

Evidence:
- Guest per-show stats are built at [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2617)
- Coverage stats overwrite the same variable at [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2960)
- README generation consumes `per_show_stats` at [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2893)
- The README generator expects `episode_count`, `guest_appearances`, `unique_guests`, and `avg_guests_per_episode` columns: [speakermining/src/process/analysis/readme_generator.py](../../../speakermining/src/process/analysis/readme_generator.py#L60)
- The generator’s per-show display logic also filters for those columns: [speakermining/src/process/analysis/readme_generator.py](../../../speakermining/src/process/analysis/readme_generator.py#L91)

Impact:
- The wrong table is fed into the README generator.
- The generator will either produce incorrect statistics or fail when it tries to sum columns that do not exist on the coverage table.
- This is not just a naming issue; it changes the data written to the published README files.

Recommendation:
- Use distinct names, e.g. `guest_per_show_stats` and `coverage_per_show_stats`, and pass the intended table explicitly into README generation.

## F-05 — Notebook section numbering is duplicated and out of order

**Severity:** Low

The notebook reuses section numbers and includes out-of-order headings, which makes the cell structure harder to navigate and makes cross-references fragile.

Evidence:
- `## 16. Network & Co-occurrence Analysis (TASK-B10)`: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2701)
- `## 16. Meta-Analysis: Source Coverage (TASK-B24)`: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L2908)
- `### 11b. Person Quality Tier Summary (TASK-F16)`: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L1103)

Impact:
- Human navigation becomes error-prone.
- References in comments or documentation can point to the wrong section.
- The notebook reads like an evolving scratch pad rather than a stable orchestration script.

Recommendation:
- Renumber sections sequentially or drop the numbering entirely if the cells are not intended to be stable references.

## F-06 — Visualization caching skips only on PNG existence, not on the full output bundle

**Severity:** High

The shared visualization exporter treats a matching figure checksum plus an existing PNG as sufficient to skip regeneration. That is weaker than the repo requirement, which says caching must only skip when the input checksum is unchanged, the output exists, and the output checksum matches the recorded checksum. The current helper also writes PNG, PDF, and optional HTML as a bundle, but the cache check only validates the PNG file.

Evidence:
- `save_fig` and its cache check are implemented in [speakermining/src/process/analysis/viz_base.py](../../../speakermining/src/process/analysis/viz_base.py#L60)
- The skip condition only checks the cached figure checksum and PNG existence: [speakermining/src/process/analysis/viz_base.py](../../../speakermining/src/process/analysis/viz_base.py#L72)
- The helper writes the PNG output first and then the PDF/HTML bundle: [speakermining/src/process/analysis/viz_base.py](../../../speakermining/src/process/analysis/viz_base.py#L78)
- The requirement explicitly calls for input checksum, output existence, and output checksum before skipping: [documentation/50_Analysis/2026-04-30_restructuring/00_requirements.md](../2026-04-30_restructuring/00_requirements.md#REQ-A02)

Impact:
- If the PNG survives but the PDF or HTML is deleted, truncated, or stale, the next run still skips regeneration.
- The cache can therefore report a figure as current while part of the published bundle is missing or outdated.
- This is a direct mismatch with the documented checksum-based caching contract.

Recommendation:
- Track and validate the full emitted bundle before skipping, or store per-output checksums so PNG, PDF, and HTML are all covered by the cache decision.

## F-07 — The final show-color registry accepts placeholder show IDs as real shows

**Severity:** Medium

`build_show_color_registry` assigns colors to every non-empty `show_id`. It does not reject sentinel values such as `NONE`, so placeholder rows can consume palette slots and appear in the published ordering. The notebook’s visualization staging table includes `NONE` rows, and that table is passed directly into the registry builder.

Evidence:
- The registry builder only checks for truthiness before assigning a color: [speakermining/src/process/analysis/viz_final.py](../../../speakermining/src/process/analysis/viz_final.py#L117)
- Any non-empty `show_id` is accepted and appended to the order: [speakermining/src/process/analysis/viz_final.py](../../../speakermining/src/process/analysis/viz_final.py#L151-L152)
- The notebook’s staged visualization table contains `NONE` rows: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L3050)
- The same notebook table is merged into `_per_show_stats_viz` and fed into `build_show_color_registry`: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L3100) and [speakermining/src/process/notebooks/50_analysis.ipynb](../../../speakermining/src/process/notebooks/50_analysis.ipynb#L3131)

Impact:
- Placeholder rows can take real color slots and shift the ordering of actual shows.
- Final publication charts can inherit bogus legend entries or ordering positions from staging data.
- The module trusts caller cleanliness instead of enforcing the show-id contract at the boundary.

Recommendation:
- Filter sentinel IDs such as `NONE` inside the registry builder, or sanitize the staging table before it reaches the final visualization layer.

## Follow-up Scope

The current findings are enough to justify corrective work. The highest-risk items are the age aggregation bug in F-04 and the duplicated notebook logic in F-03 because those can directly produce incorrect totals and downstream outputs. The remaining adjacent risk areas are the README generation path, the visualization export helper, and any other places that reuse staged output tables without sanitizing placeholder rows.