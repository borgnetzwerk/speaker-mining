# reconciliation-csv-integration

* priority: high
* scope: pipeline
* status: in-progress
* legacy-id: TODO-018

## Summary

The OpenRefine reconciliation team is producing a 6-column CSV (`alignment_unit_id`, `wikibase_id`, `wikidata_id`, `fernsehserien_de_id`, `mention_id`, `canonical_label`) as the authoritative output of manual Phase 31 reconciliation. This CSV must be integrated into Phase 32 as the highest-confidence deduplication tier, superseding automated strategies where present. The CSV itself is produced externally.

## Evidence

`documentation/archive/31_entity_disambiguation/post-processing.md` (workflow + deadlines), `ToDo/2026-05-03_Speaker_Mining_Paper/`.

## Definition of done

1. The integration contract is documented in `contracts.md`: where the incoming CSV is placed, what Phase 32 does with it, and how it overrides automated clustering.
2. Phase 32 logic reads the incoming CSV and promotes its entries to a new `manual_reconciliation` cluster strategy with confidence = `authoritative`.
3. The 6-column CSV is received from the reconciliation team and ingested.

## Implementation notes

Integration logic is implemented (2026-04-23): `_apply_manual_reconciliation_tier()` in `person_deduplication.py`, loaded by `orchestrator.py` when `data/31_entity_disambiguation/reconciliation_export.csv` exists. Drop the CSV at that path and re-run Phase 32 to ingest.

Tests: `speakermining/test/process/entity_deduplication/test_manual_reconciliation.py` (9 cases).

Remaining: receive CSV from reconciliation team and do a live ingest run (definition of done item 3).
