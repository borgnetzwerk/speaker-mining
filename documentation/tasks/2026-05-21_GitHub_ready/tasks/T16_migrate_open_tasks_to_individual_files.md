# T16: Migrate open-tasks.md to the three-tier task structure

**Supersedes the original T16 draft.** The design for the new structure is fully specified in `documentation/tasks/2026-05-22_task_redesign/assessment.md`. This task covers execution only; design questions are settled there.

---

## What

Replace the monolithic `documentation/open-tasks.md` (72 TODO items) with the three-tier task structure:

- **Small tasks** — index rows in `documentation/tasks/00_index.md` (no file)
- **Medium tasks** — individual `.md` files in `documentation/tasks/` named `YYYY-MM-DD_<slug>.md`
- **Large tasks** — individual folders in `documentation/tasks/` named `YYYY-MM-DD_<slug>/` with a README

The single entry point for all tasks is `documentation/tasks/00_index.md`.

## Why

`open-tasks.md` fails in both directions: the 8-field template is overkill for a one-line fix, and a single `Notes:` field is nowhere near enough space for a multi-session design task. The 72-item list is already hard to navigate; it will only grow. The new structure scales with task complexity and keeps the index light.

---

## Approach

### Phase 1 — Infrastructure (prerequisite, do first)

`task_principles.md` has been updated and `documentation/tasks/00_index.md` exists. If these are not yet done, do them first. See "What needs to change" in `assessment.md`.

### Phase 2 — Classify and migrate

For each of the ~72 items in `open-tasks.md`:

1. Read the item fully.
2. Classify as small / medium / large using the criteria in `task_principles.md`.
3. For **small**: add a row to the correct section of `00_index.md`.
4. For **medium**: create `documentation/tasks/YYYY-MM-DD_<slug>.md` using the medium task template; add a link row to `00_index.md`.
5. For **large**: create `documentation/tasks/YYYY-MM-DD_<slug>/README.md` (and any additional planning files needed); add a link row to `00_index.md`.
6. Record the old `TODO-NNN` → new slug mapping in `documentation/tasks/archive/todo-nnn-mapping.md`.
7. Do not migrate deferred/wont-fix items. They go directly to the archive index with a note.

Start with the items most likely to be picked up by a new contributor (currently: Phase 50 visualization gaps, transcript/NLP tasks). This gives early value before the full migration is done.

### Phase 3 — Archive open-tasks.md

Once all items are migrated:

1. Move `open-tasks.md` to `documentation/tasks/archive/open-tasks.md`.
2. Add its entry to `documentation/tasks/archive/00_index.md` with reason: "Pre-restructure monolith; 72 TODO items migrated to three-tier structure."
3. Update cross-references: `documentation/README.md`, `task_principles.md` header, any code or doc files that link to `open-tasks.md` directly.

---

## Acceptance criteria

1. `documentation/tasks/00_index.md` lists every active task (small inline, medium/large as links).
2. Every medium task has a file in `documentation/tasks/` with at minimum: slug, priority, status, one-paragraph motivation, definition of done.
3. Every large task has a folder in `documentation/tasks/` with at minimum a `README.md`.
4. `open-tasks.md` is in `documentation/tasks/archive/` and its archive entry explains why.
5. `documentation/tasks/archive/todo-nnn-mapping.md` exists and maps every migrated `TODO-NNN` to its new slug.
6. A new contributor can open `documentation/tasks/00_index.md` and find a task to work on without reading any other file.

---

## Notes

- `documentation/tasks/2026-05-21_GitHub_ready/` and `documentation/tasks/2026-05-22_task_redesign/` are already large task folders and appear in `00_index.md`. They are not migrated from `open-tasks.md` — they predate it in the new structure.
- The `TODO-NNN` ID scheme is retired by this task. New tasks created after migration use `YYYY-MM-DD_<slug>` per `task_principles.md`. Existing code references to `TODO-NNN` remain valid indefinitely via `todo-nnn-mapping.md`.
