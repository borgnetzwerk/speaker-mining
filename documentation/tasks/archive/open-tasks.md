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
- Evidence: `documentation/archive/31_entity_disambiguation/post-processing.md` (workflow + deadlines), `ToDo/2026-05-03_Speaker_Mining_Paper/`.
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
- Evidence: `data/31_entity_disambiguation/aligned/aligned_persons.csv` header (2,531 cols); `documentation/archive/31_entity_disambiguation/archive/todo_tracker.md` (archived notes).
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
- Evidence: `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context.md`, `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context_second.md`, `documentation/archive/context/node_integrity/node_integrity_20260424T140800Z.md`, `documentation/archive/context/node_integrity/node_integrity_20260424T105030Z.md`.
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
- Additional context and relevant concepts:
  - frequent set mining (https://en.wikipedia.org/wiki/Frequent_pattern_discovery) 
  - association rule mining (https://en.wikipedia.org/wiki/Association_rule_learning)

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

### TODO-045: Fernsehserien.de person ID missing from reconciled_data_summary.csv

- Priority: medium
- Status: open
- Area: contracts
- Summary: The `fernsehserien_de_id` column in `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` contains the **episode URL** (e.g. `https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614`) instead of the **person fernsehserien.de ID** (e.g. `andrej-gurkov`). The correct person URL would be: `https://www.fernsehserien.de/<person_id>/filmografie`.
- Evidence: `open_additional_input.md` batch 7; example row: `person_fs_1ff4ae2b3b83,,Q133019990,https://www.fernsehserien.de/internationaler-fruehschoppen/folgen/24-...,`
- Definition of done:
  1. Phase 31 alignment step correctly populates `fernsehserien_de_id` with the person's fernsehserien.de slug (e.g. `andrej-gurkov`), not the episode URL.
  2. The episode URL is stored in a separate column (e.g. `episode_fernsehserien_de_id` or retained in the appearance join table).
  3. Existing output files downstream of Phase 31 are regenerated.
- Notes: **Phase 5 workaround (deferred fix):** The current `fernsehserien_de_id` value IS the episode URL and can still be used as a join key with `episode_metadata_normalized.csv`. Phase 5 design spec `03_design_spec.md` already accounts for this — the join is correct as written. The person-level fernsehserien.de URL is not needed for Phase 5 analysis. Fix is deferred to the next Phase 31 re-run (post-deadline 2026-05-03).

---

### TODO-046: Visualization plot type reference library with example code

- Priority: medium
- Status: open
- Area: analysis
- Summary: Build a reference collection of visualization plot types used in Phase 5 analysis, each with minimal runnable example code using dummy data, documented principles, and exported PNG/PDF. Ensures consistent, "doing it right" implementations across all analysis notebooks.
- Evidence: `open_additional_input.md` batch 7; plot types identified: violin plot (age distribution), centered stacked bar chart (Likert scale).
- Definition of done:
  1. A reference notebook or module exists at `speakermining/src/process/notebooks/viz_reference.ipynb` (or `data/output/visualization/reference/`) with one cell per plot type.
  2. Each cell: dummy data, correct implementation, exported PNG + PDF, documented principles (axis labels, color choices, legend, accessibility).
  3. Subtypes are present where nuance exists (e.g. two ways to display grouped bar charts).
  4. All Phase 5 visualizations are verifiably consistent with the reference implementations.
- Notes: Immediately relevant for Phase 5 — violin plot needed for age distribution (C8 in design spec), grouped bar chart for gender distributions (C1/C2). Reference should be created alongside or before the first Phase 5 visualization cell.

---

### TODO-047: Research and document requirements formalization approach

- Priority: low
- Status: open
- Area: workflow
- Summary: Investigate established requirements formalization methods (e.g. user stories, formal specs, structured contracts) that could improve task clarity and cooperative project interaction (human or agent). Document recommended approach for this project.
- Evidence: `open_additional_input.md` batch 7.
- Definition of done:
  1. A recommended formalization approach is documented in `documentation/workflow.md` or a dedicated `documentation/requirements-methodology.md`.
  2. At least one existing TODO is refactored to demonstrate the approach.
- Notes: Deferred (post-deadline 2026-05-03). Does not benefit Phase 5 analysis.

---

### TODO-048: Task structure — active and sketching zones

- Priority: low
- Status: open
- Area: workflow
- Summary: Create a clear separation between the active TODO zone (tasks ready to be picked up and processed) and a sketching zone (loose ideas not yet formalized enough to be acted on). Each zone has defined entry/exit criteria so that random notes do not pollute the actionable queue.
- Evidence: `open_additional_input.md` batch 7.
- Definition of done:
  1. `documentation/tasks/` is restructured with at least two distinct areas: `open-tasks.md` (active, fully specified) and a new `sketch.md` or `ideas/` folder (unstructured, not yet actionable).
  2. Entry criteria for `open-tasks.md` are documented: every task must have all template fields filled.
- Notes: Deferred (post-deadline 2026-05-03). Does not benefit Phase 5 analysis.

---

### TODO-049: Implement validation pass protocol for larger reworks

- Priority: medium
- Status: open
- Area: workflow
- Summary: Larger reworks (e.g. Wikidata v4 redesign, Phase 31 refactor) must include a formal validation pass comparing old vs. new: output files, runtimes, event log, code diff, and intended design vs. actual implementation. This prevents regressions from going undetected.
- Evidence: `open_additional_input.md` batch 7.
- Definition of done:
  1. A validation pass checklist is documented in `documentation/workflow.md` or a dedicated `documentation/validation-protocol.md`.
  2. The checklist covers: old vs. new output diff, runtime comparison, event log comparison, code review, design-vs-implementation consistency check.
  3. At least one completed rework (retrospectively) documents its validation pass results.
- Notes: Deferred (post-deadline 2026-05-03). Does not benefit Phase 5 analysis.

---

### TODO-050: Wikidata — propagate seed/core-class/rule removals to pipeline outputs

- Priority: medium
- Status: open
- Area: architecture
- Summary: When a user removes a seed, core class, or relevancy rule from the configuration, the change should be accurately propagated to all downstream outputs (projections, output JSON files, event log). Currently, removing a config entry has no effect on previously produced outputs — the removed entity/class remains in all output files until a full re-run.
- Evidence: `open_additional_input.md` batch 7.
- Definition of done:
  1. A "removal propagation" mechanism is designed and documented: which events are emitted, which handlers react, and which output files are updated.
  2. Removing a seed or core class triggers re-computation of affected projections without requiring a full pipeline restart.
  3. An integration test verifies that a removed seed disappears from `core_*.json` after the next notebook run.
- Notes: Deferred (post-deadline 2026-05-03). Requires Phase 21 re-run. Does not benefit Phase 5 analysis.

---

### TODO-051: Machine-readable notebook cell and function runtime statistics

- Priority: medium
- Status: open
- Area: workflow
- Summary: Notebook cells and key functions should emit machine-readable timing and output statistics (row counts, sizes, key metrics) to a structured log. These statistics should be: always-on for minimum heartbeat/progress visibility, configurable in verbosity for debugging without binary on/off, and persistent across runs for regression detection.
- Evidence: `open_additional_input.md` batch 7.
- Definition of done:
  1. A lightweight statistics emitter (function decorator or context manager) is implemented that records function name, start time, elapsed time, and a configurable output summary dict to a JSON-lines log.
  2. All notebook cells' key functions are instrumented.
  3. A verbosity level config controls output detail: level 0 = heartbeat only (always on), level 1 = cell-level stats, level 2 = function-level stats.
  4. Statistics from the previous run are visible in the notebook output on re-run.
- Notes: Deferred (post-deadline 2026-05-03). Heartbeat is already implemented in Phase 21 (F1/F2 fixes). This extends the concept to all notebooks. Does not block Phase 5 analysis.

---

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

---

### TODO-052: Episode multi-topic classification from ZDF description text

- Priority: medium
- Status: open
- Area: analysis
- Summary: Each episode currently carries at most one ZDF-provided topic label; a keyword-weighted multi-topic taxonomy applied to the episode description and title text would enable topic × demographic analysis as a new Phase 50 dimension.
- Evidence: `documentation/tasks/visualization_references/Lanz-und-Precht/theme_detection.ipynb` demonstrates a working 10-topic taxonomy with evidence-weighted scoring across title, description, bag-of-words, named entities, and transcript text. The approach requires only description text for partial benefit — no transcripts needed for the first version.
- Definition of done:
  1. A topic taxonomy (10–15 German-language topics; e.g. Politics, Economy, Climate, Technology, Society, International, Health, Science, Media, Migration) is documented in `documentation/analysis/` with its keyword lists.
  2. A Phase 50 module classifies each episode with one or more topics, writing `topic_labels` as a list column in the analysis output.
  3. At least one new Phase 50 visualization shows guest gender distribution broken down by topic.
- Notes: Topic taxonomy should be iteratively validated against known episodes before running on the full corpus. Weighted scoring strategy from `theme_detection.ipynb` (higher weight for title/description than bag-of-words) should be preserved.

---

### TODO-053: Transcript acquisition pipeline for ZDF talk show episodes

- Priority: low
- Status: open
- Area: ingestion
- Summary: ZDF talk show episodes are available as audio via ZDF Mediathek or mirrored on YouTube; a Whisper-based German transcription pipeline would open an entirely new class of content-level analysis (see TODO-054, TODO-055, TODO-056).
- Evidence: `documentation/tasks/visualization_references/Lanz-und-Precht/` demonstrates the full pipeline for the Lanz & Precht podcast: episode metadata → YouTube matching → Whisper JSON → NLP artifacts (bag_of_words, named_entities) → theme detection. Markus Lanz episodes follow the same structure. ZDF episodes are also available via the ZDF Mediathek API.
- Definition of done:
  1. Legal and terms-of-use position is assessed and documented: can ZDF audio be transcribed for non-commercial academic research?
  2. Audio retrieval strategy is decided: ZDF Mediathek API, yt-dlp from YouTube, or both; retention policy (delete audio after transcription) is documented.
  3. Whisper pipeline produces per-episode JSON with at minimum `text` (full transcript), `language`, and `segments` (timestamped). German model (`large-v3` or equivalent) is used.
  4. Transcripts are stored as JSONL or individual JSON files under `data/transcripts/` following the existing `data/` naming conventions.
  5. A notebook cell demonstrates loading a transcript and retrieving its segment list.
- Notes: Whisper `large-v3` model handles German well. Segment timestamps are essential for diarization (TODO-054). The Lanz & Precht notebooks store NLP artifacts (bag_of_words, named_entities) separately from the raw Whisper output — that separation should be preserved.

---

### TODO-054: Guest speaking time from diarized transcripts

- Priority: low
- Status: open
- Area: analysis
- Summary: Given Whisper-transcribed episodes and speaker diarization, each guest's actual speaking time and word count can be measured per appearance — quantifying participation inequality and enabling a "voice share" dimension beyond appearance count.
- Evidence: The existing pipeline measures guest *presence* (appearance count) but not *participation*. Lanz-und-Precht `analysis_advanced.ipynb` computes word count per episode as a proxy for content volume; with diarization that breaks down per speaker. Requires TODO-053 (transcripts) first. Diarization can be done with `pyannote.audio` (speaker diarization) or Whisper's native `--diarize` flag in combination with pyannote.
- Definition of done:
  1. A diarization strategy is chosen and documented: Whisper diarize flag vs. pyannote post-processing. Limitations (speaker count uncertainty, host vs. guest confusion) are noted.
  2. A `voice_share` metric is defined: words spoken per appearance, normalized to episode total. Stored in analysis output alongside existing `appearance_count`.
  3. At least one Phase 50 visualization shows voice share distribution by gender and by occupation.
  4. Correlation between `voice_share` and Wikidata prominence (page rank or P18 image) is computed and documented.
- Notes: Speaker count per Lanz episode is typically 3–5 (host + guests). Diarization accuracy is sufficient for word-count estimation even without perfect speaker labelling — the key signal is "total words attributed to identified guest X" not sentence-level attribution. Manual spot-check on 5 episodes should validate the approach before full corpus run.

---

### TODO-055: Named entity co-mention analysis across the corpus

- Priority: low
- Status: open
- Area: analysis
- Summary: Persons mentioned in episode descriptions or transcripts who never appear as guests are an invisible but significant layer of the public discourse graph; mining this co-mention layer would reveal whose names travel through the show without their presence.
- Evidence: `analysis_advanced.ipynb` extracts named entities from NLP artifacts per episode and tracks their frequency over time. In the talk show context this distinguishes three populations: (A) guests who appear and are mentioned, (B) persons mentioned but never appearing, (C) guests who appear but are rarely mentioned outside their own episode. Requires only description text for a first version; transcript NER would add significantly more mentions. Named entity extraction can use spaCy `de_core_news_lg` or `flair/ner-german-large`.
- Definition of done:
  1. Named entities are extracted from at least episode description text using a German NER model; results stored per episode as a JSON artifact.
  2. A co-mention table is produced: for each Wikidata-resolved guest, their mention count in episodes where they did NOT appear as a guest.
  3. The "mentioned but never guest" population is characterized: count, Wikidata resolution rate, and gender/occupation distribution compared to the actual guest population.
  4. Results are incorporated into Phase 50 output or documented in `documentation/analysis/`.
- Notes: The co-mention analysis is a direct input to link prediction (the currently unimplemented Phase 4/P4): "person X is frequently co-mentioned with show Y → candidate for future guest or related entity". High-prominence persons who are frequently mentioned but never appear may represent a systematic invitation gap.

---

### TODO-056: Topic × guest demographic correlation in Phase 50

- Priority: low
- Status: open
- Area: analysis
- Summary: Adding topic labels (TODO-052) as a new dimension to Phase 50 would reveal whether specific topics are discussed with systematically different guest demographics — a key question for diversity analysis beyond aggregate counts.
- Evidence: Lanz-und-Precht `analysis_advanced.ipynb` cross-references thematic evolution with publication cadence. In the talk show context the question is: "do climate episodes have different gender distribution than economy episodes?" or "has the gender balance on international-politics episodes shifted post-2020?". This requires TODO-052 (topic labels) and the existing Phase 50 demographic data.
- Definition of done:
  1. Topic labels from TODO-052 are joined with the deduped persons data used in Phase 50 analysis.
  2. At least two new visualizations are produced: (a) gender distribution by topic (bar chart), (b) temporal gender trend per topic (line chart).
  3. Statistical significance of topic × gender differences is tested and documented using the existing Mann-Whitney U infrastructure in `statistical_tests.py`.
  4. Findings are added to `documentation/analysis/README.md` as planned analysis angles.
- Notes: Depends on TODO-052 for topic labels. Can be prototyped with ZDF-provided single topic labels first (already in Phase 10 output) before multi-topic labels are available. This task directly extends the published paper's analysis scope.

---

## Phase 50 Analysis — Implementation Backlog

The tasks below (TODO-057 through TODO-074) were recovered from `documentation/archive/50_Analysis/` open-task files (TASK-A, TASK-B, TASK-F series). They were archived without migration during the 2026-05-22 synthesis pass — a process error. Each is still open or partially implemented. Source archive: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` (primary), `2026-04-29_Initialization/open-tasks.md`, and `2026-04-30_restructuring/open-tasks.md`.

---

### TODO-057: Phase 50 — Dynamic property-driven analysis pipeline

- Priority: medium
- Status: open
- Area: analysis
- Summary: All suitable analyses and visualizations for every configured property should run automatically from `data/00_setup/analysis_properties.csv` without manual wiring per new property.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F02.
- Definition of done:
  1. Analysis routing reads from `analysis_properties.csv`; adding a new property row causes it to appear in all applicable chart families without code changes.
  2. Cross-property combination analyses run automatically for all ordered property pairs of type `item`.
  3. Per-property and cross-property visualization outputs are produced in one notebook run without manually specifying pairs.

---

### TODO-058: Phase 50 — Class hierarchy walk completion and loop resolution

- Priority: medium
- Status: open
- Area: analysis
- Summary: The P279 hierarchy walk is incomplete: mid-level class mapping is missing, loop detection uses no configuration, and occupation rollup breakages (visible in top-10 lists as duplicate "Schauspieler", "Teacher" variants) remain unfixed.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F03; `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` TASK-A02 known issues. See also TODO-042 (P279 walk architecture).
- Definition of done:
  1. P279 hierarchy walk completes for all first-level classes including Q488205 (Singer-Songwriter) and other QIDs currently missing resolution.
  2. Loop detection consults `data/00_setup/loop_resolution.csv`; unlisted cycles use lowest-QID fallback; loop diagnostics (`number_of_loops`, `classes_in_loops`) are published.
  3. Mid-level class mapping is defined and applied: sunburst/hierarchy charts show meaningful mid-level groups rather than direct top-level or first-level only.
  4. "Two kinds of Schauspieler" symptom is gone from top-10 occupation lists.
- Notes: Depends on TODO-042 for architectural design. Blocked on V4 Wikidata entity access until basic_fetch is reliable (see T02).

---

### TODO-059: Phase 50 — Standardized property statistics tables

- Priority: medium
- Status: open
- Area: analysis
- Summary: A generic `carrier_stats` + `episode_appearance_stats` function pair should produce standardized per-value statistics tables for every configured property, including min/max/mean/median per episode, episode-% without, unique persons, and total appearances.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F04; `2026-04-29_Initialization/open-tasks.md` TASK-A04.
- Definition of done:
  1. `carrier_stats(property_id, data)` and `episode_appearance_stats(property_id, data)` are generalized and work for all property types (item, quantity, string, time).
  2. Both functions emit an explicit "Unknown / no data" row, `person_count`, and `appearance_count` columns.
  3. Combination tables (within-property and cross-property) are produced automatically for all item-type properties.
  4. Remaining work from TASK-F04: downstream combination tables verified; dominance ratio and outlier flag confirmed present in all property output directories.

---

### TODO-060: Phase 50 — Visualization infrastructure: layout, file naming, and language

- Priority: medium
- Status: open
- Area: analysis
- Summary: Several visualization infrastructure items remain open: language variants (DE/EN with fully localized chart text), file naming convention enforcement (`{chart_type}_{pid}_{short_label}`), per-show chart runs for cross-property charts (ALL ↔ per-show symmetry), and episode-level property pipeline (duration, guest count, description, topic).
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F05 and TASK-F09 remaining work sections.
- Definition of done:
  1. Every output file includes both the PID and a ≤25-char slug: `{chart_type}_{pid}_{short_label}.{ext}`.
  2. Language variant support: EN and DE localization controlled by a single config constant. At least `visualization-principles.md` documents the DE/EN capitalization rule.
  3. Cross-property charts run per show in addition to the combined "all" scope.
  4. Episode-level property pipeline produces duration, guest-count, and description outputs where data is available.
  5. Source coverage dashboard shows unique-to-source episode count.

---

### TODO-061: Phase 50 — Universal and cross-property chart completion

- Priority: medium
- Status: open
- Area: analysis
- Summary: Universal visualizations need full ColorRegistry integration (currently uses palette cycling); cross-property `% A over B` stacked bar families need the per-show scope; and cross-property charts need verification that `guest_label`/`canonical_label` column is always available.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F06 remaining work.
- Definition of done:
  1. All universal charts load colors exclusively from `ColorRegistry`; no local palette definitions remain in any `viz_*.py` module.
  2. Cross-property stacked bar charts run per show as well as combined.
  3. `guest_label` / `canonical_label` inconsistency is resolved; frames always carry the expected column name.

---

### TODO-062: Phase 50 — Hierarchical item visualizations (sunburst, Sankey, timeline)

- Priority: medium
- Status: open
- Area: analysis
- Summary: Hierarchical visualizations for occupation and role data (sunburst, Sankey, mid-level class charts) and timeline visualizations with adaptive granularity are not yet implemented.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F07; `2026-04-29_Initialization/open-tasks.md` TASK-A02. Blocked on TODO-058 (hierarchy completion).
- Definition of done:
  1. Sunburst chart for occupation: combined + per-show; 5% "Other" cutoff; innermost ring = top-level classes. Center section is a meaningful class label, not "Person".
  2. Sankey diagram for occupation hierarchy: combined + per-show; flow width = appearances and unique guests.
  3. Mid-level class dedicated stacked bars and sunbursts for each designated mid-level class.
  4. Timeline visualizations with adaptive granularity (max 50 data points, progressive coarsening).
  5. All outputs exported PNG + PDF to `data/50_analysis/visualizations/`.
- Notes: Multi-parent strategy needed for subclasses with multiple superclasses (primary-parent assignment or proportional count split) — document chosen strategy in notebook cell.

---

### TODO-063: Phase 50 — Remaining scalar and extended plot families

- Priority: low
- Status: open
- Area: analysis
- Summary: Two remaining items in the scalar/extended plot family: birth-year × gender frequency scatter (cross-scalar) and stacked area charts for temporal property-value prevalence.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F08 remaining work.
- Definition of done:
  1. Birth-year × gender scatter is implemented: X = birth year, Y = appearance count, color = gender. Written to `visualizations/scatter_birthyear_vs_appearances_by_gender.png`.
  2. Stacked area charts for temporal property value prevalence implemented once timeline module (TODO-062 item 4) is available.

---

### TODO-064: Phase 50 — Person-level analysis completion

- Priority: medium
- Status: open
- Area: analysis
- Summary: Two items from TASK-F10 remain: within-category per-person charts (for each property value, who are the top guests?) and empty-property reporting for top-N most-appeared guests.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F10 remaining work.
- Definition of done:
  1. For each top-N value of every item-type property, a "within-category top persons" chart is produced showing top guests carrying that value, segmented by show.
  2. For the top-N most-appeared guests, a report lists which configured properties had no Wikidata value (e.g., "Robin Alexander — employer field empty"). Written to `all/top_guests_property_gaps.csv`.

---

### TODO-065: Phase 50 — Data quality follow-ups: age outliers and apparent QID duplicates

- Priority: medium
- Status: open
- Area: analysis
- Summary: Two data quality issues require investigation: (1) implausible age outliers (3-year-old and 117-year-old guest) in distribution outputs; (2) semantically equivalent values split across multiple QIDs (e.g. "Doktor phil" vs "Doktor Philosophiae", capitalization variants of church names).
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F12; `2026-04-29_Initialization/open-tasks.md` TASK-A09.
- Definition of done:
  1. Age outliers investigated: specific QIDs/labels identified, birth year correctness in Wikidata verified, formula confirmed or corrected, finding documented as bug fix or data limitation.
  2. Apparent QID duplicates catalogued: a list of value-pairs that appear to represent the same real-world concept is produced. For each pair: either merged in pipeline (via alias/normalization rule) or documented as a genuine Wikidata distinction.
  3. Any corrections propagated through Phase 50 re-run.
- Notes: See also TODO-040 (audit guest classification accuracy) which overlaps with item 1.

---

### TODO-066: Phase 50 — Analysis taxonomy and notebook structural compliance

- Priority: low
- Status: open
- Area: docs
- Summary: The analysis angle taxonomy (property types A/B/C/D, function types F1–F5) and its visualization mapping must be consistently applied across all documentation and all notebook cells.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F13; `2026-04-29_Initialization/open-tasks.md` TASK-A12.
- Definition of done:
  1. `documentation/analysis/README.md` lists all analysis angles by property type (A/B/C/D) and function type (F1–F5).
  2. `50_analysis.ipynb`: each Step C cell opens with a comment identifying its F-type (e.g. `# F1 — gender distribution`).
  3. The §6 visualization mapping table (in `documentation/analysis/`) covers every F-type and matches `visualization-principles.md`.
  4. No analysis angle is described only in narrative terms — all reference their property type and function type.

---

### TODO-067: Phase 50 — Exploratory analysis angles

- Priority: low
- Status: open
- Area: analysis
- Summary: A set of exploratory analysis angles deferred from the initial design: subset dominance analysis, cross-show guest overlap, career arc patterns (shooting star vs. evergreen), property co-occurrence predictive analysis, and temporal chunking by year/decade.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F14; `2026-04-29_Initialization/open-tasks.md` TASK-A05.
- Definition of done:
  1. Each analysis angle is prototyped in `50_analysis.ipynb` and produces at least one output artifact.
  2. Findings from each angle are documented in `documentation/analysis/README.md`.
  3. Career arc patterns (shooting star / evergreen) have an operational definition documented before implementation.
- Notes: These are exploratory — implementation can be incremental. Party affiliation history deep-dive and Poisson applicability check are sub-items.

---

### TODO-068: Phase 50 — Quality tier classification and filtering

- Priority: medium
- Status: open
- Area: analysis
- Summary: The `data_quality_tier` column exists in `build_person_catalogue` but property stats expansion inputs are not yet filtered to Tiers 1+2, per-show tier breakdowns are missing from `person_quality_tiers.csv`, and the analysis documentation does not explain how many Tier 3/4 entries are excluded.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F16 remaining work.
- Definition of done:
  1. `data_quality_tier.isin([1, 2])` filter applied to all property stats and visualization expansion inputs; only Wikidata-reconciled persons enter property statistics.
  2. `person_quality_tiers.csv` includes per-show tier breakdown rows.
  3. `data/50_analysis/all/README.md` or `documentation/analysis/README.md` documents the tier exclusion: how many Tier 3+4 entries exist and what they represent.

---

### TODO-069: Phase 50 — Structured output folder README generation

- Priority: medium
- Status: open
- Area: docs
- Summary: `readme_generator.py` exists and is wired, but the embedded visualization list in `all/README.md` needs expanding as more chart types are completed, per-show visualizations need adding once per-show charts exist, and output needs visual validation on GitHub.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F17 remaining work.
- Definition of done:
  1. `all/README.md` embeds all chart types produced by the completed Phase 50 pipeline (at minimum: universal bars, treemaps, cross-property stacked bars, coverage dashboard, pareto, cooccurrence heatmap).
  2. Each per-show README embeds show-specific visualizations.
  3. Output visually validated by navigating the GitHub repository after a commit.
  4. Every subdirectory under `data/50_analysis/` has a README (binding principle from TASK-F17).

---

### TODO-070: Phase 50 — GitIgnore tuning for analysis outputs

- Priority: medium
- Status: open
- Area: workflow
- Summary: The root `.gitignore` has initial analysis output rules but they need verification and fine-tuning once the full Phase 50 output set is known; a dedicated `data/50_analysis/.gitignore` may be needed for finer control.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F18 remaining work.
- Definition of done:
  1. `git check-ignore` confirms all raw occurrence matrices and per-person CSV files are excluded.
  2. All aggregate/summary CSVs (carrier_stats, episode_stats, per_show_statistics, top_guests) are tracked.
  3. PNG visualizations are tracked; PDF and HTML are not.
  4. `data/50_analysis/.gitignore` created with rules specific to the analysis output tree if root rules are insufficient.

---

### TODO-071: Phase 50 — Appearance totals validation and occurrence source completeness

- Priority: medium
- Status: open
- Area: analysis
- Summary: Episode appearance totals have not been validated against expected bounds (25,902 total appearances vs per-property totals); Wikidata is not yet wired as a third occurrence source alongside ZDF and fernsehserien.de.
- Evidence: `documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F01 remaining work and TASK-F12 item "Add Wikidata as 3rd source".
- Definition of done:
  1. End-to-end appearance totals validated: `sum(occurrence_matrix)` ≈ expected 25,902 total appearances; per-property appearance totals do not exceed that total.
  2. Wikidata raw_import and normalized episode data wired as a third source in `build_person_catalogue` (alongside ZDF and FS sources already implemented).
  3. Source attribution breakdown in `person_quality_tiers.csv` shows counts from each of the three sources.

---

### TODO-072: Phase 50 — Unclassified persons fernsehserien.de link investigation

- Priority: low
- Status: open
- Area: modeling
- Summary: 215 canonical persons have `match_strategy=wikidata_person_only_baseline` and no fernsehserien.de episode link; at least one confirmed false negative (Marie-Agnes Strack-Zimmermann, Q15391841). Each should be verified against fernsehserien.de episode pages.
- Evidence: `documentation/archive/50_Analysis/2026-04-29_Initialization/open-tasks.md` TASK-A13.
- Definition of done:
  1. All 215 persons individually verified against fernsehserien.de.
  2. True missing-link cases have corrected `fernsehserien_de_id` in reconciliation data; Phase 31 → 32 → 50 re-run for corrections.
  3. Remaining persons confirmed as genuinely unlinked and documented as such.
- Notes: Can be done manually or with an agent. Volume: 215 persons.

---

### TODO-073: Document v4 Wikidata architecture design in living Wikidata docs

- Priority: medium
- Status: open
- Area: architecture
- Summary: The v4 Wikidata redesign (implemented as TODO-044) is documented in `documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md` but its 6 design principles are not yet mirrored into a living `documentation/Wikidata/` doc. Before T02 (V3 archive removal) can happen, this gap must be filled.
- Evidence: `documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md` — 6 principles: event store is sole source of truth; no post-hoc repair; two actor types (EventHandlers vs ExternalEventReaders); queues persisted in handler projections; rules are config (CSV files); backward compatibility permanent.
- Definition of done:
  1. A new `documentation/Wikidata/v4_architecture.md` (or equivalent section in `Wikidata.md`) documents the 6 v4 design principles in pipeline-neutral terms.
  2. The module layout and handler responsibilities from `13_architecture_design.md` are summarized.
  3. T02 (V3 archive removal) can proceed without losing this design knowledge.
- Notes: Dependency for T02. Low urgency while V4 is ~20% complete. Recovery: `documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md` is the canonical source.
