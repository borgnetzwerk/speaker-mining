# dataset-overview-statistics

* priority: medium
* scope: documentation
* legacy-id: TODO-023

## Summary

No structured overview exists showing how many instances, classes, and subclasses exist per core class; what percentage of instances have Wikidata mappings; how many were successfully deduplicated; and step-by-step pipeline statistics.

## Evidence

Phase 32 output: 8,976 canonical entities, 640 Wikidata-matched.

## Definition of done

1. A dataset statistics table is produced: class → instance count → Wikidata-matched count → deduplicated count → subclass count.
2. Step-by-step pipeline statistics are documented (Phase 1 → Phase 2 → Phase 31 → Phase 32 → Analysis row counts).
3. Optionally: a dashboard visualization per core class and one for the total repository is added to `documentation/visualizations/`.
