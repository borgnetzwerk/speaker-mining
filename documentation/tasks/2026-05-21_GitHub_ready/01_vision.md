# Vision: GitHub-Ready Repository — Target State

## What a new contributor should be able to do

From `README.md` alone:
- Understand what the project does (German broadcast metadata → speaker demographics)
- Know what data it produces and at what scale
- Follow installation and run instructions

From `documentation/`:
- Follow the pipeline from text extraction through analysis, understanding each phase's role
- Find the data contracts between phases (what each phase expects and produces)
- Understand why design decisions were made
- Find the open tasks (public backlog) and pick one up without prior context

---

## Target documentation artifacts

These must exist, be accurate, and be cross-referenced in the final repository.

**Principle:** organize by data source and component, not by phase number. Phase numbers
are unstable — they have already shifted (Phase 4 → Phase 5) and will shift again if
phases merge. Source names do not change.

### Root-level (pipeline narrative, stable)

| Artifact | Path | Purpose |
|---|---|---|
| Entry point | `README.md` | What, why, how to install, how to run, pointer to docs |
| Pipeline overview | `documentation/repository-overview.md` | End-to-end pipeline description (current phases referenced by name, not number) |
| Workflow narrative | `documentation/workflow.md` | Step-by-step walkthrough of a full pipeline run |
| Data contracts | `documentation/contracts.md` | Data schemas passed between pipeline components |
| Coding principles | `documentation/coding-principles.md` | Standards governing new code |
| Task governance | `documentation/task-principles.md` | How tasks are scoped and written |
| Data reference | `documentation/data_reference.md` | Verified record of all pipeline output numbers |
| Corpus rationale | `documentation/corpus_selection.md` | Why specific shows/sources were chosen |
| Project context | `documentation/background.md` | Predecessor approaches and how the project evolved |

### Source and component subfolders (stable, named after what they are)

| Artifact | Path | Purpose |
|---|---|---|
| ZDF docs | `documentation/ZDF/` | ZDF metadata structure, access patterns, mention detection |
| Wikidata docs | `documentation/Wikidata/` | Entity resolution, event schema, guardrails (already exists) |
| fernsehserien.de docs | `documentation/fernsehserien_de/` | Scraping specification, QA notes (already exists) |
| OpenRefine docs | `documentation/OpenRefine/` | OpenRefine usage in reconciliation (already exists) |
| Analysis docs | `documentation/analysis/` | Statistical analysis methods and results |
| Visualization docs | `documentation/visualizations/` | Visualization principles and design decisions (already exists) |

### Future work (separate from docs, but within documentation/)

| Artifact | Path | Purpose |
|---|---|---|
| Open backlog | `documentation/tasks/` | Prioritized public list of future work; one file per task |

**Completeness check for each artifact:** accurate, written for someone with no prior context, cross-referenced to adjacent docs, free of paper-framing and stale references.

---

## Folder inventory: current → final

This table declares the fate of every major folder and root-level document in
`documentation/`. Use it during synthesis to confirm each item has a declared destination.

| Current path | Status | Final fate |
|---|---|---|
| `documentation/Wikidata/` | Exists, keep | Target artifact subfolder; archive/ subfolder stays |
| `documentation/fernsehserien_de/` | Exists, keep | Target artifact subfolder |
| `documentation/OpenRefine/` | Exists, keep | Target artifact subfolder |
| `documentation/visualizations/` | Exists, keep | Target artifact subfolder |
| `documentation/archive/` | Exists, keep | Permanent home for historical records; never deleted |
| `documentation/ZDF/` | Does not exist | Create during synthesis; receives ZDF and mention-detection content |
| `documentation/analysis/` | Does not exist | Create during synthesis; receives statistical analysis content |
| `documentation/tasks/` | Exists (renamed 2026-05-22 from `ToDo/`) | Public task backlog; `2026-05-21_GitHub_ready/` synthesis coordination lives here; individual task files replace the monolithic `open-tasks.md` |
| `documentation/phases/` | Dissolved | Content extracted to source subfolders; archived to `documentation/archive/phases/` |
| `documentation/context/` | Dissolved | Content extracted; archived to `documentation/archive/context/` |
| `documentation/31_entity_disambiguation/` | Dissolved | Content archived to `documentation/archive/31_entity_disambiguation/` |
| `documentation/50_Analysis/` | Dissolved | Content extracted to `documentation/analysis/`; archived to `documentation/archive/50_Analysis/` |

### Root-level documents in `documentation/`

| File | Status | Final fate |
|---|---|---|
| `repository-overview.md` | Exists | Target artifact; verify and update |
| `workflow.md` | Exists | Target artifact; verify and update |
| `contracts.md` | Exists | Target artifact; verify and update |
| `coding-principles.md` | Exists | Target artifact; verify and update |
| `task-principles.md` | Exists | Target artifact; verify and update |
| `data_reference.md` | Exists (new) | Target artifact; already verified |
| `corpus_selection.md` | Exists (new) | Target artifact; already verified |
| `background.md` | Exists | Target artifact; may need expansion |
| `mention-detection.md` | Exists | Assess during synthesis: absorb into `ZDF/` or keep as root doc |
| `notebook-observability.md` | Exists | Assess during synthesis: absorb into `coding-principles.md` or `workflow.md` |

---

## Knowledge taxonomy

**Status: draft — to be finalized once the target artifact structure above is stable.**

The taxonomy's value is its `Target artifact` column: every knowledge type maps to exactly
one artifact. That mapping can only be correct once we know what artifacts exist. Treat
the draft below as a starting point; revise any row whose target artifact changed when the
table above was updated.

Each raw file contains zero or more of the following knowledge types. During processing,
each piece of knowledge is classified, checked against target artifacts (already captured?
needs writing? needs a task?), and either written into a target artifact or converted into
a scoped task.

| Type | Symbol | Target artifact | Description |
|---|---|---|---|
| Pipeline fact | `PF` | `repository-overview.md` + the relevant source subfolder (`ZDF/`, `Wikidata/`, `fernsehserien_de/`, `analysis/`) | How a component works; inputs, outputs, data flow |
| Design decision | `DD` | The relevant source subfolder, or `coding-principles.md` if it applies across sources | Why something was built a certain way |
| Future task | `FT` | `documentation/tasks/` | Something that needs to be done; scope + motivation; one file per task |
| Lesson learned | `LL` | `background.md` for cross-cutting history; relevant source subfolder for source-specific lessons | What was tried; what failed; what was learned |
| Data fact | `DF` | `data_reference.md` | Verified number, stat, or data characteristic mapped to its CSV source |
| Principle | `PR` | `coding-principles.md` (code standards) or `task-principles.md` (task governance) | A rule governing future work |
| Corpus rationale | `CR` | `corpus_selection.md` | Why specific shows/sources/corpora were chosen |
| Visualization principle | `VP` | `documentation/visualizations/visualization-principles.md` | Design choices for charts and diagrams |
| Data contract | `DC` | `contracts.md` | Schema or interface between pipeline components |
| Predecessor context | `PC` | `background.md` | Prior approaches, why they were abandoned, and what was learned |

When classifying `PF` or `DD` findings, identify the source first (ZDF, Wikidata,
fernsehserien.de, analysis, or cross-cutting) — the source determines the subfolder.
Cross-cutting facts belong in `repository-overview.md`.

If a file contains knowledge that fits none of these types, stop and update this taxonomy
before continuing.

---

## File disposal decisions

After a file is processed, it receives exactly one of these dispositions:

| Disposition | Meaning | Next action |
|---|---|---|
| `Extracted` | All knowledge captured in target artifacts | Add to ready-for-delete list |
| `Redundant` | Already fully covered elsewhere; nothing new | Add to ready-for-delete list |
| `Archive` | Historical record; not needed for pipeline operation | Move to `archive/` subfolder and note where |
| `Task` | Requires code work; a task file was created or already exists | Mark done for now; task file is the owner |
| `Keep` | Still actively needed in current location | Document why; do not delete |
| `Partial` | Knowledge partially extracted; needs follow-up | Note what remains; return to it |

A file is only added to ready-for-delete when all its knowledge has been extracted or is
demonstrably redundant. When in doubt, choose `Partial` over `Extracted`.

---

## Existing evidence base

`documentation/archive/documentation_synthesis/catalogue.jsonl` contains 937 findings from
571 files, organized into 25 cluster types. During processing, consulting the catalogue
for a file's known findings can accelerate classification — but the file must still be
read directly to verify accuracy and catch anything the catalogue missed.

Cluster files in `documentation/archive/documentation_synthesis/data/clusters/` provide
pre-grouped views by finding type (todo, issue, design, contract, note, etc.).
