# Implementation Plan

1. TASK-F01 - Guest Role Separation and Appearance Accounting | Partial
2. TASK-F02 - Dynamic Property-Driven Analysis Pipeline | Open
3. TASK-F03 - Class Hierarchy and Loop Resolution Completion | Open
4. TASK-F04 - Standardized Property Statistics and Combination Tables | Partial
5. TASK-F05 - Visualization Infrastructure Hardening | Partial
6. TASK-F06 - Universal and Cross-Property Chart Completion | Partial
7. TASK-F07 - Hierarchical Item Visualizations | Open
8. TASK-F08 - Scalar, Quantity, String, and Extended Plot Families | Partial
9. TASK-F09 - Episode, Source, and Cross-Show Dashboards | Partial
10. TASK-F10 - Person-Level and Relevance Analyses | Partial
11. TASK-F11 - Temporal Claim Qualification and Historical Views | Partial
12. TASK-F12 - Data Quality and Coverage Follow-Ups | Open
13. TASK-F13 - Documentation and Structural Compliance | Open
14. TASK-F14 - Lower-Priority Exploratory Angles | Low priority
15. TASK-F15 - PageRank Node Visualizations | Open

## Progress Log

- 2026-05-04: TASK-F01 moved to `Partial`.
	Notebook updates in `50_analysis.ipynb` now enforce guest-only property expansion and fix birthyear column collisions that triggered `KeyError` during catalogue projection.
- 2026-05-04: TASK-F04 property standardization was validated.
	The property merge helper now keeps guest base rows visible even when extracted property frames omit `value`, and the notebook completed all 16 enabled property outputs successfully.
- 2026-05-04: property expansion was corrected to use unique guest-episode rows.
	A synthetic regression test now asserts that per-property appearance totals stay bounded by the actual guest-appearance matrix instead of inflating beyond it.
- 2026-05-04: QID propagation and property matrix outputs were hardened.
	Guest episode joins now use canonical QIDs from the occurrence basis, and each property writes a value-by-episode matrix for direct per-episode carrier inspection.
- 2026-05-04: guest frequency and Pareto outputs were completed in the analysis notebook.
	The notebook now writes `guest_frequency_distribution.csv`, `guest_frequency_pareto.csv`, and a Plotly Pareto chart for top guest appearances, which closes the current visualization stub in TASK-B21 / TASK-F09.
- 2026-05-04: source-attribution and cross-show coverage dashboards were added.
	TASK-F09 now emits overall Wikidata coverage, stacked by-show completeness, and unique-person coverage comparison charts alongside `source_coverage_dashboard.csv`.
- 2026-05-04: dashboard visualization logic was moved into `speakermining/src/process/analysis/viz_dashboards.py`.
	The notebook now only orchestrates the dashboard helpers, matching the repository rule that chart construction lives in analysis modules.
- 2026-05-05: `role_priority` dict in `occurrence_matrix.build_person_catalogue` was fixed.
	Previous order (guest=0, moderator=1) caused moderators to be classified as guests when they also appeared as guests in other shows. New order (moderator=0, staff=1, guest=2, incidental=3) ensures moderators and staff always win the dominant-role aggregation. This removes Frank Plasberg, Gert Scobel, and production entities from guest Pareto and per-show top-guest outputs on the next notebook run.
	* **Clarification:** "Guest" or "moderator" or anything else must be decided per_episode: We need a guest_occurrence matrix and a moderator_occurrence_matrix and a ... . These will show if person X was a guest of some show. Maybe, a previous moderator is guest in a later show of the format - we cannot say "Person X categorically is a guest/moderator/staff/... of show A", we must find out episode by episode.
- 2026-05-05: `build_role_occurrence_matrices` added to `occurrence_matrix.py` and exported from `__init__.py`.
	Produces separate moderator and staff occurrence matrices in the same format as the guest matrix. Notebook call site needs to be wired up in the next session.
	* **Clarification:** Exactly! This is what we need. When we want to know something about guests: inspect the guest matrix.
- 2026-05-05: `03_intermediate_review.md` populated with binding principles (7) and task-by-task review with implementation plans for all TASK-F01 through TASK-F15.
- 2026-05-05 (session 3): `compute_top_guests_by_show` wired into notebook (cells `a7f2c5e8` + `b3d9e1f4` after `77d0a8d8`). Writes `top_guests.csv` to each show directory and `top_guests_combined.csv` to `all/`. Closes TASK-F10 item 5.
- 2026-05-05 (session 3): `data_quality_tier` column added to `build_person_catalogue` in `occurrence_matrix.py` via `_quality_tier()`. Column added to `CATALOGUE_COLS` in notebook. Tier summary cells (`d4f8a231` + `e5c9b342`) inserted after dataset overview. Partially closes TASK-F16.
- 2026-05-05 (session 3): Root `.gitignore` updated to unignore `data/50_analysis/` subtree while blocking persons/, occurrence matrices, value-episode matrices, and duplicate format files (PDF/HTML). Partially closes TASK-F18.
- 2026-05-05 (session 3): Pareto chart converted to stacked bar by show. `_build_stacked_pareto` and `_build_simple_pareto` added to `viz_dashboards.py`. Notebook cell `229b7a80` passes `episode_appearances` to enable stacked mode. Closes TASK-F09 item 6.
- 2026-05-05 (session 3): `readme_generator.py` module created and exported. Notebook cells `f6a3c891` + `c9d2b745` inserted after export summary. Generates `README.md` in `all/` and each show directory with embedded PNGs and top-guest tables. Partially closes TASK-F17.
- 2026-05-05 (session 3): TASK-F16, TASK-F17, TASK-F18 added to task list and `03_intermediate_review.md`; TASK-F09, TASK-F10, TASK-F16, TASK-F17, TASK-F18 progress notes updated in `open-tasks.md`.
