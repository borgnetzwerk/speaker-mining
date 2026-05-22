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
3. All top-N ranking lists (occupations, parties, etc.) include the count alongside each entry — no ranking output is published without its supporting number.
4. A "most relevant person" metric is defined and implemented: candidates include highest `appearance_count`, widest cross-show presence, highest page rank score, and a composite of these. The chosen metric is documented in the analysis README with a justification for the weighting.

## Notes

TASK-A10 (from `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md`) specified items 3 and 4 above: missing counts in top-X lists and the "most relevant person" concept. Both are incorporated here rather than a separate task.
