# OpenRefine Documentation

This folder contains reference documentation for the OpenRefine reconciliation workflow used in Phase 31 (entity disambiguation).

## Contents

- **`Open Refine + Wikibase Cloud + Reconciliation (full Setup Documentation).pdf`** — External setup guide covering OpenRefine installation, Wikibase Cloud connection, and the reconciliation service configuration. This is a reference document for reproducing the reconciliation environment; its content has not been extracted to plaintext.

## Relationship to the pipeline

OpenRefine was used in Step 3.1.2 to reconcile person mentions against Wikidata QIDs. Two curators worked through 31,165 alignment units, achieving 55.91% automatic reconciliation and 18.79% manual mapping. The reconciliation output is stored in `data/31_entity_disambiguation/` and feeds directly into Phase 32 deduplication.

For the reconciliation integration task (making the OpenRefine output the authoritative deduplication tier), see the [`reconciliation-csv-integration` task](../tasks/2026-05-22_reconciliation-csv-integration/).

## Human action needed

The PDF in this folder has not been assessed for content that should be extracted to a plaintext document. A future pass should determine whether the setup steps described in the PDF are still current and whether a brief plaintext procedure note should be written here.
