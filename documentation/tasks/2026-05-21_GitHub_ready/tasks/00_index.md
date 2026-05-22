# GitHub-Ready Tasks

Scope: documentation-only changes to make the repository genuinely GitHub-ready. Code changes are deferred to the Deferred section. Completed task files are in `tasks/archive/`.

See `PROGRESS.md` for the C1 → C2 → C3 execution order and phase context.

---

## Active

| ID | Phase | File | Summary |
|---|---|---|---|
| T20 | C2 | T20_institution_extraction_docs.md | Surface institution extraction design from gitignored files into tracked documentation |
| T28 | C2 | T28_sample_output_excerpt.md | Add 2-row sample of `persons.csv` output to README or CONTRIBUTING |
| T31 | C2 | T31_reconciliation_annotator_provenance.md | Document annotator count and IAA status for `reconciliation.csv` in `data_reference.md` |
| T25 | C2 | T25_limitations_and_methodology_docs.md | Write `documentation/limitations.md`; document name-matching algorithm; add Wikidata snapshot date |
| T24 | C2 | T24_readme_improvements.md | Add "Where to start", data availability, reuse context, and Phase 50 entry-point to `README.md` and `CONTRIBUTING.md` |
| T26 | C3 | T26_citation_and_sustainability.md | Create `CITATION.cff`; write `SUSTAINABILITY.md`; add data source terms section to README |
| T29 | C3 | T29_codemeta.md | Create `codemeta.json` at the repository root for FAIR software metadata |
| T30 | C3 | T30_phase4_future_task.md | Document Phase 4 (link prediction) as a scoped future deliverable in `documentation/future_work/` |
| T21 | C3 | T21_corpus_selection_polish.md | Human decision: polish or archive `documentation/corpus_selection.md` |

---

## Deferred (code changes required)

| ID | File | Reason |
|---|---|---|
| T02 | T02_v3_archive_removal.md | V4 Wikidata only ~20% complete — keep V3 until then |
| T03 | T03_pyproject_toml.md | `pyproject.toml` — dedicated investigation later |
| T11 | T11_notebook_archive_review.md | Removing archive notebooks and test audit is code scope |
| T15 | T15_statistical_analysis_phase.md | Future pipeline phase; working code in `documentation/future_work/statistical_analysis/` |
| T27 | T27_ci_and_package_install.md | GitHub Actions CI + `pyproject.toml` editable install |

---

## Archive

Completed task files are in `tasks/archive/`.

| ID | Outcome |
|---|---|
| T17 | Done — `statistical_analysis_results.json` moved to `data/`; summary section added to `data_reference.md` |
| T18 | Done — all stray folders confirmed empty; `wikibase/` and `youtube/` documented in `workflow.md`; empty folders queued for human deletion |
| T19 | Done — `wikidata_todo_tracker.md` archived to `documentation/Wikidata/archive/`; both items confirmed superseded by `wikidata-v4-rework`; README updated |
| T22 | Done — `documentation/OpenRefine/README.md` created describing PDF context; PDF content extraction queued for human |
| T23 | Done — V3 status banners added to all 6 `documentation/Wikidata/` docs; README updated with V3/V4 version map |
| T01 | Partial — Likert chart pattern extracted to `visualization-principles.md`; cluster PDFs unviewable; folder queued for human deletion |
| T05 | Done — three paper draft folders deleted; canonical docs verified present |
| T06 | Done — `documentation/50_Analysis/` dissolved; content extracted to `documentation/analysis/`; historical files archived |
| T10c | Done — all four V3 drawio diagrams assessed; accurate as architectural vision; no changes required |
| T16 | Done — 73 TODO items migrated to three-tier task structure; `open-tasks.md` archived; all cross-references updated |
