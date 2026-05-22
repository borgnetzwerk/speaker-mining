# Mission: GitHub-Ready Repository

## What we are doing

This folder coordinates the transformation of the Speaker Mining research workspace
into a cohesive, self-explanatory, publicly approachable repository.

The work has two equally important dimensions:

**1. Document what exists.**
Make the current state of the pipeline, data, and analyses legible to someone with no
prior context. This means synthesizing scattered artifacts into coherent documentation —
not just organizing files, but understanding them and expressing their value clearly.

**2. Synthesize what must still be done.**
Approximately 60% of what exists in this repository is unfinished: deferred tasks,
partial implementations, open design decisions, identified gaps, abandoned approaches
that taught us something. This raw material must be transformed into a cohesive future
work structure — a clear roadmap of what needs to happen next and why, so that anyone
picking up this work can orient themselves and contribute meaningfully.

**The goal is not cleanup. The goal is synthesis.**

---

## The two dimensions in detail

### Dimension 1: Documenting what IS

For each artifact that documents the current state, ask:
- Is it in the right place with a self-evident name?
- Does it accurately reflect the current pipeline state?
- Is it connected to related documentation (cross-referenced, not isolated)?
- Would a newcomer understand it without prior context?

Examples of this work:
- `data_reference.md` — verified numbers mapped to CSV sources
- `repository-overview.md` — accurate end-to-end pipeline description
- `visualization-principles.md` — design decisions captured as reusable rules
- `corpus_selection.md` — why the specific shows were chosen

### Dimension 2: Synthesizing what MUST BE DONE

The repository contains scattered future work in many forms:
- Explicit `# TODO` and `# FIXME` comments in source code
- Deferred design decisions in phase analysis notes
- "Not yet implemented" sections in documentation
- Partial implementations with `pass` or placeholder logic
- Statistical analyses that ran once but aren't integrated into the pipeline
- Gaps identified in peer review that expose real pipeline limitations
- Predecessor approaches (Lanz-und-Precht) that weren't completed
- Gitignored work-in-progress that represents real research directions

All of this must be aggregated into a structured set of future tasks, where each task:
- Has a clear scope (what exactly needs to be done)
- Has a clear motivation (why it matters for the pipeline)
- Has traceable inputs (where the relevant code/data/notes live)
- Is independent of the "paper" framing it may have originated from

The result should be a backlog that any future contributor can pick up from — not
a personal to-do list, but a public, self-contained, prioritized roadmap.

---

## What exists in this repository (artifact inventory)

### Active pipeline
- `speakermining/src/process/` — phases 10–50, analysis modules, notebooks
- `speakermining/src/config/` — Caddy proxy (planned implementation), manifest files
- `speakermining/test/` — test suite

### Pipeline documentation
- `documentation/repository-overview.md` — authoritative pipeline description
- `documentation/workflow.md` — end-to-end workflow narrative
- `documentation/phases/` — per-phase analysis notes (PHASE_ANALYSIS_*.md)
- `documentation/contracts.md` — output contracts between phases
- `documentation/coding-principles.md` — coding standards
- `documentation/task-principles.md` — task governance

### Data and analysis reference
- `documentation/data_reference.md` — verified record of all pipeline output numbers,
  each mapped to its CSV source
- `documentation/statistical_analysis_results.json` — precomputed statistical test
  results (gender-age Mann-Whitney, trend tipping point, Wikidata bias)
- `documentation/corpus_selection.md` — rationale for show selection

### Visualization
- `documentation/visualizations/visualization-principles.md` — evolving design guide
- `documentation/visualizations/` — V3 architecture diagrams (gitignored source)
- `documentation/tasks/visualization_references/` — reference material to learn from:
  - `2025-scicom-ki-survey/` — stakeholder cluster + UEQ visualizations (SciCom Wiki context)
  - `Lanz-und-Precht/` — predecessor exploratory project (episode analysis + charts)
  - `Scientific knowledge fit for society Evaluation/` — Likert scale chart reference

### Unfinished / future work material (scattered across the repo)
- `speakermining/src/process/analysis/statistical_tests.py` — analysis functions that
  exist but are not integrated into the pipeline and have paper-framing docstrings
- `speakermining/src/process/analysis/gender_trend_analysis.py` — temporal trend
  analysis, same status
- `documentation/phases/PHASE_ANALYSIS_*.md` — per-phase gap analysis and open questions
- `documentation/open-tasks.md` — tracked open tasks (high-level)
- `documentation/50_Analysis/` — temporal output structure with significant consolidation
  work remaining
- `speakermining/src/process/candidate_generation/wikidata/_v3_archive/` — V3 code
  kept until V4 implementation reaches ~80% completeness
- `speakermining/src/config/Caddyfile` — planned implementation (CORS proxy), not yet deployed

### Related and prior work (gitignored, for learning)
- `documentation/ToDo/visualization_references/` — see Visualization section above
- `documentation/archive/paper/main.tex` — canonical paper source

### Archive
- `documentation/archive/` — superseded permanent documents
- `documentation/31_entity_disambiguation/archive/` — phase-specific archived records
- `documentation/Wikidata/archive/` — Wikidata investigation archive
- `documentation/archive/` — superseded working documents (includes former `ToDo/archive/` content)

---

## How to approach a task

Before touching any file or folder:

1. **Read it.** Not the name — the contents. A folder called `visualization_references`
   contains visualization references. A script called `statistical_tests.py` may contain
   reusable pipeline analytics. A folder in `ToDo` may contain permanent documentation.

2. **Understand its role.** Is it documenting what IS, or pointing at what MUST BE DONE?
   Is it an active module, a reference to learn from, a predecessor approach, or a
   deferred implementation?

3. **Decide what to transform it into.** For "what IS" artifacts: the clearest possible
   documentation. For "what MUST BE DONE" artifacts: a well-scoped task with clear
   motivation and traceable inputs.

4. **Never delete without explicit understanding.** If it's not clear what something is,
   the task is to understand it — not to delete it on the grounds that it seems out of place.

---

## Current active tasks

See `tasks/00_index.md`.

Each task file describes a specific transformation: what the artifact currently is,
what it should become, and why. Tasks are ordered by impact on public-facing repository
quality, not by convenience.
