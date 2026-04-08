# Repository Overview

This document explains how the repository currently works end-to-end.

## Pipeline Summary

1. Optional pre-phase (`10_text_extraction.ipynb`) converts raw archive PDFs into canonical `*.pdf_episodes.txt` files.
2. Phase 1 (`10_mention_detection.ipynb`) parses archive text into structured mention tables.
3. Optional inspection (`19_analysis.ipynb`) provides lightweight, confidence-aware checks over Phase 1 outputs.
4. Phase 2 (`20_` to `23_` candidate-generation notebooks) prepares lookup tables and source-specific candidate search inputs; `22_candidate_generation_fernsehserien_de.ipynb` exists as an unexecuted scaffold.
5. Phase 3 (`30_`, `31_`) contains manual reconciliation and deduplication decisions.
6. Phase 4 (`40_`) produces relation/link outputs.

## Main Runtime Entry Points

Notebook entry points are in `speakermining/src/process/notebooks`.

Authoritative source for default order and historical notebook status:

- [workflow.md](workflow.md)

## Code Modules Called By Notebooks

### Phase 1 modules

- `process.mention_detection.config`
- `process.text_extraction.text`
- `process.mention_detection.episode`
- `process.mention_detection.publications`
- `process.mention_detection.season`
- `process.mention_detection.guest`
- `process.mention_detection.topic`
- `process.mention_detection.duplicates`

### Phase 2 modules

- `process.candidate_generation.broadcasting_program`
- `process.candidate_generation.season`
- `process.candidate_generation.episode`
- `process.candidate_generation.person`
- `process.candidate_generation.topic`
- `process.candidate_generation.persistence`

Wikidata stage modules used by notebook 21 (v3 event-sourcing runtime):

- `process.candidate_generation.wikidata.bootstrap`
- `process.candidate_generation.wikidata.expansion_engine`
- `process.candidate_generation.wikidata.fallback_matcher`
- `process.candidate_generation.wikidata.materializer`
- `process.candidate_generation.wikidata.node_store`
- `process.candidate_generation.wikidata.triple_store`
- `process.candidate_generation.wikidata.query_inventory`
- `process.candidate_generation.wikidata.checkpoint`

## Data Ownership Model

Authoritative source for phase ownership and write boundaries:

- [workflow.md](workflow.md)

Supporting folders:

- `data/00_setup`: seed classes/properties/broadcasting programs
- `data/01_input`: raw and pre-exported source inputs

## Current Stable Produced Artifacts

Authoritative source for output contracts, file names, and schema headers:

- [contracts.md](contracts.md)

### `data/10_mention_detection`

- mention-detection tables and duplicate reports

### `data/20_candidate_generation`

- setup copies, reduced/augmented tables, feedback tables, and candidate table
- runtime tabular projections currently ship as CSV compatibility files with matching Parquet sidecars during the storage transition

## Known Architecture Tensions

1. Institution extraction is documented in findings and deferred code, but is not part of active default outputs.
2. Candidate generation is split into multiple notebooks; legacy documentation assumed one notebook.
3. Wikidata candidate generation is graph-first plus fallback-stage orchestration on top of a v3 JSONL eventstore and projection handlers.

See `open-tasks.md` for operational tracking and `findings.md` for aggregated evidence.
