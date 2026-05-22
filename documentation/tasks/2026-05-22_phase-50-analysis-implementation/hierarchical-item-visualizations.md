# hierarchical-item-visualizations

* priority: medium
* scope: pipeline
* legacy-id: TODO-062

## Summary

Hierarchical visualizations for occupation and role data (sunburst, Sankey, mid-level class charts) and timeline visualizations with adaptive granularity are not yet implemented.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F07; `2026-04-29_Initialization/open-tasks.md` TASK-A02. Blocked on `class-hierarchy-walk`.

## Definition of done

1. Sunburst chart for occupation: combined + per-show; 5% "Other" cutoff; innermost ring = top-level classes.
2. Sankey diagram for occupation hierarchy: combined + per-show; flow width = appearances and unique guests.
3. Mid-level class dedicated stacked bars and sunbursts for each designated mid-level class.
4. Timeline visualizations with adaptive granularity (max 50 data points, progressive coarsening).
5. All outputs exported PNG + PDF to `data/50_analysis/visualizations/`.

## Notes

Multi-parent strategy needed for subclasses with multiple superclasses (primary-parent assignment or proportional count split) — document chosen strategy in notebook cell.
