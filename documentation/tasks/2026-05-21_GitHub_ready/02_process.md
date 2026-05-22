# Process: Executing the GitHub-Ready Synthesis

## Before starting any session

1. Read `01_vision.md` — internalize the target artifacts and knowledge taxonomy.
2. Read `PROGRESS.md` — find the current folder and file position. The `## Current position`
   section names the next unprocessed file. Start there.
3. Read `tasks/00_index.md` — active tasks represent specific high-priority transformations
   already scoped. Do not re-scope them; just note when a file is covered by a task.

---

## Per-file procedure

### Step 1: Read

Read the file completely. Not the filename — the contents. Do not skip sections.

### Step 2: List knowledge

Before writing anything, scan the full file and identify what it contains. For each
distinct piece, write one line:
```
[TYPE] <brief description> → <target artifact path>
```
Use the symbols from `01_vision.md`: PF, DD, FT, LL, DF, PR, CR, VP, DC, PC.

**Why not a JSONL file?** `documentation_synthesis/catalogue.jsonl` already provides
937 classified findings from 571 files — that is the structured evidence base. This
process consumes it; it does not rebuild it. Use `data/clusters/*.md` as a per-type
lookup when scanning a file. If the catalogue is missing a finding, note it in
`PROGRESS.md`; do not maintain a parallel JSONL.

For large automated batch runs, an optional `extraction_log.jsonl` (fields: `file`,
`type`, `summary`, `target`, `process_version`) enables auditing of what went where.

### Step 3: Extract

Consult the **Folder inventory** in `01_vision.md` to confirm where this file's knowledge
belongs in the final structure. If the target folder does not yet exist (`ZDF/`,
`analysis/`, `tasks/`), create it when writing the first piece of knowledge into it.

For each piece of knowledge:

- **Already in a target artifact?** → mark as covered; no action. **HARD RULE:** you must
  cite the specific TODO-XXX number, or the exact file path and section, that contains this
  knowledge. The phrase "already in open-tasks.md" or "already in documentation" with no
  citation is forbidden — it is an unverified claim, not evidence. If you cannot cite the
  specific location after reading the target artifact, the knowledge is missing; write it in.
- **Missing from a target artifact?** → write it in now, directly into the target artifact.
  If the knowledge requires a code change to be useful (e.g., a design decision about
  code that hasn't been written yet), write a task file instead.
- **Needs a task file?** → check `tasks/00_index.md`. If a task already covers it, note
  the task ID. If not, create `tasks/T<NN>_<slug>.md` and add it to the index.

Never write paper-framing language into target artifacts. Rewrite in pipeline-neutral terms.

### Step 4: Assess disposal

Choose exactly one from `01_vision.md`: Extracted / Redundant / Archive / Task / Keep / Partial.

Apply the criteria strictly. When in doubt, choose Partial.

### Step 5: Log in PROGRESS.md

Under the current folder's section, add one line:
```
- [Disposition] `relative/path/to/file` — <what was extracted, or why this disposition> (Vn)
```

Include the current process version `(Vn)` at the end of each entry. This makes it
possible to identify files processed before a taxonomy update that may need a second pass.

Then update `## Current position` to point to the next file.

### Step 6: Process check (after every file)

Ask:
- **New knowledge type encountered?** → Update `01_vision.md` taxonomy. Increment the
  process version in `PROGRESS.md → ## Process version history`. Identify files already
  logged at the previous version where the new type could plausibly apply; mark them
  `Partial` and add them back to the work queue. A file cannot be marked `Extracted`
  if it was processed at a version that lacked a type that could apply to it.
- **Knowledge with no clear target artifact?** → Either update `01_vision.md` or create
  a task. Do not leave it unresolved.
- **Process itself unclear or incomplete?** → Update this document before moving on.

---

## Per-folder checkpoint

After processing all files in a folder:

1. If every file is `Extracted`, `Redundant`, `Archive`, or `Task` at the current
   process version → add the folder path to `## Folders ready for delete` in `PROGRESS.md`.
2. If any file is `Keep` or `Partial` → note this in `PROGRESS.md`; the folder stays.
3. Review: does the process need to evolve? Update this document before moving on.

---

## Process versioning

When the taxonomy or process steps change materially:

1. Increment the version label: V1 → V2 → etc.
2. Record the change and date in `PROGRESS.md → ## Process version history`.
3. Identify files already logged at a lower version that could have yielded a finding
   under the new type. Mark them `Partial` and append them them to the back of the work queue.

**Rule:** a file cannot be marked `Extracted` if it was processed at a version that
did not include a knowledge type that could plausibly apply to it.

---

## Folder processing order

Work through folders in this sequence. The order moves from most-uncertain to most-stable.

### Step A: All documentation/tasks/ subfolders (formerly documentation/ToDo/)

Every subfolder of `documentation/tasks/` is accounted for below. None are skipped
silently — each has a declared treatment.

Note: `documentation/tasks/` was renamed from `documentation/ToDo/` on 2026-05-22.
Historical PROGRESS.md log entries still reference the old `documentation/ToDo/` path —
this is intentional (they document what happened at that time).

| Subfolder | Treatment |
|---|---|
| `archive/` | **Complete.** Process: extract surviving knowledge; mark files for delete |
| `2026-04-18 Rework/` | **Complete.** Empty folder — deleted |
| `2026-05-15_Speaker_Mining_Paper/` | **Complete.** Redundant — deleted |
| `2026-05-17_Speaker_Mining_Paper/` | **Complete.** Redundant — deleted |
| `DOC/` | **Complete.** Empty folder — deleted |
| `peer_review_paper/` | **Complete.** Redundant — deleted |
| `documentation_synthesis/` | **Complete.** Archived to `documentation/archive/documentation_synthesis/` |
| `visualization_references/` | **Partial.** T01 complete; human delete queue |
| `2026-05-21_GitHub_ready/` | **Active.** This is the synthesis coordination folder itself |
| `open_additional_input.md` | **Complete.** Redundant; no current human input |

### Step B: Remaining folders (after all ToDo/ subfolders)

1. `documentation/context/` — eventsourcing notes, jsonl notes, alias files
2. `documentation/Wikidata/archive/` — full Wikidata transition history
3. `documentation/31_entity_disambiguation/archive/` — phase-specific archived records
4. `documentation/fernsehserien_de/` — scraping specification and QA notes
5. `documentation/50_Analysis/` — temporal analysis output folder
6. `speakermining/src/` — read-only pass: extract design decisions, TODOs, docstrings.
   No code edits. Every finding here that needs code action becomes a task.
7. `documentation/phases/` — synthesis input to dissolve; extract content into source
   subfolders (`ZDF/`, `Wikidata/`, `fernsehserien_de/`, `analysis/`) then mark for delete
8. `documentation/` root files — final pass: verify all target artifacts are complete

Within each folder: process files in alphabetical order unless dependency is obvious.

---

## Ready-for-delete management

`PROGRESS.md` maintains two append-only lists:

- `## Files ready for delete` — individual files fully processed (`Extracted` or `Redundant`)
- `## Folders ready for delete` — entire folders where every file is on the file list

Do not delete anything yourself. These lists are the human's deletion queue.

A file moves to the folder list only when every file within it is on the file list.
Subfolders count as files for this purpose — a folder is only ready when all its
contents (files and subfolders) are on the list.

---

## Resumption

If work pauses mid-folder:
1. `PROGRESS.md → ## Current position` names the next unprocessed file.
2. Continue from that file, in the same folder.
3. The folder order in this document is authoritative for cross-folder sequencing.
4. The session-start checklist at the top of this document is the entry point every time.
