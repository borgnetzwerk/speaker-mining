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

### TODO-036: Fix Phase 31/32 notebook orchestration drift

- Priority: high
- Status: open
- Area: workflow
- Summary: `run_phase31` in `entity_disambiguation/orchestrator.py` and `run_phase32` in `entity_deduplication/orchestrator.py` wrap all logic in single functions, violating the notebook-first principle in `documentation/coding-principles.md`. Notebooks should be the orchestrators with step-by-step cells and intermediate output; modules should expose granular functions.
- Evidence: `speakermining/src/process/entity_disambiguation/orchestrator.py`, `speakermining/src/process/entity_deduplication/orchestrator.py`, `documentation/coding-principles.md`; TODO-017 column trimming was implemented in `run_phase31` instead of in the notebook (see `ToDo/archive/additional_input.md` batch 5).
- Definition of done:
  1. Audit Notebooks 31 and 32 to identify all steps currently delegated to `run_phase31`/`run_phase32` and not represented as notebook cells.
  2. Each logical step becomes a notebook cell calling a granular module function, with visible output after each step. The `run_phase3x` wrappers are removed or deprecated.
  3. ✓ TODO-017 column trimming is applied inside `build_aligned_*` functions, not inside `run_phase31` (done 2026-04-24).
  4. Notebooks 31 and 32 can be run cell-by-cell with intermediate results visible.
- Notes: Likely introduced when Claude Code generated code without following notebook-first conventions. Fix before any further Phase 31/32 work. See also TODO-037.

### TODO-037: Create AGENT.md and CLAUDE.md with project coding principles

- Priority: high
- Status: open
- Area: workflow
- Summary: No AGENT.md or CLAUDE.md exists to communicate notebook-first orchestration and coding conventions to AI assistants. This is the root cause of the orchestration drift in TODO-036.
- Evidence: `documentation/coding-principles.md`; `ToDo/archive/additional_input.md` batch 5.
- Definition of done:
  1. `CLAUDE.md` created at the repository root summarizing: notebook-first orchestration, no `run_phase*` wrapper functions, intermediate output in cells, module/test boundaries.
  2. Explicitly warns against `run_phase*` wrappers; instructs placing logic in notebook cells instead.
  3. References `documentation/coding-principles.md` rather than duplicating it.

### TODO-018: Integrate authoritative 6-column reconciliation CSV into Phase 32

- Priority: high
- Status: in-progress
- Area: workflow
- Summary: The OpenRefine reconciliation team is producing a 6-column CSV (`alignment_unit_id`, `wikibase_id`, `wikidata_id`, `fernsehserien_de_id`, `mention_id`, `canonical_label`) as the authoritative output of manual Phase 31 reconciliation. This CSV must be integrated into Phase 32 as the highest-confidence deduplication tier, superseding automated strategies where present. Our task is to be ready to receive and integrate it — the CSV itself is produced externally.
- Evidence: `documentation/31_entity_disambiguation/post-processing.md` (workflow + deadlines), `ToDo/2026-05-03_Speaker_Mining_Paper/`.
- Definition of done:
  1. The integration contract is documented in `contracts.md`: where the incoming CSV is placed, what Phase 32 does with it, and how it overrides automated clustering.
  2. Phase 32 logic (`orchestrator.py` or a new step) reads the incoming CSV and promotes its entries to a new `manual_reconciliation` cluster strategy with confidence = `authoritative`.
  3. The 6-column CSV is received from the reconciliation team and ingested — deadline 2026-05-03.
- Notes: The CSV is produced externally (manual OpenRefine reconciliation); deadline for receiving it is 2026-04-29. Integration logic is implemented (2026-04-23): `_apply_manual_reconciliation_tier()` in `person_deduplication.py`, loaded by `orchestrator.py` when `data/31_entity_disambiguation/reconciliation_export.csv` exists. Drop the CSV at that path and re-run Phase 32 to ingest. Tests: `speakermining/test/process/entity_deduplication/test_manual_reconciliation.py` (9 cases). Remaining: receive CSV and do a live ingest run (item 3).

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

### TODO-017: Reduce aligned_*.csv column footprint

- Priority: medium
- Status: in-progress
- Area: contracts
- Summary: `aligned_persons.csv` has 2,531 columns — a symptom of two issues: (1) `raw_json_wikidata` column containing full JSON payload is redundant alongside the individual property columns, and (2) both raw `*_wikidata` and `*_norm_wikidata` variants of every Wikidata property column are propagated, doubling the column count. The bloated count also makes OpenRefine reconciliation projects slow to load, but some context columns are genuinely useful for manual reconciliation.
- Evidence: `data/31_entity_disambiguation/aligned/aligned_persons.csv` header (2,531 cols); `documentation/31_entity_disambiguation/archive/todo_tracker.md` (archived notes).
- Definition of done:
  1. `raw_json_wikidata` column is removed from Phase 31 output schema (full payloads live in `core_persons.json`).
  2. Either the raw or the `_norm_` variant of each Wikidata property column is removed; the surviving column is documented in `contracts.md`.
  3. Column selection prioritizes: core IDs, label, description, aliases, source links, and the most commonly populated properties (e.g. occupation for persons). Columns that are ≥ 99% empty or offer no value to a human reviewer are cut first.
  4. `aligned_persons.csv` column count drops to approximately 40 after re-run (hard ceiling: 50).
- Notes: The ~40-column target is driven by OpenRefine usability — a reconciliation project with thousands of columns is difficult to load and review. Preserve enough columns for a human reviewer to confidently match or reject an entity without leaving OpenRefine. Implementation (2026-04-24): `trim_to_top_columns` added to `utils.py`; applied at end of every `build_aligned_*` function (persons, episodes, roles, organizations, topics, seasons, broadcasting_programs). Selection is data-driven per entity type: COMMON_BASE_COLUMNS always kept, `_norm_*` variants and `raw_json_wikidata` always excluded, remaining 25 slots filled by highest-population-rate columns in that entity's actual data. Remaining: re-run Notebook 31 to regenerate all aligned CSVs and verify column counts ≤ 50.

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
- Notes: All analysis must exclude the moderator (Markus Lanz, Q43773) — see TODO-039. Age distribution should also add a second overlay counting every appearance (not just first), so a person appearing over multiple seasons is counted at each appearance age. Omar's approach file path in `additional_input.md` is incomplete
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


### TODO-034: Resolve instances.csv dual-write architectural conflict

- Priority: medium
- Status: open
- Area: architecture
- Summary: `_materialize` writes `instances.csv` (materializer format, `id` column, 36,890 rows) at line 2419, then `run_handlers` overwrites it with InstancesHandler format (`qid` column, 20,836 rows). The parquet sidecar (`instances.parquet`) is only written by the materializer and is therefore the reliable comprehensive source. This violates event-sourcing principles: `instances.csv` is owned by InstancesHandler, and `_materialize` should not write to it.
- Evidence: `materializer.py` line 2419 (`_write_tabular_artifact(paths.instances_csv, instances_df)`); `handlers/instances_handler.py` `materialize()` — writes qid-format CSV only; `instances.parquet` (36,890 rows, `id`/`label_en`/`label_de` columns) vs `instances.csv` (20,836 rows, `qid`/`label`/`labels_de` columns).
- Definition of done:
  1. `_materialize` no longer writes to `paths.instances_csv`; it writes to a separate file (e.g. `instances_materialized.csv`) or relies solely on the parquet sidecar.
  2. All consumers that need the comprehensive entity view (e.g. Notebook 41's `qid_label` lookup) read from `instances.parquet` or the renamed file.
  3. `contracts.md` is updated to document which file is owned by which component.
- Notes: The current state is functional — Notebook 41's `qid_label` comes from `instances.csv` (handler format) and resolves all occupation labels correctly via the 20,836 entities in the handler file. The 16,054-row gap is entities added through node-store paths (property-value hydration, subclass expansion) rather than entity_fetch events. Fix this before the next time the label lookup breaks.



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

### TODO-038: Investigate Wikidata Node Integrity Pass performance

- Priority: medium
- Status: open
- Area: ingestion
- Summary: The Wikidata Node Integrity Pass step in Notebook 21 took 1648 seconds on first run and over 6726 seconds on a second run without completing. This is likely a performance or loop issue that needs investigation before the step can be relied upon.
- Evidence: `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context.md`, `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context_second.md`, `documentation/context/node_integrity/node_integrity_20260424T140800Z.md`, `documentation/context/node_integrity/node_integrity_20260424T105030Z.md`.
- Definition of done:
  1. Root cause of the excessive runtime is identified and documented.
  2. Either the step is optimized to complete in a reasonable time (< 5 minutes), or a principled decision is made to skip/replace it with an explanation.
  3. If a bug is found, it is fixed and the fix is documented in `documentation/findings.md`.

### TODO-039: Exclude moderator (e.g. Markus Lanz) from all analysis outputs

- Priority: medium
- Status: open
- Area: analysis
- Summary: Moderators, such as Markus Lanz, appear in every episode and would skew all statistics (gender distribution, age, occupation frequency, page rank). They must be excluded from all analysis outputs. Currently unknown whether they are already excluded.
- Evidence: `ToDo/archive/additional_input.md` batch 5; `data/40_analysis/guest_catalogue.csv`, `speakermining/src/process/notebooks/51_visualization.ipynb`.
- Definition of done:
  1. Check whether Markus Lanz (Q43773) currently appears in `guest_catalogue.csv`, gender distribution, occupation counts.
  2. If present: When person classification happens, we already classify into "guest" and "topic" etc. - we should have a dedicated category for "moderator"
  3. When creating any guest related statistics, this should only count guests. Not Moderators, not topics, not other related persons. See TODO-040 for additional details.
  4. Analysis outputs are re-run with the rules above applied.

### TODO-040: Audit guest classification accuracy with random sample tracing

- Priority: medium
- Status: open
- Area: analysis
- Summary: Elon Musk appears in `guest_catalogue.csv` but was (as far as known) never a guest — he appeared only in a topic description. This suggests systematic misclassification of topic-mentioned persons as guests. A random-sample audit is needed.
- Evidence: `data/40_analysis/guest_catalogue.csv` (Elon Musk present); `ToDo/archive/additional_input.md` batch 5.
- Definition of done:
  1. Trace Elon Musk's entry back to its source (which Phase 1 row, which episode, which parsing rule).
  2. Take a random sample of ≥ 20 entries from `guest_catalogue.csv` and trace each back to its Phase 1 source row to verify correct classification.
  3. If systematic misclassification is found, raise a new TODO with the specific root cause and fix.
  4. Results (sample + classification verdict) are documented in `documentation/findings.md`.

### TODO-041: Respect time-sensitive Wikidata claims using episode date

- Priority: medium
- Status: open
- Area: analysis
- Summary: Wikidata claims for party affiliation (P102), occupation (P106), position held (P39), employer (P108) etc. may have start/end qualifiers. A statement true in 2015 may be false today. Guest properties should be evaluated against the date of the episode they appeared in, not the current Wikidata snapshot.
- Evidence: `ToDo/archive/additional_input.md` batch 5; `data/40_analysis/guest_catalogue.csv`; `data/10_mention_detection/episodes.csv` (contains episode dates).
- Definition of done:
  1. Identify which Wikidata properties in the guest catalogue have start/end date qualifiers in the raw claim data (`core_persons.json`).
  2. For each such property, filter to only claims whose date range covers the guest's first (or any) appearance date.
  3. Updated analysis reflects time-contextual properties; discrepancies (e.g. former party member shown as current) are reduced.
  4. The filtering logic is documented in `contracts.md` or `documentation/findings.md`.

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

### TODO-042: Fix roles projection — use subclasses (P279) not instances (P31)

- Priority: high
- Status: in-progress
- Area: modeling
- Summary: Role-type Wikidata entities (journalist, politician, etc.) are defined via P279 (subclass-of), making them class nodes. The pipeline filtered ALL class nodes out of `core_roles.json`, producing an empty file. Fix: `core_classes.csv` now has a `projection_mode` column; roles has `projection_mode=subclasses`, which causes `_write_core_instance_projections` to build the roles projection from class nodes (filtered by `resolved_core_class_id`) rather than instance nodes.
- Evidence: `data/20_candidate_generation/wikidata/projections/core_roles.json` (currently `{}`); `data/00_setup/core_classes.csv`; `speakermining/src/process/candidate_generation/wikidata/materializer.py` `_write_core_instance_projections`; `speakermining/src/process/candidate_generation/wikidata/bootstrap.py` `_load_class_setup_rows`.
- Definition of done:
  1. `core_roles.json` contains role entities (e.g. journalist Q1930187, politician Q82955) after re-running Phase 2 materialization.
  2. Phase 31 `aligned_roles.csv` contains Wikidata-matched role rows (currently 0 Wikidata matches).
  3. Finding documented in `documentation/findings.md`: role class uses P279 subclass mode.
- Notes: Implementation (2026-04-24): `projection_mode` column added to `core_classes.csv` and `bootstrap.py`; `class_nodes_df` built alongside `non_class_instances_df` in materializer and used when `projection_mode=subclasses`. All `instances_core_*.json` files renamed to `core_*.json` (and `not_relevant_instance_core_*` → `not_relevant_core_*`) throughout codebase and on disk (2026-04-24). **Finding (2026-04-24):** After re-running Phase 2, `core_roles.json` is still empty — all role class nodes ended up in `not_relevant_core_roles.json`. Root cause: relevancy propagation only operates on instance-instance relationships; it never marks class nodes as relevant because the propagation logic and `relevancy_relation_contexts.csv` are built exclusively around P31 instance-of chains. The `occupation` property (P106, which would link persons → roles) is entirely absent from `relevancy_relation_contexts.csv`. **Redesign implemented (2026-04-26):** `bootstrap_relevancy_events` in `relevancy.py` now builds a parallel `class_qid_to_core_class` dict from `class_hierarchy_df` (mapping role subclass QIDs → Q214339, etc.). Triple scanning uses this as a fallback for both subject and object lookups, so `(person, P106, journalist_class_node)` triples now produce the context `(Q215627, P106, Q214339)`. BFS propagation accepts class nodes as targets (`class_node_ids` guard replaces the `qid_to_core_class`-only check) and emits `is_core_class_instance=False` for them. The approved context `(Q215627, P106, Q214339)` is added to `data/00_setup/relevancy_relation_contexts.csv` with `can_inherit=TRUE`. Phase 2 re-run required to verify `core_roles.json` is populated.

### TODO-043: Align property hydration config with relevancy propagation config structure

- Priority: low
- Status: open
- Area: architecture
- Summary: Property-based hydration (whitelisting P106, P102, etc.) and relevancy propagation both use "if subject meets criteria, follow this property to hydrate/expand the object" logic. They should use parallel config structures — two independent but similarly-shaped config files — rather than ad-hoc code.
- Evidence: `ToDo/archive/additional_input.md` batch 5; `relevancy_relation_contexts.csv` (relevancy config); Phase 2.1 hydration whitelist (currently hardcoded).
- Definition of done:
  1. A dedicated config file for property hydration (e.g. `hydration_properties.csv`) mirrors the structure of the relevancy propagation config.
  2. Both configs are documented side-by-side in `documentation/workflow.md` explaining the distinction: relevancy targets core-class-instance subjects; hydration can target any subject.
  3. Hardcoded hydration predicate lists in Phase 2.1 are replaced by the config file.

### TODO-044: Wikidata v4 conceptual rework

- Priority: medium
- Status: in-progress
- Area: architecture
- Summary: Phase 2.1 is currently a patchwork of modules mending each other's shortcomings. The ideal is a single rule-driven graph expansion engine: find core node → apply rules → hydrate or expand linked objects → repeat. Active investigation and redesign underway.
- Evidence: `ToDo/archive/additional_input.md` batch 5; `documentation/Wikidata/2026-04-26_investigation/` (full investigation + clarifications).
- Definition of done:
  1. Conceptual design for the rule-driven graph expansion engine is documented in `documentation/workflow.md` (future state section).
  2. Clarification.md and 05_related_tasks.md in the investigation folder establish the agreed baseline.
  3. Redesigned Notebook 21 implements the event-sourced, handler-driven, single-pass architecture with generic rule-driven relevancy propagation and no post-hoc repair step.
- Notes: Investigation complete (2026-04-26). Clarifications aggregated. Related tasks wired in: TODO-042, TODO-034, TODO-038, TODO-043, TODO-041. Implementation phase next.

### TODO-035: Extend pipeline scope beyond Markus Lanz to other shows

- Priority: low
- Status: open
- Area: ingestion
- Summary: The current pipeline is scoped to Markus Lanz archive files only; `DEFAULT_PDF_TXT_INPUTS` and `ZDF_ARCHIVE_DIR` hardcode that path. Extending to other shows would require parameterized input discovery and show-specific parsing configuration.
- Evidence: `speakermining/src/process/notebooks/11_mention_detection.ipynb` cell `d4f55fab`, `speakermining/src/process/mention_detection/config.py`.
- Definition of done:
  1. Input discovery is parameterized so that a different show can be processed by changing a config value, not code.
  2. At least one additional show archive is processed successfully end-to-end through Phase 1.
  3. Show identity is propagated as a column in all Phase 1 output CSVs.
