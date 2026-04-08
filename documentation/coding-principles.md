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
2. Each notebook must include a self-contained setup cell with deterministic repository-root discovery and import-path setup.
3. Add one markdown cell per major step with input/output intent.
4. Persist key tables at stable checkpoints, not only at notebook end.
5. Keep temporary exploratory cells separate from production cells.
6. Do not hardcode display-only row limits in notebooks (for example `.head(10)` before `display(...)`) unless explicitly required by the task.
7. Always expose real DataFrames to notebook viewers so sorting/filtering/search can operate on full data.
8. For network-backed workflows, test cache-first compatibility before new fetches whenever possible by running at least one validation pass with `max_network_calls=0`.

### Notebook Setup Conventions

1. Use a single code cell per action where possible.
2. Split work into multiple small cells where it improves followability of progress.
3. Insert markdown between action cells to explain what the next cell will do.
4. Keep bootstrap logic in the first setup cell(s), including repository-root/path discovery and import-path setup.
5. Never outsource notebook bootstrap/path-finding logic to process modules; the notebook must be able to initialize itself before importing project modules.

## Process Module Principles

1. Keep functions composable and side-effect-light where possible.
2. Prefer explicit schemas and column selection over implicit DataFrame assumptions.
3. Include confidence and parsing metadata for heuristic extraction logic.
4. Add helper functions for deduplication/reporting instead of ad hoc notebook logic.
5. Keep presentation concerns out of process modules: no hardcoded preview slices, sample limits, or UI-specific output shaping.

### Outsourcing To Python Files

1. Do not outsource notebook bootstrap/path-discovery logic to Python files.
2. Prefer Python files that are dedicated to a single primary task.
3. Secondary helper behavior in the same file should be limited to closely related save/load support.
4. Avoid broad multi-purpose modules when a focused task module is sufficient.

## Data Contract Principles

1. If a schema changes, update `contracts.md` in the same PR.
2. If output filenames change, update `workflow.md` and root `README.md` in the same PR.
3. Add or update validation cells whenever core parsing behavior changes.

## File Write Resilience Principles

1. Production writes must use guarded atomic helpers (temp file + replace) instead of direct `to_csv(...)` or `write_text(...)` calls.
2. Guarded writers must catch lock-related write failures (for example Windows `PermissionError`) and persist a recovery snapshot under a separate `*.recovery` filename.
3. After writing a recovery snapshot, fail fast with a clear stop message; do not continue processing with partially persisted state.
4. On the next run, guarded writers/loaders must detect recovery snapshots first, restore/merge them back into the primary file, and only then proceed.
5. New process modules must not introduce unguarded output writes; migrations of legacy direct writes should be tracked in `open-tasks.md`.
6. Exception for append-only event logs: JSONL event streams may use buffered append writes in the hot path (instead of full-file atomic rewrite) as long as flush-on-read and flush-on-close boundaries are enforced.

## Event-Sourcing Principles

1. When event sourcing is in place, treat the append-only event log as the source of truth and treat CSV/JSON outputs as projections, caches, or snapshots unless a file is explicitly defined as canonical input.
2. Prefer appending a domain event over mutating derived state in place; if a decision matters for replay, make it an event.
3. Rebuild derived state from events, not from other derived state, unless the derived file is explicitly a cache or stage-local convenience artifact.
4. Keep event append operations O(1) in the hot path; any required index, deduplication, or projection work should be incremental and flushed at clear boundaries.
5. Make projections idempotent and replay-safe; rerunning the same event slice should produce the same output bytes or a documented equivalent ordering.
6. Keep bootstrap and restart logic lazy and deterministic; do not require eager creation of empty sidecars when the runtime can create them on first write or restore.
7. On restart, revert, or snapshot restore, clear in-memory caches before loading from disk so stale state cannot outlive the event stream.
8. If a file is only a view of event data, do not use it as a write target in the hot loop.
9. If a new behavior cannot be reconstructed from events, it is not yet an event-sourced behavior and should be modeled before implementation.
10. Once event-backed or handler-backed projections exist for a workflow, remove mutable JSON sidecars and compatibility writes rather than preserving them as permanent runtime state.
11. Transitional sidecars are acceptable only until the last consumer has moved to replayable projections; at that point they become technical debt and should be deleted.
12. No future event-sourced architecture may ship without persistent handler progress tracking. Event handlers must persist at least `handler_name`, `last_processed_sequence`, `artifact_path`, and `updated_at` so incremental replay/resume remains deterministic and auditable.
13. Cached source pages and append-only event logs are immutable runtime assets: once downloaded/appended, they must not be deleted during normal notebook/process execution.
14. If a reset is needed for testing, delete only derived projections/artifacts; never delete cache or event history.
15. Every event-sourced workflow must provide checkpoint snapshots with dual-form restore support (directory and zip), include eventstore payload (`chunks/`, `chunk_catalog.csv`, `eventstore_checksums.txt`) plus runtime projections, keep append-only checkpoint timeline history, and enforce retention: 3 newest unzipped, one protected daily-latest zip per day, plus 7 newest additional zipped snapshots.

## Notebook Observability Principles

1. Production notebooks with network activity must emit append-only runtime events into `data/logs/notebooks/*.events.jsonl`.
2. Log schema must follow `documentation/notebook-observability.md`, including `notebook_id`, `run_id`, `phase`, `event_type`, `network`, `rate_limit`, and `budget` fields.
3. Logging must happen at the network decision boundary, not only for successful calls (cache-hit skip, budget block, retry/backoff, and errors must be visible).
4. Notebook heartbeats shown in cell output should summarize the same underlying event stream.
5. Heartbeats must be actionable: include recent event throughput, per-event-type counts, and the most recent event with payload snapshot.
6. Notebook pipeline cells must handle user interruption gracefully (`KeyboardInterrupt`) by stopping cleanly and emitting a final lifecycle status event instead of failing with a traceback-only exit.
7. Cross-notebook field names should remain stable so metrics are comparable across workflows.
8. Notebook event log writers must be corruption-tolerant: quarantine malformed JSONL lines to `*.corrupt.<timestamp>`, preserve valid history, append a repair event, and continue.

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
6. For network-backed changes, include evidence of a cache-only validation pass (`max_network_calls=0`) whenever feasible.
