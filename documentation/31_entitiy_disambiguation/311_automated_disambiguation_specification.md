# Phase 31 Disambiguation - Step 311 Automated Specification (Draft)

Date: 2026-04-09  
Status: Draft v0.1 (implementation-guiding)

Naming note:

1. Canonical naming is Phase 31 (Disambiguation), Step 311 (Automated), Step 312 (Manual).
2. Data path remains `data/31_entity_disambiguation/` as the current repository folder owner.

## 1. Purpose

Phase 31 is split into two sub-steps with different ownership:

1. Step 311 (this specification): fully automated alignment bootstrap.
2. Step 312 ([312_manual_reconciliation_specification.md](312_manual_reconciliation_specification.md)): human refinement in OpenRefine.

Primary objective for Step 311:

1. Align source information as far as possible with deterministic rules only.
2. Preserve unresolved cases as explicit records (no forced links).
3. Produce one handoff CSV per core class for OpenRefine.

This specification follows repository governance in [workflow.md](../workflow.md), [coding-principles.md](../coding-principles.md), and [contracts.md](../contracts.md).

## 2. Scope And Non-Goals

In scope for Step 311 (automated):

1. Deterministic alignment bootstrap across sources, grounded in broadcasting program and episode context.
2. Episode-grounded person alignment as first priority.
3. Generation of machine-prepared CSV handoff tables for human refinement.

Out of scope for Step 311:

1. Manual acceptance/rejection decisions.
2. Cross-episode entity consolidation (handled in Phase 32 deduplication).
3. Final truth curation; this remains a human-in-the-loop activity in Step 312.

## 3. Input Boundaries (Immutable Upstream)

Step 311 reads upstream data only and writes only to data/31_entity_disambiguation.

Required upstream sources:

1. Specified broadcasting programs:
   - data/00_setup/broadcasting_programs.csv
2. Mention detection episode/person ground truth:
   - data/10_mention_detection/episodes.csv
   - data/10_mention_detection/persons.csv
   - data/10_mention_detection/publications.csv
   - data/10_mention_detection/seasons.csv
   - data/10_mention_detection/topics.csv
3. Wikidata projections (graph-first/fallback outputs):
   - data/20_candidate_generation/wikidata/projections/instances_core_broadcasting_programs.csv
   - data/20_candidate_generation/wikidata/projections/instances_core_series.csv
   - data/20_candidate_generation/wikidata/projections/instances_core_episodes.csv
   - data/20_candidate_generation/wikidata/projections/instances_core_persons.csv
   - data/20_candidate_generation/wikidata/projections/instances_core_topics.csv
   - data/20_candidate_generation/wikidata/projections/instances_core_roles.csv
   - data/20_candidate_generation/wikidata/projections/instances_core_organizations.csv
4. Fernsehserien.de projections:
   - data/20_candidate_generation/fernsehserien_de/projections/episode_guests_normalized.csv
   - data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv
   - data/20_candidate_generation/fernsehserien_de/projections/episode_broadcasts_normalized.csv

## 4. Layered Matching Model

The disambiguation strategy is hierarchical. Higher layers constrain lower layers.

1. Layer 1: Broadcasting Program (already unified from setup, no new disambiguation in Phase 31).
2. Layer 2: Episode alignment across sources, primarily by time and publication signals.
3. Layer 3: Person alignment within an already aligned episode.
4. Layer 4: Role and organization facts may increase confidence but do not overwrite stronger layer-1/2 links.

Operational rule:

1. Never force a match below confidence threshold.
2. Keep unresolved entities as explicit orphans with reason.

## 5. Canonical Matching Unit

The canonical matching unit in Step 311 is:

1. One person mention in one episode of one broadcasting program.

Alignment question:

1. Which candidate entity (if any) corresponds to this episode-scoped mention under deterministic evidence rules?

This means the same real-world person can appear in multiple episode-scoped rows at this phase.

## 6. Core-Class Output Strategy

Step 311 outputs a set of CSV files, one per core class defined in data/00_setup/core_classes.csv.

Current core class set:

1. broadcasting_programs
2. series
3. episodes
4. persons
5. topics
6. roles
7. organizations

Each output file is an alignment workspace table that aggregates available source evidence (ZDF mention detection, Wikidata projections, fernsehserien.de projections) into one row model per class-specific matching unit.

## 7. Deterministic Join Strategy

Step 311 joins should be deterministic and replayable.

Episode bridge priorities:

1. Use shared episode identity when present (episode_id from mention detection/candidate generation tables).
2. Use publication-time attributes as secondary evidence (date, time, duration, season/folge metadata).
3. Keep unmatched episodes as unresolved; do not synthesize weak links.

Person candidate bridge priorities within episode:

1. Exact or normalized name compatibility.
2. Episode-local context compatibility.
3. Source traceability fields retained from candidate-generation projections.

## 8. Automated Execution Contract (Notebook 30)

Notebook path: speakermining/src/process/notebooks/31_entity_disambiguation.ipynb

Runtime requirement:

1. This step must run end-to-end with a single Run All.
2. No manual cell editing or human decision entry is part of Step 311.
3. Reruns must be deterministic for unchanged inputs.

Operational behavior:

1. Read immutable upstream Phase 1 and Phase 2 artifacts.
2. Build deterministic alignment candidates and confidence/explanation fields.
3. Write per-core-class handoff CSVs to data/31_entity_disambiguation.

## 9. Deterministic Alignment Policy

Policy defaults are precision-first:

1. Commit automated link hypotheses only when evidence is explicit and explainable.
2. Keep low-confidence rows unresolved rather than over-linking.
3. Preserve source-level traceability fields needed for later human review.

Detailed artifact definitions are in [313_disambiguation_artifact_contract_draft.md](313_disambiguation_artifact_contract_draft.md).

## 10. Quality And Traceability Requirements

1. Every automated alignment row must be reproducible from explicit input evidence fields.
2. Every unresolved/orphan case must remain visible (not silently dropped).
3. Handoff CSVs must keep enough context for OpenRefine review without re-querying upstream systems.
4. Step 311 outputs must not modify upstream phase directories.

## 11. Human Handoff And Phase 32 Boundary

Step 312 consumes the automated per-core-class CSVs in OpenRefine and performs human enrichment/disambiguation.

See [312_manual_reconciliation_specification.md](312_manual_reconciliation_specification.md).