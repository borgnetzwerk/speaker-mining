# Phase Analysis Index

> Generated: 2026-04-18 | Last updated: 2026-04-23  
> This is the master index for the phase-by-phase analysis pass over all .md, .py, and .ipynb files.

---

## Analysis Documents

| Document | Phases Covered | Status |
|----------|---------------|--------|
| [PHASE_ANALYSIS_PRE_P1.md](PHASE_ANALYSIS_PRE_P1.md) | Pre-Phase (text extraction) + Phase 1 (mention detection) | Complete |
| [PHASE_ANALYSIS_P2.md](PHASE_ANALYSIS_P2.md) | Phase 2 (Wikidata + fernsehserien.de candidate generation) | Complete |
| [PHASE_ANALYSIS_P31_P32.md](PHASE_ANALYSIS_P31_P32.md) | Phase 31 (disambiguation) + Phase 32 (deduplication) | Complete |
| [PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md](PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md) | Phase 4 (link prediction) + Analysis + Visualization | Complete |
| [ROADMAP_48H.md](archive/ROADMAP_48H.md) | 48-hour staged implementation roadmap | Complete (archived) |

---

## Pipeline Status Summary

| Phase | Notebook | Status | Notes |
|-------|----------|--------|-------|
| Pre-Phase | `10_text_extraction.ipynb` | ✓ Complete / Optional | Text dumps already exist |
| Phase 1 | `11_mention_detection.ipynb` | ✓ Active — Stage 1 complete | All P1 bugs resolved or triaged (2026-04-22); re-run notebook to pick up new fields |
| Phase 1 inspect | `19_analysis.ipynb` | ✓ Optional | Confidence checks only |
| Phase 2a | `20_candidate_generation_wikibase.ipynb` | ✓ Active (legacy prereq) | Must run before 2b |
| Phase 2b | `21_candidate_generation_wikidata.ipynb` | ✓ Complete | v3 event-sourced engine |
| Phase 2c | `22_candidate_generation_fernsehserien_de.ipynb` | ✓ Complete | Row 3 bug CLOSED 2026-04-22 (non-issue) |
| Phase 2d | `23_candidate_generation_other.ipynb` | ✗ Placeholder | Not implemented |
| Phase 31 | `31_entity_disambiguation.ipynb` | ✓ Step 311 runs | Step 312 needs tooling |
| Phase 32 | `32_entity_deduplication.ipynb` | ✓ Active 2026-04-23 | 31,811→8,976 entities (71.8% reduction); manual reconciliation CSV integration pending (TODO-018) |
| Phase 4 | `40_link_prediction.ipynb` | ✗ Placeholder | Not implemented |
| Analysis | `41_analysis.ipynb` | ✓ Active 2026-04-23 | Guest catalogue (640 matched) + page-rank computed; QID label fix pending (TODO-031) |
| Visualization | `51_visualization.ipynb` | ✓ Active 2026-04-23 | 5 chart types (plotly HTML+PNG); principles + rework pending (TODO-024, TODO-025, TODO-032) |

---

## Current Scale (from notebook outputs)

| Entity | Count | Source |
|--------|-------|--------|
| ZDF archive episodes | 2,036 | Phase 1 |
| ZDF archive persons (mention rows) | 10,381 | Phase 1 |
| ZDF archive topics | 10,713 | Phase 1 |
| Wikidata persons | 640 | Phase 2b |
| Wikidata organizations | 51 | Phase 2b |
| Wikidata series | 397 | Phase 2b |
| Wikidata episodes | 997 | Phase 2b |
| Wikidata triples (graph edges) | 120,930 | Phase 2b |
| fernsehserien.de episodes | 6,459 | Phase 2c |
| fernsehserien.de guests (rows) | 25,452 | Phase 2c |
| fernsehserien.de broadcasts | 15,929 | Phase 2c |
| Aligned persons (Phase 31) | ~10,000+ | Phase 31 |
| Aligned seasons (Phase 31) | 412 (410 unresolved) | Phase 31 |
| Canonical entities (Phase 32) | 8,976 (from 31,811; 71.8% reduction) | Phase 32 |
| Wikidata-matched persons (Analysis) | 640 | Phase 32 → Analysis |
| Unmatched canonical entities | ~8,336 | Phase 32 (no Wikidata link yet) |

---

## Open Issues — Current State

> **Source of truth**: `documentation/open-tasks.md`  
> **Execution order and dependency map**: `ToDo/TASK_EXECUTION_PLAN.md`  
>  
> All pre-Phase-32 bugs are resolved or triaged. Phase 32 is implemented. Current work is in analysis, visualization, and documentation.

### Resolved since initial analysis (2026-04-22/23)

| ID | Resolution |
|----|------------|
| TODO-001 | Episode dedup — resolved (SHA1 ID + exact dedup) |
| TODO-002 | Umlaut/ß normalization — done (`normalize_name_for_matching`) |
| TODO-003 | Abbreviation normalization — done (`_expand_abbreviations`) |
| TODO-004 | `mention_category` field — done (`guest`/`incidental` in config + guest.py) |
| TODO-008 | 13 miss episodes — triaged (all `not_extractable`) |
| TODO-009 | EPISODE 363 infos drop — resolved |
| TODO-010 | Split family names — wont-fix (2 occurrences in 10,390 rows) |
| TODO-011 | Guarded file writes — done |
| TODO-012 | Wikidata language-default fallback — done |
| TODO-013 | Notebook network event log — done |
| TODO-014 | JSONL migration assessment — done |
| TODO-015 | Misspelling cluster identification — done |

### Open — High Priority

| ID | Title | Blocks |
|----|-------|--------|
| TODO-018 | Integrate 6-column reconciliation CSV (**deadline 2026-05-03**) | TODO-019 |
| TODO-019 | Complete guest catalogue (add unmatched ~8,336 entities) | TODO-020, TODO-021, TODO-022 |
| TODO-024 | Visualization principles document | TODO-020, TODO-025, TODO-032 |

### Open — Medium Priority

| ID | Title | Blocks |
|----|-------|--------|
| TODO-016 | Normalization-timing policy document | — |
| TODO-017 | Reduce `aligned_persons.csv` to ~40 columns | — |
| TODO-020 | Extended gender distribution analysis | TODO-022 |
| TODO-022 | Compare to prior work | — |
| TODO-023 | Dataset overview and pipeline statistics | TODO-022 |
| TODO-025 | Ingest Wikidata viz + 5 improvements | TODO-022 |
| TODO-026 | Unify ToDo structure | — |
| TODO-027 | Propagate `mention_category` through pipeline | TODO-019, TODO-020 |
| TODO-031 | Fix QID labels in analysis output | TODO-020, TODO-025, TODO-023 |
| TODO-032 | Fix page rank viz (replace bar chart with node graph) | — |

### Open — Low Priority

| ID | Title |
|----|-------|
| TODO-005 | Clarify institution extraction responsibility |
| TODO-006 | Define gender-framing analysis methodology |
| TODO-007 | Define role/occupation merge strategy |
| TODO-021 | Predictive analytics |
| TODO-028 | Document title disambiguation finding |
| TODO-029 | Document Wikidata birthdate bias finding |
| TODO-030 | Compile pipeline findings for paper/talk |
| TODO-033 | Document gender bias scope limitation |
| TODO-034 | Document phase equivalence of discovery sources |

---

## File Inventory Summary

### Python Modules

| Area | File Count | Key Files |
|------|-----------|-----------|
| Text extraction | 1 | `text_extraction/text.py` |
| Mention detection | 7 | `episode.py`, `guest.py`, `config.py`, `duplicates.py` |
| Candidate generation (common) | 6 | `broadcasting_program.py`, `person.py`, `persistence.py` |
| Wikidata engine | 35+ | `expansion_engine.py`, `materializer.py`, `event_log.py` |
| fernsehserien.de engine | 14 | `orchestrator.py`, `parser.py`, `projection.py` |
| Entity disambiguation | 13 | `orchestrator.py`, `person_alignment.py`, `contracts.py` |
| Infrastructure | 2 | `io_guardrails.py`, `notebook_event_log.py` |
| **Total** | **~78** | |

### Notebooks

| Notebook | Status |
|----------|--------|
| `10_text_extraction.ipynb` | Complete / Optional |
| `11_mention_detection.ipynb` | Active |
| `19_analysis.ipynb` | Active / Optional |
| `20_candidate_generation_wikibase.ipynb` | Active (prereq) |
| `21_candidate_generation_wikidata.ipynb` | Active |
| `21_wikidata_vizualization.ipynb` | Active / Optional |
| `22_candidate_generation_fernsehserien_de.ipynb` | Active |
| `23_candidate_generation_other.ipynb` | Placeholder |
| `31_entity_disambiguation.ipynb` | Partially active |
| `32_entity_deduplication.ipynb` | Active (2026-04-23) |
| `40_link_prediction.ipynb` | Placeholder |
| `41_analysis.ipynb` | Active (2026-04-23) |
| `51_visualization.ipynb` | Active (2026-04-23) |

### Documentation Files (key)

| File | Purpose |
|------|---------|
| `documentation/workflow.md` | Authoritative execution order |
| `documentation/contracts.md` | Output schemas and file contracts |
| `documentation/open-tasks.md` | Single source of truth for TODO items |
| `documentation/findings.md` | Aggregated research notes |
| `documentation/repository-overview.md` | End-to-end architecture |
| `documentation/coding-principles.md` | Contributor standards |
| `documentation/notebook-observability.md` | Notebook logging contract |
| `documentation/31_entitiy_disambiguation/` | Phase 31 design docs (12+ files) |
| `documentation/Wikidata/` | Wikidata migration history (extensive) |
| `documentation/fernsehserien_de/` | fernsehserien.de specs |

---

## Cross-Cutting Findings

### F-A: The Critical Path Is Phase 1 Quality
Every downstream phase reads Phase 1 output. The bugs in TODO-001, TODO-008, TODO-009 inflate row counts, drop valid guests, and affect Phase 31 alignment fidelity. **Fix Phase 1 bugs first.**

### F-B: Phase 31 Already Runs End-to-End
`31_entity_disambiguation.ipynb` produces all 7 aligned tables. The main issues are:
1. High unresolved rate for seasons (expected)
2. Empty roles (needs Wikidata expansion fix)
3. OpenRefine handoff columns not yet defined

### F-C: Phase 32 Is Implemented; Phase 4 Remains Greenfield
Phase 32 (`32_entity_deduplication.ipynb`) was implemented 2026-04-23, reducing 31,811 entities to 8,976 (71.8%). Manual reconciliation CSV integration (TODO-018) is the remaining high-priority item. Phase 4 (`40_link_prediction.ipynb`) is still a pure placeholder.

### F-D: Analysis Can Start Sooner Than Expected
The Wikidata triples (120,930 edges), Wikidata persons (640 with 767 properties), and Phase 31 aligned persons already exist. A preliminary analysis limited to matched persons is possible **without** completing Phase 32.

### F-E: Gender Analysis Must Use Wikidata P21
Gender inference from description text is explicitly documented as inadvisable (`speaker_mining_code.md`). The only safe gender source is Wikidata property P21.

### F-F: Page-Rank Input Already Available
`data/20_candidate_generation/wikidata/projections/triples.csv` has 120,930 rows and can be used immediately for page-rank computation via `networkx` — no additional data collection needed.

### F-G: fernsehserien.de Guest Coverage Is Structurally Limited
Finding F-013: many early episodes on fernsehserien.de have no guest data. This is a data source limitation, not a parsing bug. Analysis should treat fernsehserien.de guests as supplementary, not authoritative.

---

## Recommended Next Steps

> Full dependency-ordered execution plan: **`ToDo/TASK_EXECUTION_PLAN.md`**

**Wave 0 (deadline-driven):** TODO-018 — implement 6-column CSV integration before 2026-05-03.

**Wave 1 (foundations, parallelizable):**
- TODO-024 — visualization principles (unblocks all chart work)
- TODO-031 — fix QID labels (unblocks correct analysis output)
- TODO-017 — reduce `aligned_persons.csv` to ~40 columns
- TODO-016, TODO-026 — policy/structure documentation
- TODO-028, TODO-029, TODO-033, TODO-034 — quick-win finding docs

**Wave 2 (data completeness):** TODO-027 → TODO-019 → TODO-023

**Wave 3 (analysis + visualization):** TODO-020, TODO-025, TODO-032

**Wave 4 (synthesis):** TODO-022, TODO-021, TODO-030

**Wave 5 (deferred):** TODO-005, TODO-006, TODO-007
