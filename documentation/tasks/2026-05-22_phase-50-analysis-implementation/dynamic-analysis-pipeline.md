# dynamic-analysis-pipeline

* priority: medium
* scope: pipeline
* legacy-id: TODO-057

## Summary

All suitable analyses and visualizations for every configured property should run automatically from `data/00_setup/analysis_properties.csv` without manual wiring per new property.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F02.

## Definition of done

1. Analysis routing reads from `analysis_properties.csv`; adding a new property row causes it to appear in all applicable chart families without code changes.
2. Cross-property combination analyses run automatically for all ordered property pairs of type `item`.
3. Per-property and cross-property visualization outputs are produced in one notebook run without manually specifying pairs.
