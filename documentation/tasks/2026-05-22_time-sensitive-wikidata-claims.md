# time-sensitive-wikidata-claims

* priority: medium
* scope: pipeline
* legacy-id: TODO-041

## Summary

Wikidata claims for party affiliation (P102), occupation (P106), position held (P39), and employer (P108) may have start/end qualifiers. A statement true in 2015 may be false today. Guest properties should be evaluated against the episode date, not the current Wikidata snapshot.

## Evidence

`data/40_analysis/guest_catalogue.csv`, `data/10_mention_detection/episodes.csv` (contains episode dates), `core_persons.json` (contains raw claim data with qualifiers).

## Definition of done

1. Identify which Wikidata properties in the guest catalogue have start/end date qualifiers in the raw claim data (`core_persons.json`).
2. For each such property, filter to only claims whose date range covers the guest's first (or any) appearance date.
3. Updated analysis reflects time-contextual properties; discrepancies (e.g. former party member shown as current) are reduced.
4. The filtering logic is documented in `contracts.md` or `documentation/findings.md`.
