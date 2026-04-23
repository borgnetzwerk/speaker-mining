# Work Tracker

Single source of truth for open TODO items.
solved and closed items move to `documentation/archive/closed-tasks.md`

## Entry Template

Copy this block when adding a new item.

### [ID]: [Short title]

- Priority: high | medium | low
- Status: open | in-progress | blocked | wont-fix
- Area: ingestion | parsing | modeling | docs | workflow | contracts | analysis | architecture | other
- Summary: one sentence describing the problem or goal.
- Evidence: file, notebook, or data reference.
- Definition of done:
  1. observable completion criterion.
  2. observable completion criterion.
  3. validation/documentation criterion.
- Notes: optional context or constraints.

## High Priority

### TODO-018: Integrate authoritative 6-column reconciliation CSV into Phase 32

- Priority: high
- Status: open
- Area: workflow
- Summary: The OpenRefine reconciliation team is producing a 6-column CSV (`alignment_unit_id`, `wikibase_id`, `wikidata_id`, `fernsehserien_de_id`, `mention_id`, `canonical_label`) as the authoritative output of manual Phase 31 reconciliation. This CSV must be integrated into Phase 32 as the highest-confidence deduplication tier, superseding automated strategies where present. Our task is to be ready to receive and integrate it — the CSV itself is produced externally.
- Evidence: `documentation/31_entitiy_disambiguation/post-processing.md` (workflow + deadlines), `ToDo/2026-05-03_Speaker_Mining_Paper/`.
- Definition of done:
  1. The integration contract is documented in `contracts.md`: where the incoming CSV is placed, what Phase 32 does with it, and how it overrides automated clustering.
  2. Phase 32 logic (`orchestrator.py` or a new step) reads the incoming CSV and promotes its entries to a new `manual_reconciliation` cluster strategy with confidence = `authoritative`.
  3. The 6-column CSV is received from the reconciliation team and ingested — deadline 2026-05-03.
- Notes: The CSV is produced externally (manual OpenRefine reconciliation); deadline for receiving it is 2026-04-29. We must not block on it — implement integration logic now so it is ready to run as soon as the file arrives.

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

### TODO-024: Visualization principles document

- Priority: high
- Status: open
- Area: docs
- Summary: Formalize the principles underlying existing visualizations. Core universal rules (colorblind-friendly palette, scaling, PDF+PNG export, configurable font family) must be documented first; then chart-type-specific rules (bar width, node graph label thresholds, etc.) can be added.
- Evidence: `ToDo/archive/additional_input.md` (Visualization principles section), `ToDo/visualization_references/`, `documentation/visualizations/`.
- Definition of done:
  1. A `documentation/visualization-principles.md` file is created with at minimum: color palette rule, scale/DPI rule, required export formats (PDF + PNG; HTML optional), and font-family guidance.
  2. Existing `ToDo/visualization_references/` examples are reviewed and the principles document is refined with concrete examples from them (being careful to extract signal from noise).
  3. All existing `51_visualization.ipynb` charts are verified to comply with the documented principles; gaps are noted as follow-up items.
- Notes: Hierarchy layout visualizations (horizontal, radial) should minimize line overlap by co-locating subclasses that share the same set of superclasses. Nodes whose edges do not interact with a dense cluster should be placed at the cluster perimeter, not its interior. This edge-overlap-minimization principle applies to all hierarchical layout types.

## Medium Priority

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
- Summary: `aligned_persons.csv` has 2,531 columns — a symptom of two issues: (1) `raw_json_wikidata` column containing full JSON payload is redundant alongside the individual property columns, and (2) both raw `*_wikidata` and `*_norm_wikidata` variants of every Wikidata property column are propagated, doubling the column count. The bloated count also makes OpenRefine reconciliation projects slow to load, but some context columns are genuinely useful for manual reconciliation.
- Evidence: `data/31_entity_disambiguation/aligned/aligned_persons.csv` header (2,531 cols); `documentation/31_entitiy_disambiguation/archive/todo_tracker.md` (archived notes).
- Definition of done:
  1. `raw_json_wikidata` column is removed from Phase 31 output schema (full payloads live in `instances_core_persons.json`).
  2. Either the raw or the `_norm_` variant of each Wikidata property column is removed; the surviving column is documented in `contracts.md`.
  3. Column selection prioritizes: core IDs, label, description, aliases, source links, and the most commonly populated properties (e.g. occupation for persons). Columns that are ≥ 99% empty or offer no value to a human reviewer are cut first.
  4. `aligned_persons.csv` column count drops to approximately 40 after re-run (hard ceiling: 50).
- Notes: The ~40-column target is driven by OpenRefine usability — a reconciliation project with thousands of columns is difficult to load and review. Preserve enough columns for a human reviewer to confidently match or reject an entity without leaving OpenRefine.

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
  4. All new charts are exported as PDF + PNG (+ HTML optionally)  to `documentation/visualizations/`.

### TODO-022: Compare to prior work

- Priority: medium
- Status: open
- Area: analysis
- Summary: The project has three prior datasets to compare against: Arrrrrmin (`data/01_input/arrrrrmin`), Spiegel (`data/01_input/spiegel`), and Omar (`data/01_input/omar`). For arrrrrrmin, we also have the analysis and visualization presented in `data/01_input/arrrrrmin/Website/LanzMining.html`. Two comparison artifacts are needed: a high-level comparison for the related-work section and an extensive data comparison going through all prior results. 
- Evidence: `ToDo/archive/additional_input.md` (Compare section), prior data directories listed above.
- Definition of done:
  1. A high-level summary table (methodology, scope, data volume, key findings) comparing this project against all three prior works is written and saved to `documentation/`.
  2. An analysis notebook or section ingests each prior dataset and computes comparable statistics (guest count, gender distribution, time range) to enable direct comparison.
  3. Key differences and improvements over prior work are documented.
- Notes: Omar's approach file path in `additional_input.md` is incomplete
  - clarification: Here is the entire codebase of that approach: `ToDo/2026-05-03_Speaker_Mining_Paper/First Approach Codebase`. Keep in mind that there are three different works in total: 1) Arrrrrmin 2) Spiegel 3) This Work (being created in two iterations: One is Omar's first approach, Lanz Mining but Fair, and then this second iteration, Speaker Mining. Both are part of "This Work"). So in total, there are three different major works, and Omar's analysis may be omitted from the final comparison. It can however be presented as a "V0" of this approach.

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
- Notes: Sunburst and Sankey diagrams assume tree-like hierarchy; subclasses with multiple superclasses break this assumption. Implementation must define a multi-parent strategy (e.g. primary-parent assignment or proportional count split) before items 3 and 4 can be completed.

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

### TODO-031: Fix unresolved QID labels in analysis output and visualizations

- Priority: medium
- Status: open
- Area: analysis
- Summary: Several analysis outputs display raw QIDs instead of human-readable labels — for example `top_occupations` shows `Q1238570` (political scientist / Politikwissenschaftler) and `Q40348` (lawyer / Rechtsanwalt). Both entities carry German and English labels on Wikidata, so the failure to resolve them points to a gap in the label-lookup path.
- Evidence: `ToDo/archive/additional_input.md` (QID label section), `data/40_analysis/guest_catalogue.csv`, `speakermining/src/process/notebooks/41_analysis.ipynb`.
- Definition of done:
  1. The label-lookup gap is identified: which phase or notebook step fails to resolve the QID to a label.
  2. The fix is applied so that all occupation/property values in analysis output use labels, not QIDs.
  3. The `top_occupations` list and any other summary fields are re-generated and verified to contain no bare QIDs.

### TODO-032: Fix page rank visualization — replace bar chart with node graph

- Priority: medium
- Status: open
- Area: analysis
- Summary: The current page rank chart is a bar chart, but page rank was designed to be visualized as a node graph. Bar charts are a poor fit for page rank output and should be replaced.
- Evidence: `ToDo/archive/additional_input.md` (page rank section), `speakermining/src/process/notebooks/51_visualization.ipynb`.
- Definition of done:
  1. The bar-chart page rank visualization is removed from `51_visualization.ipynb`.
  2. A node-graph visualization of page rank is implemented, showing nodes sized or colored by their rank score.
  3. The new visualization is exported as PNG + PDF to `data/output/visualization`.

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
- No machine learning or "training", just deterministic calculations. We have no time for AI training, and generally, any black box introduction would not be aligned with our principles.

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

### TODO-033: Document gender bias scope limitation — sample vs. population

- Priority: low
- Status: open
- Area: docs
- Summary: The current analysis computes gender distribution over the guest sample only; it cannot make claims about the total population (e.g. "80% of all teachers are male"). This methodological caveat must be documented clearly so results are not misinterpreted.
- Evidence: `ToDo/archive/additional_input.md` (gender bias scope section), `data/40_analysis/guest_catalogue.csv`, `speakermining/src/process/notebooks/51_visualization.ipynb`.
- Definition of done:
  1. A caveat section is added to the gender analysis output (notebook or documentation) explaining that bias metrics describe the sample set only, not the total population.
  2. Example framing is provided: "X% of teachers in our sample are male" — not "X% of all teachers are male".
  3. The caveat is referenced from `documentation/findings.md` as a known limitation.

### TODO-034: Document and evaluate phase equivalence of candidate discovery sources

- Priority: low
- Status: open
- Area: architecture
- Summary: PDF archive extraction, Wikidata graph discovery, and fernsehserien.de scraping are treated asymmetrically despite being conceptually equivalent self-contained candidate discovery steps. Documenting this equivalence simplifies the phase model: Wikidata string-based candidate generation becomes a substep of disambiguation (3.1), not a major phase, dropping the total phase count by one.
- Evidence: `ToDo/archive/additional_input.md` (Learnings / PDF Extraction section), `documentation/workflow.md`.
- Definition of done:
  1. `documentation/workflow.md` is updated with a note explaining the conceptual equivalence of the three discovery sources and the rationale for a simplified phase numbering.
  2. A proposed simplified phase map is documented: Phase 1 (all candidate discovery) → Phase 2.0 (normalization) → Phase 2.1 (reconciliation) → Phase 2.2 (deduplication) → Phase 3 (link prediction).
  3. Any concrete pipeline refactoring required to align with the new model is captured as follow-up items in the phase-structure documentation.

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
