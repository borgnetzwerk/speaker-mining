# phase31-32-zenodo-dataset

**Identified by:** Grant Evaluator (review 04), task 2

## Problem

Phase 31/32 produces a deduplicated, reconciled entity dataset that has independent scientific value beyond the pipeline itself: it is a structured dataset of German public broadcast guests linked to Wikidata, covering multiple years of ZDF programming. This dataset is not currently published or citable.

A grant evaluator notes that publishing this as a standalone Zenodo dataset would:
- Make the research output independently citable (separate DOI from the code)
- Enable reuse by researchers who do not need the full pipeline
- Satisfy open-data requirements for DFG/NFDI funded outputs
- Increase the project's research impact without requiring additional analysis work

## Action (deferred — requires data agreement review)

Before publication, verify:
1. **Legal review**: does the ZDF data agreement permit derived dataset publication? The raw PDFs cannot be published, but deduplicated name→QID mappings may be permissible
2. **fernsehserien.de terms**: scraped data must not be redistributed; exclude any fields derived solely from fernsehserien.de if terms prohibit it
3. **Wikidata fields**: CC0, freely publishable

If legal review clears publication:
1. Prepare a clean export of the Phase 31/32 output: canonical entity table (name_canonical, wikidata_qid, gender, birth_year, occupation) without raw scraped text fields
2. Write a `README.txt` for the dataset following Zenodo conventions (description, column definitions, sources, licence)
3. Publish on Zenodo and add the DOI to `documentation/data_reference.md` and `README.md`

Document the legal review outcome in `documentation/data_reference.md` regardless of whether publication proceeds.

## Definition of done

1. Legal review outcome is documented in `documentation/data_reference.md`.
2. If publication is cleared: dataset is on Zenodo with a DOI; DOI is in `data_reference.md` and `README.md`.
3. If publication is not cleared: `data_reference.md` states which fields are restricted and why.
