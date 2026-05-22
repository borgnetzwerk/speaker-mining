# Task Structure Redesign — Options Assessment

**Date:** 2026-05-22
**Status:** Draft — under review
**Context:** `documentation/open-tasks.md` is a ~72-item monolith. The `documentation/tasks/` folder (renamed from `ToDo/`) now holds both that file and the `2026-05-21_GitHub_ready/` synthesis coordination folder. The question is how to restructure `documentation/tasks/` so that simple tasks stay simple, large tasks get the space they need, and contributors have one clear entry point.

---

## The problem being solved

`open-tasks.md` fails in two directions simultaneously. For small tasks ("fix this hardcoded color in cell 8"), the current 8-field template is 10x more ceremony than the task deserves. For large tasks ("redesign the v4 Wikidata pipeline"), a single TODO block with a `Notes:` field is nowhere near enough space — it cannot hold a design document, a progress log, or sub-tasks. The result is that large tasks either get under-documented or spill into separate files with no connection back to the tracker.

The synthesis coordination folder (`2026-05-21_GitHub_ready/`) is the accidental proof of what a large task actually needs: its own folder, a PROGRESS.md, a tasks subfolder, a mission document. That structure grew organically because it had to.

---

## Evaluation dimensions

Each option below is assessed against five dimensions:

1. **Discovery** — how many places must a contributor check to find all open tasks?
2. **Appropriate detail** — can a two-line task stay two lines?
3. **Scale** — can a large task carry design docs, progress logs, and sub-tasks?
4. **Stability** — what happens when a task grows beyond its original size category?
5. **Maintenance** — how hard is it to keep the structure consistent over time?

---

## Option A — User's proposal: two subfolders by size

```
documentation/tasks/
  00_index.md
  small_task_tracker.md
  task_principles.md
  open_additional_input.md
  medium_tasks/
    README.md
    T001_fix_chart_colors.md
    T002_mention_detection_refactor.md
  large_tasks/
    README.md
    v4_wikidata_redesign/
      README.md
      01_design.md
      PROGRESS.md
    2026-05-21_GitHub_ready/   (existing)
```

**Discovery:** Two entry points for tasks — `small_task_tracker.md` (root) and `00_index.md`. A contributor either reads the index and follows links, or reads the small tracker first, then navigates subfolders. That is one step too many.

**Appropriate detail:** Excellent. Small tasks as flat rows in a dedicated file; no forced template for a fix that takes 30 minutes.

**Scale:** Excellent. Large tasks get a folder with unlimited internal structure.

**Stability:** Weak. The size boundary is defined by prediction, not by content need. When a "medium" task accumulates notes and a design doc, moving it to `large_tasks/` breaks links in the index and in any cross-references. Reclassification is disruptive.

**Maintenance:** The two-subfolder structure creates implicit rules that aren't written anywhere obvious: "when does medium become large?" This ambiguity accumulates over time and contributors will inconsistently classify.

**Summary:** The core insight (three size tiers) is sound. The implementation (subfolders by size) is the weak part, specifically because reclassification requires moving files.

---

## Option B — Progressive disclosure: structure follows content, single index

```
documentation/tasks/
  00_index.md              — single entry point; small tasks as rows, medium and large as links
  task_principles.md
  open_additional_input.md
  T001_fix_chart_colors.md    — medium task: one file
  T002_phase50_viz_gaps.md    — medium task: one file
  v4_wikidata_redesign/       — large task: folder
    README.md
    01_design.md
    PROGRESS.md
  2026-05-21_GitHub_ready/    — large task: existing folder
```

The three size tiers still exist, but they are expressed through structure rather than directory placement:
- **Small** = a row in `00_index.md` (no file needed; just title, priority, one-line description)
- **Medium** = a `.md` file in `tasks/` root (the current `open-tasks.md` template applies here)
- **Large** = a folder in `tasks/` root (README + whatever internal structure the task needs)

There is no separate `medium_tasks/` or `large_tasks/` directory. The index is the single entry point and the only navigation document that needs to be maintained.

**Discovery:** One place — `00_index.md`. Every task appears here; small tasks are inline, others are links.

**Appropriate detail:** Excellent. A small task is a table row; a medium task gets a dedicated file; a large task gets a folder.

**Scale:** Excellent. A large task's folder has no structural constraints — it can contain design docs, a PROGRESS.md, sub-tasks, research notes.

**Stability:** Excellent. Growing a small task into a medium task = create a file and update the index row to a link. Growing a medium task into a large task = create a folder, move the file in, update the index link. No reclassification ceremony; the structure just grows.

**Maintenance:** The index needs to stay accurate, but there is only one file to maintain. The size category is inferred from whether the task entry is a row (small), a file link (medium), or a folder link (large). No explicit labeling needed.

---

## Option C — Flat monolith with size metadata (minimal change)

Keep `open-tasks.md` but add a `Size:` field (small / medium / large) to each entry. No structural change to `documentation/tasks/`.

**Discovery:** One file — trivially good.

**Appropriate detail:** Still bad. Every task forces the full 8-field template, even a one-line fix.

**Scale:** Still bad. A large task cannot attach design documents.

**Stability:** N/A — no structure to migrate between.

**Maintenance:** Lowest overhead. But this option does not solve the underlying problem; it only classifies it.

**Summary:** A non-starter unless the goal is to avoid structural change entirely. It solves nothing; it only names the problem.

---

## Option D — Separate size directories with a single shared index

Identical to Option A but without `small_task_tracker.md`. Small tasks are rows in `00_index.md`; medium and large tasks are in their respective subdirectories and linked from `00_index.md`.

```
documentation/tasks/
  00_index.md              — small tasks as rows; links to medium/ and large/ entries
  task_principles.md
  open_additional_input.md
  medium/
    T001_fix_chart_colors.md
  large/
    v4_wikidata_redesign/
```

**Discovery:** One index — good.

**Appropriate detail:** Same as Options A and B — good.

**Scale:** Same as Options A and B — good.

**Stability:** Still weak for the same reason as Option A. When a medium task grows, moving it from `medium/` to `large/` is a breaking rename.

**Maintenance:** Requires deciding "medium or large?" at creation time. Reclassification overhead is moderate but real.

---

## Comparison table

| Dimension | Option A (two subfolders) | Option B (progressive disclosure) | Option C (monolith + metadata) | Option D (subfolders, shared index) |
|---|---|---|---|---|
| Discovery | 2 entry points | 1 entry point | 1 entry point | 1 entry point |
| Appropriate detail | ✓ | ✓ | ✗ | ✓ |
| Scale | ✓ | ✓ | ✗ | ✓ |
| Stability on growth | ✗ | ✓ | — | ✗ |
| Maintenance overhead | Medium | Low | Lowest | Medium |

---

## Recommendation

**Option B** (progressive disclosure, single index).

The three size tiers the user identified are correct and important. The flaw in the folder-by-size variants (A and D) is that they encode predicted size into directory placement, which makes reclassification a disruptive rename. Option B gets all the same tiers — small row, medium file, large folder — by letting the structure of the entry in `00_index.md` declare the size implicitly: a row means small, a link to a `.md` file means medium, a link to a folder means large.

The single remaining advantage of Options A/D over B is **navigational clarity**: a contributor browsing `large_tasks/` knows they are looking at significant work. Option B can replicate this with three labeled sections in the index:

```markdown
## Small tasks

### 2026-05-22_normalize-name-matching
* priority: low
* scope: pipeline
* summary: Verify symmetric normalization is applied to both sides of all canonical_label comparisons in person deduplication.
* definition of done: Code review confirms `normalize_name_for_matching` applied symmetrically; normalization-policy.md cited in the relevant function's docstring.

## Medium tasks

### fix-chart-colors — [2026-05-22_fix-chart-colors.md](2026-05-22_fix-chart-colors.md)
* priority: low
* scope: visualization
* summary: Replace hardcoded hex colors in notebook cells 8 and 11 with PALETTE constants.

## Large tasks

### v4-wikidata-redesign — [2026-05-22_v4-wikidata-redesign/](2026-05-22_v4-wikidata-redesign/)
* priority: high
* scope: architecture
* summary: Rule-driven graph expansion engine replacing the v3 Wikidata pipeline (TODO-044 implementation).
```

This gives the same affordance — "I'm looking at large work" — without requiring files to move when tasks grow.

---

## What needs to change if Option B is adopted

1. `task_principles.md` §1 (currently: "All actionable tasks belong in `documentation/open-tasks.md`. Nowhere else.") → update to: "All actionable tasks are indexed in `documentation/tasks/00_index.md`. Small tasks are tracked inline there; medium tasks have a `.md` file in `documentation/tasks/`; large tasks have a folder."
2. `task_principles.md` §7 (references `ToDo/TASK_EXECUTION_PLAN.md`) → update to current path or remove.
3. Create `documentation/tasks/00_index.md` with the three-section structure above.
4. Migrate existing TODO items: ~72 items from `open-tasks.md` → classified as small/medium/large and written into the new structure. This is the scope of T16.
5. Update all cross-references to `open-tasks.md` in other docs.

---

## Resolved decisions

### 1 — ID scheme

**Decision: date-prefix slug, not sequential numbers.**

The `TODO-NNN` system has accumulated known failures: numbers require prior context to generate, they cannot be created offline or by human annotators without coordination, they collide when tasks are created in parallel, and they carry no meaning beyond order-of-creation. The proposed replacement is `YYYY-MM-DD_short-slug` (e.g., `2026-05-22_fix-chart-colors`). The date prefix makes the ID self-generating — anyone with a clock and a description can create a unique, sortable, non-colliding ID without consulting the tracker.

**Critical improvements to the proposal:**

The date-slug is the right shape, but two roles should be kept distinct: the *filename* (with date prefix, for file system navigation and git history) and the *reference slug* (without date prefix, for use in code comments, prose, and cross-references). The current `TODO-016` in a code comment is 9 characters. Writing `2026-05-22_normalize-name-matching` in a code comment is 36 characters and obscures the code it annotates. The solution: the canonical short reference for a task is just the slug portion — `normalize-name-matching` — and the file is named `2026-05-22_normalize-name-matching.md`. In the index, both appear; in code comments or prose, only the slug is used.

For small tasks that have no file at all, the slug is also the reference. It appears in the index row and in any cross-reference. The date is metadata in the index row, not part of the reference.

**Slug format rules (to be written into `task_principles.md`):**
- Kebab-case, lowercase, hyphens only (no underscores, no special characters)
- Maximum ~40 characters
- Describes the task, not the solution (e.g., `chart-color-hardcoding` not `fix-cell-8`)
- Unique within `documentation/tasks/` (check index before creating)
- Same-day batch creation during migration: use the original creation context if known; otherwise today's date is fine since the slug itself distinguishes the entries

**Migration note:** the 72 existing `TODO-NNN` references in code and documentation are a transition problem. During migration, each task gets a slug; a mapping table (`documentation/tasks/archive/todo-nnn-mapping.md`) records the old ID → new slug so that grep searches on `TODO-016` still resolve.

---

### 2 — Retirement of `open-tasks.md`

**Decision: move to `documentation/tasks/archive/` with an archive index.**

`documentation/tasks/` should have an `archive/` subfolder. The archive maintains its own `00_index.md` listing every archived file or folder, with one line per entry explaining why it was archived and when. Archived items are never deleted from the archive without deliberate human decision. `open-tasks.md` moves there once migration to the new structure is complete; its archive entry notes that it was the monolithic pre-restructure tracker and that the migration mapping is at `archive/todo-nnn-mapping.md`.

This directly addresses the lesson from the B5 process error in the synthesis: archiving without an index led to task items being lost. The archive index ensures that future reviewers can see what was archived, read it, and recover any items that were missed.

The `archive/00_index.md` structure:

```
| File/Folder | Archived | Reason |
|---|---|---|
| open-tasks.md | 2026-XX-XX | Pre-restructure monolith; 72 TODO items migrated to individual task files; see todo-nnn-mapping.md |
| todo-nnn-mapping.md | 2026-XX-XX | Cross-reference map from old TODO-NNN IDs to new slugs |
```

---

### 3 — Size definitions

**Decision: write explicit default criteria in `task_principles.md`, framed as guidelines not hard rules.**

The criteria below are starting points. They will be wrong for edge cases — a two-sentence task can turn into a multi-session design discussion; a complex pipeline refactor can sometimes be captured in one tight definition-of-done. What matters is that the structure grows with the task (small → medium = create a file; medium → large = create a folder) rather than requiring the task to be re-filed.

Proposed criteria for `task_principles.md`:

| Size | Criterion | Structure |
|---|---|---|
| **Small** | Fully described in one sentence; no design decisions needed; can be done in one focused session with no ambiguity | Row in `00_index.md` only |
| **Medium** | Needs a motivation, scope, and verifiable done criteria; may involve multiple files but the approach is clear | `.md` file in `tasks/` |
| **Large** | Needs a design document, has sub-tasks, involves multiple sessions, or requires discussion before work can begin | Folder in `tasks/` |

The structure defines the size, not the other way around. If a small task grows and you find yourself adding notes that don't fit in an index row, create a file — it has become medium. If a medium task accumulates a design doc, create a folder — it has become large. No approval needed; just update the index link.

---

## Updated recommendation (incorporating resolved decisions)

Option B with the additions above. The full target structure:

```
documentation/tasks/
  00_index.md                       — single entry point; three sections (small/medium/large)
  task_principles.md                — governance, size criteria, slug rules, archiving rules
  open_additional_input.md          — unstructured human intake buffer
  archive/
    00_index.md                     — archive index with reason per entry
    open-tasks.md                   — (after migration) former monolith
    todo-nnn-mapping.md             — old TODO-NNN → new slug cross-reference
  2026-05-22_fix-chart-colors.md    — example medium task
  2026-05-22_v4-wikidata-redesign/  — example large task folder
    README.md
    01_design.md
    PROGRESS.md
  2026-05-21_GitHub_ready/          — existing large task (synthesis coordination)
```

**What still needs to happen (in this order):**
1. Update `task_principles.md` with the new §1, size criteria, slug format rules, archiving rules, and removal of the stale `ToDo/TASK_EXECUTION_PLAN.md` reference in §7.
2. Create `documentation/tasks/00_index.md` with the three-section layout.
3. Create `documentation/tasks/archive/` and its `00_index.md`.
4. Migrate ~72 items from `open-tasks.md`: classify each as small/medium/large, create files/rows as needed, record the `TODO-NNN → slug` mapping.
5. Move `open-tasks.md` to `documentation/tasks/archive/` and add its entry to the archive index.
6. Update cross-references to `open-tasks.md` in `documentation/README.md`, `task-principles.md`, and anywhere else.
