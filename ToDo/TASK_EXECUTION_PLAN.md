# Task Execution Plan

> Generated: 2026-04-23  
> Source of truth for open tasks: `documentation/open-tasks.md`  
> This document maps task dependencies and proposes an efficient execution order for future agents.

---

## Dependency Graph

```
TODO-024 (viz principles)
  └─► TODO-020 (gender analysis)
  └─► TODO-025 (wikidata viz)
  └─► TODO-032 (page rank viz)

TODO-031 (QID labels)
  └─► TODO-025 (wikidata viz)  [item 1 requires upstream fix]
  └─► TODO-020 (gender analysis)  [clean labels in output]
  └─► TODO-023 (dataset overview)  [correct class/occupation labels]

TODO-027 (mention_category propagation)
  └─► TODO-019 (complete guest catalogue)
  └─► TODO-020 (gender analysis by guest/incidental)
  └─► TODO-021 (predictive analytics)

TODO-018 (6-column reconciliation CSV)  ← HARD DEADLINE 2026-05-03
  └─► TODO-019 (guest catalogue benefits from reconciliation data)

TODO-019 (complete guest catalogue)
  └─► TODO-020 (extended gender analysis uses full data)
  └─► TODO-021 (predictive analytics needs full catalogue)
  └─► TODO-022 (comparison needs accurate guest counts)

TODO-023 (dataset statistics)
  └─► TODO-022 (comparison draws on pipeline statistics)

TODO-020 (extended gender analysis)
  └─► TODO-022 (comparison includes gender stats)

TODO-025 (wikidata viz)
  └─► TODO-022 (comparison includes wikidata hierarchy view)
```

**Independent tasks** (no blocking prerequisites):  
TODO-016, TODO-017, TODO-026, TODO-028, TODO-029, TODO-030, TODO-033, TODO-034, TODO-005, TODO-006, TODO-007

---

## Execution Waves

### Wave 0 — Deadline-Driven (by 2026-05-03)

| TODO | Title | Rationale |
|------|-------|-----------|
| TODO-018 | Integrate 6-column reconciliation CSV | Hard external deadline; implement integration logic now, file arrives by 2026-04-29 |

> Do not block on the CSV arriving — write the Phase 32 integration logic immediately so it runs the moment the file lands.

---

### Wave 1 — Foundation (no blocking predecessors; start in parallel with Wave 0)

These tasks unblock all later visualization and analysis work. Start as many as available agent bandwidth allows.

| TODO | Title | Why first |
|------|-------|-----------|
| TODO-024 | Visualization principles document | Unblocks every chart task (TODO-020, TODO-025, TODO-032) |
| TODO-031 | Fix QID labels | Unblocks correct analysis output; needed before generating final charts |
| TODO-017 | Reduce aligned_*.csv columns (~40) | Enables cleaner reconciliation workflow; reduces Phase 32 re-run cost |
| TODO-016 | Normalization-timing policy document | Standalone doc; prevents future ad-hoc decisions |
| TODO-026 | Unify ToDo structure | Clears notebook-embedded TODOs into the tracker; housekeeping |

**Quick-win documentation** (can be done by any agent in < 1 session each):

| TODO | Title |
|------|-------|
| TODO-028 | Document title disambiguation finding → `documentation/findings.md` |
| TODO-029 | Document Wikidata birthdate bias finding → `documentation/findings.md` |
| TODO-033 | Document gender bias scope caveat → `documentation/findings.md` |
| TODO-034 | Document phase equivalence of discovery sources → `documentation/workflow.md` |

---

### Wave 2 — Data Completeness (after Wave 0+1 core items)

Prerequisite: TODO-018 logic implemented, TODO-031 fixed.

| TODO | Title | Prerequisites |
|------|-------|---------------|
| TODO-027 | Propagate mention_category through pipeline | None strictly, but do this before re-running analysis notebooks |
| TODO-019 | Complete guest catalogue (add unmatched) | TODO-018 (reconciliation data in), TODO-027 (category split ready) |
| TODO-023 | Dataset overview and pipeline statistics | TODO-031 (clean labels), Phase 32 output stable |

---

### Wave 3 — Analysis and Visualization (after Wave 2)

Prerequisite: TODO-024 done, TODO-031 fixed, TODO-019 complete.

| TODO | Title | Prerequisites |
|------|-------|---------------|
| TODO-020 | Extended gender distribution analysis | TODO-024, TODO-027, TODO-019, TODO-031, TODO-033 |
| TODO-025 | Ingest Wikidata viz + 5 improvements | TODO-024, TODO-031 |
| TODO-032 | Fix page rank viz (node graph) | TODO-024 |

---

### Wave 4 — Synthesis (after Wave 3)

Prerequisite: TODO-019, TODO-020, TODO-023, TODO-025 done.

| TODO | Title | Prerequisites |
|------|-------|---------------|
| TODO-022 | Compare to prior work | TODO-019, TODO-020, TODO-023 (full data + analysis ready) |
| TODO-030 | Compile pipeline findings for paper/talk | Wave 3 complete (full picture of pipeline available) |
| TODO-021 | Predictive analytics | TODO-019 (full catalogue), TODO-027 (guest/other split) |

---

### Wave 5 — Deferred / Low Priority

These have no hard upstream dependencies and no active downstream blockers. Tackle when higher waves are clear.

| TODO | Title |
|------|-------|
| TODO-005 | Clarify institution extraction responsibility |
| TODO-006 | Define gender-framing analysis methodology |
| TODO-007 | Define merge strategy for role/occupation/position/institution |

---

## Agent Briefing Notes

### Starting a new session on this project

1. Read `documentation/open-tasks.md` — single source of truth for all open work.
2. Check `ToDo/PHASE_ANALYSIS_INDEX.md` for pipeline status and scale numbers.
3. Before working on any visualization task, verify `documentation/visualization-principles.md` exists (TODO-024). If not, complete that first.
4. Before working on any analysis output, check whether QID labels still appear in outputs (TODO-031). If so, fix upstream before generating charts.

### Key file locations for each wave

| Wave | Key files to read |
|------|------------------|
| 0 | `documentation/31_entitiy_disambiguation/post-processing.md`, `data/32_entity_deduplication/`, `documentation/contracts.md` |
| 1 | `ToDo/visualization_references/`, `documentation/visualizations/`, `speakermining/src/process/candidate_generation/person.py`, `data/31_entity_disambiguation/aligned/aligned_persons.csv` |
| 2 | `speakermining/src/process/config.py`, `data/10_mention_detection/persons.csv`, `data/32_entity_deduplication/dedup_persons.csv`, `data/40_analysis/guest_catalogue.csv` |
| 3 | `speakermining/src/process/notebooks/51_visualization.ipynb`, `speakermining/src/process/notebooks/21_wikidata_vizualization.ipynb`, `documentation/visualization-principles.md` |
| 4 | `data/01_input/arrrrrmin/`, `data/01_input/spiegel/`, `data/01_input/omar/`, `ToDo/2026-05-03_Speaker_Mining_Paper/` |

### Parallelization opportunities

Within Wave 1, these tasks are fully independent and can be assigned to separate agents simultaneously:
- TODO-024 (viz principles) + TODO-031 (QID labels)
- TODO-017 (columns) + TODO-016 (normalization doc)
- All four quick-win documentation tasks (TODO-028, TODO-029, TODO-033, TODO-034)

Within Wave 3, TODO-025 and TODO-032 are independent of each other (both need TODO-024 done first).
