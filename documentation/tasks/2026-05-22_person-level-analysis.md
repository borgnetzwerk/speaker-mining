# person-level-analysis

* priority: medium
* scope: pipeline
* legacy-id: TODO-064

## Summary

Two items from TASK-F10 remain: within-category per-person charts (for each property value, who are the top guests?) and empty-property reporting for top-N most-appeared guests.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F10 remaining work.

## Definition of done

1. For each top-N value of every item-type property, a "within-category top persons" chart is produced showing top guests carrying that value, segmented by show.
2. For the top-N most-appeared guests, a report lists which configured properties had no Wikidata value (e.g., "Robin Alexander — employer field empty"). Written to `all/top_guests_property_gaps.csv`.
