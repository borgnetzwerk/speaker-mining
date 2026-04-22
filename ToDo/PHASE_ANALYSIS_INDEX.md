# Phase Analysis Index

> Generated: 2026-04-18  
> This is the master index for the phase-by-phase analysis pass over all .md, .py, and .ipynb files.

---

## Analysis Documents

| Document | Phases Covered | Status |
|----------|---------------|--------|
| [PHASE_ANALYSIS_PRE_P1.md](PHASE_ANALYSIS_PRE_P1.md) | Pre-Phase (text extraction) + Phase 1 (mention detection) | Complete |
| [PHASE_ANALYSIS_P2.md](PHASE_ANALYSIS_P2.md) | Phase 2 (Wikidata + fernsehserien.de candidate generation) | Complete |
| [PHASE_ANALYSIS_P31_P32.md](PHASE_ANALYSIS_P31_P32.md) | Phase 31 (disambiguation) + Phase 32 (deduplication) | Complete |
| [PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md](PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md) | Phase 4 (link prediction) + Analysis + Visualization | Complete |
| [ROADMAP_48H.md](ROADMAP_48H.md) | 48-hour staged implementation roadmap | Complete |

---

## Pipeline Status Summary

| Phase | Notebook | Status | Notes |
|-------|----------|--------|-------|
| Pre-Phase | `10_text_extraction.ipynb` | ✓ Complete / Optional | Text dumps already exist |
| Phase 1 | `11_mention_detection.ipynb` | ✓ Active — Stage 1 complete | All P1 bugs resolved or triaged (2026-04-22); re-run notebook to pick up new fields |
| Phase 1 inspect | `19_analysis.ipynb` | ✓ Optional | Confidence checks only |
| Phase 2a | `20_candidate_generation_wikibase.ipynb` | ✓ Active (legacy prereq) | Must run before 2b |
| Phase 2b | `21_candidate_generation_wikidata.ipynb` | ✓ Complete | v3 event-sourced engine |
| Phase 2c | `22_candidate_generation_fernsehserien_de.ipynb` | ✓ Complete | 1 known bug (row 3 missing) |
| Phase 2d | `23_candidate_generation_other.ipynb` | ✗ Placeholder | Not implemented |
| Phase 31 | `31_entity_disambiguation.ipynb` | ✓ Step 311 runs | Step 312 needs tooling |
| Phase 32 | `32_entity_deduplication.ipynb` | ✗ Placeholder | Not implemented |
| Phase 4 | `40_link_prediction.ipynb` | ✗ Placeholder | Not implemented |
| Analysis | — | ✗ Not started | Requires Phase 32 |
| Visualization | — | ✗ Not started | Requires Analysis |

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

---

## All Open Issues (Consolidated)

### Critical / Phase-Blocking

| ID | Phase | Description | Fix Location |
|----|-------|-------------|--------------|
| ~~TODO-009~~ | ~~P1~~ | ~~EPISODE 363 `infos` field empty~~ — **RESOLVED 2026-04-22** | |
| ~~TODO-008~~ | ~~P1~~ | ~~13 episodes with no guest extractions~~ — **TRIAGED 2026-04-22** (all not_extractable) | |
| ~~TODO-001~~ | ~~P1~~ | ~~Cross-archive episode duplicates~~ — **ALREADY RESOLVED** (stable SHA1 ID + exact dedup) | |
| (bug) | P2c | Row 3 of fernsehserien.de guest description missing | `fernsehserien_de/projection.py` |
| (empty) | P31 | `wikidata_roles` is 0 rows — role alignment impossible | Wikidata expansion config |

### Medium Priority

| ID | Phase | Description | Fix Location |
|----|-------|-------------|--------------|
| ~~TODO-002~~ | ~~P1→P31~~ | ~~Umlaut/ß normalization~~ — **DONE 2026-04-22** (`normalize_name_for_matching` in `person.py`) | |
| ~~TODO-003~~ | ~~P1~~ | ~~Abbreviation normalization~~ — **DONE 2026-04-22** (`_expand_abbreviations` in `guest.py`) | |
| ~~TODO-004~~ | ~~P1→P31~~ | ~~No `mention_category` field~~ — **DONE 2026-04-22** (`guest`/`incidental` in `config.py` + `guest.py`) | |
| ~~TODO-010~~ | ~~P1~~ | ~~Split family names~~ — **WONT-FIX 2026-04-22** (2 occurrences, ROI too low) | |
| ~~TODO-015~~ | ~~P1~~ | ~~Misspelling cluster identification~~ — **DONE 2026-04-22** (`normalize_name_for_matching` is cluster key) | |
| (question) | P31 | OpenRefine match storage — add `open_refine_name` column to handoff | `entity_disambiguation/contracts.py` |

### Low Priority / Future Work

| ID | Phase | Description |
|----|-------|-------------|
| TODO-005 | P1 | Institution extraction responsibility clarification |
| TODO-006 | Analysis | Gender-framing analysis methodology |
| TODO-007 | Analysis | Role/occupation merge strategy |
| (future) | Governance | Forbidden Features / Data Privacy Catalogue |

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
| `32_entity_deduplication.ipynb` | Placeholder |
| `40_link_prediction.ipynb` | Placeholder |

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

### F-C: Phase 32 and Phase 4 Are Greenfield
Neither notebook has any implementation. They are pure placeholders. Building them requires designing the contracts first, then implementing.

### F-D: Analysis Can Start Sooner Than Expected
The Wikidata triples (120,930 edges), Wikidata persons (640 with 767 properties), and Phase 31 aligned persons already exist. A preliminary analysis limited to matched persons is possible **without** completing Phase 32.

### F-E: Gender Analysis Must Use Wikidata P21
Gender inference from description text is explicitly documented as inadvisable (`speaker_mining_code.md`). The only safe gender source is Wikidata property P21.

### F-F: Page-Rank Input Already Available
`data/20_candidate_generation/wikidata/projections/triples.csv` has 120,930 rows and can be used immediately for page-rank computation via `networkx` — no additional data collection needed.

### F-G: fernsehserien.de Guest Coverage Is Structurally Limited
Finding F-013: many early episodes on fernsehserien.de have no guest data. This is a data source limitation, not a parsing bug. Analysis should treat fernsehserien.de guests as supplementary, not authoritative.

---

## Recommended Next Steps (Priority Order)

1. ~~**Stage 1 (Phase 1 bugs)**~~ — **ALL DONE 2026-04-22** (TODO-001/002/003/004/008/009/010/015)
2. **Fix fernsehserien.de row 3 bug** — `fernsehserien_de/projection.py` (Stage 2a)
3. **Re-run `11_mention_detection.ipynb`** to generate persons.csv with new fields (`mention_category`, expanded abbreviations)
4. **Add `open_refine_name` columns** to Phase 31 handoff tables
5. **Implement Phase 32** deduplication notebook (Step 321)
6. **Build Phase 4 / analysis** using already-available Wikidata property data
7. **Create visualization notebooks**
