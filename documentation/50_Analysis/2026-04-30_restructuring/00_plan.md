# Restructuring Plan

This folder rebuilds the Phase 5 analysis and visualization design from scratch. Four phases, executed strictly in order to prevent concept drift from the prior initiative.

---

## Phase 1 — Requirements extraction

**Goal:** Convert the primary input into structured requirements; establish tasks.  
**Source:** `archive/additional_input.md` (verbatim input)  
**Outputs:** `00_requirements.md`, `01_design.md` (preliminary stub), `open-tasks.md` (tasks only)  
**Status:** ✅ Complete

What was done:
- All input processed into 41 requirements (REQ-G, REQ-C, REQ-P, REQ-U, REQ-I, REQ-T, REQ-Q, REQ-S, REQ-H, REQ-V)
- Two clarifications resolved via `open_additional_input.md` (Sankey semantics, loop resolution rule)
- REQ-C01 (config-file-driven specification) added
- TASK-B19 (config files) created
- 19 implementation tasks defined with dependency order

---

## Phase 2 — Internal gap analysis

**Goal:** Inspect only the new design (`00_requirements.md`) for gaps, ambiguities, and missing structure — without consulting prior initiative files.  
**Input:** `00_requirements.md`  
**Output:** Clear gaps added directly to `00_requirements.md`; ambiguous items raised as questions in `open_additional_input.md`.  
**Status:** ✅ Complete

What was done:
- 6 clear gaps found and fixed directly in `00_requirements.md` (P106 missing, Unknown row, person/appearance duality, default population, export format, hierarchy property scope)
- 7 questions raised in `open_additional_input.md` (co-occurrence definition, timeline granularity, cumulative meaning, percentage vs count, top-level class X, which properties are hierarchical, incomplete verbatim for REQ-H07)

---

## Phase 3 — Concept finalization

**Goal:** Create the authoritative, easy-to-read design document.  
**Input:** All resolved requirements from Phases 1 and 2.  
**Output:**
- 3a: `01_design.md` — hierarchically structured overview (universal → subcategory → specific). **User review required before 3b.**
- 3b: Fleshed-out concept aggregating all definitions and decisions from this folder into a single coherent spec.  
**Status:** ✅ Complete

What was done:
- `01_design.md` rewritten as full hierarchical design specification
- Architecture Overview: text pipeline diagram, 23-module structure under `speakermining/src/analysis/`, notebook orchestration pattern
- Data Model: Scope concept, 11 primary data structures with shapes and key columns, property type routing table
- Configuration File Schemas: column definitions for all 4 config CSVs
- Layer 0: ColorRegistry class interface, Okabe-Ito palette values, gray reserved for Unknown
- Layer 1 (1a–1c): Input/output contracts, algorithm descriptions, P279 walk and loop resolution logic
- Layer 2 (2a–2h): Per-module algorithm specs, output DataFrame shapes, all 8 analysis modules
- Layer 3 (3a–3m): Chart type, layout, color, label, and sorting spec for every visualization module
- Output Directory Structure: full file tree with naming conventions

---

## Phase 4 — Prior initiative aggregation

**Goal:** After the clean concept is established, inspect prior work to capture any missed items — without letting old rigid thinking overwrite the fresh design.  
**Input:** `documentation/50_Analysis/2026-04-29_Initialization/` and other existing files.  
**Output:** Additional requirements or tasks merged into `00_requirements.md` and `open-tasks.md` as appropriate.  
**Status:** ✅ Complete

What was done:
- Read `02_design_review.md` in full (40 items across 6 categories: G, M, V, P, S, X)
- Read `04_analysis_angle_structure.md` (F1–F5 taxonomy, Type A/B/C/D — structurally superseded by the Phase 3 design but mined for gaps)
- Read `05_implementation_context.md` (confirmed `duration_minutes` in `episode_metadata_normalized.csv`; German labels in `instances.csv`; class hierarchy files already exist)
- Categorized all 40 items: 13 already addressed, 9 added as new requirements, 4 added as new tasks, 14 deferred as out-of-scope or nice-to-have
- New requirements added to `00_requirements.md`: P108 added to REQ-P01; REQ-P07 (temporal snapshot); REQ-U10 (multi-value counting rule); REQ-G05 (cross-show comparison); REQ-A03 (GDPR separation); REQ-META02 (property coverage dashboard); REQ-V13 ("Other" bar styling); REQ-V14 (color overflow strategy); REQ-V15 (geographic map for P19)
- New design principles added to `01_design.md`: idempotency (P6), German-first label resolution (P7), progress reporting (P8); definition of done section added; modules 3n/3o/3p added
- New tasks added to `open-tasks.md`: TASK-B25 (CDU-black conflict), TASK-B26 (cross-show comparison), TASK-B27 (property coverage dashboard)
- Deferred items (not added): M-02 page rank, M-06 career arc, M-07 subset dominance, M-09 person property timeline, X-01 Bundestag overlay, X-02 population benchmarks, X-04 diversity metrics, X-05 seasonal patterns, X-10 interactive HTML dashboard

**Note:** `02_design_review.md` was created accidentally before Phase 3. It was used as a Phase 4 source; its contents are now fully processed.

---

## Execution sequence

```
Phase 1 → Phase 2 → Phase 3a → [user review] → Phase 3b → Phase 4
```

Each phase must be complete before the next begins. Phase 3 has a mandatory user review checkpoint between 3a and 3b.
