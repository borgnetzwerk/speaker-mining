# guest-catalogue-completion

* priority: high
* scope: pipeline
* legacy-id: TODO-019

## Summary

`guest_catalogue.csv` has only 640 rows (Wikidata-matched persons); the full Phase 32 output has 8,976 canonical entities — the remaining ~8,336 unmatched entities have no property data but should still appear in a separate output file.

## Evidence

`data/40_analysis/guest_catalogue.csv` (640 rows), `data/32_entity_deduplication/dedup_persons.csv` (8,976 rows).

## Definition of done

1. A second output file `data/40_analysis/unmatched_persons.csv` lists all canonical entities without a Wikidata match, with columns: `canonical_entity_id`, `canonical_label`, `cluster_size`, `cluster_strategy`.
2. `41_analysis.ipynb` is updated to produce both files and to display the split (matched vs. unmatched counts).
3. At least a sample of unmatched entities is inspected to confirm whether any can still be resolved (e.g. common names with missing Wikidata link).
