# Workflow

## Execution Style

1. Notebook-first execution.
2. No CLI is required for normal operation.
3. Phase notebooks are the primary entry points.

Notebook order:

1. speakermining/src/process/notebooks/10_mention_detection.ipynb
2. speakermining/src/process/notebooks/20_candidate_generation.ipynb
3. speakermining/src/process/notebooks/30_entity_disambiguation.ipynb
4. speakermining/src/process/notebooks/31_entity_deduplication.ipynb
5. speakermining/src/process/notebooks/40_link_prediction.ipynb

## Phase Ownership Rules

Each phase reads upstream data and writes only inside its own phase folder.

1. P1 writes only to data/10_mention_detection/
2. P2 writes only to data/20_canidate_generation/
3. P3.1 writes only to data/30_entity_disambiguation/
4. P3.2 writes only to data/31_entity_deduplication/
5. P4 writes only to data/40_link_prediction/

## Coupling Rules

1. Prefer low coupling over reuse.
2. Cross-phase imports are forbidden by policy.
3. Helper duplication is acceptable when it avoids tight dependencies.

## Human-in-the-loop Policy

1. Entity disambiguation is manual-only.
2. Entity deduplication is manual-only.
3. Without explicit human decisions, downstream processing must not proceed.
4. Decisions are backed up to avoid repeated review.

## Candidate Source Priority

1. Local Wikibase
2. Wikidata
3. Other sources (for example fernsehserien.de, YouTube)

## Matching Policy

1. Precision-first defaults.
2. Recall expansion is future work.
