# Progress — GitHub-Ready Synthesis

## Current position

**Step:** Complete — all steps A and B finished
**Folder:** —
**Status:** Synthesis process done. Human action queue populated. See sections below.

---

## Process version history

| Version | Date | Change |
|---|---|---|
| V1 | 2026-05-22 | Initial process; 10 knowledge types (PF, DD, FT, LL, DF, PR, CR, VP, DC, PC) |

---

## Step A: documentation/ToDo/ subfolders

### `documentation/ToDo/archive/`

Status: Complete — all files processed

Files:
- [Archive] `documentation/ToDo/archive/ROADMAP_48H.md` — 48h sprint log 2026-04-18. Extracted: not-extractable episode triage categories + `mention_category` field → `documentation/mention-detection.md` Known Boundaries. Data facts (gender/occurrence stats, entity counts) deferred to data_reference.md verification pass. Design decisions (SHA1 episode_id, three dedup strategies) in code and contracts.md. Future work items all carry TODO-XXX references → already in open-tasks.md. Move to `documentation/archive/` when ToDo/ dissolves. (V1)
- [Archive] `documentation/ToDo/archive/additional_input.md` — raw scratchpad, multiple archive batches. Extracted: "Run All is the only action" + "no one-time backfills" principle → `documentation/coding-principles.md` (Notebook Execution Contract). All other items carry "Archived → TODO-XXX" markers confirming capture in open-tasks.md. Heartbeat principle already in coding-principles.md §Notebook Observability. Move to `documentation/archive/` when ToDo/ dissolves. (V1)

---

### `documentation/ToDo/2026-04-18 Rework/`

Status: Complete — empty folder, no files

---

### `documentation/ToDo/2026-05-15_Speaker_Mining_Paper/`

Status: Complete — Redundant

Files:
- [Redundant] `documentation/ToDo/2026-05-15_Speaker_Mining_Paper/` (entire folder) — pre-submission paper draft and peer review iterations, superseded by canonical 2026-05-21 paper (T05). Build artifacts (.aux, .bbl, .blg, .fls, .log, .out, .synctex.gz, .fdb_latexmk), class files (.cls, .bst), and PDF images carry zero knowledge. review/ subfolder is a revision-round manuscript, covered by peer_review_paper/ folder later. (V1)

---

### `documentation/ToDo/2026-05-17_Speaker_Mining_Paper/`

Status: Complete — Redundant

Files:
- [Redundant] `documentation/ToDo/2026-05-17_Speaker_Mining_Paper/` (entire folder) — near-final paper draft (comp.txt is a copy of main.tex). All pipeline knowledge (first-iteration lessons, data facts, design decisions) is in the canonical 2026-05-21 paper or already in documentation. Build artifacts and class files: zero knowledge. (V1)

---

### `documentation/ToDo/DOC/`

Status: Complete — empty folder, no files

---

### `documentation/ToDo/peer_review_paper/`

Status: Complete — Redundant

Files:
- [Redundant] `documentation/ToDo/peer_review_paper/` (entire folder) — manuscript version (main.tex, bibliography.bib, images/ with 6 PDFs, class files, build artifacts). No reviewer comments or response-to-reviewers document present; folder name is misleading. All pipeline knowledge superseded by canonical 2026-05-21 paper (T05). Structurally identical to 2026-05-15 and 2026-05-17 paper folders. (V1)

---

### `documentation/ToDo/open_additional_input.md`

Status: Complete — Redundant

Files:
- [Redundant] `documentation/ToDo/open_additional_input.md` — active notepad template with no current human input. Contains only its own usage instructions (verbatim archival rule). No pipeline knowledge to extract; the ToDo folder is dissolving. (V1)

---

### `documentation/ToDo/documentation_synthesis/`

Status: Complete — Archive entire folder (do not process file-by-file)

Decision: All contents — catalogue, cluster files, PLAN, approach, prompts — are
permanent historical artifacts. Move to `documentation/archive/documentation_synthesis/`
when the synthesis is otherwise complete. The catalogue.jsonl (937 findings, 571 files)
and cluster data are the evidence base consumed by this process; they must be preserved
for future reference. (V1)

---

## Step B: Remaining folders

### B1. `documentation/context/`

Status: Complete — Archive entire folder to `documentation/archive/context/`

Files:
- [Redundant] `documentation/context/README.md` — folder navigation aid; folder is dissolving. (V1)
- [Archive] `documentation/context/alias.md` — raw scratchpad observation about Q759853 (film format) alias explosion; no actionable finding. (V1)
- [Archive] `documentation/context/de_eventsourcing_notes.md` — German-language architectural consultation notes; origin of event-sourcing principles now in `coding-principles.md`. Historical `PC` artifact. (V1)
- [Archive] `documentation/context/jsonl_potential.md` — JSONL migration assessment (2026-04-01); already summarized in `findings.md` F-011. `findings.md` reference updated to `documentation/archive/context/jsonl_potential.md`. (V1)
- [Archive] `documentation/context/jsonl_potential_for_eventsourcing.md` — Architecture design document; all key decisions captured in `coding-principles.md` Event-Sourcing Principles. (V1)
- [Archive] `documentation/context/mention-detection-guest-diagnostics-2026-03-27.md` — Parser diagnostic report; already captured in `findings.md` F-007. `findings.md` reference updated to `documentation/archive/context/mention-detection-guest-diagnostics-2026-03-27.md`. (V1)
- [Archive] `documentation/context/node_integrity/` (entire subfolder, 47 files) — runtime operational log snapshots from 2026-04-02 through 2026-04-26; no extractable knowledge beyond what is in findings.md. (V1)
- [Archive] `documentation/context/findings-assets/` (entire subfolder) — supporting evidence files for findings.md entries; move alongside folder. (V1)

---

### B2. `documentation/Wikidata/archive/`

Status: Verified — Keep (permanent archive); one gap found and tracked

Files:
- [Keep] `documentation/Wikidata/archive/` (entire folder, 7 sub-sessions, 75+ files) — complete Wikidata transition history from v2 through v3 (2026-03-31) and the v4 investigation (2026-04-26). The archive stays per 01_vision.md. (V1)

**Verification pass (2026-05-22):** The original B2 "already tracked" claim was verified:
- TODO-034, 038, 041–044 citations: verified by reading `2026-04-26_investigation/05_related_tasks.md`, which explicitly maps all these TODOs to v4 redesign requirements. ✓
- "Architecture decisions in coding-principles.md and Wikidata/ docs": **PARTIAL** — v3 architecture is in `expansion_and_discovery_rules.md` and `Wikidata_specification.md`. The v4 design principles in `13_architecture_design.md` (event store sole source of truth, no post-hoc repair, EventHandlers vs ExternalEventReaders, queue persistence, config-driven rules, backward compatibility) are **not** mirrored in any living doc. Added as **TODO-073**. (V1)

---

### B3. `documentation/31_entity_disambiguation/` (entire folder, dissolve)

Status: Complete — Archive entire folder to `documentation/archive/31_entity_disambiguation/`

Files:
- [Archive] `documentation/31_entity_disambiguation/README.md` — stale folder-level description referencing files now in archive/; superseded by workflow.md. (V1)
- [Archive] `documentation/31_entity_disambiguation/post-processing.md` — workflow notes from active OpenRefine import phase; deadlines (2026-04-29, 2026-05-03) now past; content is stale operational notes. (V1)
- [Archive] `documentation/31_entity_disambiguation/archive/` (entire subfolder — 3 sessions, 18 files) — critical issue investigation (2026-04-05), redesign session (2026-04-11), restart session (2026-04-12). All findings and tasks from these sessions are already in `open-tasks.md` and `findings.md`. (V1)
- [Archive] `documentation/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md` — referenced by `findings.md` F-012; `findings.md` reference corrected to current path. When folder is dissolved, update findings.md reference to `documentation/archive/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md`. (V1)
- [Archive] `documentation/31_entity_disambiguation/archive/todo_tracker.md` — internal task tracker; all items already in `open-tasks.md`. (V1)

**Verification pass (2026-05-22):** The original B3 "already tracked" claim was verified:
- `todo_tracker.md`: self-documenting — explicitly states items are tracked as TODO-017. ✓
- `2026-04-05_critical_issue/issue.md` fernsehserien_de_id bug: verified in `open-tasks.md` (area: contracts; includes the per-person vs per-episode URL bug and the Phase 5 workaround note). ✓
- 18-file archive sessions: designs in `99_REDESIGN_TARGET_SPECIFICATION.md` (2026-04-11) are superseded by the 2026-04-12 restart implementation, which is in `contracts.md` Phase 31 section. ✓

Note: When this folder is dissolved, update `findings.md` F-012 reference from `documentation/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md` → `documentation/archive/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md`.

---

### B4. `documentation/fernsehserien_de/`

Status: Complete — Keep (target artifact subfolder, all content appropriate)

Files:
- [Keep] `documentation/fernsehserien_de/fernsehserien_de_specification.md` — v1 decision-locked Stage-2 spec (previously named `fermsehserien_de_specification.md` — typo fixed). Comprehensive event schema, projection contract, pacing policy. (V1)
- [Keep] `documentation/fernsehserien_de/00_immutable_input.md` — Source retrieval requirements, URL examples, episodenguide traversal strategy. (V1)
- [Keep] `documentation/fernsehserien_de/episode_extraction_logic.md` — Detailed extraction spec: HTML selectors, event schema per information group, two-stage discovered/normalized persistence, handler progress tracking. (V1)
- [Keep] `documentation/fernsehserien_de/fernsehserien_de_todo_tracker.md` — Historical: all FST-001 through FST-015 items DONE. Resolution notes document implementation decisions now captured in `coding-principles.md` (checkpoint retention, graceful interrupt, buffered append writes). (V1)
- [Keep] `documentation/fernsehserien_de/representative_sample_qa_2026-04-08.md` — QA evidence for Stage-2 completion: cache-only replay verified, row counts for all 6 projection tables, sample records for all 5 information groups. (V1)

---

### B5. `documentation/50_Analysis/`

Status: Complete — Dissolved into `documentation/analysis/` (see T06 for remaining archive/delete work)

Extractions performed:
- [Extracted] `documentation/50_Analysis/2026-04-29_Initialization/00_immutable_input.md` — Analysis phase description (building blocks, properties, analysis angles, symmetry principles). Extracted into `documentation/analysis/README.md`. (V1)
- [Extracted] `documentation/50_Analysis/2026-05-04_finalization/visualization-design.md` — Visualization module boundary design + layout rules. Extracted into `documentation/analysis/visualization-design.md` (enhanced with all layout/color/label/export rules from finalization open-tasks). (V1)
- [Extracted] `documentation/50_Analysis/2026-05-11_review/findings.md` — 7 code correctness issues. Added to `documentation/findings.md` as F-021. (V1)

Files ready for archive/delete (action for human via T06):
- `documentation/50_Analysis/2026-04-29_Initialization/` — Historical (superseded by later work). Archive to `documentation/archive/50_Analysis/`.
- `documentation/50_Analysis/2026-04-30_restructuring/` — Historical (restructuring was executed). Archive to `documentation/archive/50_Analysis/`.
- `documentation/50_Analysis/2026-05-04_finalization/` — Active content extracted above; residual files (open-tasks.md, intermediate review, implementation plan) archive to `documentation/archive/50_Analysis/`. Reference HTML files stay accessible.
- `documentation/50_Analysis/2026-05-11_review/` — Code review artifacts; findings extracted to findings.md. Archive to `documentation/archive/50_Analysis/`.
- Entire `documentation/50_Analysis/` folder can be deleted after archiving.

**Process error (corrected 2026-05-22):** The B5 pass incorrectly archived three open-tasks.md files (`2026-04-29_Initialization/open-tasks.md`, `2026-04-30_restructuring/open-tasks.md`, `2026-05-04_finalization/open-tasks.md`) without migrating their open/partial items. This violated task-principles.md §1. Migration completed: TODO-057 through TODO-072 added to `documentation/open-tasks.md`. Items already covered: TASK-F11 → TODO-041, TASK-F15 → TODO-032. TASK-B series superseded by TASK-F series. (V1)

Note: T06 remains active to manage the physical file moves and verify the new analysis/ structure.

---

### B6. `speakermining/src/` (read-only pass)

Status: Complete — no new task files needed; all actionable items already tracked

Read-only pass across ~130 Python modules in `speakermining/src/process/`. No code edits.
All design decisions and TODOs found are already captured in existing documentation or
open-tasks.md/task files. Key findings below. (V1)

**Cross-cutting infrastructure:**
- [Keep] `process/io_guardrails.py` — Atomic write via `.tmp`+rename with 5-retry exponential backoff (10ms start). On final failure, writes `.recovery` sidecar restored on next run. Safe-delete guard for paths containing `archive`/`backup`. Covers CSV, text, Parquet. All principles already in `coding-principles.md`.
- [Keep] `process/notebook_event_log.py` — Centralized JSONL event log at `data/logs/notebooks/{notebook_id}.events.jsonl`. Per-session logger with thread-safe appending, 250-event deque for heartbeat snapshots, auto-repair of malformed JSONL on startup. Architecture in use; no documentation gap.

**Mention detection (Phase 10):**
- [Keep] `process/mention_detection/config.py` — Phase 10 data contracts. `PERSON_MENTION_COLUMNS` includes `mention_category` field. Already in `documentation/mention-detection.md`.
- [Keep] `process/mention_detection/guest.py` — Two-mode guest parsing: primary (host+mit anchors), conservative fallback (Studiogast/Studiogästen cues; only fires if parenthetical pairs present). Already in `documentation/mention-detection.md` findings.

**Candidate generation (Phase 20):**
- [Keep] `process/candidate_generation/wikidata/entity_access.py` — F25 interface contract: three access tiers (`get_cached_entity_doc` / `ensure_basic_fetch` / `all_outlink_fetch`). `begin_request_context` required before any batch that may trigger network calls; silent 100% failure if missing. Already in memory and `documentation/Wikidata/Wikidata.md`.

**Entity disambiguation (Phase 31):**
- [Keep] `process/entity_disambiguation/contracts.py` — FIXME at line 20: reads Wikidata from `projections/archive/` path instead of live projections, pending V4 resolution. Tracked in T02 (`T02_v3_archive_removal.md`).

**Entity deduplication (Phase 32):**
- [Keep] `process/entity_deduplication/contracts.py` — 4 strategies (manual_reconciliation > wikidata_qid_match > normalized_name_match > singleton), 4 confidence levels (authoritative > high > medium > low), SHA-1 canonical_entity_id. Already in `documentation/contracts.md`.

**Analysis (Phase 50):**
- [Keep] `process/analysis/viz_base.py` — `save_fig` checks full bundle (PNG + PDF + optional HTML) for cache skip. NOTE: F-21d (2026-05-11 review: "skips on PNG only") appears already fixed in current code. Cannot confirm notebook-level fix without reading the live .ipynb.
- [Keep] `process/analysis/color_registry.py` — `ColorRegistry` immutable: raises `KeyError` on unregistered QID (no silent fallback). `UNKNOWN_COLOR = #999999`, `OTHER_COLOR = #CCCCCC`. Tier 1–4 colors defined here. Consistent with `documentation/analysis/visualization-design.md`.
- [Keep] `process/analysis/statistical_tests.py` — PAPER NOTE at line 665 (gender bounds [37.7%, 62.3%] incorrect). Canonical paper (2026-05-21) already corrected to `[37.7%, 77.2%]` (confirmed at line 357 of canonical main.tex). Code comment documents the mathematical error to prevent regression. No action needed.

**Notebooks archive:**
- [Keep] `process/notebooks/archive/gen_50_analysis.py`, `gen_51_visualization.py` — Programmatic notebook generators (older approach). Notebooks now maintained directly. Covered by T11 (`T11_notebook_archive_review.md`).

**PROGRESS update for B6: current position advances to B7.**

**Verification pass (2026-05-22):** The original B6 "all actionable items already tracked" claim was verified by a full grep for TODO/FIXME/HACK/NOTE comments across all ~130 Python modules. Result: 10 matches total.
- `statistical_tests.py` PAPER NOTE and NOTE: already covered in B6 log above. ✓
- `entity_deduplication/person_deduplication.py:165` — references TODO-016 (normalization-timing policy). TODO-016 is **closed** (`documentation/normalization-policy.md` exists, per `archive/TASK_EXECUTION_PLAN.md`). ✓
- `entity_disambiguation/contracts.py:20` FIXME — covered by T02. ✓
- `notebooks/archive/gen_50_analysis.py` — references TODO-040, TODO-027 in comments; covered by T11. ✓
- `notebooks/archive/gen_51_visualization.py` — TASK-A03 reference; covered by T11. ✓
Conclusion: B6 claim verified correct. No new tasks needed. (V1)

---

### B7. `documentation/phases/` (dissolve)

Status: Complete — Archive entire folder to `documentation/archive/phases/`

Files:
- [Extracted] `documentation/phases/02_phase1_mention_detection.md` — Exhaustive Phase 1 code reference (agent synthesis artifact, 2026-04-23). Unique content: confidence tier table with specific float values (0.95, 0.82, 0.70, 0.68, 0.62, 0.55, 0.45, 0.50) per parsing_rule → extracted into `documentation/mention-detection.md` §Parsing Rule And Confidence Expectations. Remainder (schema tables, method-by-method analysis) superseded by actual code + existing docs. Archive. (V1)
- [Archive] `documentation/phases/PHASE_ANALYSIS_PRE_P1.md` — Pre-Phase (text extraction) + Phase 1 overview. No unique content not already in mention-detection.md and contracts.md. Stale status info. (V1)
- [Archive] `documentation/phases/PHASE_ANALYSIS_P2.md` — Phase 2 (Wikidata + fernsehserien.de) notebook steps and config params. All architecture in Wikidata.md and fernsehserien_de/. Stale status. (V1)
- [Archive] `documentation/phases/PHASE_ANALYSIS_P31_P32.md` — Phase 31/32 notebook steps and run statistics. All architecture in contracts.md. Scale data superseded by data_reference.md. Stale status. (V1)
- [Archive] `documentation/phases/PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md` — Phase 4 (placeholder spec) + analysis/viz review. Phase 4 remains unimplemented; placeholder fact already in workflow.md. Analysis findings superseded by documentation/analysis/. Stale. (V1)
- [Archive] `documentation/phases/PHASE_ANALYSIS_INDEX.md` — Master index of phase analysis files. Pipeline status table (2026-04-23), scale counts (superseded by data_reference.md), open issues (in open-tasks.md), cross-cutting findings (all captured in findings.md or target docs). Archive with folder. (V1)

---

### B8. `documentation/` root files (final pass)

Status: Complete

Files:
- [Keep] `documentation/README.md` — Updated: removed dead `context/README.md` link (folder being archived); added entries for `normalization-policy.md`, `analysis/README.md`, `analysis/visualization-design.md`, `Wikidata/README.md`, `fernsehserien_de/fernsehserien_de_specification.md`, `data_reference.md`. (V1)
- [Keep] `documentation/repository-overview.md` — Wikidata module list is stale (refers to v3 archive module names); acceptable — code scope, already covered by T02/T11. (V1)
- [Keep] `documentation/workflow.md` — No issues found; content correct. (V1)
- [Keep] `documentation/contracts.md` — No issues found. (V1)
- [Keep] `documentation/notebook-observability.md` — No issues found. (V1)
- [Keep] `documentation/mention-detection.md` — Updated: added specific confidence float values per parsing_rule (extracted from 02_phase1_mention_detection.md). (V1)
- [Keep] `documentation/coding-principles.md` — No issues found. (V1)
- [Keep] `documentation/normalization-policy.md` — No issues found. (V1)
- [Keep] `documentation/open-tasks.md` — Updated: pre-corrected 3 evidence paths to archive/ locations (31_entity_disambiguation/post-processing.md, 31_entity_disambiguation/archive/todo_tracker.md, context/node_integrity/*.md). (V1)
- [Keep] `documentation/findings.md` — Updated: pre-corrected 2 evidence paths to archive/ locations (50_Analysis/2026-05-11_review/findings.md, 50_Analysis/2026-05-11_review/code_update_plan.md). Previously updated F-007, F-011, F-012 paths (B1/B3 pass). F-021 added (B5 pass). (V1)
- [Keep] `documentation/background.md` — Historical context; appropriate; no changes needed. (V1)
- [Keep] `documentation/task-principles.md` — Stable reference. (V1)
- [Keep] `documentation/data_reference.md` — Verified pipeline counts; no changes needed. (V1)
- [Draft] `documentation/corpus_selection.md` — Unpolished draft (untracked file); not yet ready to be a canonical reference; excluded from README authoritative sources list. Human should review and either polish or archive. (V1)
- [Keep] `documentation/statistical_analysis_results.json` — Auto-generated output from statistical_tests.py; not documentation. No changes needed. (V1)

Cross-reference fixes applied:
- `findings.md` F-021: pre-corrected evidence paths to `documentation/archive/50_Analysis/...`
- `open-tasks.md` TODO-018: pre-corrected path to `documentation/archive/31_entity_disambiguation/post-processing.md`
- `open-tasks.md` TODO-017: pre-corrected path to `documentation/archive/31_entity_disambiguation/archive/todo_tracker.md`
- `open-tasks.md` TODO-035: pre-corrected paths to `documentation/archive/context/node_integrity/...`

Remaining cross-reference fix (needs human action after folder moves):
- `findings.md` F-012: when `31_entity_disambiguation/` is archived, update path from `documentation/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md` → `documentation/archive/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md`

---

## Active task completion (2026-05-22)

### T05 — Paper folder cleanup
Status: Complete. All three draft folders already deleted by human (see Completed actions below). Acceptance criteria verified:
- `documentation/data_reference.md` — exists ✓
- `documentation/corpus_selection.md` — exists ✓
- `speakermining/src/process/analysis/statistical_tests.py` — exists ✓

### T10c — V3 drawio diagrams assessment
Status: Complete. All four PNGs reviewed:

**Approach diagram** (embedded in README.md line 19):
- P1 (mention detection from ZDF PDFs) — accurate
- P2 (candidate generation / Wikidata) — accurate
- P3 (entity disambiguation + deduplication) — accurate
- P4 (link prediction / inference) — shown but NOT YET IMPLEMENTED; this is future work. The "V3-Approach" label signals architectural vision, not current state. Acceptable; no update required.

**P1, P2, P3 detail diagrams**: not embedded anywhere in README or workflow.md. Accurate descriptions of V3 design. No changes needed.

Conclusion: diagrams are accurate as V3-era architectural references. No drawio.xml edits required.

### T01 — visualization_references extraction
Status: Partial (cluster PDFs in 2025-scicom-ki-survey unviewable — PDF-only files).

Extraction performed:
- [Extracted] `Scientific knowledge fit for society Evaluation/Likert5/*.png` — diverging stacked bar chart pattern (5-level Likert scale, symmetric x-axis, count annotations, dashed center line). Added as new section "Diverging Stacked Bar Charts — Likert / Quality-Tier Style" to `documentation/visualizations/visualization-principles.md`. (V1)
- [Extracted] `Lanz-und-Precht/` — NLP analysis of the Lanz & Precht podcast using Whisper transcription. Demonstrates: theme_detection.ipynb (keyword-weighted multi-topic taxonomy, evidence-weighted scoring across title/description/NLP/transcript), analysis_advanced.ipynb (temporal analysis, word frequency trends, named entity tracking, speaking volume, episode type classification). Five future tasks extracted to `documentation/open-tasks.md`: TODO-052 (episode topic classification), TODO-053 (transcript acquisition pipeline), TODO-054 (guest speaking time via diarization), TODO-055 (named entity co-mention analysis), TODO-056 (topic × demographic correlation). (V1)
- [Partial] `2025-scicom-ki-survey/` — cluster PDFs (Cluster_0-3, Merged_Stakeholder_Clusters, Stakeholder_Clusters_Side_by_Side) describe stakeholder cluster visualization in 2D space; could not view PDF contents. Low priority: stakeholder clustering is not a current Speaker Mining visualization need. (V1)

Human action: `documentation/ToDo/visualization_references/` is gitignored — can be deleted entirely.

### T06 — 50_Analysis consolidation
Status: Complete. All content extracted to `documentation/analysis/` (README.md + visualization-design.md). All historical files archived to `documentation/archive/50_Analysis/`. Phase 50 open tasks are in `documentation/open-tasks.md`. Acceptance criteria met: visitor finds analysis design in one file; historical context preserved in archive; no dated subdirectory navigation required.

---

## Completed actions

### Files deleted (human)
- `documentation/ToDo/2026-05-15_Speaker_Mining_Paper/` — Done
- `documentation/ToDo/2026-05-17_Speaker_Mining_Paper/` — Done
- `documentation/ToDo/peer_review_paper/` — Done
- `documentation/ToDo/open_additional_input.md` — Old template deleted; recreated with updated template pointing to the current task destinations (`open-tasks.md` for pipeline tasks, `2026-05-21_GitHub_ready/tasks/` for GitHub-readiness tasks). Archive target remains `documentation/ToDo/archive/additional_input.md`.

### Empty folders deleted (human)
- `documentation/ToDo/2026-04-18 Rework/` — Done
- `documentation/ToDo/DOC/` — Done

### Folders archived (agent)
- `documentation/context/` → `documentation/archive/context/` — Done
- `documentation/31_entity_disambiguation/` → `documentation/archive/31_entity_disambiguation/` — Done
- `documentation/phases/` → `documentation/archive/phases/` — Done
- `documentation/50_Analysis/` → `documentation/archive/50_Analysis/` — Done

### Cross-reference fixes applied (agent)
- `findings.md` F-012: path updated to `documentation/archive/31_entity_disambiguation/archive/311_upstream_handover_2026-04-11.md` — Done
- `findings.md` F-021: evidence paths updated to `documentation/archive/50_Analysis/2026-05-11_review/` — Done
- `open-tasks.md` TODO-018: path updated to `documentation/archive/31_entity_disambiguation/post-processing.md` — Done
- `open-tasks.md` TODO-017: path updated to `documentation/archive/31_entity_disambiguation/archive/todo_tracker.md` — Done
- `open-tasks.md` TODO-035: paths updated to `documentation/archive/context/node_integrity/` — Done

---

## Human action queue (remaining)

### Folders ready for delete (gitignored — no git impact)
- `documentation/ToDo/visualization_references/` — T01 complete; Likert pattern extracted to visualization-principles.md; remainder is unviewable PDFs and generic NLP notebooks.

### ToDo folder dissolution (after all above is done)
When `documentation/ToDo/visualization_references/` is deleted, the only remaining contents of `documentation/ToDo/` are:
- `archive/` — two files to keep (see Step A); move to `documentation/archive/ToDo-archive/` when dissolving
  - **Clarification:** Done
- `documentation_synthesis/` — archive to `documentation/archive/documentation_synthesis/` (already decided)
  - **Clarification:** Done
- `2026-05-21_GitHub_ready/` — this coordination folder itself; can be dissolved after human confirms everything is done
  - **Clarification:** Not done, will take weeks to finish - we are not talking about a small task here.

Final dissolution sequence:
1. Delete `visualization_references/`
2. Move `documentation_synthesis/` → `documentation/archive/documentation_synthesis/`
3. Move `archive/` contents → `documentation/archive/ToDo-archive/` (or merge with `documentation/archive/`)
  - **Clarification:** Done
4. Delete `documentation/ToDo/` itself (will be empty)
