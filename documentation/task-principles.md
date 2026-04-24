# Task Principles

> Related tracker item: TODO-026  
> Single source of truth for open tasks: `documentation/open-tasks.md`  
> Closed/solved tasks archive: `documentation/archive/closed-tasks.md`

---

## 1. Where Tasks Live

**All actionable tasks belong in `documentation/open-tasks.md`.** Nowhere else.

Tasks must NOT live in:
- Notebook cells (`.ipynb` files)
- Code comments (`# TODO: ...` in `.py` files)
- `ToDo/open_additional_input.md` (that file is a temporary intake buffer, not a tracker)
- Phase analysis documents or any other markdown file

If you find a task in one of these locations: move it to `documentation/open-tasks.md` immediately. If it is already tracked there, delete the duplicate. If it is already resolved, delete it from the notebook/code.

---

## 2. Raising a Task

Use the entry template at the top of `documentation/open-tasks.md`. The minimum required fields are:

- **ID**: next available TODO-NNN
- **Priority**: high / medium / low
- **Status**: open
- **Area**: ingestion | parsing | modeling | docs | workflow | contracts | analysis | architecture | other
- **Summary**: one sentence — the problem or goal
- **Definition of done**: at least two observable, verifiable completion criteria

A task with only a title is still better than no task — raise it first, fill in detail later. Do not let perfect be the enemy of traceable.

---

## 3. Progressing a Task

Update the `Status` field to reflect current state:

| Status | Meaning |
|--------|---------|
| `open` | Not yet started |
| `in-progress` | Actively being worked |
| `blocked` | Cannot proceed; add a note explaining what is blocking |
| `wont-fix` | Deliberately not implemented; add a note with the rationale |

Add progress notes to the task's `Notes` field when significant decisions are made or partial work is completed. Future agents and contributors read these notes to avoid duplicating work.

---

## 4. Resolving a Task

A task is resolved when all items in its Definition of done are met.

**When a task is resolved:**
1. Move the entire task block from `documentation/open-tasks.md` to `documentation/archive/closed-tasks.md`. Do not leave it in open-tasks.md with `Status: solved`.
2. In closed-tasks.md: keep the full task block with `Status: solved (YYYY-MM-DD)`.
3. If the resolution produced a new document or finding, add a pointer in the task's `Notes` before archiving.

**Do not** mark a task solved in open-tasks.md without immediately moving it. Solved tasks remaining in open-tasks.md create noise and confusion.

---

## 5. Archiving a Task

Closed tasks live in `documentation/archive/closed-tasks.md` permanently. They should not be deleted — the archive is a record of completed work and reasoning.

Organizing closed-tasks.md:
- Group under `## Solved`, `## Wont-fix` headings.
- Within each group, tasks appear in reverse chronological order (most recently closed first).

---

## 6. Intake from `ToDo/open_additional_input.md`

`open_additional_input.md` is a human-writable notepad for unstructured input. It is not a task tracker. When processing its content:

1. Convert actionable items into formal TODO entries in `open-tasks.md`.
2. Move the processed content to `ToDo/archive/additional_input.md` with an archive note.
3. Leave `open_additional_input.md` clean (containing only unprocessed or clarification-pending items).
4. If an item needs clarification before it can be tracked, raise a `**QUESTION:**` block in `open_additional_input.md`.

---

## 7. Execution Planning

For planning task execution order and dependencies, see `ToDo/TASK_EXECUTION_PLAN.md`. That document provides wave-based ordering and identifies parallelization opportunities for agents working through the backlog.
