# property-stats-tables

* priority: medium
* scope: pipeline
* legacy-id: TODO-059

## Summary

`carrier_stats` and `episode_appearance_stats` functions need generalization to work for all property types (item, quantity, string, time) and to emit standardized output including Unknown/no-data rows and combination tables.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F04; `2026-04-29_Initialization/open-tasks.md` TASK-A04.

## Definition of done

1. `carrier_stats(property_id, data)` and `episode_appearance_stats(property_id, data)` are generalized and work for all property types.
2. Both functions emit an explicit "Unknown / no data" row, `person_count`, and `appearance_count` columns.
3. Combination tables (within-property and cross-property) are produced automatically for all item-type properties.
4. Downstream combination tables verified; dominance ratio and outlier flag confirmed present in all property output directories.
