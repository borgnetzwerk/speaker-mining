# fernsehserien-person-id-fix

* priority: medium
* scope: contracts
* legacy-id: TODO-045

## Summary

The `fernsehserien_de_id` column in `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` contains the episode URL (e.g. `https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614`) instead of the person fernsehserien.de slug (e.g. `andrej-gurkov`).

## Evidence

Example row: `person_fs_1ff4ae2b3b83,,Q133019990,https://www.fernsehserien.de/internationaler-fruehschoppen/folgen/24-...,`

The correct person URL would be: `https://www.fernsehserien.de/<person_id>/filmografie`.

## Definition of done

1. Phase 31 alignment step correctly populates `fernsehserien_de_id` with the person's fernsehserien.de slug (e.g. `andrej-gurkov`), not the episode URL.
2. The episode URL is stored in a separate column (e.g. `episode_fernsehserien_de_id`).
3. Existing output files downstream of Phase 31 are regenerated.

## Notes

Phase 5 workaround (deferred fix): the current `fernsehserien_de_id` value IS the episode URL and can still be used as a join key with `episode_metadata_normalized.csv`. Phase 5 design spec `03_design_spec.md` already accounts for this — the join is correct as written. Fix is deferred to the next Phase 31 re-run.
