# Upstream Handover - Downstream Findings and Remediation Loop

Date: 2026-04-11  
Source phase: Phase 31 Step 311 (Entity Disambiguation)  
Target upstream phases: Phase 20 (Wikidata Candidate Generation), Phase 10 (Mention Detection), setup/config governance

## Purpose

This handover summarizes issues found downstream, the local downstream mitigation applied in Phase 31, and recommended upstream fixes so the full pipeline quality improves over time.

This is a clean-slate feedback loop:
1. Detect issue downstream.
2. Implement safe local mitigation so current pipeline remains usable.
3. Document root cause and upstream fix path.
4. Upstream updates source data and extraction rules.
5. Downstream reruns and removes temporary rewiring where no longer needed.

## Repository-Level Governance Artifacts (00_setup)

These controls are not Phase 31-local. They are global setup artifacts and must live in `data/00_setup`:

- `data/00_setup/rewiring_catalogue.csv`
   - minimal rewiring assertions in 4 columns: `subject,predicate,object,rule`
- `data/00_setup/learning_scope_registry.md`
   - human-readable scope registry for handoffs and ownership

Rule:
- If a learning has repository-level relevance, it must be represented in `data/00_setup` and not only in phase-local code.

## Scope Classification Model (Mandatory for New Findings)

Every finding must declare an affected scope level and targets.

Scope levels:
- `step`: one concrete pipeline step (example: `phase31.step311`)
- `phase`: all steps inside one phase (example: `phase20.*`)
- `repository`: cross-phase/global behavior (example: class rewiring policy)

Required metadata per finding (recorded in markdown handoff + registry):
- `learning_id`
- `scope_level`
- `scope_targets`
- `upstream_owner`
- `status`
- `first_seen`
- `last_validated`

Application policy:
1. `step` scope: implement in local step and add test/diagnostic at step level.
2. `phase` scope: implement in shared phase module/config and validate against all phase outputs.
3. `repository` scope: implement in `data/00_setup` + shared config, then propagate to all affected phases.

## Evidence Base (from diagnostic notebook)

Notebook used: speakermining/src/process/notebooks/31_entity_disambiguation_diagnostic.ipynb

Current measured state:
- classes_with_full_property_payload: 7 / 7
- remaining_high_gaps: 0
- Q3464665 season-like entities in WD broadcasting_programs: 66
- Q3464665 now present in aligned_series: 66
- Q3464665 missing from aligned_series: 0

Interpretation:
- The critical misrouting issue was real and reproducible.
- A downstream mitigation is now in place and validated.
- Upstream should still fix source classification and extraction logic to avoid relying on downstream rewiring.

## Issue Card 1 - Season entities misclassified under broadcasting_programs

Severity: High (historically caused full drop from aligned_series)

Observed behavior:
- Wikidata entities with P31 = Q3464665 (television series season) appeared in broadcasting_programs input.
- These entities were not being represented in aligned_series prior to mitigation.

Root cause hypothesis:
- Upstream class-to-core-class assignment in Phase 20 is too coarse for certain classes that can map to multiple semantic buckets.
- Season-like entities were routed only by source container instead of semantic class evidence.

Downstream mitigation applied (Phase 31):
- During Wikidata broadcasting_program seed pass, entities with P31 containing Q3464665 are additionally routed into series output.
- This keeps visibility in both semantic contexts while preserving deterministic behavior.

Validation result:
- Before: 66/66 missing from aligned_series.
- After: 0/66 missing from aligned_series.

Upstream recommendation (Phase 20 Wikidata Team):
1. Add semantic class routing rule in projection generation:
   - If P31 includes Q3464665, entity must be emitted into series projection (even if also present in broadcasting_programs projection).
2. Introduce multi-target projection capability for ambiguous/high-overlap classes.
3. Add QA check in Phase 20:
   - Count entities where P31=Q3464665 in broadcasting_programs projection.
   - Assert those entities exist in series projection as well.

Suggested acceptance criteria upstream:
- 100% of P31=Q3464665 entities are present in series projection.
- No reduction in existing broadcasting_programs projection coverage.

## Issue Card 2 - Insufficient Wikidata property projection width

Severity: High (historically prevented rich downstream reasoning and auditability)

Observed behavior:
- Source entities have hundreds of distinct Wikidata properties per core class in some sets.
- Downstream aligned outputs previously carried only a very narrow subset of Wikidata evidence.

Downstream mitigation applied (Phase 31):
- Added generic property payload columns across all aligned projections:
  - wikidata_claim_properties
  - wikidata_claim_property_count
  - wikidata_claim_statement_count
  - wikidata_property_counts_json
  - selected key relation vectors (P31, P179, P106, P39, P921, P527, P361)
- These now appear across all 7 core-class outputs.

Validation result:
- Full payload coverage columns present in 7/7 core classes.

Upstream recommendation (Phase 20 Wikidata Team):
1. Emit a normalized property profile directly in Phase 20 projections for each entity.
2. Preserve key relationship properties in explicit fields for stable downstream contracts.
3. Version projection schema so downstream can detect property profile support explicitly.

Suggested acceptance criteria upstream:
- Every projected entity includes explicit property profile fields.
- Key property vectors are present for deterministic downstream routing.

## Known-Mismatch Rewiring Catalogue (Repository-Wide Governance Artifact)

This catalogue is a controlled override mechanism for class/core-class mismatches discovered downstream.

Storage location (global):
- `data/00_setup/rewiring_catalogue.csv`

### 1) Authoritative mapping (minimal format)

Goal:
- Allow deterministic local policy when upstream semantics are known to be wrong or incomplete.

Required capabilities:
- Add assertion triples for class rewiring.
- Remove assertion triples when invalid.
- Keep detailed rationale in markdown handoff documents.

Proposed schema (CSV):
- subject
- predicate
- object
- rule

Example:
- `Q3464665,P279,Q7725310,add`

Behavior:
- `rule=add` adds/overrides local semantic wiring.
- `rule=remove` forbids the asserted triple locally.
- Audit context (why/when/who/scope) is captured in markdown handoff docs and the scope registry.

### 2) Wikidata manual correction option

Goal:
- Encourage correcting semantics at the source of truth.

Workflow:
1. Analyst identifies problematic class mapping.
2. Analyst updates Wikidata statements (for example P31/P279 structure) directly.
3. Pipeline reruns Phase 20 extraction.
4. Phase 31 reruns diagnostics and verifies mismatch resolved.
5. Local rewiring rule can be retired if no longer needed.

Governance note:
- Keep a ticket link to the exact Wikidata edits so provenance is explicit.

### 3) Wikidata subclass expansion (n-degree)

Goal:
- Improve class coverage by traversing subclass chains from core classes.

Algorithm:
1. Start with configured core classes.
2. Fetch subclasses at degree 1.
3. Expand recursively to degree n.
4. Build class-to-core-class candidate map with path metadata.

Required controls:
- max_depth (n)
- cycle protection
- exclusion list
- cache timestamp
- deterministic ordering of class resolution

Output fields suggested:
- class_qid
- root_core_class
- min_depth
- all_paths_json
- resolution_conflict_flag

### 4) Core-class hierarchy and precedence

Goal:
- Resolve cases where one class can map to multiple core classes.

Policy:
- More fine-grained class wins over broader class.
- Example: if a class maps to both broadcasting_programs and series, series has higher precedence.

Proposed precedence (highest to lowest):
1. episodes
2. series
3. persons
4. organizations
5. roles
6. topics
7. broadcasting_programs

Notes:
- This list should be explicit config, not hardcoded logic.
- Keep policy versioned and documented.

## Upstream Ticket Suggestions

### Ticket P20-WD-001: Season class dual-routing
- Add rule for P31=Q3464665 to route into series projection.
- Add QA assertion for parity between detected season-like entities and series projection coverage.

### Ticket P20-WD-002: Property profile contract
- Add property profile payload in projections for all core classes.
- Include relation vectors for class-routing and semantic enrichment.

### Ticket P20-WD-003: Rewiring catalogue integration
- Support loading local rewiring catalogue before final projection assignment.
- Add force_include/force_exclude with deterministic precedence.

### Ticket P20-WD-004: Subclass expansion service
- Implement configurable n-degree subclass expansion.
- Export class-to-core-class resolution map with provenance and conflict flags.

## Operational Loop for Future Findings

Whenever a new downstream issue is identified:
1. Add a short issue card in a dated upstream handover document.
2. Capture reproducible evidence from diagnostic notebook.
3. Classify and register scope in `data/00_setup/learning_scope_registry.md`.
4. If scope is repository-level, add/adjust rules in `data/00_setup/rewiring_catalogue.csv`.
5. Add downstream mitigation if needed for continuity.
6. File upstream ticket with acceptance criteria.
7. Re-run diagnostics after upstream update.
8. Remove obsolete overrides when upstream truth is corrected.

## Suggested Owners

- Phase 20 Wikidata Team: class routing, subclass expansion, projection schema.
- Phase 31 Team: diagnostics, temporary rewiring, validation, deprecation of temporary rules.
- Data Governance: precedence policy and override audit process.

## Current Status

- Downstream mitigation in place and validated for both major findings.
- Phase 20 upstream execution for this handover is complete (P20-WD-001 through P20-WD-004 implemented and validated).
- Remaining long-term recommendation: reduce reliance on local rewiring by correcting source semantics directly in Wikidata where applicable.

## Phase 20 Task Progress (Implementation Started)

Status snapshot:
- P20-WD-001 (Season class dual-routing): implemented and validated.
- P20-WD-002 (Property profile contract): implemented at projection schema level and validated.
- P20-WD-003 (Rewiring catalogue integration): implemented with global setup source `data/00_setup/rewiring_catalogue.csv`.
- P20-WD-004 (Subclass expansion service): implemented and validated.

Validation evidence after Phase 20 materialization run:
- `instances_core_series.json` contains 66 entities with `class_id=Q3464665`.
- `instances_core_broadcasting_programs.json` also contains the same 66 entities (dual-routing behavior preserved).
- New property-profile columns are present in both projections, including:
   - `wikidata_claim_properties`
   - `wikidata_claim_property_count`
   - `wikidata_property_counts_json`
   - `wikidata_p31_qids`
   - `wikidata_p279_qids`

Implementation notes:
- Rewiring assertions are now consumed during class-path resolution and projection writing.
- The minimal rewiring tuple `Q3464665,P279,Q7725310,add` is active and contributes to series routing.
- Subclass expansion max depth is now configurable via `WIKIDATA_SUBCLASS_EXPANSION_MAX_DEPTH` (default: `2`).
- `class_resolution_map.csv` is now emitted with deterministic conflict resolution output and provenance paths.
- Legacy `instances_core_*.csv` and `instances_core_*.parquet` outputs are deprecated and no longer produced.
- Core-class handoff is now JSON-only via `instances_core_*.json`.

Additional validation evidence for P20-WD-004:
- Materialization completed successfully with class-resolution artifact emission.
- `subclass_expansion_max_depth`: `2`
- `class_resolution_rows`: `2092`
- `class_resolution_conflict_rows`: `16`
- `class_resolution_map.csv` columns:
   - `class_id`
   - `resolved_core_class_id`
   - `resolution_depth`
   - `resolution_reason`
   - `conflict_flag`
   - `candidate_core_class_ids`
   - `candidate_paths_json`
   - `max_depth`
