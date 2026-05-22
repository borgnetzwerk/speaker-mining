# appearance-totals-validation

* priority: medium
* scope: pipeline
* legacy-id: TODO-071

## Summary

Episode appearance totals have not been validated against expected bounds (25,902 total appearances vs per-property totals); Wikidata is not yet wired as a third occurrence source alongside ZDF and fernsehserien.de.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F01 remaining work and TASK-F12 item "Add Wikidata as 3rd source".

## Definition of done

1. End-to-end appearance totals validated: `sum(occurrence_matrix)` ≈ expected 25,902 total appearances; per-property appearance totals do not exceed that total.
2. Wikidata raw_import and normalized episode data wired as a third source in `build_person_catalogue` (alongside ZDF and FS sources already implemented).
3. Source attribution breakdown in `person_quality_tiers.csv` shows counts from each of the three sources.
