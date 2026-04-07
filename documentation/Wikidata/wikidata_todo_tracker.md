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

### WDT-010: clear differentiation between "core classes" and "root classes"
Person, Organization, Episode - those are core classes. They are what we are intrerested in

Entity - thats a root class. Very likely, everything is a subclass or instance of this. Conflating a root class with a core class could mean we're exploring thousands of nodes and their neighbors despite us actually not being interested in them.

we need a dedicated cell early in the notebook to clear all those conflations and missconcptions up.

### WDT-011: Full eventsourcing implementation identification
Actual everntsourcing could be identified by a notebook (excluding setup) mostly being one line of code: start event handlers. everything else would be them resolving the event log and their respective reactions

### WDT-012: Low Hanging fruit: We could use more projections
* One projection per core class for all instance of that core class.
* One projection for all leftover instances that are neither classes nor instances of a core class.

### WDT-013: Transition from CSV to Parquet 
* CSVs are particularly bad at handling Lists. This is a problem for columns such as "Guests" or "Topcis"
* As the input for Phase 3, we need a CSV file. Everywhere else, we can use Parquet instead of CSVs.

### WDT-014: Deprecate any non-eventsourced file writing.
Everything that writes to a file should be eventsourced. There is plenty of code labeled "materialize" or similar that just recreates entire csv files without doing proper Event-Sourcing. Entire files are rebuild over and over again despite non of the events they are build from having changed. Some examples:

[notebook] Step 6 start: graph-first expansion
Target rows from episodes.csv: 27390
[notebook] -> run_graph_expansion_stage
[graph_stage] Starting graph expansion stage
[graph_stage] Resume mode=append has_checkpoint=True
[graph_stage] Seed 12/12 start qid=Q2108918
[graph_stage] Seed 12/12 done stop_reason=queue_exhausted network_queries=0 elapsed=59.43s
[graph_stage] Materialize checkpoint start
[materializer] Start stage=checkpoint:2026-04-07T09:52:49Z run_id=20260402T194346Z_4f3e95f1
[materializer] build instances done in 34.53s
[materializer] build classes done in 0.22s
[materializer] build properties done in 0.00s
[materializer] build aliases done in 1.03s
[materializer] build triples done in 1.28s
[materializer] build class_hierarchy done in 28.98s
[materializer] build query_inventory done in 0.37s
[materializer] write csv artifacts done in 0.78s
[materializer] Completed stage=checkpoint:2026-04-07T09:52:49Z in 67.21s
[materializer][warning] Stage checkpoint:2026-04-07T09:52:49Z exceeded 20s target (67.21s)
[graph_stage] Materialize checkpoint done in 67.34s
[graph_stage] Final materialization start
[materializer] Start stage=final run_id=20260402T194346Z_4f3e95f1
[materializer] build instances done in 36.16s
[materializer] build classes done in 0.21s
[materializer] build properties done in 0.00s
[materializer] build aliases done in 1.02s
[materializer] build triples done in 1.29s
[materializer] build class_hierarchy done in 30.77s
[materializer] build query_inventory done in 0.04s
[materializer] write csv artifacts done in 0.74s
[materializer] Completed stage=final in 70.24s
[materializer][warning] Stage final exceeded 20s target (70.24s)
[graph_stage] Final materialization done in 70.37s
[graph_stage] Completed graph expansion stage in 221.72s with total_queries=1043

[notebook] Step 6 complete
[notebook] Step 6 elapsed seconds: 222.04
Execution Summary:
==================================================
  seed_id                        None
  instances_rows                 13737
  classes_rows                   4114
  properties_rows                221
  triples_rows                   209793
  query_inventory_rows           6811
  run_id                         20260402T194346Z_4f3e95f1
  resume_mode                    append
  resume_has_checkpoint          True
  seeds_completed                11
  seeds_remaining                1
  stop_reason                    queue_exhausted
  total_nodes_discovered         342
  total_nodes_expanded           1
  total_queries                  1043
  stage_a_network_queries        1043
  total_queries_before_run       1043
  stage_a_network_queries_this_run 0
  start_seed_index               11
  seed_count                     12
  stage_elapsed_seconds          221.72


### WDT-015 Query easier for Wikidata
We currently have about 80.000 queries to Wikidata pending (see context below).
Most of these queries are of the same nature: minimal payload restored.
This means that currently, we send Wikidata 80.000 almost identical queries for all of these items to retrieve the bare minimum of data.
This is both slow (~30 hours) as well as probably not the best way wikidata could handle our request. There mus be a better way that is better for both services: Both wikidata, by processing a bunch of similar queries without the overhead of processing each query individually, as well as us, by progressing faster.

Context below:

[notebook] Step 6.5 start: node integrity pass
[notebook] Step 6.5 budget planning: stage_a_queries_this_run=0, node_integrity_budget=unlimited
[node_integrity:discovery] Network calls used: 26 / unlimited elapsed=60.1s rate=25.97/min
[node_integrity:discovery] heartbeat: checked=36 pending=87784 known=87820 repaired=28 newly_discovered=28
[node_integrity:discovery] example: minimal payload restored for Q100154476 -> label="How Propaganda Works"; p31=Q47461344; p279=<none>
[node_integrity:discovery] Network calls used: 50 / unlimited elapsed=88.9s rate=33.75/min
[node_integrity:discovery] heartbeat: checked=100 pending=87738 known=87838 repaired=78 newly_discovered=78
[node_integrity:discovery] example: minimal payload restored for Q100382 -> label="Johannes Kreidler"; p31=Q5; p279=<none>
[node_integrity:discovery] Network calls used: 98 / unlimited elapsed=149.8s rate=39.26/min
[node_integrity:discovery] Network calls used: 100 / unlimited elapsed=152.2s rate=39.43/min
[node_integrity:discovery] heartbeat: checked=168 pending=87683 known=87851 repaired=132 newly_discovered=132
[node_integrity:discovery] example: minimal payload restored for Q1006733 -> label="Grasland"; p31=<none>; p279=Q101998,Q2083910
[node_integrity:discovery] Network calls used: 150 / unlimited elapsed=212.2s rate=42.41/min
[node_integrity:discovery] heartbeat: checked=226 pending=87634 known=87860 repaired=183 newly_discovered=183
[node_integrity:discovery] example: minimal payload restored for Q100783589 -> label="Wirtschaft Sachsen-Anhalts"; p31=Q100773131; p279=Q8046
[node_integrity:discovery] Network calls used: 199 / unlimited elapsed=273.1s rate=43.72/min
[node_integrity:discovery] Network calls used: 200 / unlimited elapsed=274.3s rate=43.75/min
[node_integrity:discovery] heartbeat: checked=293 pending=87578 known=87871 repaired=239 newly_discovered=239
[node_integrity:discovery] example: minimal payload restored for Q10092859 -> label="Kategorie:Politische Macht"; p31=Q4167836; p279=<none>
[node_integrity:discovery] Network calls used: 249 / unlimited elapsed=335.4s rate=44.55/min
[node_integrity:discovery] Network calls used: 250 / unlimited elapsed=336.6s rate=44.56/min
[node_integrity:discovery] heartbeat: checked=361 pending=87518 known=87879 repaired=292 newly_discovered=292
[node_integrity:discovery] example: minimal payload restored for Q101247458 -> label="FAO representation in Kenya"; p31=Q245065; p279=<none>
[node_integrity:discovery] Network calls used: 300 / unlimited elapsed=396.9s rate=45.35/min
[node_integrity:discovery] heartbeat: checked=426 pending=87462 known=87888 repaired=346 newly_discovered=346
[node_integrity:discovery] example: expanded class frontier from Q101565734: +1 class qids
[node_integrity:discovery] Network calls used: 350 / unlimited elapsed=457.3s rate=45.92/min
[node_integrity:discovery] heartbeat: checked=485 pending=87416 known=87901 repaired=402 newly_discovered=402
[node_integrity:discovery] example: minimal payload restored for Q10185 -> label="Berliner Zeitung"; p31=Q1110794; p279=<none>
[node_integrity:discovery] Network calls used: 400 / unlimited elapsed=517.4s rate=46.39/min
[node_integrity:discovery] heartbeat: checked=559 pending=87354 known=87913 repaired=461 newly_discovered=461
[node_integrity:discovery] example: minimal payload restored for Q102139 -> label="Margrethe II."; p31=Q5; p279=<none>
[node_integrity:discovery] Network calls used: 450 / unlimited elapsed=577.4s rate=46.76/min
[node_integrity:discovery] heartbeat: checked=623 pending=87302 known=87925 repaired=519 newly_discovered=519
[node_integrity:discovery] example: minimal payload restored for Q1023141 -> label="CDU Hamburg"; p31=Q18744396; p279=<none>
[node_integrity:discovery] Network calls used: 500 / unlimited elapsed=637.5s rate=47.06/min
[node_integrity:discovery] heartbeat: checked=686 pending=87255 known=87941 repaired=571 newly_discovered=571
[node_integrity:discovery] example: minimal payload restored for Q102542 -> label="Julius Lehr"; p31=Q5; p279=<none>
[node_integrity:discovery] Network calls used: 550 / unlimited elapsed=697.6s rate=47.30/min
[node_integrity:discovery] heartbeat: checked=752 pending=87205 known=87957 repaired=623 newly_discovered=623
[node_integrity:discovery] example: minimal payload restored for Q102775317 -> label="Katharina Eck"; p31=Q5; p279=<none>
[node_integrity:discovery] Network calls used: 600 / unlimited elapsed=757.8s rate=47.50/min
[node_integrity:discovery] heartbeat: checked=815 pending=87153 known=87968 repaired=675 newly_discovered=675
[node_integrity:discovery] example: expanded class frontier from Q1029421: +3 class qids
[node_integrity:discovery] Network calls used: 650 / unlimited elapsed=818.0s rate=47.68/min

## Notes

- This tracker is dedicated to Wikidata workflow internals and avoids overlap with OpenRefine/Wikidata Reconciliation Service terminology.


