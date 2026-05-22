# Repository Overview

This document explains how the repository currently works end-to-end.

## Pipeline Summary

1. Optional pre-phase (`10_text_extraction.ipynb`) converts raw archive PDFs into canonical `*.pdf_episodes.txt` files.
2. Phase 1 (`10_mention_detection.ipynb`) parses archive text into structured mention tables.
3. Optional inspection (`19_analysis.ipynb`) provides lightweight, confidence-aware checks over Phase 1 outputs.
4. Phase 2 (`20_` to `23_` candidate-generation notebooks) prepares lookup tables and source-specific candidate search inputs; `22_candidate_generation_fernsehserien_de.ipynb` is the active fernsehserien.de stage-2 pipeline notebook.
5. Phase 3 (`30_`, `31_`) contains manual reconciliation and deduplication decisions.
6. Phase 4 (`40_`) produces relation/link outputs.
7. Phase 5 (`50_analysis.ipynb`) produces the guest catalogue, property distribution statistics, page-rank scores, and all publication-ready visualizations.

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

### Phase 5 modules

Core data-loading and property-extraction:

- `process.analysis.config`
- `process.analysis.property_extraction`
- `process.analysis.meta_analysis`
- `process.analysis.meta_statistics`
- `process.analysis.occurrence_matrix`
- `process.analysis.person_analysis`
- `process.analysis.universal_stats`
- `process.analysis.readme_generator`

Visualization layer (all rooted in `viz_base`):

- `process.analysis.color_registry`
- `process.analysis.viz_base`
- `process.analysis.viz_binary`
- `process.analysis.viz_comparison`
- `process.analysis.viz_coverage`
- `process.analysis.viz_cross_property`
- `process.analysis.viz_dashboards`
- `process.analysis.viz_final`
- `process.analysis.viz_persons`
- `process.analysis.viz_radar`
- `process.analysis.viz_scalar`
- `process.analysis.viz_treemap`
- `process.analysis.viz_universal`

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

### `data/50_analysis`

- guest catalogue, property distribution tables, occurrence matrices
- page-rank scores and co-occurrence data
- publication-ready visualizations (PDF + PNG) under `data/50_analysis/all/`
- person-level data under `data/50_analysis/persons/` (GDPR-sensitive, gitignored)

## Known Architecture Tensions

1. Institution extraction is documented in findings and deferred code, but is not part of active default outputs.
2. Candidate generation is split into multiple notebooks; legacy documentation assumed one notebook.
3. Wikidata candidate generation is graph-first plus fallback-stage orchestration on top of a v3 JSONL eventstore and projection handlers.
4. No `__init__.py` at `speakermining/src/` level — import path setup is done manually in each notebook via `sys.path` manipulation rather than an installed package.

See `tasks/00_index.md` for operational tracking and `findings.md` for aggregated evidence.
