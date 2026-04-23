# Phase 31 Disambiguation - Step 312 Manual Reconciliation Specification (Draft)

Date: 2026-04-09  
Status: Draft v0.1 (implementation-guiding)

Naming note:

1. Canonical naming is Phase 31 (Disambiguation), Step 311 (Automated), Step 312 (Manual).
2. Data path remains `data/31_entity_disambiguation/` as the current repository folder owner.

## 1. Purpose

Step 312 is the human refinement stage after the automated bootstrap in Step 311.

Primary goals:

1. Review machine-aligned rows in OpenRefine.
2. Resolve unresolved/conflicting rows where evidence is sufficient.
3. Preserve reviewer reasoning so later phases remain auditable.

## 2. Core-Class Input files

Step 312 receives one CSV per core class from Step 311 outputs under data/31_entity_disambiguation.

Current core class set:

1. broadcasting_programs
2. series
3. episodes
4. persons
5. topics
6. roles
7. organizations

Expected input naming:

1. aligned_broadcasting_programs.csv
2. aligned_series.csv
3. aligned_episodes.csv
4. aligned_persons.csv
5. aligned_topics.csv
6. aligned_roles.csv
7. aligned_organizations.csv

Each file is an alignment workspace table that aggregates available source evidence (ZDF mention detection, Wikidata projections, fernsehserien.de projections) into one row model per class-specific matching unit.

## 3. Basic principles

1. Precision over forced closure: unresolved is preferred over incorrect linkage.
2. Traceability over convenience: every changed row needs a short reason.
3. Reproducibility: review edits should be exportable and replayable.

## 4. OpenRefine Reconciliation Workflow

1. Import one aligned_*.csv file into OpenRefine.
2. Sort/filter by `match_tier` (`unresolved` rows are the primary review targets).
3. Use `open_refine_name` as the reconciliation query column — it is a cleaned copy of `canonical_label` with leading-dash parse artifacts stripped, pre-formatted for reconciliation against Wikidata.
4. Cluster/normalize key text fields (for example names, role labels, organization labels).
5. Decide row-level outcome:
	- aligned_confirmed
	- aligned_corrected
	- unresolved
	- conflict
6. Fill reviewer metadata fields before export.
7. Export reviewed file as CSV with stable headers.

## 5. Required Human Decision Columns

The reviewed export must include at least:

1. human_decision
2. human_reason
3. reviewer
4. reviewed_at

Recommended value set for human_decision:

1. aligned_confirmed
2. aligned_corrected
3. unresolved
4. conflict

## 6. Feedback Loop To Upstream Phases

Human assessment should propagate backward where patterns are recurring.

Examples:

1. Repeated role extraction misses should become parser improvements in Phase 1.
2. Recurring deterministic false positives should update Step 311 matching rules.
3. Systematic source-field gaps should be tracked in documentation/open-tasks.md.

## 7. Phase 32 Boundary

1. Step 312 does not perform cross-episode deduplication logic.
2. Phase 32 consumes reviewed/refined artifacts and decides merges across records.
3. Unresolved rows remain valid handoff rows and must not be dropped.