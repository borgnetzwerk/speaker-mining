# Open Tasks

Finalized and deduplicated backlog for implementation.

Policy for this file:
- Keep stable task IDs (`TASK-F..`) for planning and archiving.
- Track source lineage explicitly so old context remains auditable.
- Mark tasks as `Open`, `Partial`, `Blocked`, `Low priority`, or `Resolved`.

## TASK-F01 - Guest Role Separation and Appearance Accounting
**Priority:** Immediate  
**Status:** Open

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

---

## TASK-F05 - Visualization Infrastructure Hardening
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Finalize shared chart helpers for reusable labeling, ordering, unknown buckets, and scope/context metadata.
2. Implement visualization caching sidecar (checksum-based skip logic).
3. Ensure dual export contract (PNG + PDF).
4. Make long-label handling robust: dynamic width, wrapping, and height adaptation.
5. Add language variants (DE/EN) with fully localized chart text.
6. Include episode-count and broadcasting-program context in titles/subtitles.

**Primary sources:**
- 2026-04-30 TASK-B08, TASK-B20
- 2026-05-04 additional input (`Visualizations are not very dynamic yet`)

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

**Primary sources:**
- 2026-04-30 TASK-B23, TASK-B24, TASK-B26, TASK-B27
- 2026-05-04 additional input (`Source specific analysis`, `Episode specific property visualization`)

---

## TASK-F10 - Person-Level and Relevance Analyses
**Priority:** High  
**Status:** Partial

**Scope:**
1. Complete person-level chart set (top guests, by-show, within-category, encounter matrix).
2. Add per-person claim count outputs.
3. Define and implement a documented "most relevant person" metric.
4. Preserve and extend specialization/dominance analyses.

**Primary sources:**
- 2026-04-30 TASK-B22
- 2026-04-29 TASK-A10
- 2026-05-04 additional input (`Per Person`)

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

**Primary sources:**
- 2026-04-29 TASK-A09, TASK-A11, TASK-A13
- 2026-05-04 additional input (`Ensure correct fernsehserien IDs`, `data basis`)

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

## Task Lineage Notes

Items explicitly recognized as already resolved in prior documentation (not queued here as implementation tasks):
- 2026-04-29 TASK-A01, TASK-A06, TASK-A07, TASK-A08

Items represented as sub-scope under `TASK-F..` IDs above rather than duplicated one-to-one:
- 2026-04-30 TASK-B18 integrated under chart/export completion scope
- 2026-04-30 TASK-B21 integrated under dashboard/statistics scope
