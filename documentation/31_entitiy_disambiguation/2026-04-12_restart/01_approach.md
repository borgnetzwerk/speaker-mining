# Approach

## Goal
Create aligned core-class instance tables for Phase 31, prioritizing reliable person alignment through episode context.

Canonical matching unit for person work:
1. One person mention in one episode of one broadcasting program.

The authoritative matching order from `00_immutable_input.md` is fixed:
1. Broadcasting Program (already unified)
2. Episode (main alignment target)
3. Person (episode-guided first, then weaker evidence)
4. Role and Organization (best-effort)

## Scope

### In scope
1. Build a repeatable, rerunnable disambiguation workflow for ZDF archive, fernsehserien.de, and Wikidata projections.
2. Produce aligned tables per core class with explicit confidence, evidence, and unresolved status in-table.
3. Perform one automated best-effort matching pass and hand off all outputs for human manual analysis and manual matching.
4. Keep inspectable example artifacts and handover-ready documentation.

### Out of scope
1. Any upstream mention detection or candidate generation logic changes.
2. Any event-sourcing redesign for Phase 31.
3. Forcing low-confidence role/organization matches.
4. Performing manual reconciliation inside this automated step.

## Input Inventory

### Baseline
1. `data/00_setup/broadcasting_programs.csv`

### ZDF archive (Phase 10 outputs)
1. `data/10_mention_detection/seasons.csv`
2. `data/10_mention_detection/episodes.csv`
3. `data/10_mention_detection/publications.csv`
4. `data/10_mention_detection/persons.csv`
5. `data/10_mention_detection/topics.csv`

### Wikidata projections (Phase 20 outputs)
1. `data/20_candidate_generation/wikidata/projections/instances_core_broadcasting_programs.json`
2. `data/20_candidate_generation/wikidata/projections/instances_core_series.json`
3. `data/20_candidate_generation/wikidata/projections/instances_core_episodes.json`
4. `data/20_candidate_generation/wikidata/projections/instances_core_persons.json`
5. `data/20_candidate_generation/wikidata/projections/instances_core_roles.json`
6. `data/20_candidate_generation/wikidata/projections/instances_core_topics.json`
7. `data/20_candidate_generation/wikidata/projections/instances_core_organizations.json`
8. `data/20_candidate_generation/wikidata/projections/triples.csv`
9. `data/20_candidate_generation/wikidata/projections/properties.csv`
10. `data/20_candidate_generation/wikidata/projections/classes.csv`
11. `data/20_candidate_generation/wikidata/projections/aliases_en.csv`
12. `data/20_candidate_generation/wikidata/projections/aliases_de.csv`

### Fernsehserien.de projections (Phase 20 outputs)
1. `data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv`
2. `data/20_candidate_generation/fernsehserien_de/projections/episode_broadcasts_normalized.csv`
3. `data/20_candidate_generation/fernsehserien_de/projections/episode_guests_normalized.csv`

### Phase 31 workspace target
1. `data/31_entity_disambiguation/raw_import/`
2. `data/31_entity_disambiguation/normalized/`
3. `data/31_entity_disambiguation/aligned/`

## Method

### 1. Raw import snapshot
Copy all required inputs into `data/31_entity_disambiguation/raw_import/` as run-stable snapshots to decouple Phase 31 from moving upstream files.

### 2. Value normalization
Standardize values before any matching:
1. Date and datetime formats
2. Duration and time formats
3. Numeric representations
4. Language-sensitive textual variants (German/English, varying ordinal forms)
5. Abbreviations and punctuation variants

Normalization must be loss-aware: if a value cannot be normalized, preserve raw value and add a normalization status flag.

### 3. Property/schema harmonization
Build a per-class canonical schema and map source-specific columns/claims to it.
1. Extract source property inventories
2. Define canonical columns per class
3. Map source properties to canonical properties with traceability
4. Persist mapping table for auditability and iterative improvement
5. Add inferred canonical properties when a source omits critical context fields but the context is derivable from other source columns or joins.
6. Represent source evidence in flattened, source-suffixed column families, not single scalar placeholder fields per source.
7. Expand repeated source properties into deterministic wide-column families so one aligned row can hold all available evidence for that entity.

Wikidata property IDs and labels are the primary alignment anchor where available.

Missing-context policy:
1. Blank fields in one source must not block alignment when equivalent context can be inferred from adjacent columns, publication joins, season/episode relations, or normalized title/program signals.
2. Inferred values must be marked as inferred with source lineage in evidence fields.

Evidence modeling policy:
1. Source evidence must preserve multi-field context and repeated values within a single wide row, using deterministic column families for repeated properties.
2. Human handoff must be able to inspect exact source fragments used for the decision via explicit flattened columns.

### 4. Layered alignment execution

#### Layer 1: Broadcasting Program
No disambiguation. Use as stable backbone key for lower layers.

#### Layer 2: Episode (and season support)
Primary alignment objective. Match using weighted publication/date/time/title signals constrained by broadcasting program.

#### Layer 3: Person
Primary strategy: align persons through already aligned episodes.
Secondary strategy: name plus contextual/property similarity only when episode evidence is absent.

#### Layer 4: Role and Organization
Best-effort only. Use structured Wikidata claims and weak textual hints in source descriptions. Keep unresolved by default when evidence is insufficient.

Layer interaction rule:
1. Layer 4 may increase confidence when consistent with Layers 1-3 evidence.
2. Layer 4 must not overwrite or contradict stronger Layer 1/2 constraints.

### 5. Confidence and unresolved policy
1. Never force a match below threshold.
2. Record match score and evidence fields.
3. Keep unresolved entities in the aligned tables with explicit unresolved reason codes.
4. Separate exact/high-confidence/weak-confidence tiers.
5. Treat this as an automated handoff step; manual resolution happens after output delivery.

Status vocabulary:
1. `aligned`
2. `unresolved`
3. `conflict`

## Deliverables
1. Aligned core-class tables in `data/31_entity_disambiguation/aligned/`
2. Raw import snapshots in `data/31_entity_disambiguation/raw_import/`
3. Normalized intermediate artifacts in `data/31_entity_disambiguation/normalized/`
4. Schema harmonization artifacts in `data/31_entity_disambiguation/aligned/` (for example mapping and diagnostics tables)
5. Example artifacts for every written instance file across:
	- Raw import snapshot
	- Value normalization
	- Property/schema harmonization
	- Layered alignment execution
6. Handover notes in `documentation/00_actionably_handover/` when needed

Handoff readiness rules:
1. Aligned tables must have stable, deterministic column names and ordering across reruns with unchanged input.
2. Deterministic method and reason fields must be human-readable for OpenRefine review.
3. Output row ordering must be deterministic (chronological where applicable; stable tie-breakers for equal timestamps).

## Acceptance Criteria For Phase 1 Planning
1. Approach reflects the immutable layered model exactly.
2. Input inventory is complete and source-specific.
3. Matching policy explicitly prioritizes precision and orphan preservation.
4. Approach is implementation-ready and maps directly to notebook/module steps.