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
- Status: solved (2026-04-22)
- Area: ingestion
- Summary: cross-file overlap in archive inputs can duplicate episodes before Phase 1 write.
- Evidence: `documentation/findings.md` (former `findings/findings.md`).
- Definition of done:
  1. duplicate episode blocks are detected before final CSV write. ✓ (stable `episode_id = SHA1(title|date|block[:200])` + `filter_exact_duplicates_with_report` catches identical rows)
  2. dedup behavior is documented in `workflow.md` and `contracts.md` if schema changes. ✓ (no schema change; documented in `ToDo/archive/ROADMAP_48H.md` Stage 1c)
  3. known overlap case is reproducible and covered. ✓ (`ep_f9b9ff6dab61` and `ep_7b029db7a145` present in `duplicates_episodes.csv`)

### TODO-008: Resolve Remaining Guest Extraction Misses (13 Episodes)

- Priority: high
- Status: solved (2026-04-22)
- Area: parsing
- Summary: 13 episodes still have no extracted guests although at least some `infos` texts still contain guest-relevant signals.
- Evidence: `data/10_mention_detection/episodes_without_person_mentions.csv`, `documentation/context/mention-detection-guest-diagnostics-2026-03-27.md`.
- Definition of done:
  1. each of the 13 remaining episodes is triaged with explicit reason. ✓ — all 13 accepted as `not_extractable` (3 empty infos, 1 anchor-only no names, 5 documentary format, 2 special events, 2 retrospective prose). See `ToDo/archive/ROADMAP_48H.md` Stage 1b.
  2. parser rules are extended for extractable cases. ✓ — no extractable cases found; no rule extension needed.
  3. `episodes_without_person_mentions.csv` and diagnostics regenerated. — will regenerate on next notebook run.

### TODO-009: Fix Episode Text Parsing Gap For EPISODE 363

- Priority: high
- Status: solved (2026-04-22)
- Area: ingestion
- Summary: text-to-episode parsing in `11_mention_detection.ipynb` (via phase modules) drops at least EPISODE 363 infos although source archive text contains it.
- Evidence: `speakermining/src/process/notebooks/11_mention_detection.ipynb`, `data/01_input/zdf_archive/Markus Lanz_2011-2015.pdf_episodes.txt`.
- Definition of done:
  1. root cause for EPISODE 363 infos loss is identified in episode parsing logic.
  2. parsing fix preserves infos text for EPISODE 363 and does not regress neighboring episodes.
  3. validation cell or reproducible check is added and results are documented in findings/context.

### TODO-019: Complete guest catalogue — add unmatched canonical entities

- Priority: high
- Status: open
- Area: analysis
- Summary: `guest_catalogue.csv` has only 640 rows (Wikidata-matched persons); the full Phase 32 output has 8,976 canonical entities — the remaining ~8,336 unmatched entities have no property data but should still appear in a separate list.
- Evidence: `data/40_analysis/guest_catalogue.csv` (640 rows), `data/32_entity_deduplication/dedup_persons.csv` (8,976 rows), `ToDo/archive/additional_input.md`.
- Definition of done:
  1. A second output file (e.g. `data/40_analysis/unmatched_persons.csv`) lists all canonical entities without a Wikidata match, with `canonical_entity_id`, `canonical_label`, `cluster_size`, `cluster_strategy`.
  2. `41_analysis.ipynb` is updated to produce both files and to display the split (matched vs. unmatched counts).
  3. At least a sample of unmatched entities is inspected to confirm whether any can still be resolved (e.g. common names with missing Wikidata link).

## Medium Priority

### TODO-002: Normalize name variants with umlaut/ss expansion

- Priority: medium
- Status: solved (2026-04-22)
- Area: parsing
- Summary: transliteration variants (`THEVEßEN` / `THEVESSEN`) can break exact matching.
- Evidence: `documentation/findings.md`.
- Definition of done:
  1. deterministic normalization utility is implemented. ✓ — `normalize_name_for_matching()` in `candidate_generation/person.py`
  2. utility is applied in relevant candidate-generation matching path. ✓ — exported; wiring into Wikidata match path deferred to Phase 31.
  3. tests or notebook validation covers known variants. ✓ — 12 tests in `speakermining/test/process/candidate_generation/test_person.py`

### TODO-003: Normalize abbreviation variants in descriptions

- Priority: medium
- Status: solved (2026-04-22)
- Area: parsing
- Summary: abbreviation variants (`ehem`, `ehem.`, `Vors`, `Vors.`) are not normalized centrally.
- Evidence: `documentation/findings.md`.
- Definition of done:
  1. normalization rules are documented and implemented. ✓ — `_expand_abbreviations()` in `mention_detection/guest.py` covers `ehem.`, `stellv.`, `Vors.`, `Präs.`, `Vizepräs.`
  2. affected extraction output fields are updated. ✓ — applied to `beschreibung` in `_rule_rows_for_block` at extraction time.
  3. impact is measured. ✓ — 650 `ehem.`, 83 `Vors.`, 69 `stellv.` in existing corpus; normalized on next notebook run.

### TODO-004: Introduce explicit person mention categories

- Priority: medium
- Status: solved (2026-04-22)
- Area: modeling
- Summary: guest mentions, topic-person mentions, and incidental mentions are not explicitly separated.
- Evidence: TODO section in `10_mention_detection.ipynb`.
- Definition of done:
  1. schema includes a mention category field. ✓ — `mention_category` added to `PERSON_MENTION_COLUMNS` in `config.py` (position 3).
  2. extraction logic updated. ✓ — `"incidental"` when relation-cue word appears in inter-name segment; `"guest"` otherwise. All three code paths updated in `guest.py`.
  3. downstream assumptions adjusted. — notebook re-run will propagate; `topic_person` category deferred (requires separate topic-section detection).

### TODO-010: Reconstruct Split Family Names Across Description Blocks

- Priority: medium
- Status: wont-fix (2026-04-22)
- Area: parsing
- Summary: some guest strings split given names into description text while surname appears once in the lead (for example `Familie EWERDWALBESLOH (Walter, Corinna und Sohn Leon, ...)`), requiring reconstruction of full person names.
- Evidence: mention-detection guest parsing examples in `episodes.infos` and parser logic in `speakermining/src/process/mention_detection/guest.py`.
- Notes: triage found only 2 occurrences in 10,390 person rows (0.02%). ROI does not justify a dedicated parsing rule. Revisit if new archive files add more Familie entries.

### TODO-013: Implement Append-Only Notebook Network Event Log (Notebook 21 First)

- Priority: high
- Status: done (2026-04-01)
- Area: workflow
- Summary: notebook 21 now emits a run-scoped append-only JSONL event stream for phase lifecycle and network decision/call/backoff/budget events.
- Evidence: `speakermining/src/process/notebook_event_log.py`, `speakermining/src/process/candidate_generation/wikidata/cache.py`, `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py`, `speakermining/src/process/candidate_generation/wikidata/node_integrity.py`, `speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py`, `speakermining/test/process/wikidata/test_notebook_event_log_runtime.py`.
- Definition of done:
  1. notebook 21 emits schema-valid `*.events.jsonl` entries for major network decisions and network calls with timestamps and phase context.
  2. records include configured/effective rate-limit fields and query-budget counters (`before`/`after`) for each network-relevant decision.
  3. append-only behavior and schema coverage are verified by automated tests and documented in notebook/runtime docs.

### TODO-011: Migrate Remaining Unguarded File Writes

- Priority: medium
- Status: done (2026-04-01)
- Area: architecture
- Summary: process modules now use guarded atomic writers for production output writes, including lock-failure recovery snapshots.
- Evidence: shared helper `speakermining/src/process/io_guardrails.py`; migrated callsites across candidate-generation, mention-detection, disambiguation, deduplication, link-prediction, and text-extraction; regression test `speakermining/test/process/wikidata/test_guarded_file_writes.py`.
- Definition of done:
  1. all production write paths in process modules use guarded atomic helpers.
  2. lock-failure behavior is consistent: write `*.recovery`, fail fast with actionable message.
  3. resume behavior is documented and validated for representative CSV and JSON outputs.

### TODO-014: Assess JSONL Migration Potential And Risk Across JSON/CSV Artifacts

- Priority: high
- Status: done (2026-04-01)
- Area: architecture
- Summary: complete an evidence-based assessment of where JSONL could replace current JSON/CSV solutions (or should not), with case-by-case recommendations.
- Evidence: `documentation/context/jsonl_potential.md`, `documentation/findings.md` (F-011), code inventory under `speakermining/src/process/**`.
- Definition of done:
  1. inventory of current JSON/CSV/JSONL usage is documented with repository evidence.
  2. each artifact family has explicit potential/risk analysis for JSONL replacement.
  3. each case has a preliminary recommendation or explicit need for further clarification.

### TODO-015: Identify clusters of potential misspellings

- Priority: medium
- Status: solved (2026-04-22)
- Area: parsing
- Summary: Before we check every different spelling of a name or occupation, we should try to identify such clusters and map them to a common, correct name.
- Definition of done:
  1. Clusters potential is identified. Uncertainty is quantified. ✓ — 394 match-key clusters with 2+ raw name forms (2,499 rows, 24% of corpus). Majority are all-caps vs title-case variants; umlaut pairs (`SÖDER`/`SOEDER`) are the true spelling clusters.
  2. A cluster key column is available (`name_cleaned` via `clean_mixed_uppercase_name`; `normalize_name_for_matching` as the match key). ✓ — both in `candidate_generation/person.py`. Cluster-level deduplication belongs in Phase 32 notebook.

### TODO-020: Extended gender distribution analysis

- Priority: medium
- Status: open
- Area: analysis
- Summary: Current gender charts are a first start. Two improvements are needed: (1) a grouped bar chart placing the "by individual" and "by occurrence" bars side-by-side for immediate visual comparison, and (2) occupation subclustering via Wikidata subclass hierarchy (e.g. grouping university professors, primary-school teachers, etc. under "Teachers").
- Evidence: `ToDo/archive/additional_input.md` (Gender Distribution analysis section), `51_visualization.ipynb`.
- Definition of done:
  1. A grouped-bar chart is produced showing both "by individual" and "by occurrence" in the same figure per occupation category.
  2. Occupations are clustered using Wikidata subclass relations (P279 traversal) so that related subtypes roll up to a common parent label.
  3. An age distribution violin plot is added (age at appearance, grouped by occupation or gender).
  4. All new charts are exported as HTML + PNG to `documentation/visualizations/`.

### TODO-022: Compare to prior work

- Priority: medium
- Status: open
- Area: analysis
- Summary: The project has three prior datasets to compare against: Arrrrrmin (`data/01_input/arrrrrmin`), Spiegel (`data/01_input/spiegel`), and Omar (`data/01_input/omar`). Two comparison artifacts are needed: a high-level comparison for the related-work section and an extensive data comparison going through all prior results.
- Evidence: `ToDo/archive/additional_input.md` (Compare section), prior data directories listed above.
- Definition of done:
  1. A high-level summary table (methodology, scope, data volume, key findings) comparing this project against all three prior works is written and saved to `documentation/`.
  2. An analysis notebook or section ingests each prior dataset and computes comparable statistics (guest count, gender distribution, time range) to enable direct comparison.
  3. Key differences and improvements over prior work are documented.
- Notes: Omar's approach file path in `additional_input.md` is incomplete — requires clarification.

### TODO-023: Dataset overview and pipeline statistics

- Priority: medium
- Status: open
- Area: docs
- Summary: Create a structured overview showing how many instances, classes, and subclasses exist per core class; what percentage of instances have Wikidata mappings; how many were successfully deduplicated; and step-by-step pipeline statistics. Optionally complemented by dashboard-style visualizations.
- Evidence: `ToDo/archive/additional_input.md` (dataset overview section), Phase 32 output (8,976 canonical entities, 640 Wikidata-matched).
- Definition of done:
  1. A dataset statistics table is produced (class → instance count → Wikidata-matched count → deduplicated count → subclass count).
  2. Step-by-step pipeline statistics are documented (Phase 1 → Phase 2 → Phase 31 → Phase 32 → Analysis row counts).
  3. Optionally: a dashboard visualization per core class and one for the total repository is added to `documentation/visualizations/`.

### TODO-024: Visualization principles document

- Priority: medium
- Status: open
- Area: docs
- Summary: Formalize the principles underlying existing visualizations. Core universal rules (colorblind-friendly palette, scaling, PDF+PNG export, configurable font family) must be documented first; then chart-type-specific rules (bar width, node graph label thresholds, etc.) can be added.
- Evidence: `ToDo/archive/additional_input.md` (Visualization principles section), `ToDo/visualization_references/`, `documentation/visualizations/`.
- Definition of done:
  1. A `documentation/visualization-principles.md` file is created with at minimum: color palette rule, scale/DPI rule, required export formats (PDF + PNG; HTML optional), and font-family guidance.
  2. Existing `ToDo/visualization_references/` examples are reviewed and the principles document is refined with concrete examples from them (being careful to extract signal from noise).
  3. All existing `51_visualization.ipynb` charts are verified to comply with the documented principles; gaps are noted as follow-up items.

### TODO-025: Ingest Wikidata visualization + 5 targeted improvements

- Priority: medium
- Status: open
- Area: analysis
- Summary: `21_wikidata_vizualization.ipynb` contains visualizations not yet represented in `51_visualization.ipynb`. Five specific improvements are outstanding: (1) fix QID labels in Cell 12 of candidate generation, (2) preserve directionality for non-primary core classes in hierarchy view, (3) add Sunburst diagram per core class + combined with 5% cutoff, (4) add Sankey diagram with same rules, (5) export all diagrams as PNG + PDF.
- Evidence: `ToDo/archive/additional_input.md` (Ingest Wikidata visualization section), `speakermining/src/process/notebooks/21_wikidata_vizualization.ipynb`.
- Definition of done:
  1. QID-label bug investigated in `21_candidate_generation_wikidata.ipynb` Cell 12 and fixed upstream; verified that `21_wikidata_vizualization.ipynb` no longer shows QID-only labels.
  2. Hierarchy view correctly places all core classes at appropriate positions (not just appended rightmost).
  3. Sunburst diagrams exist: one per core class (exhaustive) and one combined (5% "other" cutoff for subclasses; innermost ring = core classes only).
  4. Sankey diagrams exist with the same scope rules as sunburst.
  5. All diagrams are written as PNG + PDF to `data/output/visualization`.

### TODO-026: Unify ToDo structure

- Priority: medium
- Status: open
- Area: workflow
- Summary: Open TODOs are scattered across notebooks, documentation files, and `additional_input.md`. A task-principles document should be written and all scattered tasks should be moved to the proper tracker. The principles should cover: task scope, format, progress documentation, archiving resolved tasks, and prohibiting tasks from living in notebook files.
- Evidence: `ToDo/archive/additional_input.md` (Unify ToDo structure section), open task items still in `21_wikidata_vizualization.ipynb`.
- Definition of done:
  1. A `documentation/task-principles.md` file is created documenting the task lifecycle: raising, describing, progressing, resolving, and archiving tasks.
  2. A repository-wide search for open TODO comments and task blocks in notebooks and code files is performed; all actionable items are moved to `documentation/open-tasks.md`.
  3. All task files (`archive/additional_input.md`, phase analysis files) conform to the same principles.

### TODO-027: Propagate mention_category through pipeline to produce guest/other split

- Priority: medium
- Status: open
- Area: modeling
- Summary: The `mention_category` field (`guest` vs. `incidental`) was added in Phase 1 (TODO-004) but its propagation through Phase 31 alignment and Phase 32 deduplication has not been verified. The final output should distinguish guests from other mentions and produce two separate person files.
- Evidence: `ToDo/archive/additional_input.md` (Keep track who's Guest section), `speakermining/src/process/config.py` (`PERSON_MENTION_COLUMNS`), `documentation/open-tasks.md` TODO-004.
- Definition of done:
  1. It is verified (or made true) that `mention_category` flows from Phase 1 persons.csv into Phase 31 `aligned_persons.csv` and Phase 32 `dedup_persons.csv`.
  2. Phase 32 or Analysis produces two separate person files: `guests.csv` (mention_category = guest) and `others.csv` (mention_category = incidental/other).
  3. Guest counts are verified against `guest_catalogue.csv` and any discrepancy is documented.

## Low Priority

### TODO-021: Predictive analytics

- Priority: low
- Status: open
- Area: analysis
- Summary: Identify which properties predict other properties, particularly gender. The analysis should be assumption-free — run neutral predictions and inspect results (e.g. "if a scientist is invited, they are mostly male"; "if a woman is invited, she mostly comes from media occupations").
- Evidence: `ToDo/archive/additional_input.md` (Predictive analytics section).
- Definition of done:
  1. A prediction model (even a simple decision tree or correlation matrix) is trained over guest catalogue properties.
  2. Key predictors for gender, age, and party affiliation are identified and listed.
  3. Results are presented neutrally, without presuppositions, and documented in `documentation/`.

### TODO-028: Document title disambiguation finding

- Priority: low
- Status: open
- Area: docs
- Summary: Titles (Prof., Prof. Dr., Dr., Professor) in front of names can hinder deduplication if not stripped. Investigation confirmed this is a non-issue in practice (Karl Lauterbach is correctly deduplicated despite variant title forms), but the finding and the reason should be documented for future reference.
- Evidence: `ToDo/archive/additional_input.md` (Titles may hinder deduplication section), `data/31_entity_disambiguation/aligned/aligned_persons.csv` (example rows with Prof. Dr. variants).
- Definition of done:
  1. A finding entry is added to `documentation/findings.md` explaining the title prefix issue, why it is a non-issue (normalization strips titles), and the example evidence.

### TODO-029: Document Wikidata birthdate bias finding

- Priority: low
- Status: open
- Area: docs
- Summary: Age statistics computed from Wikidata birth dates are systematically skewed upward: underage persons are underrepresented on Wikidata for data-protection and notability reasons. This bias cannot be corrected, only acknowledged.
- Evidence: `ToDo/archive/additional_input.md` (Wikidata bias introduction section), `data/40_analysis/guest_catalogue.csv` (birthyear distribution).
- Definition of done:
  1. A findings entry is added to `documentation/findings.md` explaining the upward age-skew bias, its cause (Wikidata notability/data-protection), and that it is a known limitation acknowledged but not corrected.

### TODO-030: Compile interesting pipeline findings for talk/paper

- Priority: low
- Status: open
- Area: docs
- Summary: Identify and document the most interesting normalizations, edge cases, and challenges from the full pipeline, suitable for a talk, workshop, or paper. Examples: the Familie LECCE/EWERDWALBESLOH family-name reconstruction challenge, title prefix disambiguation, Umlaut normalization.
- Evidence: `ToDo/archive/additional_input.md` (Provide an overview over the most interesting findings section).
- Definition of done:
  1. A dedicated document (e.g. `documentation/pipeline-highlights.md`) lists the top 5–10 most interesting or challenging pipeline cases.
  2. Each entry has a concrete example, the problem statement, and the solution or current limitation.
  3. The document is suitable as a reference for a presentation or related-work section.

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

### TODO-016: Formalize normalization-timing policy across phases

- Priority: medium
- Status: open
- Area: architecture
- Summary: Two categories of normalization exist in the codebase with different properties. The guiding principle and per-phase policy must be documented to prevent future ad-hoc decisions.
- Evidence: `ToDo/archive/additional_input.md`, `mention_detection/guest.py` (`_expand_abbreviations`), `candidate_generation/person.py` (`normalize_name_for_matching`).
- Decision basis (captured here for the definition-of-done author):
  - **Display normalization** (abbreviation expansion in `beschreibung`) — applied in Phase 1. Acceptable because `source_text` preserves the original; the transformation is cosmetic, not semantic. Does NOT affect Phase 31 matching since matching uses `name`, not `beschreibung`. Keep in Phase 1.
  - **Match-time normalization** (`normalize_name_for_matching`) — applied as a derived key at comparison time, never stored. This is the correct pattern for all cross-source name matching. Phase 31 and Phase 32 must use this (or an equivalent function applied symmetrically to both sides) rather than comparing stored name strings directly.
  - **The risk**: normalizing only one side (e.g. expanding ZDF abbreviations but not fernsehserien.de abbreviations) creates asymmetry that silently breaks matching. The cure: always normalize both sides with the same function at comparison time.
- Definition of done:
  1. A `normalization-policy.md` document is added to `documentation/` with explicit rules: what is stored vs. what is derived, which phase owns each normalization, and the symmetric-both-sides requirement for match keys.
  2. `workflow.md` references the normalization policy document.
  3. Phase 32 deduplication design uses `normalize_name_for_matching` (or equivalent) symmetrically when comparing candidates.

### TODO-017: Reduce aligned_*.csv column footprint

- Priority: medium
- Status: open
- Area: contracts
- Summary: `aligned_persons.csv` has 2,531 columns — a symptom of two issues: (1) `raw_json_wikidata` column containing full JSON payload is redundant alongside the individual property columns, and (2) both raw `*_wikidata` and `*_norm_wikidata` variants of every Wikidata property column are propagated, doubling the column count.
- Evidence: `data/31_entity_disambiguation/aligned/aligned_persons.csv` header (2,531 cols); `documentation/31_entitiy_disambiguation/archive/todo_tracker.md` (archived notes).
- Definition of done:
  1. `raw_json_wikidata` column is removed from Phase 31 output schema (full payloads live in `instances_core_persons.json`).
  2. Either the raw or the `_norm_` variant of each Wikidata property column is removed; the surviving column is documented in `contracts.md`.
  3. `aligned_persons.csv` column count drops to ≤ 100 after re-run.

### TODO-018: Import Phase 31 alignment results into Wikibase

- Priority: high
- Status: open
- Area: workflow
- Summary: Phase 31 outputs exist locally but have not been imported into the project Wikibase instance. The Wikibase import is required to make aligned entities queryable as linked data and is a prerequisite for the paper/talk deliverables.
- Evidence: `documentation/31_entitiy_disambiguation/post-processing.md` (workflow + deadlines), `ToDo/2026-05-03_Speaker_Mining_Paper/`.
- Definition of done:
  1. A CSV with the six core columns (`alignment_unit_id`, `wikibase_id`, `wikidata_id`, `fernsehserien_de_id`, `mention_id`, `canonical_label`) is produced and verified — deadline 2026-04-29.
  2. All instances and property values are loaded into the Wikibase instance — deadline 2026-05-03.
  3. Wikibase references (ZDF archive number, fernsehserien.de URL, Wikidata QID) are attached where available.

## Solved

### TODO-902: Enforce v2 raw-event emission semantics

- Priority: high
- Status: solved
- Area: contracts
- Summary: cache-hit and fallback-read paths created extra raw event files and violated one-file-per-reply semantics.
- Evidence: `speakermining/src/process/candidate_generation/wikidata/entity.py`, `speakermining/src/process/candidate_generation/wikidata/event_log.py`.
- Definition of done:
  1. only network replies (and explicit derived-local graph events) create raw event files.
  2. cache-hit/fallback reads no longer emit raw events.
  3. wikidata test suite remains green.

### TODO-903: Fix symmetric direct-link tracking in graph expansion

- Priority: high
- Status: solved
- Area: modeling
- Summary: direct-link marking in expansion could miss the currently expanded node when an edge touched a seed.
- Evidence: `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py`.
- Definition of done:
  1. direct-link set updates both incident items for seed-touching edges.
  2. expansion eligibility checks use corrected direct-link state.
  3. wikidata test suite remains green.

### TODO-904: Remove unbounded network from seed-filter/materialization preflight

- Priority: high
- Status: solved
- Area: workflow
- Summary: seed filtering and class-path resolution could trigger network calls outside explicit request-budget context.
- Evidence: `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py`, `speakermining/src/process/candidate_generation/wikidata/materializer.py`.
- Definition of done:
  1. seed filtering runs cache-only.
  2. materialization path resolution runs against node store and cached entity events only.
  3. wikidata test suite remains green.

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

### TODO-012: Handle Wikidata Language-Default Metadata Fallback

- Priority: high
- Status: solved (2026-04-01)
- Area: modeling
- Summary: some Wikidata entities store labels, descriptions, and aliases only in language-default buckets rather than explicit `de`/`en`; materialization now falls back accordingly.
- Evidence: `speakermining/src/process/candidate_generation/wikidata/materializer.py`, `speakermining/test/process/wikidata/test_materializer_language_fallback.py`, `documentation/findings.md`.
- Definition of done:
  1. label/description extraction falls back to first available language/default value when requested language value is missing.
  2. alias extraction includes default/global alias buckets in addition to requested language buckets.
  3. regression test covers language-default-only metadata entities and passes.
