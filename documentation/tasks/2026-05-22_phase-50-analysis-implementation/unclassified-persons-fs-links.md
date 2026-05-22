# unclassified-persons-fs-links

* priority: low
* scope: pipeline
* legacy-id: TODO-072

## Summary

215 canonical persons have `match_strategy=wikidata_person_only_baseline` and no fernsehserien.de episode link; at least one confirmed false negative (Marie-Agnes Strack-Zimmermann, Q15391841). Each should be verified against fernsehserien.de episode pages.

## Evidence

`documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` TASK-A13.

## Definition of done

1. All 215 persons individually verified against fernsehserien.de.
2. True missing-link cases have corrected `fernsehserien_de_id` in reconciliation data; Phase 31 → 32 → 50 re-run for corrections.
3. Remaining persons confirmed as genuinely unlinked and documented as such.

## Notes

Can be done manually or with an agent. Volume: 215 persons.
