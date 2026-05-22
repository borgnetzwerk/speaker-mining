# Progress — GitHub-Ready Repository

## Current position

**Phase:** C2 — Write
**Next action:** T20 — surface `INSTITUTION_EXTRACTION_DEFERRED.md` content into tracked documentation

Steps A and B (documentation synthesis) are complete. The full synthesis record is in `synthesis/synthesis_log.md`.

---

## Phase C — Remaining work

Three sequential phases. Complete C1 before starting C2. C3 can run alongside C2 but is lower priority.

### C1 — Repair

**Goal:** Eliminate structural confusions that would mislead a newcomer before any new documentation is written.

| Task | Summary | Who | Status |
|---|---|---|---|
| C7 | Fixed CONTRIBUTING.md stale link (`open-tasks.md` → `tasks/00_index.md`) | Agent | Done (2026-05-22) |
| T19 | Archived `wikidata_todo_tracker.md` to `documentation/Wikidata/archive/`; both items confirmed superseded by `wikidata-v4-rework`; README updated | Agent | Done (2026-05-22) |
| T17 | Moved `statistical_analysis_results.json` → `data/`; added section to `data_reference.md` | Agent | Done (2026-05-22) |
| T23 | Added V3 banners to all 6 `documentation/Wikidata/` docs; README updated with V3/V4 version section | Agent | Done (2026-05-22) |
| T22 | Created `documentation/OpenRefine/README.md` describing PDF content and pipeline context; PDF content extraction queued for human | Agent | Done (2026-05-22) |
| T18 | All stray folders confirmed empty (no tracked git content); `wikibase/` and `youtube/` documented in `workflow.md`; empty folders queued for human deletion below | Agent | Done (2026-05-22) |

### C2 — Write

**Goal:** A newcomer cloning the repository can understand what the pipeline does, what its limitations are, and where to start contributing.

| Task | Summary | Who | Status |
|---|---|---|---|
| T20 | Surface `INSTITUTION_EXTRACTION_DEFERRED.md` design into tracked documentation | Agent | Open |
| T28 | Add 2-row sample of `persons.csv` output to README or CONTRIBUTING | Agent | Open |
| T31 | Document reconciliation annotator provenance in `data_reference.md` | Agent | Open |
| T25 | Write `documentation/limitations.md`; document name-matching algorithm; add Wikidata snapshot date | Agent | Open |
| T24 | README improvements: "Where to start", data availability, reuse context, Phase 50 entry-point | Agent | Open |

### C3 — Repository identity

**Goal:** The repository is citable, discoverable by research infrastructure, and has a documented roadmap.

| Task | Summary | Who | Status |
|---|---|---|---|
| T26 | Create `CITATION.cff`; write `SUSTAINABILITY.md`; add data source terms to README | Agent (Zenodo DOI = human) | Open |
| T29 | Create `codemeta.json` at repository root | Agent | Open |
| T30 | Write `documentation/future_work/phase4_link_prediction.md` | Agent | Open |
| T21 | `documentation/corpus_selection.md` — polish and promote, or archive | Human decision | Open |

### Deferred (code-scope, tracked separately)

| Task | Summary |
|---|---|
| T27 | GitHub Actions CI + `pyproject.toml` editable install — see `tasks/T27_ci_and_package_install.md` |

---

## Human action queue

- **T21**: Make `corpus_selection.md` decision — polish or archive
- **T26**: Register Zenodo DOI after `CITATION.cff` is created; add DOI back to `CITATION.cff` and `README.md`
- **T22**: Review `documentation/OpenRefine/` PDF and decide whether to extract its content to plaintext or delete it
- **Delete (T18)**: `speakermining/src/process/candidate_generation/wikibase/` — empty placeholder; no implementation
- **Delete (T18)**: `speakermining/src/process/candidate_generation/youtube/` — empty placeholder; no implementation
- **Delete (T18)**: `speakermining/src/process/notebooks/data/32_entity_deduplication/` — empty data folder inside source tree
- **Delete (T18)**: `speakermining/src/process/notebooks/data/40_analysis/` — empty data folder inside source tree
- **Delete (T18)**: `speakermining/src/data/32_entity_deduplication/` — empty data folder inside `src/`
- **Delete**: `documentation/ToDo/visualization_references/` — T01 complete; gitignored; safe to delete
