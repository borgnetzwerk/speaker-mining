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
