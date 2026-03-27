# Work Tracker

Single source of truth for open and solved TODO items.

## Entry Template

Copy this block when adding a new item.

### [ID]: [Short title]

- Priority: high | medium | low
- Status: open | in-progress | blocked | solved | wont-fix
- Area: ingestion | parsing | modeling | docs | workflow | contracts | analysis | architecture | other
- Summary: one sentence describing the problem or goal.
- Evidence: file, notebook, or data reference.
- Definition of done:
  1. observable completion criterion.
  2. observable completion criterion.
  3. validation/documentation criterion.
- Notes: optional context or constraints.

## High Priority

### TODO-001: Add archive-level episode dedup before extraction

- Priority: high
- Status: open
- Area: ingestion
- Summary: cross-file overlap in archive inputs can duplicate episodes before Phase 1 write.
- Evidence: `documentation/findings.md` (former `findings/findings.md`).
- Definition of done:
  1. duplicate episode blocks are detected before final CSV write.
  2. dedup behavior is documented in `workflow.md` and `contracts.md` if schema changes.
  3. known overlap case is reproducible and covered.

### TODO-008: Resolve Remaining Guest Extraction Misses (13 Episodes)

- Priority: high
- Status: open
- Area: parsing
- Summary: 13 episodes still have no extracted guests although at least some `infos` texts still contain guest-relevant signals.
- Evidence: `data/10_mention_detection/episodes_without_person_mentions.csv`, `documentation/context/mention-detection-guest-diagnostics-2026-03-27.md`.
- Definition of done:
  1. each of the 13 remaining episodes is triaged with explicit reason (`extractable_with_rules` vs `not_extractable_from_infos`).
  2. parser rules are extended for extractable cases and reduce the unresolved count.
  3. `episodes_without_person_mentions.csv` and diagnostics context are regenerated and documented.

### TODO-009: Fix Episode Text Parsing Gap For EPISODE 363

- Priority: high
- Status: open
- Area: ingestion
- Summary: text-to-episode parsing in `11_mention_detection.ipynb` (via phase modules) drops at least EPISODE 363 infos although source archive text contains it.
- Evidence: `speakermining/src/process/notebooks/11_mention_detection.ipynb`, `data/01_input/zdf_archive/Markus Lanz_2011-2015.pdf_episodes.txt`.
- Definition of done:
  1. root cause for EPISODE 363 infos loss is identified in episode parsing logic.
  2. parsing fix preserves infos text for EPISODE 363 and does not regress neighboring episodes.
  3. validation cell or reproducible check is added and results are documented in findings/context.

## Medium Priority

### TODO-002: Normalize name variants with umlaut/ss expansion

- Priority: medium
- Status: open
- Area: parsing
- Summary: transliteration variants (`THEVEßEN` / `THEVESSEN`) can break exact matching.
- Evidence: `documentation/findings.md`.
- Definition of done:
  1. deterministic normalization utility is implemented.
  2. utility is applied in relevant candidate-generation matching path.
  3. tests or notebook validation covers known variants.

### TODO-003: Normalize abbreviation variants in descriptions

- Priority: medium
- Status: open
- Area: parsing
- Summary: abbreviation variants (`ehem`, `ehem.`, `Vors`, `Vors.`) are not normalized centrally.
- Evidence: `documentation/findings.md`.
- Definition of done:
  1. normalization rules are documented and implemented.
  2. affected extraction output fields are updated.
  3. impact is measured on a representative sample.

### TODO-004: Introduce explicit person mention categories

- Priority: medium
- Status: open
- Area: modeling
- Summary: guest mentions, topic-person mentions, and incidental mentions are not explicitly separated.
- Evidence: TODO section in `10_mention_detection.ipynb`.
- Definition of done:
  1. schema includes a mention category field.
  2. extraction logic and validation cells are updated.
  3. downstream assumptions are adjusted.

### TODO-010: Reconstruct Split Family Names Across Description Blocks

- Priority: medium
- Status: open
- Area: parsing
- Summary: some guest strings split given names into description text while surname appears once in the lead (for example `Familie EWERDWALBESLOH (Walter, Corinna und Sohn Leon, ...)`), requiring reconstruction of full person names.
- Evidence: mention-detection guest parsing examples in `episodes.infos` and parser logic in `speakermining/src/process/mention_detection/guest.py`.
- Definition of done:
  1. parser detects family/group patterns with shared surname and reconstructs full names (for example `Walter EWERDWALBESLOH`, `Corinna EWERDWALBESLOH`, `Leon EWERDWALBESLOH`).
  2. reconstructed rows are tagged with dedicated parsing rules and conservative confidence.
  3. validation examples are added to analysis context and checked for false-positive drift.

### [ID]: Identify clusters of potential misspellings 

- Priority: medium
- Status: open
- Area: ingestion | parsing | modeling | docs | workflow | contracts | analysis | architecture | other
- Summary: Before we check every different spelling of a name or occupation, we should try to identify such clusters and map them to a common, correct name.
- Definition of done:
  1. Clusters potential is identified. Uncertainty is quantified and documented alongside.
  2. A new cell is created, like "name_cleaned" or "name_before_clustering", not dropping the old.

## Low Priority

### TODO-005: Clarify institution extraction responsibility by phase

- Priority: low
- Status: open
- Area: architecture
- Summary: institution extraction exists in deferred code/findings but not in active default outputs.
- Evidence: `speakermining/src/process/candidate_generation/INSTITUTION_EXTRACTION_DEFERRED.md`, `documentation/findings.md`.
- Definition of done:
  1. architecture decision is documented in `workflow.md`.
  2. conflicting wording is removed from docs.
  3. deferred extraction is either activated with contract updates or explicitly archived.

### TODO-006: Define reproducible methodology for gender-framing analysis

- Priority: low
- Status: open
- Area: analysis
- Summary: gender-framing question exists but lacks reproducible query/method.
- Evidence: archived note in `documentation/findings.md`.
- Definition of done:
  1. metrics and categories are explicitly defined.
  2. reproducible analysis step is documented.
  3. output artifact location is specified.

### TODO-007: Define merge strategy for role/occupation/position/institution

- Priority: low
- Status: open
- Area: modeling
- Summary: merge-identification requirement is noted but not operationalized.
- Evidence: archived note in `documentation/findings.md`.
- Definition of done:
  1. merge semantics are defined.
  2. required schema or pipeline changes are identified.
  3. implementation plan is documented.

## Solved

### TODO-900: Correct candidate-generation notebook links in root README

- Priority: high
- Status: solved
- Area: docs
- Summary: README referenced non-existing `20_candidate_generation.ipynb`.
- Evidence: root `README.md` history.
- Definition of done:
  1. split notebook sequence (`20` to `23`) is documented.
  2. historical notebook is marked as non-default.
  3. workflow docs are consistent.

### TODO-901: Fix phase path typo in documentation

- Priority: high
- Status: solved
- Area: docs
- Summary: typo `20_canidate_generation` existed in docs.
- Evidence: docs history.
- Definition of done:
  1. all references use `data/20_candidate_generation`.
  2. workflow and contracts are aligned.
  3. no stale typo remains in core docs.

### TODO-902: Archive orphan findings and track them structurally

- Priority: low
- Status: solved
- Area: docs
- Summary: short orphan notes were converted into tracked work items and archived notes.
- Evidence: `documentation/findings.md`.
- Definition of done:
  1. orphan topics are represented in this tracker.
  2. orphan source notes are archived/aggregated.
  3. stale findings index files are removed.

### TODO-903: Inline tracker template at top of tracker file

- Priority: low
- Status: solved
- Area: docs
- Summary: template moved into the top of the single tracker file.
- Evidence: this document.
- Definition of done:
  1. template appears at top of this file.
  2. no separate templates are required.
  3. documentation hub points contributors here.

### TODO-904: Stabilize Guest Detection For Anchor And Name Variants

- Priority: high
- Status: solved
- Area: parsing
- Summary: guest extraction missed episodes when host-anchor phrasing varied or when names appeared as mononyms or surname-primary blocks without parenthetical descriptors.
- Evidence: `data/10_mention_detection/episodes_without_person_mentions.csv`, `documentation/context/mention-detection-guest-diagnostics-2026-03-27.md`.
- Definition of done:
  1. parser supports broader interview-opening section detection beyond strict `Mark... LANZ ... mit`.
  2. surname-primary guest extraction fallback exists for non-parenthetical guest list lead segments.
  3. mention-detection conventions are documented in dedicated documentation.
