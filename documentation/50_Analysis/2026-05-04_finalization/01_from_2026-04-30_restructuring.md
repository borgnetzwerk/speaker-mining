## Documentation Policy

Taking from: `documentation/50_Analysis/2026-04-30_restructuring/open-tasks.md`

## Implementation Status (code matched)

The following status summary was ingested from the codebase and notebook scans. Each task lists the current implementation status and pointers to the implementing modules or notebooks.

- **TASK-B02 — Person-Episode Occurrence Matrix:** Implemented — see `analysis/occurrence_matrix.py` (`build_occurrence_matrix`, `build_cooccurrence_matrix`) and `speakermining/src/process/notebooks/50_analysis.ipynb` (cells building `occurrence_matrix.csv` and per-show outputs).
- **TASK-B03 — Property Data Extraction by Type:** Implemented — see `analysis/property_extraction.py` (`extract_all_properties`, `extract_item_values`, `extract_time_values`, `extract_quantity_values`, `extract_string_values`, `compute_age`).
- **TASK-B04 — Class Hierarchy Computation:** Not implemented (open) — no `class_hierarchy.py` present; `load_midlevel_classes` exists in `analysis/config.py` but P279 walk module is missing.
- **TASK-B05 — Universal Carrier-Based Statistics:** Implemented — see `analysis/universal_stats.py` (`compute_carrier_stats`) used in `50_analysis.ipynb`.
- **TASK-B06 — Universal Episode Appearance Statistics Table:** Implemented — see `analysis/universal_stats.py` (`compute_episode_appearance_stats`) used in the notebook.
- **TASK-B07 — Item: Co-occurrence Matrices and Combination Tables:** Partially implemented — per-episode co-occurrence and `co_occurrence` CSVs exist via `occurrence_matrix.build_cooccurrence_matrix` and notebook code; full within-/cross-property combination tables not yet present.
- **TASK-B08 — Visualization System Infrastructure:** Largely implemented — `analysis/viz_base.py` provides `save_fig`, `sort_bars_descending`, `add_unknown_row`, `add_scope_label`, `add_context_stats`, `stacked_bar_from_zero`, `place_bar_labels`, `apply_other_grouping`. Missing: centralized caching sidecar logic (TASK-B20).
- **TASK-B09 — Universal Visualizations (appearances + unique):** Implemented (partial notes) — `analysis/viz_universal.py` with `universal_visualizations` and `make_universal_chart` wired from `50_analysis.ipynb`. ColorRegistry exists in `analysis/color_registry.py` but full integration into `viz_universal.py` is noted as a gap.
- **TASK-B10 — Item: Timeline Visualizations:** Not implemented (open) — no `viz_timelines.py` or timeline module found.
- **TASK-B11 — Item: Sunburst Visualizations:** Not implemented (open) — no sunburst module found.
- **TASK-B12 — Item: Sankey Diagram:** Not implemented (open) — no sankey module; design helpers exist in `viz_base` but no Sankey-specific code.
- **TASK-B13 — Item: % A over B Stacked Bar Charts:** Not implemented (open) — no dedicated implementation found.
- **TASK-B14 — Mid-Level Class Dedicated Analyses and Visualizations:** Not implemented (open) — depends on TASK-B04.
- **TASK-B15 — Point in Time: Birth Year Visualizations:** Partially implemented — birthyear extraction exists in `occurrence_matrix.extract_wikidata_properties` and age derivation appears in `50_analysis.ipynb`; dedicated visualization module not present.
- **TASK-B16 — Quantity: Violin Plot and Binary Presence:** Not implemented (open) — extraction supported; viz module missing.
- **TASK-B17 — String: Binary Presence:** Not implemented (open) — extraction supported; viz missing.
- **TASK-B20 — Architecture: Visualization Caching:** Not implemented (open) — `viz_base.save_fig()` writes files but no checksum cache sidecar exists yet.
- **TASK-B21 — Guest Appearance Frequency Distribution and Pareto:** Implemented — functions `build_frequency_distribution` and `build_pareto_table` in `analysis/universal_stats.py` and used in the notebook.
- **TASK-B22 — Person-Level Visualizations:** Partially implemented — `person_analysis.py` provides functions (`compute_top_guests_by_show`, `compute_guest_specialization`) and the notebook writes `top_guests_combined.csv`; dedicated visualizations per-person are not consolidated.
- **TASK-B23 — Episode-Level Visualizations and Dashboard:** Partially implemented — `analysis/meta_analysis.py` and the notebook compute coverage and per-show stats; episode visualization modules (calendar heatmap, etc.) are not present.
- **TASK-B24 — Meta-Level: Source Coverage and Data Completeness Visualization:** Partially implemented — `analysis/meta_analysis.py` has `compute_wikidata_coverage` and helpers; visualization outputs are not fully implemented.
- **TASK-B26 — Cross-Show Comparison Visualizations:** Not implemented (open) — design references `viz_comparison.py` but no such module found.
- **TASK-B27 — Property Coverage Dashboard:** Not implemented (open) — design references `viz_coverage.py` but no such module found.
- **TASK-B28 — Temporal Claim Handling:** Largely implemented — `analysis/config.py` documents and enforces claim-level temporal handling (`normalize_analysis_properties` drops `temporal_variable`, `TEMPORAL_QUALIFIER_PIDS`, `has_temporal_claims`/`infer_temporal_properties_from_values` exist); `property_extraction.extract_item_values` captures `qualifier_pids`. Remaining work: add `is_temporal` flag to per-property DataFrames and add `effective_at` filtering to `compute_carrier_stats` if desired.

## Next Steps — Structured ToDo (actionable)

Work items below are ordered by priority and focused on concrete implementation tasks derived from the status review. Each item is short and actionable so it can be checked off when completed.

**Immediate (foundation):**
- Implement `analysis/class_hierarchy.py` (TASK-B04): P279 walk, mid-level detection, loop resolution via `data/00_setup/loop_resolution.csv`.
- Implement visualization caching sidecar (TASK-B20): add checksum logic and per-scope `.viz_cache.json`, integrate with `viz_base.save_fig()`.
- Extend `analysis/viz_universal.py` with `ColorRegistry` integration and ensure PDF export behavior meets REQ-V12.

**Near-term (analysis & combos):**
- Implement within-/cross-property co-occurrence and combination tables (TASK-B07).
- Implement `viz_timelines.py` (TASK-B10): adaptive-granularity timelines for Items.
- Implement `viz_sunburst.py` (TASK-B11) and `viz_sankey.py` (TASK-B12) for hierarchical Item properties (depends on TASK-B04).

**Visualization polish & dashboards:**
- Implement `viz_comparison.py` (TASK-B26) for cross-show comparisons.
- Implement `viz_coverage.py` (TASK-B27) to produce `property_coverage.csv` and dashboard.
- Implement property-specific visualizations: age violin, quantity binary presence, string presence (TASK-B15, TASK-B16, TASK-B17).

**Correctness & small fixes:**
- Add `is_temporal` boolean to per-property DataFrames in `property_extraction.extract_all_properties` for claims that include P580/P582 (TASK-B28 follow-up).
- Optionally add `effective_at` filter argument to `compute_carrier_stats` and `compute_episode_appearance_stats` to filter to claims valid at a date.
