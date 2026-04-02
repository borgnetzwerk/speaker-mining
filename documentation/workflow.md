# Workflow

This is the authoritative source for execution order and phase ownership rules.

## Visual Overview

![SpeakerMining V3 Approach](visualizations/SpeakerMining_V3-Approach.drawio.png)

## Execution Style

1. Notebook-first execution.
2. No CLI is required for normal operation.
3. Process modules under `speakermining/src/process` are invoked by notebooks and should stay orchestration-focused.

Active notebook implementation order:

1. `speakermining/src/process/notebooks/10_text_extraction.ipynb` (optional pre-phase; only needed when source PDFs must be converted to text dumps)
2. `speakermining/src/process/notebooks/10_mention_detection.ipynb`
3. `speakermining/src/process/notebooks/19_analysis.ipynb` (optional lightweight inspection of Phase 1 outputs)
4. `speakermining/src/process/notebooks/20_candidate_generation_wikibase.ipynb`
5. `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`

Placeholder notebooks (not implemented yet):

1. `speakermining/src/process/notebooks/22_candidate_generation_fernsehserien_de.ipynb`
2. `speakermining/src/process/notebooks/23_candidate_generation_other.ipynb`
3. `speakermining/src/process/notebooks/30_entity_disambiguation.ipynb`
4. `speakermining/src/process/notebooks/31_entity_deduplication.ipynb`
5. `speakermining/src/process/notebooks/40_link_prediction.ipynb`

Historical notebook (legacy placeholder):

- `speakermining/src/process/notebooks/21_candidate_generation_wikidata_old.ipynb`

## Phase Scope

### Pre-Phase: Text Extraction (Optional)

Converts raw archive PDFs into canonical text dump files in `data/01_input/zdf_archive`.

This pre-phase is optional and should be skipped when `*.pdf_episodes.txt` files already exist.

### Phase 1: Mention Detection

Extracts from text archives in `data/01_input` and writes to `data/10_mention_detection`:

- Episodes
- Publications
- Seasons
- Persons/Guests
- Topics

Institutions are currently documented as deferred from active Phase 1 outputs.

### Phase 2: Candidate Generation

Loads setup and Phase 1 outputs, then creates lookup/context tables and candidate tables under `data/20_candidate_generation`.

### Phase 3.1: Entity Disambiguation

Manual decisions over candidate entities in `data/30_entity_disambiguation`.

### Phase 3.2: Entity Deduplication

Manual decisions over duplicate entity records in `data/31_entity_deduplication`.

### Phase 4: Link Prediction

Final relation-level outputs in `data/40_link_prediction`.

## Phase Ownership Rules

Each phase reads upstream data and writes only inside its owned folder:

1. P1 writes only to `data/10_mention_detection/`
2. P2 writes only to `data/20_candidate_generation/`
3. P3.1 writes only to `data/30_entity_disambiguation/`
4. P3.2 writes only to `data/31_entity_deduplication/`
5. P4 writes only to `data/40_link_prediction/`

## Human-In-The-Loop Policy

1. Entity disambiguation is manual.
2. Entity deduplication is manual.
3. Downstream phases must not treat unresolved manual decisions as final truth.

## Candidate Source Priority

1. Local Wikibase
2. Wikidata
3. Fernsehserien and other sources

## Notebook Runtime Logging Contract

Notebook runtime/network logging design is defined in `notebook-observability.md`.

For `21_candidate_generation_wikidata.ipynb`, major network-related decisions
must be logged into one append-only notebook event stream that persists across
runs.

## Wikidata v3 Execution Contract

The active Wikidata workflow in `21_candidate_generation_wikidata.ipynb` is canonical v3 event-sourcing.

Execution sequence:

1. Bootstrap required artifacts under `data/20_candidate_generation/wikidata/`.
2. Stage A graph-first expansion (seed-order deterministic, checkpointed resume).
3. Build unresolved target handoff.
4. Stage B fallback string matching only for unresolved targets.
5. Re-check fallback discoveries against graph expandability and re-enter eligible QIDs.
6. Append runtime events to `chunks/*.jsonl` and maintain checkpoint state.
7. Materialize deterministic projection artifacts under `projections/` through handler replay.

Policy guardrails:

1. `chunks/` is the canonical append-only event log; boundary continuity is represented by `eventstore_opened` and `eventstore_closed` events.
2. Legacy `raw_queries/` artifacts are migration/archive inputs and are not the canonical runtime event stream.
3. Legacy/pre-v3 compatibility logic is out of scope for runtime code.

## Matching Policy

1. Precision-first defaults.
2. Recall expansion is acceptable only when confidence and traceability fields are maintained.
