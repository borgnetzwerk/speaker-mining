# Phase 31 Step 311 Artifact Contract Draft

Date: 2026-04-09  
Status: Draft v0.1 (to be promoted into documentation/contracts.md after notebook implementation)

Naming note:

1. Canonical naming is Phase 31 (Disambiguation), Step 311 (Automated), Step 312 (Manual).
2. Data path remains `data/31_entity_disambiguation/` as the current repository folder owner.

This draft defines the intended first stable automated outputs for data/31_entity_disambiguation.

## 1. Output Directory Ownership

Step 311 writes only to:

1. data/31_entity_disambiguation/

No writes are allowed to upstream phase folders.

## 2. Primary Files (Automated Step 311)

The initial output is one CSV per core class.

Core class filenames are sourced from data/00_setup/core_classes.csv.

Expected files:

1. aligned_broadcasting_programs.csv
2. aligned_series.csv
3. aligned_episodes.csv
4. aligned_persons.csv
5. aligned_topics.csv
6. aligned_roles.csv
7. aligned_organizations.csv

Each file contains deterministic, source-aligned evidence rows for that class and is intended for OpenRefine import.

## 3. Required Baseline Columns (All aligned_*.csv)

Purpose:

1. Preserve common join keys and explainability fields across all classes.

Columns:

1. alignment_unit_id
2. core_class
3. broadcasting_program_key
4. episode_key
5. source_zdf_value
6. source_wikidata_value
7. source_fernsehserien_value
8. deterministic_alignment_status
9. deterministic_alignment_score
10. deterministic_alignment_method
11. deterministic_alignment_reason
12. requires_human_review

Additional property policy:

1. Class-specific and source-specific evidence columns are allowed beyond the baseline set.
2. Repeated multi-value properties should use deterministic suffixing (`<property>_1`, `<property>_2`, ...).
3. Property column naming should remain stable across reruns with unchanged input.
4. For persons in particular, high-cardinality Wikidata properties (occupation, positions held, affiliations, interests) should be included when available.

Status value set:

1. aligned
2. unresolved
3. conflict

## 4. Class-Specific Extensions

Class files may add columns as needed, but must not drop baseline columns.

Examples:

1. aligned_persons.csv may include mention_id, person_name, person_description, candidate_id, candidate_label.
2. aligned_episodes.csv may include publication date/time/duration evidence fields.
3. aligned_roles.csv and aligned_organizations.csv may include extracted role/org fragments from person descriptions.

## 5. OpenRefine Handoff Requirements

1. Files must be directly importable as plain CSV with stable headers.
2. All deterministic methods and reasons must be human-readable.
3. Rows that are unresolved or conflicting must remain in output (no pre-filtering).

## 5.1 Projection Ordering Contract

Ordering must be deterministic and reproducible across reruns with unchanged inputs.

Global time-aware ordering:

1. Chronological oldest-first where publication date/time exists.
2. Season and episode numbers are deterministic tie-breakers where present.

Persons ordering:

1. Pass 1: chronological by episode appearance (oldest first).
2. Pass 2: stable alphabetical by person name.
3. For same-name rows, chronological order from pass 1 must remain preserved.

## 6. Optional Technical Sidecars

Optional sidecars are allowed for reproducibility, but are not the primary handoff contract.

Allowed examples:

1. alignment_run_summary.json
2. alignment_provenance.csv

## 7. Promotion Criteria Into Global Contracts

This draft should be moved into documentation/contracts.md when all are true:

1. Notebook 30 implementation is active (not placeholder).
2. A single Run All generates all aligned_*.csv files under data/31_entity_disambiguation.
3. OpenRefine pilot import validates that baseline columns are sufficient for manual enrichment.
