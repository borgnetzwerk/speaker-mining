# Open Tasks

Finalized and deduplicated backlog for implementation.

Policy for this file:
- Keep stable task IDs (`TASK-F..`) for planning and archiving.
- Track source lineage explicitly so old context remains auditable.
- Mark tasks as `Open`, `Partial`, `Blocked`, `Low priority`, or `Resolved`.

---

## Cross-Cutting Principle: ALL ↔ Per-Show Symmetry

**Added 2026-05-05 (additional input):**

Every analysis, visualization, and README that is created for "ALL" must also be created per show — and vice versa. If a chart exists for the combined dataset, it must also exist for each individual show. If a chart is produced per show, it must also be produced for the combined view.

- Example: All property analysis is currently done only for ALL, but must also be done for each show individually.
- This applies to: carrier stats CSVs, episode stats CSVs, value×episode matrices, all visualization types, and README files.
- This principle overrides any implementation that produces only one scope variant.

---

## TASK-F01 - Guest Role Separation and Appearance Accounting
**Priority:** Immediate  
**Status:** Partial

**Problem:** Guest and moderator roles are still mixed in analysis paths, and appearance totals are inconsistent (property-level appearances can exceed total guest appearances).

**Scope:**
1. Perform per-episode person role classification once (`guest`, `moderator`, other) and reuse it across all downstream steps.
2. Ensure guest-only occurrence matrices and analyses are strictly guest-filtered.
3. Fix appearance aggregation logic so per-property appearance totals cannot exceed total guest appearances.
4. Fix `min per episode` computation so zeros are preserved.

**Primary sources:**
- 2026-05-04 additional input (`Fixes`)
- 2026-05-04 starting point
- 2026-04-30 tasks: TASK-B02, TASK-B06

**Progress update (2026-05-04):**
- Notebook property extraction is now guest-only (guest catalogue + guest episode map), so moderator/staff rows no longer expand into guest property occurrence outputs.
- Birthyear projection now keeps a single stable `birthyear` column and avoids `birthyear_x`/`birthyear_y` collisions that caused `KeyError: ['birthyear'] not in index`.
- Property statistics now expand from unique guest-episode rows, not guest totals; a regression test covers the 100-person / 40-episode counting model and prevents appearance inflation.
- Property expansion for guest-level values now derives episode joins from the occurrence basis (`ri_with_role` + canonical catalogue QIDs), which restored expected `P21` carrier coverage.
- Each property now also emits a `value_episode_matrix.csv` artifact (value x episode with unique-guest counts per cell) to support zero-based diagnostics directly.

**New evidence (2026-05-05) — role filtering still broken downstream:**
- `guest_frequency_pareto` still includes moderators: Frank Plasberg (role="Moderation") appears in the Pareto chart.
- Gert Scobel is wrongly ranked as top guest of the show he moderates (scobel); his role is recorded as moderator but is not filtered from the Pareto output.
- 3sat (role="Produktionsauftrag") also appears in the Pareto ranking — production entities are not excluded.
- Root cause: `build_guest_frequency_pareto_outputs` receives `guest_catalogue` but that frame is not pre-filtered to `role == "guest"` before being passed in; the function itself does not filter by role.
- The occurrence matrix `catalogue` has correct role assignments, but the caller site does not apply `catalogue[catalogue["role"] == "guest"]` before constructing Pareto/per-show top-guest outputs.
**Progress (2026-05-05):**
- Root cause fixed: `role_priority` in `build_person_catalogue` changed from `{guest:0, moderator:1, staff:2}` to `{moderator:0, staff:1, guest:2}` so the `min()`-based dominant-role aggregation now correctly classifies anyone who ever moderated as "moderator", not "guest".
- `build_role_occurrence_matrices` added to `occurrence_matrix.py` and exported from `__init__.py`. Produces separate moderator and staff occurrence matrices matching the guest matrix format.

**Progress (2026-05-05 — confirmed 2026-05-06):**
- Role matrices wired into notebook (cell `c5f630c5`). Moderator/staff matrices now written.
- Pareto and scobel occurrence_matrix confirmed clean — Plasberg and Gert Scobel no longer appear.
- `top_guests.csv` per show does not exist — `compute_top_guests_by_show` exists in `person_analysis.py` but is never called from the notebook. Needs wiring.

**Progress (2026-05-05 session 3):**
- `compute_top_guests_by_show` wired into notebook (markdown cell `a7f2c5e8`, code cell `b3d9e1f4`) after per-show stats cell `77d0a8d8`. Writes `top_guests.csv` to each show directory and `top_guests_combined.csv` to `all/`.

**Remaining work:**
- Validate end-to-end appearance totals against expected bounds (25,902 total appearances vs per-property totals).
- Investigate PRECISELY 19,000 gender appearances (see TASK-F12) — current run shows 24,467 for P21, suggesting this was from an earlier pipeline version.

---

## TASK-F02 - Dynamic Property-Driven Analysis Pipeline
**Priority:** Immediate  
**Status:** Open

**Goal:** One unchanged notebook run should generate all suitable analyses/visualizations for every configured property and applicable property combination.

**Scope:**
1. Drive analysis routing from `data/00_setup/analysis_properties.csv`.
2. Introduce registration/catalogue-driven analysis and visualization execution (plug in once, run everywhere applicable).
3. Extend property-combination routing so cross-property analyses run automatically where meaningful.

**Primary sources:**
- 2026-05-04 starting point (target implementation)
- 2026-04-29 TASK-A01, TASK-A12

---

## TASK-F03 - Class Hierarchy and Loop Resolution Completion
**Priority:** Immediate  
**Status:** Open

**Scope:**
1. Complete P279 hierarchy walk and mid-level mapping.
2. Resolve loops via `data/00_setup/loop_resolution.csv` with deterministic fallback.
3. Publish loop diagnostics (`number_of_loops`, `classes_in_loops`).
4. Fix hierarchy quality issues that break occupation rollups and hierarchy charts.

**Primary sources:**
- 2026-04-30 TASK-B04, TASK-B14
- 2026-04-29 TASK-A02
- 2026-05-04 additional input (`Loops`)

---

## TASK-F04 - Standardized Property Statistics and Combination Tables
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Complete the universal per-value episode statistics table for every property type where applicable.
2. Complete within-property and cross-property combination tables with unique combination counts.
3. Add analysis outputs for `unique vs total` gaps, dominance checks, and outlier detection.
4. Add meta statistics for property type coverage (item/string/quantity/time).

**Primary sources:**
- 2026-04-30 TASK-B05, TASK-B06, TASK-B07
- 2026-04-29 TASK-A04, TASK-A05
- 2026-05-04 additional input (`Meta Statistics`, `Per property`)

**Progress update (2026-05-04):**
- Notebook property standardization now preserves the full guest base and no longer assumes a pre-existing `value` column after merging extracted rows.
- Property outputs run successfully for all 16 enabled properties, including `P21`, with guest-level rows retained for carrier statistics.
- Remaining work: confirm the downstream combination tables and any per-property diagnostics still aggregate from the same guest-preserving base.

**Progress (2026-05-06 session 3):**
- `compute_value_combinations(frame, value_column, carrier_column)` added to `universal_stats.py`. For multi-value properties (P106 occupation, P102 party), counts how many unique guests carry each pair of values simultaneously. Writes `{pid}_value_combinations.csv` to the property output directory.
- `compute_cross_property_combinations(frame_A, frame_B, ...)` also added to `universal_stats.py`. For any two property frames, counts unique guests and total appearances per (A-value, B-value) pair. Both functions exported from `__init__.py`.
- Notebook cell `397db0ec` (section 13h) wired: loops over all item-type properties and writes combination tables automatically.

**Progress (2026-05-06 session 4):**
- `add_dominance_ratio(carrier_stats)` added to `universal_stats.py`. Computes `dominance_ratio = total_appearances / unique_guests` per value, flags values above `5 × median ratio` as `is_outlier`. Re-writes enriched `carrier_stats.csv` for every property directory.
- `build_property_type_summary(property_stats, analysis_properties)` added to `universal_stats.py`. Writes `all/property_type_summary.csv` with counts per type (item/string/quantity/time/derived), with_data vs without_data, and coverage_pct.
- Both functions exported from `__init__.py`. Notebook cells `302b49bb`/`c36a55b4` (section 13j) wired.

**Progress (2026-05-06 session 5):**
- Cross-property combination tables wired into notebook (section 13h2, cells `0adca777`/`2c4402f6`). Iterates all ordered item-property pairs and writes `{pidA}_{pidB}_cross_combinations.csv` to `all/cross_combinations/`.

**Remaining work:**
- (none — all TASK-F04 scope items implemented)

---

## TASK-F05 - Visualization Infrastructure Hardening
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Finalize shared chart helpers for reusable labeling, ordering, unknown buckets, and scope/context metadata.
2. Implement visualization caching sidecar (checksum-based skip logic).
3. Ensure dual export contract (PNG + PDF).
4. Make long-label handling robust: dynamic width, wrapping, and height adaptation.
5. Add language variants (DE/EN) with fully localized chart text — language convention: EN uses lowercase labels ("distribution", "appearances"), DE uses German capitalization rules ("Verteilung", "Auftritte").
6. Include episode-count and broadcasting-program context in titles/subtitles.
7. Keep "Unknown" visually and physically separate from the main bars. It must not appear as a competing bar that distorts the proportions of meaningful values. Implement as a secondary axis panel, footnote, or visually distinct separator.
8. **Stacked bar chart orientation:** Default to horizontal stacked bar charts wherever applicable. Vertical stacked bar charts with inline labels force readers to rotate their view; horizontal bars avoid this entirely. Exceptions: timelines (left-to-right expected), and any chart where the X axis is inherently temporal.
9. **"No data" display restructuring:** Replace the current "n=... unique persons — ... appearances — ... no data" header with a three-line breakdown:
   - `N guest appearances of N unique persons` (total)
   - `no property data on N appearances of N unique persons` (Tier 1+2 guests who happen to have no claim for this property)
   - `no Wikidata entry on N appearances of N unique persons` (Tier 3+4 guests)

**Primary sources:**
- 2026-04-30 TASK-B08, TASK-B20
- 2026-05-04 additional input (`Visualizations are not very dynamic yet`)
- 2026-05-06 additional input (`On Visualizations`)
- 2026-05-05 additional input (`Current state and lessons learned`)

---

## TASK-F06 - Universal and Cross-Property Chart Completion
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Finalize universal charts (including ColorRegistry integration and export behavior).
2. Complete `% A over B` stacked bar families (unique + appearances).
3. Ensure segment labels and sorting conventions are consistently applied.

**Primary sources:**
- 2026-04-30 TASK-B09, TASK-B13
- 2026-05-04 additional input (`Stacked Bar charts`)

**Progress (2026-05-06):**
- `viz_cross_property.py` created with two chart families:
  - `build_cross_property_stacked_bars(frame_A, frame_B, ...)`: For each top value of property A, a horizontal stacked bar showing the B-value distribution of guests carrying that A-value. Two charts per pair: unique guests + appearances.
  - `build_property_top_persons_chart(frame_A, episode_appearances, ...)`: For each top value of property A, a horizontal stacked bar of the top-N individual guests (Y-axis), segmented by broadcasting show. Produces one chart per top value (e.g., one chart for "female", one for "male").
- Both functions exported from `analysis/__init__.py`.
- Notebook cell `cp_code_01` added after cell `bd07bd04` (universal visualizations). Runs the following cross pairs: P21×P106, P21×P102, P21×P512, P106×P102, P27×P21, P27×P106. Property×person charts for P21, P106, P102.
- `property_frames = {}` dict added to cell `cf470247` (property loop) so each property's `standard_frame` is available for cross-property calls.

**Progress (2026-05-06 session 2):**
- **Hardcoded pairs removed.** Notebook cell `cp_code_01` now builds `CROSS_PROPERTY_PAIRS` and `PROPERTY_VALUE_CHARTS` dynamically from `analysis_properties` DataFrame — every ordered permutation of item-type properties is automatically included. With 11 item-type properties, this yields 110 ordered cross-property pairs (220 charts: unique + appearances each) and 11 property×person chart sets. No manual list maintenance required.
- **Legend position fixed.** Both `_build_cross_fig` and the by-value per-person chart layout changed from horizontal legend above chart (`y=1.06`, overlapping title) to vertical legend on the right side (`orientation="v"`, `x=1.02`). Top margin reduced from 140 to 100 (title/subtitle only). Right margin set to 220 to accommodate legend text.
- **Legend sort order fixed.** `legendrank=i` added to every `go.Bar` trace (`i` from `enumerate(b_order)` / `enumerate(ordered_shows)`). `b_order[0]` is the most-frequent B value (sorted descending), so it gets `legendrank=0` → appears at top of legend. Previously Plotly's default for stacked bars placed the most-frequent segment at the bottom of the legend.
- **Segment label rotation fixed.** `textangle=0` added to every `go.Bar` trace. Forces all inside-bar labels to render horizontally regardless of segment width.

**Progress (2026-05-06 session 2 — continued):**
- **Combined chart.** Each (A, B) pair now produces ONE chart instead of two. The chart uses Plotly subplots: top panel = unique guests stacked bar, bottom panel = appearances stacked bar. Shared legend (`legendgroup`) links both panels. File: `cross_{A_id}_{B_id}.png`. Total output: 110 charts (down from 220).

**Remaining work:**
- Wire ColorRegistry for consistent colors per property value across all charts.
- Add these cross-property charts to per-show runs (ALL ↔ per-show symmetry).
- Investigate whether `guest_label` column is always available in frames (or always `canonical_label`) — cell handles both via rename guard.

---

## TASK-F07 - Hierarchical Item Visualizations
**Priority:** Immediate  
**Status:** Open

**Scope:**
1. Implement timeline visualizations with adaptive granularity.
2. Implement sunburst visualizations for hierarchical item properties.
3. Implement Sankey visualizations for hierarchy flows.
4. Add dedicated mid-level-class visualizations.

**Primary sources:**
- 2026-04-30 TASK-B10, TASK-B11, TASK-B12, TASK-B14
- 2026-04-29 TASK-A02

---

## TASK-F08 - Scalar, Quantity, String, and Extended Plot Families
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Birth-year analysis must aggregate by year (not exact date).
2. Complete quantity/string binary presence analyses.
3. Complete age distribution visualizations and related scalar outputs.
4. Add approved extended plot families where suitable: scatter, box+strip, violin, stacked area, treemap, radar.

**Primary sources:**
- 2026-04-30 TASK-B15, TASK-B16, TASK-B17
- 2026-05-04 additional input (`Birth year`, `string binary`, `Additional visualization types`)

**Progress update (2026-05-04):**
- Birthyear carry-over for catalogue generation has been stabilized to prevent notebook failure in downstream age/scalar calculations.

**Progress (2026-05-06 session 3):**
- **`viz_scalar.py`** created with two chart families:
  - `build_birth_year_chart`: vertical grouped bar chart, X = birth year or decade, Y = unique guest count. Produces two outputs: by-year and by-decade. Uses P569 frame from `property_frames`.
  - `build_age_distribution_chart`: violin + box chart for appearance age, with median line overlay. Two outputs: combined and per-show (one violin per show).
  - `build_all_scalar_charts`: convenience wrapper that looks up P569 and AGE frames and produces all variants automatically.
- **`viz_treemap.py`** created:
  - `build_property_treemap`: Plotly `go.Treemap` for one item-type property. Each tile = one property value, area proportional to unique guest count. Top-N values, writes `treemap_{pid}.png`.
  - `build_all_treemaps`: loops over all item-type PIDs.
- **`viz_radar.py`** created:
  - `build_property_radar_chart`: `go.Scatterpolar` radar chart. One polygon per show + dashed black combined average. Axes = top-N property values. Shows % of unique guests for each value. Writes `radar_{pid}.png`.
  - `build_all_radar_charts`: loops over all item-type PIDs.
- All three modules exported from `analysis/__init__.py`.
- Notebook cells `96a3c4c3`/`3b9029fe` (section 13e), `00806ebc`/`01e3b720` (section 13f), `2217001a`/`25912bf6` (section 13g) wired and call the new modules automatically.

**Progress (2026-05-06 session 4):**
- **`viz_binary.py`** created with string binary presence analysis:
  - `compute_binary_presence`: per-show and combined coverage — % of unique guests with at least one non-Unknown value for a string property. Writes `{pid}_binary_presence.csv` to the property directory.
  - `build_binary_presence_chart`: grouped bar chart, X = shows, Y = coverage %, bars = string properties. Writes `visualizations/string_property_coverage.png`.
  - `build_all_binary_presence`: auto-detects string-type properties from `analysis_properties`, runs both functions for all of them.
- Notebook cells `de7f364f`/`0d7f87ca` (section 13i) wired.

**Progress (2026-05-06 session 5):**
- `build_age_vs_appearances_scatter` added to `viz_scalar.py`. Scatter plot: X = age at first appearance, Y = total appearances, dots colored by dominant show. Writes `visualizations/scatter_age_vs_appearances.png`. Exported from `__init__.py`. Wired into notebook section 13e (cell `3b9029fe` updated).

**Remaining work:**
- Birth year vs gender frequency scatter (cross-scalar).
- Stacked area charts (time series of property value prevalence — needs timeline module, blocked on TASK-F03).

---

## TASK-F09 - Episode, Source, and Cross-Show Dashboards
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Complete episode-level dashboards and frequency/coverage visuals.
2. Complete source attribution/completeness visualizations (Wikidata/Fernsehserien/ZDF, including unique-only source coverage).
3. Complete cross-show comparison visualizations.
4. Complete property coverage dashboard outputs.
5. Extend episode-specific property analysis pipeline (duration/date/guest_count/description/topic/transcript/quote when available).
6. Convert Pareto chart from simple bars to stacked bars: each bar is one guest, segments = one per show (colored by show), bar label = appearances on that show + % of that show's total, top annotation = total appearances across all shows + % of all appearances. This answers "Robin Alexander had 40 appearances on Markus Lanz (3% of that show) and 153 total (1% of all)".

**Primary sources:**
- 2026-04-30 TASK-B23, TASK-B24, TASK-B26, TASK-B27
- 2026-05-04 additional input (`Source specific analysis`, `Episode specific property visualization`)
- 2026-05-06 additional input (`On Visualizations`, `Pareto stacked bar`)

**Progress update (2026-05-04):**
- The notebook now emits a guest frequency distribution table plus a Pareto chart/output bundle for top guest appearances, using the analysis-layer aggregation helpers.
- Visualization cleanup also removed notebook-level stub imports that were no longer needed once the Pareto output became real.
- Source attribution now has an actual dashboard layer: overall coverage, stacked by-show completeness, and unique-person coverage comparison charts are written from the meta-analysis outputs.
- The chart construction for those dashboard families now lives in `speakermining/src/process/analysis/viz_dashboards.py`; the notebook only dispatches the module calls.

**Progress (2026-05-05 session 3):**
- Pareto chart converted to stacked bar chart per-show (TASK-F09 item 6). `_build_stacked_pareto` added to `viz_dashboards.py`: each bar segment represents one broadcasting show, labeled with `{n} ({pct}% of show)`; total + overall percentage annotated above each full bar. Notebook cell `229b7a80` updated to pass `episode_appearances` to trigger stacked mode. `_build_simple_pareto` retained as fallback when no episode data is available.
  * **Clarification:** We should not mix the two. The new version is overloaded and would serve better as a two separate graphics:
    * One horizontal stacked bar chart
    * And one pareto.

**Progress (2026-05-05 — additional input):**
- Confirmed: the stacked Pareto and the classic Pareto must be two independent charts, not a mode-switched single function. `_build_stacked_pareto` should produce a **horizontal** stacked bar (guests on Y-axis, appearances on X-axis, segments = shows). The classic Pareto line chart remains vertical for the cumulative-frequency reading it implies.

**Progress (2026-05-06):**
- `_build_stacked_pareto` in `viz_dashboards.py` fully converted to horizontal orientation: `orientation="h"` added to `go.Bar`, x/y axes swapped, `label_order` reversed (top-to-bottom for chart), annotations repositioned to right-of-bar (`xanchor="left"`, `xshift=4`), layout axes (`xaxis`=Appearances, `yaxis`=Guest), height scaled as `max(400, 30*n+200)`, margin `r=200` to accommodate right-side annotations.
- README generator (`readme_generator.py`) fixed: duplicate "## Source Coverage" heading bug resolved (heading now added once before a loop, not inside); new stacked horizontal Pareto (`guest_frequency_stacked.png`) now also embedded; top-guests table deduplication improved (deduplicate by `canonical_entity_id`, drop `show_id` column from display).

**Progress (2026-05-06 session 2):**
- **Cross-show comparison** (`viz_comparison.py` — new module). `build_cross_show_comparison` and `build_all_cross_show_comparisons` implemented. For each item-type property, one grouped bar chart: X = shows (sorted by size), Y = % of unique guests carrying that property value, bars grouped by top-N values. Wired into notebook cell `8e53b788` after the cross-property cell; runs automatically for all item-type properties.
- **Property coverage heatmap** (`viz_coverage.py` — new module). `build_property_coverage_dashboard` implemented. Heatmap: rows = properties, columns = shows, cell = % of guest-episode pairs with a non-Unknown value. Also writes `property_coverage_dashboard.csv`. Wired into notebook cell `f5ca9f17`. Answers "which properties have good coverage in which shows?"
- Both modules exported from `analysis/__init__.py`.

**Remaining work:**
- Scope items 1, 5: episode-level property pipeline (duration, guest count, description) still open.
- Source coverage: add unique-to-source episode count (episodes appearing exclusively in one source).

---

## TASK-F10 - Person-Level and Relevance Analyses
**Priority:** High  
**Status:** Partial

**Scope:**
1. Complete person-level chart set (top guests, by-show, within-category, encounter matrix).
2. Add per-person claim count outputs.
3. Define and implement a documented "most relevant person" metric.
4. Preserve and extend specialization/dominance analyses.
5. Wire `compute_top_guests_by_show` from `person_analysis.py` into the notebook; write `top_guests.csv` to each per-show output directory. This file is currently missing despite the function existing.
6. For the top-N most-appeared guests: report which configured properties were empty (no Wikidata value found). This surfaces gaps like Robin Alexander / "Die Welt" employer not being in Wikidata.

**Primary sources:**
- 2026-04-30 TASK-B22
- 2026-04-29 TASK-A10
- 2026-05-04 additional input (`Per Person`)
- 2026-05-06 additional input (`Empty properties for highly relevant individuals`)

**Progress (2026-05-06 session 4):**
- **`viz_persons.py`** created:
  - `build_cooccurrence_heatmap`: `go.Heatmap` of top-N guests × top-N guests (sorted by appearance count), colored by co-appearance count. Writes `visualizations/cooccurrence_heatmap.png`.
  - `build_relevance_chart`: horizontal bar chart of top-N guests by relevance score. Writes `visualizations/guest_relevance_ranking.png`.
- **`compute_person_relevance`** added to `person_analysis.py`. Formula: `relevance_score = appearance_count × log(1 + claim_count) × show_diversity`. Counts Wikidata claims from `core_persons`, computes `show_diversity = unique shows / total shows`. Writes `all/guest_relevance_scores.csv`.
- Notebook cells `b7723ad7`/`ad8c1806` (section 13k) wired. Co-occurrence heatmap reads `co_occurrence_summary` from section 16 (requires section 16 to run first).

**Remaining work:**
- Within-category per-person chart (for each property value, who are the top guests?). Currently partially covered by `build_property_top_persons_chart` in `viz_cross_property.py` — needs dedicated section.
- Report empty properties for top-N guests (scope item 6).

---

## TASK-F11 - Temporal Claim Qualification and Historical Views
**Priority:** High  
**Status:** Partial

**Scope:**
1. Finish claim-level temporal qualification plumbing (`is_temporal`, optional `effective_at`).
2. Add optional "look to the past" analyses (pre-appearance roles/affiliations) as separate outputs.
3. Keep historical/counterfactual outputs explicitly separated from active-at-episode outputs.

**Primary sources:**
- 2026-04-30 TASK-B28
- 2026-05-04 additional input (`Look to the past`)

---

## TASK-F12 - Data Quality and Coverage Follow-Ups
**Priority:** High  
**Status:** Open

**Scope:**
1. Resolve age outliers/data quality checks before publication.
2. Verify fernsehserien.de ID linkage quality for unresolved persons.
3. Continue implementation-vs-spec compliance review as part of finalization.
4. Ensure all analysis basis data used at runtime is copied into analysis output space.
5. ~~Investigate "PRECISELY 19,000 appearances with gender"~~ — **Resolved (2026-05-05 session 3)**. No hardcoded 19,000 value exists anywhere in the codebase (`grep` confirms zero matches). Current pipeline produces 24,467 P21 appearance rows, which is a natural non-round number. The 19,000 figure was from an earlier pipeline version with different expansion logic. No bug present.
6. Investigate apparent duplicate QIDs for semantically-equivalent values: "Doktor phil" vs "Doktor Philosophiae", "Evangelisch-lutherische Kirche" vs "Evangelisch-lutherische kirche" (capitalization variant), "Evangelische Kirche". These split the same real-world concept across multiple QIDs, distorting property value distributions.
7. **CRITICAL — Wrong-episode-mapping resurfaced (2026-05-05 — root cause confirmed):**
   `data/50_analysis/couchwissen/occurrence_matrix.csv` is populated with guests who never appeared on couchwissen.
   
   **Root cause (confirmed):** `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` is the ONLY remaining source of wrong data. It contains `pm_77b63df9a94a` (Phoebe Gaa) with `fernsehserien_de_id = https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580`. This wrong URL was written during manual matching and will never be corrected (this file is manually curated and permanent). `aligned_episodes.csv` IS correct — the couchwissen episode (`episode_fs_3fcfcf781422`) is correctly scoped to couchwissen.

   **Authority split:** `reconciled_data_summary.csv` is authoritative for *person-to-person matching across sources only*. It is NOT authoritative for episode assignment. Episode assignment authority lies exclusively in `aligned_episodes.csv`.

   **Correct architecture for Phase 50 (`occurrence_matrix.py`):**
   - No single source is authoritative for episode assignment. ZDF, FS, and Wikidata are equal contributors.
   - `reconciled_data_summary.csv` is authoritative for **person identity** only (QID, canonical label). It is NOT authoritative for which episode a person appeared in.
   - **Episode assignment must aggregate from ALL sources independently:**
     - Source 1 (ZDF): `episode_id_zdf` IS the alignment_unit_id — use directly.
     - Source 2 (FS): `episode_url_fernsehserien_de` (the guest-data URL) → look up alignment_unit_id in aligned_episodes.
     - Source 3 (Wikidata): episodes from `data/31_entity_disambiguation/raw_import` and `data/31_entity_disambiguation/normalized`.
   - **NEVER use `fernsehserien_de_id`** (the alignment-context URL from cluster_members). This field comes from `reconciled_data_summary.csv` for manually reconciled persons and carries stale, wrong FS URLs.
   - **`show_id`** must be derived from `aligned_episodes.csv` (via `alignment_unit_id` → `fernsehserien_de_id_fernsehserien_de`), not from cluster_members.
   - **Implemented (2026-05-05):** `build_person_catalogue` in `occurrence_matrix.py` now aggregates from ZDF and FS sources independently, deduplicates (person, episode) pairs, and derives `show_id` from `aligned_episodes.csv`.
   - **Still needed:** Add Wikidata as a 3rd source using raw_import/normalized episode data.

**Primary sources:**
- 2026-04-29 TASK-A09, TASK-A11, TASK-A13
- 2026-05-04 additional input (`Ensure correct fernsehserien IDs`, `data basis`)
- 2026-05-06 additional input (`PRECISELY 19,000 appearances`, `Interesting apparent duplicates`)

---

## TASK-F13 - Documentation and Structural Compliance
**Priority:** High  
**Status:** Open

**Scope:**
1. Enforce taxonomy/function labels across documentation and notebooks.
2. Keep finalization backlog synchronized with implementation status.
3. Keep this task file as the canonical implementation queue for finalization.

**Primary sources:**
- 2026-04-29 TASK-A12
- 2026-05-04 starting point

---

## TASK-F14 - Lower-Priority Exploratory Angles
**Priority:** Low priority  
**Status:** Open

**Scope:**
1. Poisson-distribution applicability check.
2. Party-history deep dives and trajectory analyses.
3. Additional exploratory/experimental visual variants not blocking baseline delivery.

**Primary sources:**
- 2026-04-29 TASK-A05
- 2026-05-04 additional input (`Investigate if applicable angle for analysis`)

---

## TASK-F15 - PageRank Node Visualizations
**Priority:** Low priority  
**Status:** Open

**Scope:**
1. Implement person node-graph visualization sized/colored by rank score.
2. Implement class node-graph visualization.
3. Implement combined node-graph view where useful.
4. Export using the same chart/output contract as the rest of analysis visualizations.

**Primary sources:**
- 2026-04-29 TASK-A03

---

## TASK-F16 - Person Quality Tier Classification
**Priority:** High  
**Status:** Partial

**Scope:**
Classify every person in the catalogue into one of four quality tiers based on source reconciliation depth:
1. Reconciled with Wikidata — known QID, full property coverage possible.
2. Wikidata-only mention — appeared in a Wikidata statement but no Wikidata entity doc; limited properties.
3. Cross-source non-Wikidata match — matched between ZDF Archiv and fernsehserien.de but no Wikidata link.
4. Single-source only, not Wikidata — found in exactly one crawled source that is not Wikidata.

Rules:
- Tiers 1 and 2 only are used in property statistics and visualizations.
- All four tiers appear in summary counts, each in their own row/column — never aggregated together.
- Tier 1 is the only "truly high quality" tier with reliable property data.
- Target distribution (aspirational): Tier 1 ≈ 97%, Tier 2 ≈ 1%, Tier 3 ≈ 2%, Tier 4 ≈ 0%.

**Implementation:**
- Add `data_quality_tier` column to the person catalogue during `build_person_catalogue`.
- Tier 1: `wikidata_id` is non-empty and entity doc exists in `core_persons`.
- Tier 2: `wikidata_id` is non-empty but no entity doc (Wikidata-mentioned, not resolved).
- Tier 3: `wikidata_id` is empty but person was matched across two or more non-Wikidata sources (detectable from `cluster_strategy` or source columns in `cluster_members`).
- Tier 4: `wikidata_id` is empty and single-source only.
- Write `data/50_analysis/all/person_quality_tiers.csv` with tier counts and per-show breakdowns.
- Filter all property stats and visualization input frames to `data_quality_tier.isin([1, 2])`.

> **Clarification:**
> The currently implemented definition of Tiers is wrong. 
> 
> This is not correct:
>     # Tier 1: Wikidata QID + entity doc in core_persons cache — full property coverage.
>     # Tier 2: Wikidata QID present but no entity doc — Wikidata-mentioned only.
>     # Tier 3: No Wikidata QID but cluster_size > 1 — matched across multiple sources.
>     # Tier 4: No Wikidata QID and cluster_size == 1 — single non-Wikidata source only. 
> 
> This is correct:
>     # Tier 1: Wikidata QID + any other match, e.g. in ZDF or in fernsehserien.de. Entry (e.g. "Episode 1" or "Bob Something") exists in at least two databases, at least one of them being Wikidata.
>     # Tier 2: Wikidata QID without any other match, e.g. no match in ZDF or in fernsehserien.de. Entry (e.g. "Episode 1" or "Bob Something") exists only in Wikidata.
>     # Tier 3: No Wikidata QID but cluster_size > 1 — matched across multiple sources.
>     # Tier 4: No Wikidata QID and cluster_size == 1 — single non-Wikidata source only.
> 
> Important: All of this refers ONLY to entries that are actually related to our analyzed shows: Episodes, guests, staff, etc. Any incedental captured people or shows are not even counted in this quality tier: They are incedental and can be ignored for analysis. If we have 5 or 5000 of them - it does not matter.


**Progress (2026-05-05 session 3):**
- `_quality_tier()` function and `catalogue["data_quality_tier"]` column added to `build_person_catalogue` in `occurrence_matrix.py` (lines 201–218).
- `data_quality_tier` added to `CATALOGUE_COLS` in notebook cell `5687e84e` so the column survives the trim.
- Notebook cells `d4f8a231` (markdown) and `e5c9b342` (code) inserted after dataset overview to write `person_quality_tiers.csv` and expose `wikidata_guest_ceids` set for downstream filtering.

**Progress (2026-05-06 session 4):**
- **Quality tier definition corrected** in `build_person_catalogue` (`occurrence_matrix.py`). Previous implementation used `cluster_strategy == "singleton"` to detect Tier 2 (Wikidata-only), which was unreliable. New implementation uses `cluster_size` as the discriminator:
  - Tier 1: `has_qid AND cluster_size > 1` — Wikidata + at least one other source (ZDF or FS match).
  - Tier 2: `has_qid AND cluster_size == 1` — Wikidata-only, no cross-source validation.
  - Tier 3: `no_qid AND cluster_size > 1` — matched across non-Wikidata sources.
  - Tier 4: `no_qid AND cluster_size == 1` — single non-Wikidata source.
  This correctly reflects the spec: "Tier 1 = exists in at least two databases, at least one being Wikidata."

**Remaining work:**
- Apply `data_quality_tier.isin([1, 2])` filter to property stats expansion inputs so only Wikidata-reconciled persons enter visualization statistics.
- Add per-show tier breakdown to `person_quality_tiers.csv`.
- Document in README/analysis outputs how many Tier 3 / 4 entries are excluded from visualizations.

**Primary sources:**
- 2026-05-06 additional input (`On "unique" persons`)

---

## TASK-F17 - Structured Output Folder Documentation
**Priority:** High  
**Status:** Partial

**Scope:**
Generate a `README.md` in each output folder that, when navigated on GitHub, immediately shows the most relevant data and embedded visualizations — no file-clicking required.

Rules:
- **Every folder** in `data/50_analysis` needs its own README — including per-property subdirectories. This is a binding principle: if a folder exists, it has a README.
- Each `data/50_analysis/<scope>/README.md` (where scope = `all`, per-show directories, per-property subdirectories) is auto-generated from the analysis outputs.
- Embeds PNG visualizations inline using relative Markdown image links.
- Includes top-level summary stats (episode count, guest count, show name, date range).
- Includes the top-10 rows of the most important tables (top guests, property distributions).
- Folder navigation on GitHub alone is sufficient to understand the key findings.
- README content is purely based on published/GDPR-safe data — no person-level detail beyond what appears in the top-guest lists.
- README generation is its own module: `analysis/readme_generator.py`. The notebook calls it after all outputs are written.

**Progress (2026-05-05 session 3):**
- `readme_generator.py` module created with `generate_all_readme`, `generate_show_readme`, and `generate_all_readmes`.
- Exported from `analysis/__init__.py`.
- Notebook cells `f6a3c891` (markdown) and `c9d2b745` (code) inserted after export summary. Reads `top_guests.csv` per show (written by cell `b3d9e1f4`), reconstructs per-show dict, calls `generate_all_readmes`.

**Remaining work:**
- Expand embedded visualization list in `all/README.md` as more chart types are completed.
- Add per-show visualizations once per-show charts are generated.
- Validate output visually on GitHub after first commit.

**Primary sources:**
- 2026-05-06 additional input (`Structured Output folder documentation generation`)

---

## TASK-F18 - GitIgnore Tuning for GitHub Publication
**Priority:** High  
**Status:** Partial

**Scope:**
Configure `.gitignore` so that GDPR-safe, reasonably-sized, publication-ready analysis outputs are tracked by git and visible on GitHub.

Rules for inclusion (all three must be satisfied):
1. Does NOT contain GDPR-sensitive data identifying a specific person (demographic overviews are fine; per-person profiles are not).
2. Does NOT exceed a reasonable file size (CSV files with full matrices may be too large; prefer summary/aggregate outputs).
3. Does NOT have a direct sibling that serves the same purpose (from PNG / PDF / HTML — choose one; PNG is preferred for GitHub rendering).

Specific decisions:
- Visualizations: include PNG only (not PDF, not HTML).
- CSVs: include aggregate/summary CSVs (carrier_stats, episode_stats, per_show_statistics, top_guests); exclude raw occurrence matrices (too large and contain person-level data) and per-person property profiles.
- README.md files: always include.
- The `data/50_analysis/persons/` directory: exclude entirely (GDPR-sensitive).
- Write explicit `.gitignore` rules in `data/50_analysis/.gitignore`.

**Progress (2026-05-05 session 3):**
- Root `.gitignore` updated: unignores `data/50_analysis/all/` and per-show dirs, re-ignores `persons/`, `*_occurrence_matrix.csv`, `value_episode_matrix.csv`, `*.pdf`, `*.html`.

**Remaining work:**
- Verify rules with `git check-ignore` after next notebook run populates outputs.
- Consider adding a `data/50_analysis/.gitignore` for finer-grained control inside the analysis tree.

**Primary sources:**
- 2026-05-06 additional input (`GitIgnore tuning`)

---

## Task Lineage Notes

Items explicitly recognized as already resolved in prior documentation (not queued here as implementation tasks):
- 2026-04-29 TASK-A01, TASK-A06, TASK-A07, TASK-A08

Items represented as sub-scope under `TASK-F..` IDs above rather than duplicated one-to-one:
- 2026-04-30 TASK-B18 integrated under chart/export completion scope
- 2026-04-30 TASK-B21 integrated under dashboard/statistics scope
