# aligned-csv-column-footprint

* priority: medium
* scope: contracts
* status: in-progress
* legacy-id: TODO-017

## Summary

`aligned_persons.csv` has 2,531 columns — caused by (1) the `raw_json_wikidata` column containing full JSON payload alongside individual property columns, and (2) both raw `*_wikidata` and `*_norm_wikidata` variants of every Wikidata property column being propagated. The bloated column count makes OpenRefine reconciliation projects slow to load.

## Evidence

`data/31_entity_disambiguation/aligned/aligned_persons.csv` header (2,531 cols); `documentation/archive/31_entity_disambiguation/archive/todo_tracker.md`.

## Definition of done

1. `raw_json_wikidata` column is removed from Phase 31 output schema (full payloads live in `core_persons.json`).
2. Either the raw or the `_norm_` variant of each Wikidata property column is removed; the surviving column is documented in `contracts.md`.
3. Column selection prioritizes: core IDs, label, description, aliases, source links, and the most commonly populated properties. Columns ≥99% empty are cut first.
4. `aligned_persons.csv` column count drops to approximately 40 after re-run (hard ceiling: 50).

## Implementation notes

Implementation complete (2026-04-24): `trim_to_top_columns` added to `utils.py`; applied at end of every `build_aligned_*` function (persons, episodes, roles, organizations, topics, seasons, broadcasting_programs). Selection is data-driven per entity type: COMMON_BASE_COLUMNS always kept, `_norm_*` variants and `raw_json_wikidata` always excluded, remaining 25 slots filled by highest-population-rate columns.

Remaining: re-run Notebook 31 to regenerate all aligned CSVs and verify column counts ≤ 50.
