# Implementation Review and Improvement Plan

---

## Part 1 — Binding Principles for Phase 5: Analysis and Visualization

These principles are derived from sources spread across: `visualization-design.md`, the critical issue documentation in `documentation/31_entitiy_disambiguation/2026-04-05_critical_issue/`, all additional input archives, and the task history. They are the canonical, binding specification that every implementation in Phase 5 must follow. Spec documents take a back seat to these when they conflict.

---

### PRINCIPLE-1: No Source Hierarchy — All Sources Are Peers

**Origin:** Root cause analysis of the Phase 31 critical bug (`root_cause_analysis.md`) and the issue investigation (`issue.md`).

The core failure that corrupted the entire occurrence matrix was the assumption that fernsehserien.de is the authoritative episode source. It is not. ZDF Archiv, Wikidata, and fernsehserien.de are three equal, partially overlapping sources. None is a superset of the others.

**Binding rules:**

1. The episode universe for every analysis is the **union** of all three sources, mediated by `aligned_episodes.csv`.
2. `alignment_unit_id` is the only permitted canonical episode identifier in Phase 5. `fernsehserien_de_id` used as an episode column header is a bug.
3. `fernsehserien_de_id` at the episode level (the FS episode URL) must never be used as a join key for person–episode relationships. Use `alignment_unit_id`.
4. `fernsehserien_de_id_fernsehserien_de` (the show-level FS slug, e.g. `markus-lanz`) is still valid as a **show** identifier — the distinction matters.
5. For air date ordering: use `publikationsdatum_zdf` first, `premiere_date_date_fernsehserien_de` as fallback, Wikidata date as last resort.
6. No episode may be silently dropped from the occurrence matrix because it lacks a fernsehserien.de record.

---

### PRINCIPLE-2: Role Classification Happens Once, Is Reused Everywhere

**Origin:** TASK-F01, additional input of 2026-05-04 and 2026-05-05, `00_starting_point.md`.

Every person appearing in any episode carries exactly one role per episode: `guest`, `moderator`, `staff`, or `incidental`. This classification must be:

- **Computed once** at catalogue/occurrence-matrix construction time (`build_person_catalogue`).
- **Stored** in the person catalogue and persisted in the occurrence matrix outputs.
- **Never overridden or re-computed** by downstream steps.
- **Consistently applied**: if a person has `role == "moderator"` in the catalogue, they must not appear in any guest analysis output, guest Pareto chart, per-show guest ranking, or property statistic that is scoped to "guests".

Separate occurrence matrices are the canonical output form:
- `guest_occurrence_matrix.csv` — persons with `role == "guest"` only.
- `moderator_occurrence_matrix.csv` — persons with `role == "moderator"`.
- `staff_occurrence_matrix.csv` — persons with roles like `Produktionsauftrag`, `Redaktion`, etc.

All downstream analysis and visualization modules accept a pre-filtered frame. They never filter by role themselves — they trust the input is already scoped correctly.

---

### PRINCIPLE-3: The Canonical Analysis Data Flow

**Origin:** Additional input "For Documentation" (2026-05-05, archived), `00_starting_point.md`.

Every analysis step follows this chain. No step may skip a level or derive values from a non-canonical predecessor:

```
1. Episode universe (aligned_episodes.csv — full union, alignment_unit_id as key)
        │
        ▼
2. Guest × Episode binary occurrence matrix
   Rows: canonical_entity_id (guests only, role == "guest")
   Columns: alignment_unit_id
   Values: 1 if guest appeared, 0 if not
        │
        ▼
3. Per-property Value × Episode matrices
   One matrix per property (e.g. P21 gender, P106 occupation, P569 birth year, ...)
   Rows: property value (QID label, year, string, ...)
   Columns: alignment_unit_id (same column set as the occurrence matrix)
   Cell value: count of unique guests carrying this value who appeared in that episode
               (0 = none; 1 = exactly one; N = N guests with this value were present)
        │
        ▼
4. Derived statistics (carrier counts, episode coverage, appearance totals, ...)
        │
        ▼
5. Visualizations
```

A cell value of 0 in the value×episode matrix means "no guest with this property value appeared". This makes zero-based queries trivial: episodes without a female guest = count of zeros in the P21/Q6581072 row.

Appearance totals derived from any downstream step **must** remain bounded by the total guest appearances from the occurrence matrix. Per-property appearance totals cannot exceed total guest appearances. Any violation is a counting bug.

---

### PRINCIPLE-4: Single Responsibility — Modules Compute, Notebook Orchestrates

**Origin:** `visualization-design.md`, all progress notes.

- **`speakermining/src/process/analysis/` modules** own: data transformations, statistics computation, chart construction, file exports.
- **The notebook** owns: loading raw inputs, calling module functions in sequence, displaying summary text, passing outputs between steps.
- No chart construction, file I/O, or statistical aggregation lives in notebook cells. Every notebook cell that builds a figure or writes a file is a violation.
- Module functions must be idempotent and safe to call multiple times in the same session (same output, no side effects beyond writing files).
- Module functions accept an `output_dir` / `viz_dir` argument — they never hard-code paths.

---

### PRINCIPLE-5: The Dynamic Property-Driven Pipeline

**Origin:** `00_starting_point.md`, TASK-F02.

The analysis is driven entirely by `data/00_setup/analysis_properties.csv`. Adding a new property to that file and re-running the notebook must automatically produce all applicable analyses and visualizations for that property.

- Analysis types are registered once. The routing logic reads the property type (item/quantity/string/time) and dispatches to all registered handlers for that type.
- Adding a new visualization type means: implement it, register it for the applicable property types, done. No per-property code.
- Cross-property combinations are similarly routing-driven: define which property pairs are meaningful, register the combination analysis, it runs automatically.

---

### PRINCIPLE-6: Visualization Contract

**Origin:** TASK-F05, TASK-F06, additional input visualization principles.

Every chart produced by the pipeline must satisfy all of the following:

1. **Dual export**: PNG and PDF, always. The notebook displays the PNG; the PDF is for print/publication.
2. **Labeled segments**: Every bar, segment, or slice is labeled with its value. No chart requires the reader to look up a legend to understand segment sizes.
3. **Dynamic layout**: Chart width and height adapt to content. Long labels trigger line-breaking and increased vertical space allocation. No static `figsize` that clips labels.
4. **Unknown bucket**: Every categorical distribution includes an explicit "Unknown" row/segment for carriers without a value for that property. Unknown is always placed last.
5. **Other grouping**: Top-N displays group the remainder as "Other" rather than discarding them.
6. **Scope metadata in title/subtitle**: Every chart title or subtitle states the episode count and the broadcasting program(s) covered (e.g., "Markus Lanz: 2200 episodes | Caren Miosga: 400 episodes").
7. **Language variants**: Every chart is produced in both German (DE) and English (EN). Every hardcoded string (axis labels, legend entries, category names) must go through a localization mapping — no raw German or English literals embedded in chart-building code.
8. **ColorRegistry**: Persistent color assignment so the same value gets the same color across all charts and runs.
9. **Caching sidecar**: Charts are only rebuilt when their input data checksum changes. A `.viz_cache.json` sidecar tracks checksums per chart output path.
10. **Sorting convention**: Bars sorted descending by appearance count. Unknown always last. Other always second-to-last.

---

### PRINCIPLE-8: Show Everything — Every CSV Gets a Visualization

**Origin:** Additional input "General principle: Show everything we found" (2026-05-06, archived).

This is a guideline, not an absolute rule, but it must be the default posture: if a statistic is computed and written to a CSV, a corresponding chart should be produced. Stats that are never visualized are effectively invisible to readers — visualizations are the primary interface for the analysis audience.

**Binding default:** When a new CSV output is added to the pipeline, a visualization for that output must be planned in the same task or explicitly deferred with a reason. Being displayed in a README, e.g. as a statistics table on top of a property README, also counts as "visualized".

**Exceptions:** Very large matrices (occurrence matrices, value×episode matrices) are not individually charted — they feed into other aggregations that are charted. Internal diagnostic files (cache files, checksums) are exempt.

---

### PRINCIPLE-7: Appearance Counting Is Bounded

**Origin:** TASK-F01, `00_starting_point.md` (appearance inflation bug).

- **Total guest appearances** = number of (guest, episode) pairs in the occurrence matrix where the cell is 1.
- **Per-property appearance count** for a value V = number of episodes where at least one guest carrying V appeared. This is the sum of the V-row in the value×episode matrix (counting non-zero cells), or optionally the sum of unique-guest counts per episode across the V-row.
- The per-property total must always be ≤ total guest appearances. If it exceeds it, the counting logic is wrong.
- **`min per episode`** for any property value is the minimum over all episodes (including zeros). It is almost always 0 for most values, because most episodes have no guest with that value. Reporting 1 as min-per-episode is a bug that hides zero coverage.

---

## Part 2 — Task-by-Task Review

---

### TASK-F01 — Guest Role Separation and Appearance Accounting

**What it should achieve:**
Role classification (guest/moderator/staff/incidental) is computed once per person at catalogue construction, stored in the catalogue and occurrence matrix, and used verbatim by every downstream step. The Pareto chart, per-show top-guest ranking, property statistics, and all occurrence outputs cover exclusively the `role == "guest"` population. Moderators, hosts, and production companies never appear in guest analysis. Separate occurrence matrices exist per role type.

**What the implementation achieves today:**
- `build_person_catalogue` in `occurrence_matrix.py` does compute a `role` column using `role_map` and `role_priority`. The logic maps fernsehserien.de role strings to internal role labels and allows an override set of `moderator_qids`.
- Property extraction and property statistics correctly filter to guest-only rows (using `ri_with_role` filtered to `role == "guest"`).
- `value_episode_matrix.csv` is emitted per property.
- Birthyear collision fixed; regression test for bounded appearance totals exists.

**Where it still fails / pending validation:**
- The Pareto IS called with `guest_cat` (already `role == "guest"` filtered). Root cause of Plasberg/Scobel appearing was the **inverted `role_priority` dict**: `{guest:0, moderator:1}` made `min()` select "guest" over "moderator" for people who appeared in both roles. **Fixed 2026-05-05**: priority changed to `{moderator:0, staff:1, guest:2, incidental:3}`.
	* **Clarification:** We must identify a persons role on an episode basis, not on the show basis. use guest_occurrence_matrix to identify guests appearing in an episode.
- `moderator_occurrence_matrix.csv` and `staff_occurrence_matrix.csv` were missing. **Fixed 2026-05-05**: `build_role_occurrence_matrices` added to `occurrence_matrix.py`, exported from `__init__.py`, and wired into the notebook (cell `c5f630c5`) after the guest matrix cell.
- `min per episode` — the `compute_episode_appearance_stats` code looks correct (reindexes to all episodes with fill_value=0 before taking min). Needs validation on next notebook run; may have been fixed already.
- End-to-end appearance totals: `total_guest_appearances = 25,902` at last run with ~4,864 episode columns. Needs cross-check against per-property totals.

**Next steps and implementation plan:**

1. **Filter guest catalogue at the call site (notebook).** Before passing to any analysis function, apply `catalogue[catalogue["role"] == "guest"]`. This single fix removes moderators and production entities from all downstream outputs immediately.
   - File: `speakermining/src/process/notebooks/50_analysis.ipynb`
   - Change: define `guest_catalogue = catalogue[catalogue["role"] == "guest"].copy()` once, then use `guest_catalogue` everywhere a guest-scoped frame is expected.

2. **Emit role-specific occurrence matrices.** In `build_occurrence_matrix` (or as a wrapper), after building the guest matrix, build analogous matrices for `role == "moderator"` and `role == "staff"` from `ri_with_role`. Write as `moderator_occurrence_matrix.csv` and `staff_occurrence_matrix.csv`.
   - File: `speakermining/src/process/analysis/occurrence_matrix.py`
   - Add a `build_role_occurrence_matrices` helper that takes `ri_with_role`, the aligned episode ordering, and `output_dir`, and writes one matrix per role.

3. **Fix `min per episode`.** The value×episode matrix already has zeros. The statistic `min_per_episode` should read directly from the matrix row minimum (including zero columns). Confirm that `compute_episode_appearance_stats` uses `value_episode_matrix.min(axis=1)` and not a filtered non-zero minimum.
   - File: `speakermining/src/process/analysis/universal_stats.py`

4. **Add end-to-end bounds assertion.** After computing all property statistics, assert that no property's `total_appearances` exceeds the sum of the guest occurrence matrix. This can be a notebook-level check or a test.

---

### TASK-F02 — Dynamic Property-Driven Analysis Pipeline

**What it should achieve:**
A single unchanged notebook execution generates all suitable analyses and visualizations for every property listed in `analysis_properties.csv`. Adding a new property to that CSV automatically produces all applicable outputs. Adding a new analysis type to the catalogue automatically applies it to all compatible properties.

**What the implementation achieves today:**
- `analysis_properties.csv` exists and is read in the notebook.
- Properties loop through extraction and statistics.
- There is no registration/routing mechanism: analysis types are called by name in notebook cells, not dispatched by property type.
- Cross-property combination analyses are not auto-generated.

**Next steps and implementation plan:**

1. **Define a property type routing table.** In `analysis/config.py` (or a new `analysis/routing.py`), map each property type (`item`, `quantity`, `string`, `time`) to a list of registered analysis/visualization callables.

2. **Implement `run_property_analysis(prop_config, data_frames, output_dirs)`.** This single entry point looks up the property type, iterates registered handlers, and calls each with the prepared data frame. The notebook calls this function in a loop over all properties.
   - File: `speakermining/src/process/analysis/pipeline.py` (new)

3. **Register existing analyses.** Port `universal_visualizations`, `compute_carrier_stats`, `compute_episode_appearance_stats`, and `value_episode_matrix` output into the registration table so they run automatically.

4. **Add cross-property registration.** Define a separate table mapping property pairs to combination analyses. The pipeline iterates all valid pairs and runs registered combination handlers.

---

### TASK-F03 — Class Hierarchy and Loop Resolution

**What it should achieve:**
For item-type properties (occupation P106, party P102, place of birth P19, employer P108, etc.), values are Wikidata items that form a class hierarchy via P279 (subclass of). The pipeline walks this hierarchy to build a mid-level class mapping (e.g., "musician" rolls up to "artist" rolls up to "creative professional"). Loops in the hierarchy are resolved deterministically via `data/00_setup/loop_resolution.csv`. Diagnostics include loop count and affected classes.

**What the implementation achieves today:**
- `load_midlevel_classes` exists in `analysis/config.py`, suggesting mid-level classes are loadable from a CSV.
- No `class_hierarchy.py` or P279 walk implementation exists.
- No loop detection or loop_resolution.csv integration exists.
- Hierarchy-dependent visualizations (sunburst, sankey, mid-level rollups) are blocked on this.

**Next steps and implementation plan:**

1. **Implement `analysis/class_hierarchy.py`.** Functions:
   - `fetch_class_hierarchy(item_qids, wikidata_cache)` — for a set of QIDs, iteratively walk P279 statements from the cache (not live Wikidata queries) to build a directed graph of superclass edges.
   - `detect_loops(graph)` — find cycles; return `(loop_count, classes_in_loops)`.
   - `resolve_loops(graph, resolution_csv_path)` — break cycles using entries in `loop_resolution.csv`; apply a deterministic fallback (sever the alphabetically-later edge) for unregistered loops.
   - `build_midlevel_mapping(graph, midlevel_classes)` — for each leaf QID, find its nearest ancestor that appears in the mid-level class list. Return a `{qid: midlevel_qid}` dict.

2. **Emit loop diagnostics.** Write `class_hierarchy_diagnostics.csv` with `number_of_loops` and `classes_in_loops` for each item-type property. Include in the notebook output.

3. **Wire into property extraction.** After `extract_item_values`, apply `build_midlevel_mapping` to add a `midlevel_value` column to item property frames. Downstream statistics and visualizations can then operate at the mid-level.

---

### TASK-F04 — Standardized Property Statistics and Combination Tables

**What it should achieve:**
For every property: a universal per-value statistics table (carrier count, episode coverage, appearances, min/max/avg per episode), a value×episode matrix, within-property combination table, and cross-property combination table where meaningful. Meta-statistics cover property type distribution.

**What the implementation achieves today:**
- `compute_carrier_stats` and `compute_episode_appearance_stats` in `universal_stats.py` produce per-value stats.
- All 16 enabled properties produce output successfully.
- `value_episode_matrix.csv` is emitted per property.
- Within-property and cross-property combination tables are not implemented.
- Meta-statistics (how many properties are item/string/quantity/time) are not implemented.
- Unique-vs-total gap analysis and dominance/outlier checks are not implemented.

**Next steps and implementation plan:**

1. **Within-property combination table.** For item-type properties with multi-value support (e.g., P106 occupation, P102 party), count how many guests carry each pair of values simultaneously. Write as `{property}_value_combinations.csv`.
   - File: `speakermining/src/process/analysis/universal_stats.py` — add `compute_value_combinations(extracted_frame, property_id)`.

2. **Cross-property combination table.** For a specified pair of properties (e.g., P21 × P106), count unique guests and appearances per combination of values. Write as `{propA}_{propB}_cross_combinations.csv`.
   - File: `speakermining/src/process/analysis/universal_stats.py` — add `compute_cross_property_combinations(frameA, frameB)`.

3. **Unique-vs-total gap analysis.** For each value, compute `total_appearances / unique_carriers`. High ratios indicate a small number of individuals dominating the count. Flag values above a threshold (e.g., ratio > 5× the property median). Integrate into the per-value stats table as `dominance_ratio` and `is_outlier`.

4. **Meta-statistics.** After all property outputs are generated, emit `property_type_summary.csv` with counts per type and basic coverage metrics.

5. **Fix `min per episode`.** See TASK-F01 step 3; same root issue.

---

### TASK-F05 — Visualization Infrastructure Hardening

**What it should achieve:**
Shared chart helpers cover: label formatting, dynamic width/height, line-breaking for long labels, unknown/other bucket insertion, scope metadata, ColorRegistry, dual export (PNG+PDF), language variants, and checksum-based caching.

**What the implementation achieves today:**
- `viz_base.py` has `save_fig`, `sort_bars_descending`, `add_unknown_row`, `add_scope_label`, `add_context_stats`, `stacked_bar_from_zero`, `place_bar_labels`, `apply_other_grouping`.
- `color_registry.py` exists.
- Missing: caching sidecar, full PDF export, language variant support, dynamic label wrapping.
- `ColorRegistry` is not wired into `viz_universal.py`.
- Chart layout uses static sizing; long labels overflow.

**Next steps and implementation plan:**

1. **Caching sidecar.** In `viz_base.save_fig`, before writing, compute a checksum of the input data frame. Compare against a per-output-dir `.viz_cache.json`. Skip writing if unchanged.
   - File: `speakermining/src/process/analysis/viz_base.py`
   - Add `_compute_df_checksum(df)` and `_load_cache(viz_dir)` / `_save_cache(viz_dir, cache)` helpers.

2. **PDF export.** Ensure `save_fig` always calls `fig.write_image(path.with_suffix(".pdf"))` in addition to PNG. Confirm `kaleido` is installed.

3. **Dynamic label wrapping.** Add `wrap_labels(labels, max_chars=25)` in `viz_base.py` that inserts `<br>` at word boundaries for Plotly text. Caller passes labels through this before building figures. Increase figure height by `n_lines * line_height_px` when wrapped labels are present.

4. **Language variant support.** Add `LABELS_DE` and `LABELS_EN` dicts in `viz_base.py` (or a new `viz_i18n.py`). Every hardcoded string (axis titles, legend entries, "Unknown", "Other", "Appearances", "Unique guests", etc.) is looked up by key. Chart-building functions accept a `lang="de"` parameter, defaulting to German. A second call with `lang="en"` produces the English variant.

5. **ColorRegistry wiring.** In `viz_universal.py`, import and use `ColorRegistry` for color assignment instead of the local cycling palette.

6. **Scope metadata.** In every chart title or subtitle: include episode count and show label(s). Pass these as parameters from the notebook call site. Update `add_scope_label` in `viz_base.py` to format "Show A: N eps | Show B: M eps" strings.

---

### TASK-F06 — Universal and Cross-Property Chart Completion

**What it should achieve:**
For every property: an "appearances" bar chart and a "unique guests" bar chart (these are the universal base charts). Additionally: `% A over B` stacked bar charts showing the distribution of property B values within each top value of property A, both for unique guests and for appearances.

**What the implementation achieves today:**
- `viz_universal.py` has `universal_visualizations` and `make_universal_chart` producing appearances and unique-guests bar charts.
- `ColorRegistry` not wired in.
- `% A over B` stacked bars are not implemented.
- Segment labeling is partially applied.
- Sorting conventions mostly follow the spec.

**Next steps and implementation plan:**

1. **Wire `ColorRegistry`.** Replace the local `_assign_colors` function in `viz_universal.py` with `ColorRegistry.get_color(label)`. Persist the registry across property runs so the same party/occupation gets the same color in every chart.

2. **Implement `% A over B` stacked bars.** Add `build_cross_property_stacked_bars(frameA, frameB, output_dir, viz_dir)` in a new `viz_cross_property.py`. For each top-N value of property A, produce a 100%-stacked bar showing the B-distribution of guests carrying that A-value. Two variants: unique-guest count and appearance count.

3. **Ensure segment labels.** Every segment in every stacked bar must carry its label (value name + percentage). Use `place_bar_labels` from `viz_base.py` consistently.

---

### TASK-F07 — Hierarchical Item Visualizations

**What it should achieve:**
For item-type properties with P279 hierarchy: timeline visualizations showing value prevalence over time, sunburst charts for class hierarchy depth, Sankey diagrams for hierarchy flows, and dedicated mid-level class analyses.

**What the implementation achieves today:**
- None of these visualization modules exist yet.
- All are blocked on TASK-F03 (class hierarchy walk).

**Next steps and implementation plan:**

1. **Implement `viz_timelines.py`.** After TASK-F03 provides the mid-level mapping, build a timeline visualization: X-axis = episode air date, Y-axis = number of guests carrying a given value (or mid-level class). Adaptive granularity: monthly for < 2 years, quarterly for 2–5 years, yearly beyond 5 years. Use Plotly `go.Scatter` with filled area.

2. **Implement `viz_sunburst.py`.** Use the class hierarchy graph to build a sunburst: root = property ID, second level = mid-level classes, outer level = leaf values. Segment size = unique guest count. Use Plotly `go.Sunburst`.

3. **Implement `viz_sankey.py`.** Show flow: top-level class → mid-level class → leaf value → episode count. Use Plotly `go.Sankey`. Primary use case: occupation hierarchy for journalism, politics, science.

4. **Register all three** in the property routing table (TASK-F02) for property type `item`.

---

### TASK-F08 — Scalar, Quantity, String, and Extended Plot Families

**What it should achieve:**
Birth year analyses aggregate by year (not exact date). Quantity and string properties have binary presence analyses. Age distributions use violin/box/strip plots. Extended plot types (scatter, treemap, radar) are available and registered for applicable property types.

**What the implementation achieves today:**
- Birth year extraction works; a `birthyear` column exists in catalogue.
- Age derivation appears in the notebook but dedicated visualization is missing.
- Violin, boxplot, scatter, treemap, radar modules do not exist.
- String properties: extraction works; binary presence visualization is missing.
- Quantity properties: extraction works; violin/binary presence missing.

**Next steps and implementation plan:**

1. **Birth year aggregation.** Confirm that birth year is always stored as a 4-digit year string (not a full date). If not, strip to year in `extract_wikidata_properties`. Add a grouped bar chart: X = birth year (or decade), Y = unique guest count. Module: `viz_scalar.py`.

2. **Violin / box+strip plots.** In `viz_scalar.py`, implement `build_violin_chart(values, labels, output_dir, viz_dir)` using Plotly `go.Violin`. Use for age distribution per show and combined.

3. **Scatter plots.** For scalar × scalar combinations (e.g., age vs. appearance count, birth year vs. gender frequency): `build_scatter_chart(x_series, y_series, output_dir, viz_dir)`. Use Plotly `go.Scatter`.

4. **String binary presence.** For string properties (e.g., Wikimedia Commons category P18, IMDB ID P345): compute per-guest whether they have a value (binary 1/0). Analyze what other properties predict presence. Write `{property}_binary_presence.csv`. Visualize as a comparison bar chart between "has value" and "no value" groups across other properties.

5. **Treemaps.** For item-type properties: a treemap where each tile is a value, area proportional to unique guest count. Per show and combined. Use Plotly `go.Treemap`. Module: `viz_treemap.py`.

6. **Radar charts.** Per show and combined. For each property: the show's percentage for the top value (e.g., % male, % journalist, % SPD). Layer individual show radar over the combined average. Use Plotly `go.Scatterpolar`. Module: `viz_radar.py`.

---

### TASK-F09 — Episode, Source, and Cross-Show Dashboards

**What it should achieve:**
Episode-level dashboards (frequency distribution, guest count per episode, episodes without guests), source coverage dashboards (how many episodes each source has, unique-to-source counts, episodes without any metadata), cross-show comparison charts, and property coverage dashboard.

**What the implementation achieves today:**
- `viz_dashboards.py` has `build_guest_frequency_pareto_outputs` and `build_source_coverage_dashboards`.
- Source attribution covers overall coverage, stacked per-show completeness, and unique-person coverage.
- `guest_frequency_distribution.csv`, `guest_frequency_pareto.csv` are written.
- Pareto output still includes moderators — see TASK-F01 new evidence.
- Cross-show comparison (`viz_comparison.py`) does not exist.
- Property coverage dashboard (`viz_coverage.py`) does not exist.
- Episode-specific property analyses (duration, guest count, description, topic) are not implemented.

**Next steps and implementation plan:**

1. **Fix moderator contamination in Pareto** (see TASK-F01, step 1). This is the immediate blocker.

2. **Implement `viz_comparison.py`.** Cross-show comparison: for each property value (e.g., P21/Q6581072 = female), a grouped bar showing the percentage across each show. This answers "is the gender distribution different between Markus Lanz and Caren Miosga?"

3. **Implement `viz_coverage.py`.** Property coverage dashboard: which properties are covered for what fraction of guests. A heatmap where rows = properties, columns = shows, cell = coverage percentage. Write `property_coverage_dashboard.csv`.

4. **Episode-specific property pipeline.** Apply the same analysis pipeline to episode-level properties: duration (P2047), air date (P577), guest count (derived), description (P836). These are episode-scoped, not guest-scoped, so the data flow differs: the occurrence matrix columns (episodes) are the subjects.

5. **Source coverage: unique-to-source count.** Add to `build_source_coverage_dashboards`: how many episodes appeared exclusively in one source (ZDF only, Wikidata only, FS only). How many had no guests? How many had no metadata at all?

---

### TASK-F10 — Person-Level and Relevance Analyses

**What it should achieve:**
Top-guest charts per show and combined, within-category rankings, encounter matrices (guests who co-appear frequently), per-person claim count, and a documented "most relevant person" metric.

**What the implementation achieves today:**
- `person_analysis.py` has `compute_top_guests_by_show` and `compute_guest_specialization`.
- `top_guests_combined.csv` is written.
- Per-person claim count is not computed.
- "Most relevant person" metric is not defined or implemented.
- Encounter (co-occurrence) matrix visualization is not implemented.

**Next steps and implementation plan:**

1. **Per-person claim count.** In `build_person_catalogue` or as a post-processing step, count `len(wikidata_doc["claims"])` for each person with a Wikidata entry. Add as `claim_count` column to the catalogue. Write to the analysis output.

2. **Define and implement "most relevant person" metric.** Proposed: `relevance_score = appearance_count × log(1 + claim_count) × show_diversity` where `show_diversity = unique shows appeared in / total shows`. Document this formula in the analysis config. Compute and rank.

3. **Co-occurrence encounter matrix visualization.** The co-occurrence matrix already exists. Implement a visualization: heatmap of top-N guests × top-N guests, colored by co-appearance count. Module: `viz_persons.py`.

4. **Within-category per-person chart.** For each property value (e.g., P21 = female), show the top individual guests. This answers "who are the most-invited female guests?"

---

### TASK-F11 — Temporal Claim Qualification and Historical Views

**What it should achieve:**
Claim-level temporal qualification is tracked (`is_temporal` flag, optional `effective_at` filter). A separate "look to the past" analysis set examines what properties guests had before their episode appearance.

**What the implementation achieves today:**
- `TEMPORAL_QUALIFIER_PIDS`, `has_temporal_claims`, `infer_temporal_properties_from_values` exist in `config.py`.
- `extract_item_values` captures `qualifier_pids`.
- `is_temporal` flag is not yet added to per-property DataFrames.
   * **Clarification:** Remember: is_temporal is a claim-level quality.  
- `effective_at` filtering in `compute_carrier_stats` is not implemented.
- "Look to the past" analyses are not implemented.

**Next steps and implementation plan:**

1. **Add `is_temporal` column.** In `extract_all_properties`, for each returned frame, add a boolean `is_temporal` column based on whether the claim's `qualifier_pids` intersect `TEMPORAL_QUALIFIER_PIDS`.

2. **`effective_at` filter (optional).** Add an optional `effective_at: str` parameter to `compute_carrier_stats`. When provided, filter to claims where the temporal qualifiers place the claim as active on that date.

3. **"Look to the past" analysis set.** As a separate notebook section (clearly marked "historical / counterfactual"), compute property values without the `effective_at` filter (i.e., all claims ever held). Produce a parallel set of statistics and charts labeled "ehem." (former). Keep these outputs in a separate subdirectory so they cannot be confused with the active-at-episode outputs.

---

### TASK-F12 — Data Quality and Coverage Follow-Ups
   * **Clarification:** Only proceed with this task (TASK-12) once all other visualizations are implemented.

**What it should achieve:**
Age outlier detection and remediation before publication, fernsehserien.de ID linkage quality verification, all analysis basis data copied into the analysis output folder, and ongoing implementation-vs-spec compliance review.

**What the implementation achieves today:**
- Age derivation exists; no outlier detection or sanity checks are implemented.
- Fernsehserien.de ID quality check: the root issue (cross-show episode merging) is documented and fixed in Phase 31's design, but re-running Phase 31 with the fix has not been done yet. Downstream IDs may still be corrupt.
- Analysis basis data is not systematically copied to the output folder.

**Next steps and implementation plan:**

1. **Age outlier detection.** After computing ages, flag persons where `age < 15` or `age > 100` as outliers. Write `age_outliers.csv`. Do not silently include them in violin/distribution charts; either exclude or mark explicitly.

2. **Fernsehserien.de ID re-run.** Apply Fix A from `root_cause_analysis.md` (show-identity check in `_match_fernsehserien_episode`), re-run Phase 31, then re-run Phase 32 and Phase 50. This is a prerequisite for trusting any FS-sourced show attribution.

3. **Analysis basis data copy.** At the start of the analysis notebook, copy the input data files used (`aligned_episodes.csv`, `dedup_cluster_members.csv`, `dedup_persons.csv`, `analysis_properties.csv`) into the analysis output directory. These are the basis for reproducibility.

---

### TASK-F13 — Documentation and Structural Compliance
   * **Clarification:** Only proceed with this task (TASK-13) once all other visualizations are implemented.

**What it should achieve:**
Consistent taxonomy and function labels across all docs and code. This file (`03_intermediate_review.md`) is the binding reference for next-step decisions. `open-tasks.md` is the canonical implementation queue.

**What the implementation achieves today:**
- `open-tasks.md` is maintained.
- Some legacy terminology (e.g., "expansion" instead of "entity_discovered") persists in older docs.
- Part 1 of this document (above) is the first consolidated binding principles definition.

**Next steps and implementation plan:**

1. **Propagate principles into CLAUDE.md** (or equivalent project-level doc) so all future sessions start from the same foundation.
2. **Audit notebooks and modules** for any remaining references to `fernsehserien_de_id` used as episode column headers and replace with `alignment_unit_id`.
3. **Sync `02_implementation_plan.md`** task statuses after each implementation session.

---

### TASK-F14 — Lower-Priority Exploratory Angles
   * **Clarification:** Only proceed with this task (TASK-14) once all other visualizations are implemented.

**What it should achieve:**
Poisson distribution applicability check for guest frequency. Party trajectory deep dives. Experimental visual variants not blocking baseline.

**Status:** Open, low priority. No implementation yet. No immediate next steps until TASK-F01 through TASK-F09 are substantially complete.

---

### TASK-F15 — PageRank Node Visualizations

**What it should achieve:**
Person node-graph visualization sized and colored by PageRank score. Class node-graph. Combined view. Exported using the same chart/output contract.

**Status:** Open, low priority. Blocked on: (a) PageRank score computation not implemented, (b) node-graph library choice not finalized (NetworkX + Plotly or pyvis). No immediate next steps until baseline pipeline is stable.

---

### TASK-F16 — Person Quality Tier Classification

**What it should achieve:**
Every person in the catalogue carries a `data_quality_tier` (1–4) based on source reconciliation depth. Only tiers 1 and 2 feed into property statistics and visualizations. All four tiers appear separately in summary counts.

- Tier 1: Wikidata QID + entity doc — full property coverage.
- Tier 2: Wikidata QID but no entity doc (Wikidata-mentioned only).
- Tier 3: Matched across two non-Wikidata sources (ZDF + fernsehserien.de) but no Wikidata link.
- Tier 4: Single non-Wikidata source only.

**What the implementation achieves today:**
- `wikidata_id` column exists in catalogue. No `data_quality_tier` column exists.
- No tier-based filtering of property stats or visualization inputs exists.

**Next steps and implementation plan:**

1. **Add tier computation in `build_person_catalogue`.** After building the catalogue, compute `data_quality_tier`:
   ```python
   def _assign_quality_tier(row, core_persons):
       qid = str(row.get("wikidata_id", "")).strip()
       if qid and qid in core_persons:
           return 1
       if qid:
           return 2
       # Tier 3 vs 4: check cluster_strategy or cross-source evidence
       strategy = str(row.get("cluster_strategy", "")).lower()
       if "cross" in strategy or "multi" in strategy:
           return 3
       return 4
   catalogue["data_quality_tier"] = catalogue.apply(lambda r: _assign_quality_tier(r, core_persons), axis=1)
   ```
   File: `speakermining/src/process/analysis/occurrence_matrix.py`

2. **Write tier summary.** After catalogue is built, write `person_quality_tiers.csv` with counts per tier and per-show breakdowns.
   File: notebook cell after catalogue construction.

3. **Filter property stats inputs.** Define `high_quality_catalogue = catalogue[catalogue["data_quality_tier"].isin([1, 2])]` and use it as the source for `guest_episode_map` and `guest_catalogue_for_props` so property stats only count tier 1+2 guests.

---

### TASK-F17 — Structured Output Folder Documentation
   * **Clarification:** Only proceed with this task (TASK-F17) once all other visualizations are implemented.

**What it should achieve:**
Each `data/50_analysis/<scope>/README.md` is auto-generated and GitHub-navigable. Opening the folder on GitHub shows embedded visualizations, top-line stats, and top-guest tables — no file clicks needed.

**What the implementation achieves today:**
- No `README.md` files exist in analysis output directories.
- No `readme_generator.py` module exists.

**Next steps and implementation plan:**

1. **Implement `analysis/readme_generator.py`.**
   - `build_readme(scope_label, stats_dict, top_guests_df, viz_paths, output_dir)` — writes `README.md` with: scope heading, episode/guest/show counts, embedded PNGs (relative paths), top-10 guest table in Markdown.
   - Called from the notebook after all outputs are written.

2. **Per-show README.** Call `build_readme` once for each show directory and once for `all/`.

3. **Embed visualizations.** Use `![chart title](visualizations/chart.png)` syntax. List only charts that exist on disk (check before embedding).

---

### TASK-F18 — GitIgnore Tuning for GitHub Publication
   * **Clarification:** Only proceed with this task (TASK-F18) once all other visualizations are implemented.

**What it should achieve:**
A `data/50_analysis/.gitignore` that allows GDPR-safe, size-appropriate, single-format outputs into git while excluding matrices, HTML duplicates, PDF duplicates, and person-level data.

**What the implementation achieves today:**
- No `.gitignore` in `data/50_analysis/`. All analysis outputs are likely excluded by a parent `.gitignore`.

**Next steps and implementation plan:**

1. **Check parent `.gitignore`** for existing data directory exclusions.
2. **Write `data/50_analysis/.gitignore`** with:
   ```
   # Exclude GDPR-sensitive person-level outputs
   persons/
   # Exclude duplicate visualization formats (keep PNG only)
   *.pdf
   *.html
   # Exclude large occurrence matrices
   occurrence_matrix.csv
   co_occurrence_matrix.csv
   value_episode_matrix.csv
   # Allow everything else (summary CSVs, PNGs, READMEs)
   !*.png
   !*.csv
   !README.md
   ```
3. **Verify** that per-show `top_guests.csv`, `carrier_stats.csv`, `episode_stats.csv`, and visualization PNGs are tracked after the rule change.
