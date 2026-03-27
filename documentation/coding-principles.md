# Coding Principles

This page defines repository-level engineering practices for notebooks and process modules.

Governance reference model:

- Authoritative execution order and phase ownership source: `workflow.md`
- Authoritative architecture and module map source: `repository-overview.md`
- Authoritative output contract source: `contracts.md`
- Authoritative work tracking source: `open-tasks.md`
- Authoritative findings and evidence source: `findings.md`

## Guiding Principles

1. Precision over recall for automated extraction unless explicitly discussed and documented.
2. Traceability over convenience: keep parsing rule and confidence fields where relevant.
3. Reproducibility over hidden state: notebooks should be runnable top-to-bottom in order.
4. Clear phase ownership: no writes outside the phase output directory.

## Notebook Principles

1. Notebooks orchestrate; core transformation logic lives in `speakermining/src/process` modules.
2. Use deterministic path discovery (`find_repo_root`) and explicit imports.
3. Add one markdown cell per major step with input/output intent.
4. Persist key tables at stable checkpoints, not only at notebook end.
5. Keep temporary exploratory cells separate from production cells.

## Process Module Principles

1. Keep functions composable and side-effect-light where possible.
2. Prefer explicit schemas and column selection over implicit DataFrame assumptions.
3. Include confidence and parsing metadata for heuristic extraction logic.
4. Add helper functions for deduplication/reporting instead of ad hoc notebook logic.

## Data Contract Principles

1. If a schema changes, update `contracts.md` in the same PR.
2. If output filenames change, update `workflow.md` and root `README.md` in the same PR.
3. Add or update validation cells whenever core parsing behavior changes.

## Documentation Principles

1. `workflow.md` is the authoritative source for execution order and phase ownership.
2. `repository-overview.md` is the authoritative source for architecture and module mapping.
3. `contracts.md` is the authoritative source for output files and schema contracts.
4. `open-tasks.md` is the authoritative source for open and solved work items.
5. `findings.md` is the authoritative source for aggregated analysis and evidence.
6. If a governed topic is mentioned in another document, reference its authoritative file instead of duplicating long operational lists.

## Minimal Quality Checklist For Contributions

1. Notebook paths and order still valid.
2. No phase writes outside owned `data/<phase>` folder.
3. CSV headers still match contract docs or contract docs updated.
4. New work item entered in `open-tasks.md`.
5. Remaining work entered in `open-tasks.md`.
