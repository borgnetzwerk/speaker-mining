# Task Principles

> Design document: `documentation/tasks/archive/2026-05-22_task_redesign/assessment.md`
> Task index: `documentation/tasks/00_index.md`
> Archive: `documentation/tasks/archive/00_index.md`

---

## 1. Where tasks live

All actionable tasks are indexed in `documentation/tasks/00_index.md`. Nowhere else.

Tasks must NOT live in:
- Notebook cells (`.ipynb` files)
- Code comments (`# TODO: ...` in `.py` files)
- `documentation/tasks/open_additional_input.md` (that file is a temporary intake buffer, not a tracker)
- Phase analysis documents or any other markdown file

If you find a task in one of these locations: add it to `documentation/tasks/00_index.md` and create the appropriate file or folder. If it is already tracked there, delete the duplicate. If it is already resolved, delete it from the notebook/code.

---

## 2. Three task sizes

Tasks come in three sizes. The size determines the structure, not the other way around — if a task grows, evolve its structure, do not re-file it.

| Size | When to use | Structure |
|---|---|---|
| **Small** | Can be fully described in one sentence; no design decisions needed; can be done in one focused session with no ambiguity | Row in `00_index.md` only — no file |
| **Medium** | Needs a motivation, scope, and verifiable done criteria; approach is clear before work begins | `.md` file in `documentation/tasks/` |
| **Large** | Needs a design document, has sub-tasks, involves multiple sessions, or requires discussion before work can begin | Folder in `documentation/tasks/` with a `README.md` |

**Growing a task:** small → medium means creating a file and updating the index row to a link. Medium → large means creating a folder, moving the file in as `README.md` or keeping it as a planning doc, and updating the index link. No approval needed; just update the index.

---

## 3. Task IDs and naming

Tasks are identified by a **slug**: a short kebab-case phrase describing the task (e.g., `fix-chart-colors`, `v4-wikidata-redesign`). The slug is the reference used in cross-references, code comments, and prose.

Files and folders are named `YYYY-MM-DD_<slug>` (e.g., `2026-05-22_fix-chart-colors.md`). The date prefix is for file system sorting and git history; the slug alone is the canonical cross-reference.

**Slug format rules:**
- Kebab-case, lowercase, hyphens only (no underscores, no special characters beyond hyphens)
- Maximum ~40 characters
- Describes the problem or goal, not the solution (e.g., `chart-color-hardcoding` not `fix-cell-8`)
- Unique within `documentation/tasks/` — check the index before creating
- Created from today's date when the task is first formalized

The legacy `TODO-NNN` numbering scheme is retired. Existing code and documentation references to `TODO-NNN` remain valid indefinitely — a mapping from old IDs to new slugs is at `documentation/tasks/archive/todo-nnn-mapping.md`.

---

## 4. Raising a task

All three sizes use the same heading-based format. Properties appear only when they add information not already communicated by the structure. `status: open` is never written — presence in the active index means open. `status:` only appears when the task is `in-progress` or `blocked`.

**Small task** — all properties inline in `00_index.md`, no file:

```markdown
### YYYY-MM-DD_slug
* priority: low | medium | high
* scope: documentation | visualization | pipeline | architecture | contracts | other
* summary: One sentence — the problem or goal.
* context: Optional — evidence, prior work, constraints.
* definition of done: One or two verifiable criteria.
```

**Medium task** — one line in `00_index.md` linking to a file; full detail in the file:

```markdown
### YYYY-MM-DD_slug — [file](YYYY-MM-DD_slug.md)
* priority: low | medium | high
* scope: ...
* summary: One sentence.
```

The linked file expands with free-form sections as needed (motivation, scope, definition of done, notes). No fixed template beyond the heading and the three properties above — let the task's complexity determine what sections it needs.

**Large task** — one line in `00_index.md` linking to a folder; full detail in `README.md` inside the folder:

```markdown
### YYYY-MM-DD_slug — [folder](YYYY-MM-DD_slug/)
* priority: low | medium | high
* scope: ...
* summary: One sentence.
```

For **large tasks**: create `documentation/tasks/YYYY-MM-DD_<slug>/README.md`. The folder may additionally contain design documents, a PROGRESS.md, sub-task files, or any other planning artifacts the task needs.

A task with only a title is still better than no task — raise it first, fill in detail later. Do not let perfect be the enemy of traceable.

---

## 5. Progressing a task

Do not write `status: open` — a task present in the active index is open by definition. Only write `status:` when the state is exceptional:

| Write this | When |
|---|---|
| `status: in-progress` | Actively being worked |
| `status: blocked — <reason>` | Cannot proceed; the reason must be included inline |
| `status: wont-fix — <reason>` | Deliberately not implemented; move to archive after adding the reason |

Add progress notes to the `context` or `notes` field when significant decisions are made or partial work is completed. Future contributors read these to avoid duplicating work.

---

## 6. Resolving a task

A task is resolved when all items in its Definition of done are met.

**When a task is resolved:**
1. Move the task file or folder from `documentation/tasks/` to `documentation/tasks/archive/`.
2. Add an entry to `documentation/tasks/archive/00_index.md` with the slug, resolution date, and one-line reason.
3. Update the row in `documentation/tasks/00_index.md`: move it to the Completed section or remove it.
4. If the resolution produced a new document or finding, add a pointer in the task's Notes before archiving.

Do not mark a task resolved in the index without immediately moving it. Resolved tasks remaining in the active index create noise.

---

## 7. Archiving

`documentation/tasks/archive/` is the permanent home for resolved tasks, superseded designs, and retired trackers. Items are never deleted from the archive without deliberate human decision.

`documentation/tasks/archive/00_index.md` lists every archived item with: slug or filename, date archived, and one-line reason for archiving.

---

## 8. Intake from `open_additional_input.md`

`documentation/tasks/open_additional_input.md` is a human-writable notepad for unstructured input. It is not a task tracker. When processing its content:

1. Convert actionable items into tasks using the structure above (small row, medium file, or large folder).
2. Move the processed content verbatim to `documentation/tasks/archive/additional_input.md` with an archive note.
3. Leave `open_additional_input.md` clean (containing only unprocessed or clarification-pending items).
4. If an item needs clarification before it can be tracked, raise a `**QUESTION:**` block in `open_additional_input.md`.
