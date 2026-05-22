# phase-50-analysis-implementation

* priority: medium
* scope: pipeline

## Summary

Implement the full Phase 50 analysis and visualization suite for the speaker-mining pipeline. Phase 50 reads from the finalized guest catalogue and Wikidata property data to produce property distribution statistics, cross-property charts, hierarchical visualizations, and summary outputs covering all ZDF talk show episodes.

This large task groups all Phase 50 sub-tasks: implementation work, bug fixes in the current 50_analysis.ipynb notebook, infrastructure tasks, and output management.

## Context

The Phase 50 analysis is structured around a property-type taxonomy (A: categorical hierarchical, B: categorical single-value, C: continuous/numeric, D: temporal) and function types (F1–F5). The design spec lives in `documentation/analysis/`. Output folder structure is `data/50_analysis/`.

## Dependency order (from 2026-04-30 restructuring notes)

Implementation follows this ordering:

1. Data setup: `appearance-totals-validation`, `quality-tier-classification`
2. Property extraction and hierarchy: `class-hierarchy-walk`, `dynamic-analysis-pipeline`
3. Statistics: `property-stats-tables`
4. Infrastructure: `visualization-infrastructure`, `gitignore-analysis-outputs`
5. Charts: `cross-property-charts`, `hierarchical-item-visualizations`, `scalar-extended-plot-families`
6. Person-level: `person-level-analysis`
7. Data quality and compliance: `data-quality-followups`, `analysis-taxonomy-compliance`
8. Outputs: `output-folder-readmes`
9. Exploratory: `exploratory-analysis-angles`
10. Follow-up: `unclassified-persons-fs-links`

## Sub-tasks — implementation

- [dynamic-analysis-pipeline](dynamic-analysis-pipeline.md)
- [class-hierarchy-walk](class-hierarchy-walk.md)
- [property-stats-tables](property-stats-tables.md)
- [visualization-infrastructure](visualization-infrastructure.md)
- [cross-property-charts](cross-property-charts.md)
- [hierarchical-item-visualizations](hierarchical-item-visualizations.md)
- [scalar-extended-plot-families](scalar-extended-plot-families.md)
- [person-level-analysis](person-level-analysis.md)
- [data-quality-followups](data-quality-followups.md)
- [analysis-taxonomy-compliance](analysis-taxonomy-compliance.md)
- [exploratory-analysis-angles](exploratory-analysis-angles.md)
- [quality-tier-classification](quality-tier-classification.md)
- [output-folder-readmes](output-folder-readmes.md)
- [gitignore-analysis-outputs](gitignore-analysis-outputs.md)
- [appearance-totals-validation](appearance-totals-validation.md)
- [unclassified-persons-fs-links](unclassified-persons-fs-links.md)

## Sub-tasks — bug fixes in 50_analysis.ipynb

Found during 2026-05-11 review. All are code-scope and deferred until Phase 50 implementation is active.

- [age-aggregation-bug](age-aggregation-bug.md) — F-04: age values summed instead of appearance counts
- [analysis-summary-dual-write](analysis-summary-dual-write.md) — F-01: analysis_summary.json overwritten with incompatible schema
- [per-show-stats-corruption](per-show-stats-corruption.md) — F-02: per_show_stats variable reused for incompatible DataFrames
- [notebook-module-duplication](notebook-module-duplication.md) — F-03: notebook duplicates logic that exists in modules
- [notebook-section-numbering](notebook-section-numbering.md) — F-05: duplicate/out-of-order section numbers
- [viz-cache-bundle-check](viz-cache-bundle-check.md) — F-06: cache validity check covers PNG only, not full bundle
- [color-registry-none-filter](color-registry-none-filter.md) — F-07: build_show_color_registry() accepts NONE as a real show ID

## Definition of done

1. All 16 implementation sub-tasks are complete.
2. All 7 bug fix sub-tasks are resolved.
3. `data/50_analysis/` contains complete outputs: per-show occurrence matrices, combined analysis CSVs, all chart types (PNG exports), README.md in each subdirectory.
4. `.gitignore` correctly tracks aggregate CSVs and PNG visualizations while excluding raw per-person data.

## Source material

- 2026-04-29 initialization open-tasks: `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` (TASK-A series)
- 2026-04-30 restructuring open-tasks: `documentation/archive/50_Analysis/2026-04-30_restructuring/open-tasks.md` (TASK-B series, includes dependency graph)
- 2026-05-11 review: `documentation/archive/50_Analysis/2026-05-11_review/` (code_update_plan.md, findings.md, test_plan.md)
