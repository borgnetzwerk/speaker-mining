# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed

## Migration Triage Policy (v3)

- Preserve behavior that is already working in v2.
- Fix low-hanging issues when implementation is localized and low risk.
- Do not block migration rollout on known unsolved legacy issues.
- Validate v3 primarily on its own correctness guarantees (event integrity, determinism, recovery, handler correctness).
- When comparing v2 and v3 outputs, classify mismatches as:
  1. preserved behavior
  2. intentional low-hanging fix
  3. known unresolved legacy issue
  4. new regression (must fix before rollout)

## Priority Items

### WDT-007: Graceful notebook exit without hard interrupt corruption

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  Notebook execution currently depends on hard `CTRL+C` interruption, which can break writes in progress and leave partial runtime state.
- Requirements:
  1. Add a graceful termination path that does not rely on process-kill semantics.
  2. Use a cooperative stop signal checked during long loops (for example a shutdown marker file or equivalent runtime flag).
  3. Ensure write paths complete atomic sections before exit.
  4. Emit a clear stop reason in checkpoint/event logs when graceful termination is requested.
- Acceptance criteria:
  1. User can request termination without forcing `KeyboardInterrupt`.
  2. Run exits at a safe boundary with deterministic state.
  3. No partial-write corruption appears in projections or event chunks after graceful stop.

### WDT-008: Restore runtime heartbeat and operator progress visibility

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  Heartbeat/progress output regressed, reducing operator visibility during long Stage A runs.
- Requirements:
  1. Restore periodic progress heartbeat during graph expansion and integrity/fallback stages.
  2. Report at minimum: current seed, network calls used, elapsed time, and approximate rate.
  3. Keep output cadence configurable (reuse existing progress settings where possible).
  4. Preserve low overhead so heartbeat logging does not materially slow runtime.
- Acceptance criteria:
  1. Long-running notebook cells produce regular status output without waiting for stage completion.
  2. Heartbeat output is present in Notebook 21 and useful for operational monitoring.
  3. Progress output remains stable across append/restart/revert modes.
* note: the eventsourcing should theoretically provide plenty of information for the heartbeat to communicate what happened in the last minute. But due to Issues such as WDT-009, many events that should be logged are currently not logged. While this is the case, we can't really unlock the full potential of the heartbeat.

### WDT-009: Expand event model beyond query_response (deferred)

- Status: [ ]
- Priority: P1
- Owner: unassigned
- Problem:
  Event sourcing remains underused because runtime currently persists mostly `query_response` events and misses many durable decision events.
- Requirements:
  1. Define and emit domain events for persistent decisions with future implications.
  2. Candidate minimum set: `entity_discovered`, `entity_expanded`, `triple_discovered`, `class_membership_resolved`, `expansion_decision`, and eligibility transition events.
  3. Add replay/invariant tests proving these events are sufficient for deterministic analysis and projection diagnostics.
  4. Keep `query_response` for provenance, but do not rely on it as the only event type.
- Acceptance criteria:
  1. Event stream contains domain events that capture runtime decisions and state transitions.
  2. Heartbeat and statistical summaries can be derived from recent domain events.
  3. Diagnostic analytics no longer depend on ad-hoc reconstruction from query payloads alone.
- Delivery note:
  This is explicitly a later-wave task and is not expected to be fully resolved this month.

### WDT-006: Checkpoint snapshots must preserve and restore eventlog state

- Status: [x]
- Priority: P0
- Owner: unassigned
- Problem:
  Checkpoint snapshots currently risk diverging from the actual event-sourced state because eventstore chunk history is not treated as first-class snapshot data.
- Requirements:
  1. Snapshot must include eventstore artifacts (`chunks/`, `chunk_catalog.csv`, `eventstore_checksums.txt`).
  2. Restore/revert must clear current eventstore artifacts and restore them from the selected checkpoint snapshot.
  3. Regression tests must prove that events appended after checkpoint A are absent after reverting to checkpoint A.
  4. Keep resume semantics deterministic across append, restart, and revert.
- Acceptance criteria:
  1. Revert to previous checkpoint removes post-checkpoint query events from the active eventlog.
  2. Snapshot/restore preserves eventstore chunk continuity for resumed runs.
  3. Existing checkpoint tests still pass, plus new eventlog-restore regression coverage.
  4. Notebook 21 resume/revert behavior stays consistent with restored event history.
- Implementation notes (2026-04-02):
  - Completed: checkpoint snapshot/restore now copies and restores eventstore artifacts.
  - Completed: added checkpoint regression test for eventlog restore on revert.
  - Completed: snapshot retention policy now keeps 3 newest unzipped snapshots, compresses older snapshots, preserves daily-latest zipped snapshots, and caps additional zipped snapshots to 7.
  - Completed: each snapshot now stores its checkpoint manifest copy so manifest metadata is included in snapshot zips.
  - Completed: checkpoint creation history now appends to `checkpoints/checkpoint_timeline.jsonl` (JSONL creation log).

### WDT-001: Re-evaluate prior eligibility decisions when class lineage improves

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  Nodes previously marked as not eligible may become eligible once new subclass paths to core classes are discovered.
- Requirements:
  1. Recompute eligibility on all persisted known nodes each integrity pass.
  2. Detect state transitions from ineligible -> eligible.
  3. Trigger expansion for newly eligible, not-yet-expanded nodes.
  4. Persist audit evidence for each transition.
- Acceptance criteria:
  1. A node that becomes connected via `P279` to a core class is reclassified within the next integrity pass.
  2. The node is expanded in that same pass if not already expanded.
  3. A persistent diagnostics record captures old/new status and evidence path.

### WDT-002: Persist reclassification diagnostics for longitudinal analysis

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  We need durable evidence to identify recurring integrity failures and code hotspots.
- Requirements:
  1. Write per-run diagnostics artifacts that include all eligibility transitions.
  2. Include node id, previous reason, new reason, path-to-core-class, run id, and timestamp.
  3. Keep output append-only at run granularity.
- Acceptance criteria:
  1. Each run produces a transition artifact when transitions occur.
  2. Artifacts are stored in a stable path under `data/20_candidate_generation/wikidata/node_integrity`.
  3. Documentation artifacts are mirrored under `documentation/context/node_integrity`.

### WDT-003: Add regression tests for reclassification edge cases

- Status: [ ]
- Priority: P1
- Owner: unassigned
- Problem:
  Reclassification behavior can silently regress if not covered by tests.
- Requirements:
  1. Add tests for delayed class discovery (`Q5` style path discovered later).
  2. Add tests for no-op integrity pass when no transition occurs.
  3. Add tests that prevent duplicate expansion of already expanded nodes.
- Acceptance criteria:
  1. Tests fail when reclassification logic is disabled.
  2. Tests pass when integrity pass reclassifies and expands correctly.

### WDT-004: Data is wrongly fetched for all langauges, despite us only needing german, english and default.
* Status: [x]
* by default, when accessing wikidata, only the "default for all langauges" should always be loaded
* additional languages need to be explicitly specified - labels, descriptions, aliases and alike in a language that is not specified should never be pulled
* The goal would be an initial specification of required languages. This should be a list where the user can easily change any language from false to true. By default, every language should be set to false. If this state is loaded, it should throw an error "Please define at least one language".
  * For our case, every run will only proceed with "en" and "de". Still, the user should specify exactly this themselves.
* Implementation notes (2026-04-02):
  * Added explicit language-selection policy via `set_active_wikidata_languages(...)`.
  * Notebook config now contains `wikidata_entity_languages` with all flags `False` by default and raises `ValueError("Please define at least one language")` when unresolved.
  * Entity/property payloads are filtered to selected languages plus `mul` before downstream processing.

### WDT-005: Not only default language aliases are added, but also all others
* Status: [x]
* There seems to be a bug in the current implementation of alias appending (see `documentation\context\findings-assets\wrong_alias_appending.csv`)
  * The intention was the following:
    * we fetch the label, description and aliases for our specified languages 
      * currently: 2 languages, "en" and "de", so we would have:
        * label_en
        * desciption_en
        * alias_en
        * label_de
        * desciption_de
        * alias_de
    * We then also fetch the "default for all languages"
      * for every specified language label and description field, we check if its empty. for example:
        * label_en: empty -> replace with "default for all languages" label
        * desciption_en: not empty -> don't replace with "default for all languages"
      * for the alias fields, we just append the alias from "default for all languages"
        * alias_en: ["...", "..."] -> ["...", "...", "first_alias_form_default_for_all_languages", "second_alias_form_default_for_all_languages", ...]
  * instead of that intended behaviour, all language alias are appended to all aliases. This is wrong.
* Implementation notes (2026-04-02):
  * Fixed alias aggregation in materializer: each alias field now uses only `alias_<lang>` + `alias_mul`.
  * Removed cross-language alias leakage (`mapping.values()` merge across all languages).
  * Added regression tests for alias fallback and language filtering.




## Notes

- This tracker is dedicated to Wikidata workflow internals and avoids overlap with OpenRefine/Wikidata Reconciliation Service terminology.


