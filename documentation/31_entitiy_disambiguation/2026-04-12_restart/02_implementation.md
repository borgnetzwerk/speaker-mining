# Implementation

## Objective
Implement a rerunnable Phase 31 pipeline that materializes aligned core-class tables with explicit confidence/evidence and unresolved status handling in-table.

This step performs one automated best-effort match pass only and then hands off artifacts for human manual analysis and manual matching.

The implementation must execute the layered strategy defined in `00_immutable_input.md` and `01_approach.md`.

Canonical matching unit for person alignment:
1. One person mention in one episode of one broadcasting program.

## Governing Constraints

### Repository standards
1. Apply repository coding standards from `documentation/coding-principles.md`.
2. Keep notebook orchestration in notebook cells; move core transformations/matching to `speakermining/src/process/entity_disambiguation/` modules.
3. Keep all writes inside `data/31_entity_disambiguation/`.

### Operational rules
1. Never force matches below threshold.
2. Keep unresolved records in the aligned tables; unresolved rationale is captured in dedicated unresolved columns.
3. Every aligned row must expose confidence tier and evidence summary.
4. The pipeline must be idempotent and safe to rerun on updated upstream projections.
5. No manual reconciliation is executed inside this phase step.
6. Layer 4 signals may only enrich confidence and evidence; they must not override stronger Layer 1/2 constraints.

## Target Runtime Layout

### Phase 31 data folders
1. `data/31_entity_disambiguation/raw_import/`
2. `data/31_entity_disambiguation/normalized/`
3. `data/31_entity_disambiguation/aligned/`

### Notebook entrypoint
1. `speakermining/src/process/notebooks/31_entity_disambiguation.ipynb`

### Process-module package target
1. `speakermining/src/process/entity_disambiguation/`

## Output Contract For This Restart

### Aligned tables
1. `data/31_entity_disambiguation/aligned/aligned_broadcasting_programs.csv`
2. `data/31_entity_disambiguation/aligned/aligned_seasons.csv`
3. `data/31_entity_disambiguation/aligned/aligned_episodes.csv`
4. `data/31_entity_disambiguation/aligned/aligned_persons.csv`
5. `data/31_entity_disambiguation/aligned/aligned_topics.csv`
6. `data/31_entity_disambiguation/aligned/aligned_roles.csv`
7. `data/31_entity_disambiguation/aligned/aligned_organizations.csv`

### Diagnostics and lineage
1. `data/31_entity_disambiguation/aligned/match_evidence.csv`
2. `data/31_entity_disambiguation/aligned/source_schema_mapping.csv`
3. `data/31_entity_disambiguation/aligned/run_summary.json`

### Inspectable examples
Create inspectable examples for every written instance file across all implementation stages:
1. Stage 1 Raw import snapshot examples under `data/31_entity_disambiguation/raw_import/examples/`
2. Stage 2 Value normalization examples under `data/31_entity_disambiguation/normalized/examples/`
3. Stage 3 Property/schema harmonization examples under `data/31_entity_disambiguation/aligned/examples/schema_harmonization/`
4. Stage 4 Layered alignment execution examples under `data/31_entity_disambiguation/aligned/examples/layered_alignment/`

Each example should contain one representative record while preserving original column structure.

## Canonical Field Model


### Single aligned row schema (all aligned core tables)

Row shape rule:
1. Each aligned output file contains exactly one flattened row per aligned entity/mention unit.
2. All source evidence for that unit must be expressed inside that single row.
3. Repeated properties are expanded into deterministic column families rather than separate output rows.
4. The schema must be wide enough to preserve all known source context without row splitting.

### Shared metadata fields (all aligned core tables)
1. `alignment_unit_id`
2. `wikidata_id`
3. `fernsehserien_de_id`
4. `mention_id`
5. `canonical_label`
6. `entity_class`
7. `match_confidence`
8. `match_tier` (exact, high, medium, unresolved)
9. `match_strategy`
10. `evidence_summary`
11. `unresolved_reason_code`
12. `unresolved_reason_detail`
13. `inference_flag` (true, false)
14. `inference_basis`
15. `notes` (optional analyst free text only)

Reason-code vocabulary for `unresolved_reason_code`:
1. `no_candidate`
2. `low_confidence`
3. `contradiction`
4. `insufficient_context`

Field role split for row explainability:
1. `evidence_summary` stores deterministic, human-readable matching evidence.
2. `unresolved_reason_code` and `unresolved_reason_detail` store unresolved status rationale.
3. `inference_flag` and `inference_basis` store whether context inference was used and from which columns/joins.
4. `notes` remains optional and must not be required by quality gates.

Alignment is computed once per row and persisted directly in this schema.

### Additional basic fields
Every other property is appended then, every time in the three variants:
16. `label_wikidata`
17. `label_fernsehserien_de`
18. `label_zdf`
19. `description_wikidata`
20. `description_fernsehserien_de`
21. `description_zdf`
22. `alias_wikidata` (Always "|" merged string list)
23. `alias_fernsehserien_de` (Always "|" merged string list)
24. `alias_zdf` (Always "|" merged string list)

### Additional Properties
Depending on the class, there are potentially many other properties. They are added then here, once again with _wikidata, _fernsehserien_de and _zdf suffix as appropriate.

## Matching Model Specification

### Confidence score
Use weighted score $S$ per candidate pair:

$$
S = \sum_i w_i \cdot f_i
$$

where each feature score $f_i \in [0,1]$ and $\sum_i w_i = 1$.

### Tier thresholds
1. `exact`: $S \ge 0.95$ and no contradiction flags
2. `high`: $0.85 \le S < 0.95$
3. `medium`: $0.70 \le S < 0.85$ (manual-check by default for persons/episodes)
4. `unresolved`: $S < 0.70$ or contradiction detected

### Hard contradiction rules
1. Different broadcasting program after normalization
2. Mutually exclusive time windows for episode candidate pairs
3. Explicit negative constraints from source metadata

Any hard contradiction forces unresolved status even if score is high.

### Missing-context inference rules
1. Missing source fields (for example missing broadcasting program in some ZDF episode rows) must not block candidate generation when context can be inferred.
2. Inference is allowed from related columns and joins, including publication rows, season and episode relations, normalized labels, and source-specific stable identifiers.
3. Every inferred value must be traceable in row-local flattened columns, with `inference_flag = true` and non-empty `inference_basis`.

### Wide-row expansion rules
1. If a property can have multiple objects, expand it into deterministic columns such as `<property>_1`, `<property>_2`, and so on.
2. If a source contributes multiple relevant fragments, e.g. multiple guests or publications for one single episode, preserve them as repeated column families in the aligned row.
3. Column expansion order must be deterministic and stable across reruns.

## Layer Implementation Plan

### Step 311.1: Raw import staging
1. Read all source files listed in `01_approach.md`.
2. Copy/stage snapshots into `raw_import/`.
3. Record import manifest (filename, row count, checksum) in `run_summary.json`.

### Step 311.2: Value normalization
1. Normalize dates/times/durations.
2. Normalize names/titles (case, whitespace, punctuation, locale variants).
3. Preserve raw value columns with `_raw` suffix.
4. Write normalized per-source artifacts into `normalized/`.

### Step 311.3: Schema harmonization
1. Extract source property inventories.
2. Build canonical field mappings by core class.
3. Persist mapping to `source_schema_mapping.csv`.
4. Define derivation rules for critical missing context fields (for example `broadcasting_program_key`) and include lineage metadata fields.

### Step 311.4: Layer 1 backbone build
1. Materialize broadcasting-program backbone from setup baseline.
2. Attach normalized source keys for downstream constraints.
3. Provide context backfill lookup tables to downstream layers so blank source fields do not block alignment.

### Step 311.5: Layer 2 episode alignment
1. Build episode candidate pairs constrained by broadcasting program and season hints.
2. Score candidates with publication date/time/title features.
3. Apply contradiction checks.
4. Resolve one-to-one episode matches by descending score with conflict prevention.
5. Write `aligned_episodes.csv` with both matched and unresolved rows; unresolved rows remain in-table and are marked via `match_tier` with rationale in unresolved columns.

### Step 311.6: Layer 3 person alignment
1. Build person candidate pairs primarily via aligned episode context.
2. Add secondary name/property-only candidates when no episode match exists.
3. Score, threshold, and resolve with one-to-one safeguards.
4. Write `aligned_persons.csv` with both matched and unresolved rows; unresolved rows remain in-table and are marked via `match_tier` with rationale in unresolved columns.

### Step 311.7: Topic alignment
1. Align topics by episode context and normalized label similarity.
2. Keep ambiguous topic links unresolved unless confidence is high.
3. Write `aligned_topics.csv` with both matched and unresolved rows; unresolved rows remain in-table.

### Step 311.8: Layer 4 role/organization best-effort
1. Extract structured role/organization hints from Wikidata claims.
2. Match against text-derived hints from ZDF/fernsehserien metadata.
3. Only promote high-confidence matches; default unresolved otherwise.
4. Write `aligned_roles.csv` and `aligned_organizations.csv` with unresolved rows in-table.

### Step 311.9: Evidence and QA artifacts
1. Emit one evidence row per accepted/rejected candidate decision in `match_evidence.csv`.
2. Emit run-level summary metrics and unresolved distributions in `run_summary.json`.
3. Emit one-record inspectable examples for every written artifact in stages 1 to 4.
4. Emit handoff-ready summary sections that highlight unresolved counts for manual analysts.

## Notebook Orchestration Specification

### Cell structure
1. Setup cell: deterministic repo root and imports.
2. Configuration cell: thresholds, source paths, output paths.
3. One cell per implementation step (311.1 to 311.9).
4. Validation/reporting cell with quality gates.
5. Final persist-and-summary cell.

### Runtime controls
1. `RUN_ID` timestamp string for artifact lineage.
2. `OVERWRITE_OUTPUTS` boolean for controlled reruns.
3. `STRICT_MODE` boolean to fail on schema drifts.
4. `WRITE_EXAMPLES` boolean for one-row sample generation.

### Deterministic ordering contract
1. Ordering must be deterministic and reproducible across reruns with unchanged input.
2. Time-aware classes should sort chronologically oldest-first where date/time is available.
3. Tie-breakers must be stable (for example season number, episode number, then alignment key).
4. Person rows use two-pass deterministic ordering:
	- Pass 1 chronological by episode appearance.
	- Pass 2 stable alphabetical by normalized person label, preserving chronological order for same-name rows.

Generally, the output files should be sorted chronological and alphabetical:
* Pass 1 chronological if a date is available, e.g. by publication date.
* Pass 2 stable alphabetical if a label is available, e.g. by name.
This will cluster same-name rows together for easy human disambiguation, and preserve chronological order within those same-name rows.

## Module Breakdown

### Proposed files in `speakermining/src/process/entity_disambiguation/`
1. `io_staging.py` (raw import snapshot + manifests)
2. `normalization.py` (value normalization helpers)
3. `schema_mapping.py` (property inventory and canonical mapping)
4. `episode_alignment.py` (layer 2 candidate generation + scoring + assignment)
5. `person_alignment.py` (layer 3 matching logic)
6. `topic_alignment.py` (topic matching)
7. `role_org_alignment.py` (layer 4 best-effort matching)
8. `evidence.py` (evidence row construction and serialization)
9. `quality_gates.py` (acceptance checks)
10. `contracts.py` (column constants and output schemas)

## Quality Gates

### Gate A: Structural
1. All expected output files exist.
2. Required columns exist in each output table.
3. No duplicate `alignment_unit_id` inside one aligned class table.
4. Single aligned row schema columns are present in every aligned core table.

### Gate B: Semantic
1. Every matched row has at least one evidence feature.
2. No hard contradictions in matched rows.
3. Every unresolved row is explicitly marked with `match_tier = unresolved`, has non-empty `unresolved_reason_code`, and has non-empty `unresolved_reason_detail`.
4. Every inferred-context decision is explicitly marked with `inference_flag = true` and non-empty `inference_basis`.

### Gate C: Coverage and risk
1. Report unresolved ratio per class.
2. Report medium-confidence accepted counts separately.
3. If unresolved ratio spikes above configured threshold, fail in strict mode.

## Human Handoff Contract
1. This step ends after writing aligned artifacts and diagnostics.
2. Human analysts perform manual analysis and manual matching outside this automated step.
3. Handoff package must include aligned tables, evidence, schema mapping, run summary, and inspectable examples.

## Phase 1 Deliverables Checklist
1. `01_approach.md` aligned to immutable layered strategy.
2. `02_implementation.md` defines executable step sequence, outputs, scoring, and quality gates.
3. All planning artifacts are consistent with rerunnable notebook-plus-module architecture.

## Deferred To Phase 2 (Refinement)
1. Reuse opportunities from `2026-04-11_redesign` code/docs.
2. Additional heuristic feature tuning after first baseline run.
3. Contract promotion to `documentation/contracts.md` once schemas stabilize.
