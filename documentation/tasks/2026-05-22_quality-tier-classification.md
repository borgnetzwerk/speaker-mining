# quality-tier-classification

* priority: medium
* scope: pipeline
* legacy-id: TODO-068

## Summary

The `data_quality_tier` column exists in `build_person_catalogue` but property stats expansion inputs are not yet filtered to Tiers 1+2, per-show tier breakdowns are missing from `person_quality_tiers.csv`, and the analysis documentation does not explain how many Tier 3/4 entries are excluded.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F16 remaining work.

## Definition of done

1. `data_quality_tier.isin([1, 2])` filter applied to all property stats and visualization expansion inputs; only Wikidata-reconciled persons enter property statistics.
2. `person_quality_tiers.csv` includes per-show tier breakdown rows.
3. `data/50_analysis/all/README.md` or `documentation/analysis/README.md` documents the tier exclusion: how many Tier 3+4 entries exist and what they represent.
