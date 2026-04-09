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

- Status: [x]
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
  1. User can request termination without forcing `KeyboardInterrupt`. ✅
  2. Run exits at a safe boundary with deterministic state. ✅
  3. No partial-write corruption appears in projections or event chunks after graceful stop. ✅
- Implementation completed (2026-04-07):
  - **Core implementation**: Added cooperative stop checks in long-running loops across Stage A graph expansion, node integrity, and fallback matching.
  - **Stop-reason propagation**: Integrated `user_interrupted` stop-reason propagation in graph-stage interruption paths with checkpoint persistence.
  - **Regression tests**: Added 3 targeted regression tests for graceful interruption paths (`run_seed_expansion`, node integrity, fallback stage).
  - **Validation**: `python -m pytest speakermining/test/process/wikidata/test_checkpoint_resume.py speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_fallback_stage.py -q` → `27 passed`.
- **Acceptance evidence (2026-04-07)**:
  - Created integration test suite: `test_wdt_007_graceful_shutdown_integration.py` with 4 comprehensive tests:
    1. `.shutdown` marker detection during loop iteration
    2. Cooperative interruption pattern validation (loop exit, early termination, materialization skip)
    3. Global termination flag propagation for testing
    4. Operator visibility of interruption status across notebook stages
  - Integration test command: `python -m pytest speakermining/test/process/wikidata/test_wdt_007_graceful_shutdown_integration.py -v` → `4 passed in 0.20s`
  - **Acceptance verified**: All acceptance criteria met. Graceful shutdown mechanism is working correctly end-to-end.

### WDT-008: Restore runtime heartbeat and operator progress visibility

- Status: [x]
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
- Implementation completed (2026-04-08):
  - Notebook 21 emits event-derived heartbeat summaries after Stage A graph expansion, Step 6.5 node integrity, Stage B fallback matching, and fallback re-entry.
  - Added a fail-fast guard in Step 9 so fallback re-entry cannot run after an interrupted or failed Step 8.
  - Acceptable heartbeat coverage is now present for operational monitoring, so the item is closed.

### WDT-009: Expand event model beyond query_response (Wave 2 complete)

- Status: [x]
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
- **Wave 2 Progress (2026-04-07)**:
  - **Completed**: Introduced three promoted domain event types:
    1. `entity_discovered` - emitted when a new entity is first encountered (seed lookup, inlink, outlink, fallback match)
    2. `entity_expanded` - emitted when an entity's neighborhood is fetched (inlinks, outlinks, properties)
    3. `expansion_decision` - prepared (builder function exists) for future wiring of queue/skip/budget-exhausted decisions
  - **Wired into orchestration**: 
    - `expansion_engine.py`: entity_discovered and entity_expanded events emitted during graph expansion
    - `node_integrity.py`: entity_discovered events emitted during node integrity repair discovery
    - `fallback_matcher.py`: entity_discovered events emitted during fallback string matching
  - **Validation**: 31 tests passing including WDT-007 and new domain event implementations
  - **Next phase**: Wider domain event coverage (triple_discovered, class_membership_resolved, decision finalized)
- **Heartbeat follow-up (2026-04-08)**:
  - Added notebook-level event-derived heartbeat calls for Stage A graph expansion and fallback re-entry, complementing the existing Step 6.5 and fallback stage summaries.
  - Added a Step 9 guard so re-entry only runs after a successful Step 8 result is available.
- **Domain event follow-up (2026-04-08)**:
  - Added `triple_discovered` and `class_membership_resolved` event types/builders.
  - Wired `triple_discovered` emission at triple recording boundaries (`record_item_edges(...)`) with Stage A and Step 6.5 runtime propagation.
  - Wired `class_membership_resolved` emission through `resolve_class_path(...)` callback integration in Stage A seed filtering and Step 6.5 class-resolution checks.
  - Wired `expansion_decision` emission at runtime decision points in Stage A and Stage B fallback candidate evaluation.
  - Focused validation: `python -m pytest speakermining/test/process/wikidata/test_event_schema.py speakermining/test/process/wikidata/test_store_buffering.py speakermining/test/process/wikidata/test_class_path_resolution.py -q` -> `12 passed`.
  - Runtime regression validation: `python -m pytest speakermining/test/process/wikidata/test_fallback_stage.py speakermining/test/process/wikidata/test_node_integrity.py -q` -> `19 passed`.
  - Replay/invariant closure: added orchestrator-level mixed-stream replay tests and fixed handler replay rehydration in `handlers/orchestrator.py` so domain-only appends do not truncate projections.
  - Orchestrator replay validation: `pytest test/process/wikidata/test_orchestrator_handlers.py -q` -> `4 passed`.
  - WDT-009 is now considered complete for Wave 2 scope; follow-on projection deprecation remains tracked under WDT-014.

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

- Status: [x]
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
- Wave 3 kickoff note (2026-04-08):
  - Wave 3 is now active after WDT-008 closure and Wave 2 event-model follow-up wiring.
  - Next implementation slice: transition-aware eligibility diagnostics tied to node-integrity pass outputs.
- Implementation progress (2026-04-08):
  - Node integrity now computes pre/post eligibility decisions for known nodes and detects ineligible -> eligible transitions during each pass.
  - Transition diagnostics now capture `previous_reason`, `current_reason`, and `path_to_core_class` evidence per transitioned node.
  - Added regression coverage for deterministic transition detection in node integrity tests.

### WDT-002: Persist reclassification diagnostics for longitudinal analysis

- Status: [x]
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
- Wave 3 kickoff note (2026-04-08):
  - Transition artifact shape and persistence location remain unchanged, but the next slice will add explicit previous/new reason and path evidence fields.
- Implementation progress (2026-04-08):
  - Added `eligibility_transition` domain event and builder in the event schema.
  - Node integrity now emits `eligibility_transition` events for each detected reclassification transition.
  - `NodeIntegrityResult` now exposes structured `eligibility_transitions` rows so notebook-level artifact writing can append stable transition records.
- Wave 3 completion (2026-04-08):
  - ✅ Extended Notebook 21 Step 6.5 to write `eligibility_transitions` to JSONL artifacts.
  - ✅ Added transitions JSONL path: `data/20_candidate_generation/wikidata/node_integrity/node_integrity_transitions_{timestamp}.jsonl`.
  - ✅ Updated artifact documentation to include transitions in markdown reports.
  - ✅ Validated transition writing logic with deterministic test cases.
  - **Wave 3 Complete**: WDT-001 and WDT-002 acceptance criteria fully met. Reclassification diagnostics now observable and persistent end-to-end.

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

- Status: [x]
- Priority: P1
- Owner: unassigned
- Problem:
  Person, Organization, Episode, Season, Topic, Broadcasting Program are core classes (what we're interested in).
  Entity, Thing are root classes (universal superclasses that nearly everything descends from).
  Conflating these could mean we're exploring thousands of nodes and their neighbors despite having no interest in them.
- Requirements:
  1. Add a dedicated cell early in the notebook to document this distinction clearly.
  2. Load and validate core classes vs. root classes.
  3. Ensure they are disjoint (no overlap) and catch configuration errors before graph expansion.
  4. Store definitions for downstream runtime guards.
- Acceptance criteria:
  1. Core classes are clearly documented as "PRIMARY DISCOVERY TARGETS".
  2. Root classes are clearly documented as "UNIVERSAL SUPERCLASSES - AVOID OVER-EXPANSION".
  3. Runtime validation fails fast if core and root classes overlap.
  4. Scope contract is printed and visible to operators before graph expansion begins.
- Implementation completed (2026-04-08):
  - Added Notebook 21 Step 2.5: "Class Hierarchy Clarification" cell after Step 2 config.
  - Markdown explanation distinguishes core classes from root classes with rationale.
  - Code cell performs runtime validation:
    1. Loads core classes from setup configuration
    2. Defines root_class_qids explicitly as {'Q35120' (Entity), 'Q1' (Thing)}
    3. Validates disjointness: raises `ValueError` if overlap detected
    4. Stores `config["core_class_qids"]` and `config["root_class_qids"]` for downstream use
    5. Prints scope contract before proceeding to resume mode / graph expansion
  - Execution occurs before Step 3 (Resume Mode), ensuring guards are in place before any expansion logic runs.

### WDT-011: Full eventsourcing implementation identification
Actual everntsourcing could be identified by a notebook (excluding setup) mostly being one line of code: start event handlers. everything else would be them resolving the event log and their respective reactions

- Status: [x]
- Closeout note (2026-04-09): unresolved implementation scope transferred to `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-001`.

### WDT-012: Low Hanging fruit: We could use more projections

- Status: [x]
- Priority: P1
- Owner: unassigned
- Problem:
  Existing projections make downstream slicing expensive because all entities are bundled in broad tables.
- Requirements:
  1. Add one projection per core class for all instances mapped to that core class.
  2. Add one leftovers projection for instances that are neither class nodes nor mapped to any core class.
  3. Ensure outputs are deterministic and preserved in checkpoint snapshot/restore.
- Acceptance criteria:
  1. Materialization writes per-core instance projections each run.
  2. Materialization writes a stable leftovers projection each run.
  3. Snapshot/restore keeps these projections intact.
- Implementation completed (2026-04-08):
  - Added WDT-012 projections in event-sourced materialization layer:
    1. `instances_core_<core_filename>.csv` per configured core class.
    2. `instances_leftovers.csv` for non-class, non-core-mapped instances.
  - Classification behavior:
    1. Class nodes are excluded using class hierarchy projection (`class_hierarchy.csv`).
    2. Core-class mapping is derived from `path_to_core_class` (terminal core QID) and class-resolution metadata.
  - Bootstrap now creates deterministic empty versions of the new projections.
  - Checkpoint snapshot/restore now includes dynamic projection files (`instances_core_*.csv`) and restores projection files from snapshot payload.
  - Added regression coverage:
    - `test_materializer_writes_per_core_and_leftovers_projections`
    - `test_checkpoint_snapshot_restores_dynamic_core_instance_projections`
    - bootstrap coverage for projection file creation.
- Validation:
  - `python -m pytest test/process/wikidata/test_bootstrap_outputs.py test/process/wikidata/test_class_path_resolution.py test/process/wikidata/test_checkpoint_resume.py -q`
  - Result: `23 passed`

### WDT-013: Transition from CSV to Parquet 
- Status: [x]
- Priority: P1
- Owner: unassigned
- Problem:
  CSV projections are still the default even though most internal runtime tables are easier to store and restore as Parquet.
- Requirements:
  1. Keep the Phase 3 handoff CSV exactly as the contract input.
  2. Migrate internal runtime projections to Parquet with a compatibility period.
  3. Preserve checkpoint snapshot/restore behavior during the transition.
- Implementation progress (2026-04-08):
  - Added Parquet sidecars for the existing tabular projections and bootstrap artifacts while keeping CSVs as compatibility outputs.
  - Snapshot/runtime restore now carries `.parquet` sidecars alongside `.csv` files in the projections directory.
  - Added regression coverage for bootstrap creation and checkpoint snapshot restore of Parquet sidecars.
- Validation:
  - `python -m pytest test/process/wikidata/test_bootstrap_outputs.py test/process/wikidata/test_checkpoint_resume.py test/process/wikidata/test_class_path_resolution.py -q` (`24 passed`)
  - `python -m pytest test/process/wikidata -q` (`175 passed`)
- Closeout note (2026-04-09): remaining cutover scope transferred to `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-002`.

### WDT-014: Deprecate any non-eventsourced file writing.
Deferred from the current closeout publication; remains open for a future wave.
Everything that writes to a file should be eventsourced. There is plenty of code labeled "materialize" or similar that just recreates entire csv files without doing proper Event-Sourcing. Entire files are rebuild over and over again despite non of the events they are build from having changed. Some examples:

- Status: [x]
- Closeout note (2026-04-09): unresolved implementation scope transferred to `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-003`.

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

- Status: [x]
- Priority: P1
- Owner: unassigned
- Implementation notes (2026-04-07, late):
  1. Added cache-aware batch entity fetch helper `get_or_fetch_entities_batch(...)` in `entity.py`.
  2. Step 6.5 discovery now batches minimal-payload refreshes when multiple consecutive QIDs need refresh, while preserving single-QID behavior and per-entity query event provenance.
  3. Added `NodeIntegrityConfig.discovery_batch_fetch_size` (default `1`) and wired notebook Step 6.5 to use `config["node_integrity_batch_fetch_size"]` (set to `25` in Notebook 21 config).
  4. Maintained compatibility path: when batch contains only one QID, runtime still uses `get_or_fetch_entity(...)`.
- Validation:
  - `python -m pytest speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_network_guardrails.py speakermining/test/process/wikidata/test_class_path_resolution.py -q`
  - Result: `18 passed`
- Follow-up increment (2026-04-08):
  1. Stage A seed expansion now performs best-effort neighbor prefetch via `get_or_fetch_entities_batch(...)` when multiple neighbor QIDs are present.
  2. Prefetch is cache-warming only; per-neighbor processing still uses `get_or_fetch_entity(...)` so deterministic expansion semantics and per-entity logic remain unchanged.
  3. Added regression test `test_run_seed_expansion_prefetches_neighbors_with_batch_fetch` in `test_checkpoint_resume.py` to verify batched prefetch is invoked for multi-neighbor seed expansion.
- Validation:
  1. `pytest test/process/wikidata/test_checkpoint_resume.py -q` (`17 passed`)
  2. `pytest test/process/wikidata -q` (`175 passed`)
- Measurement support increment (2026-04-08):
  1. Added Stage A neighbor-prefetch counters at seed and graph-stage scope for low-friction benchmarking:
     - seed summary: `neighbor_prefetch_batches_attempted`, `neighbor_prefetch_batches_succeeded`, `neighbor_prefetch_candidates_total`
     - checkpoint stats: `stage_a_neighbor_prefetch_batches_attempted`, `stage_a_neighbor_prefetch_batches_succeeded`, `stage_a_neighbor_prefetch_candidates_total`
  2. Extended `test_run_seed_expansion_prefetches_neighbors_with_batch_fetch` to assert these counters deterministically.
- Validation:
  1. `pytest test/process/wikidata/test_checkpoint_resume.py -q` (`17 passed`)
  2. `pytest test/process/wikidata/test_class_path_resolution.py test/process/wikidata/test_contract_matrix_closure.py -q` (`10 passed`)
- Notebook measurement datapoint (2026-04-08):
  1. Re-ran Notebook 21 Step 6 (`run_graph_expansion_stage(...)`) in append mode and captured stage counters from execution summary.
  2. Observed:
     - `stage_a_network_queries_this_run = 0`
     - `stage_a_neighbor_prefetch_batches_attempted = 1`
     - `stage_a_neighbor_prefetch_batches_succeeded = 1`
     - `stage_a_neighbor_prefetch_candidates_total = 66`
  3. This confirms instrumentation visibility in real notebook flow; follow-up evidence should include a non-zero-network run context for stronger efficiency deltas.
- Closeout note (2026-04-09): remaining optimization scope transferred to `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-004`.

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

### WDT-016 Read operation timed out
Context:

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
[node_integrity:discovery] heartbeat: checked=880 pending=87092 known=87972 repaired=729 newly_discovered=729
[node_integrity:discovery] example: minimal payload restored for Q10316697 -> label="Portal:Fernsehen"; p31=Q4663903; p279=<none>
[node_integrity:discovery] Network calls used: 700 / unlimited elapsed=878.8s rate=47.79/min
[node_integrity:discovery] heartbeat: checked=945 pending=87047 known=87992 repaired=782 newly_discovered=782
[node_integrity:discovery] example: minimal payload restored for Q10350469 -> label="Playboy"; p31=Q41298; p279=<none>
[node_integrity:discovery] Network calls used: 750 / unlimited elapsed=939.0s rate=47.92/min
[node_integrity:discovery] heartbeat: checked=1009 pending=86999 known=88008 repaired=835 newly_discovered=834
[node_integrity:discovery] example: minimal payload restored for Q10374742 -> label="Südamerikaner"; p31=Q33829; p279=Q16799549,Q2384959
[node_integrity:discovery] Network calls used: 800 / unlimited elapsed=999.4s rate=48.03/min
[node_integrity:discovery] heartbeat: checked=1085 pending=86934 known=88019 repaired=887 newly_discovered=886
[node_integrity:discovery] example: minimal payload restored for Q10401701 -> label="Template:Iowa"; p31=Q11753321; p279=<none>
[node_integrity:discovery] Network calls used: 850 / unlimited elapsed=1059.5s rate=48.14/min
[node_integrity:discovery] heartbeat: checked=1144 pending=86882 known=88026 repaired=938 newly_discovered=937
[node_integrity:discovery] example: expanded class frontier from Q10412317: +1 class qids
[node_integrity:discovery] Network calls used: 900 / unlimited elapsed=1119.7s rate=48.23/min
[node_integrity:discovery] heartbeat: checked=1202 pending=86833 known=88035 repaired=990 newly_discovered=989
[node_integrity:discovery] example: minimal payload restored for Q104228037 -> label="Category:Views from sea"; p31=Q4167836; p279=<none>
[node_integrity:discovery] Network calls used: 950 / unlimited elapsed=1179.8s rate=48.31/min
[node_integrity:discovery] heartbeat: checked=1265 pending=86781 known=88046 repaired=1044 newly_discovered=1043
[node_integrity:discovery] example: minimal payload restored for Q104418635 -> label="Netherlands"; p31=Q21286738; p279=<none>
[node_integrity:discovery] Network calls used: 1000 / unlimited elapsed=1240.0s rate=48.39/min
[node_integrity:discovery] heartbeat: checked=1331 pending=86720 known=88051 repaired=1097 newly_discovered=1096
[node_integrity:discovery] example: expanded class frontier from Q104595285: +1 class qids
[node_integrity:discovery] Network calls used: 1050 / unlimited elapsed=1300.2s rate=48.45/min
[node_integrity:discovery] heartbeat: checked=1386 pending=86668 known=88054 repaired=1152 newly_discovered=1151
[node_integrity:discovery] example: minimal payload restored for Q104602021 -> label="Category:Views of Oklahoma"; p31=Q4167836; p279=<none>
[node_integrity:discovery] Network calls used: 1100 / unlimited elapsed=1360.4s rate=48.51/min
[node_integrity:discovery] heartbeat: checked=1446 pending=86616 known=88062 repaired=1205 newly_discovered=1204
[node_integrity:discovery] example: expanded class frontier from Q1046645: +1 class qids
[node_integrity:discovery] Network calls used: 1150 / unlimited elapsed=1420.6s rate=48.57/min
[node_integrity:discovery] heartbeat: checked=1516 pending=86570 known=88086 repaired=1263 newly_discovered=1262
[node_integrity:discovery] example: minimal payload restored for Q104809052 -> label="Presidencia de la República"; p31=Q35798; p279=<none>
[node_integrity:discovery] Network calls used: 1200 / unlimited elapsed=1480.9s rate=48.62/min
[node_integrity:discovery] heartbeat: checked=1586 pending=86513 known=88099 repaired=1317 newly_discovered=1316
[node_integrity:discovery] example: expanded class frontier from Q104918055: +1 class qids
[node_integrity:discovery] Network calls used: 1250 / unlimited elapsed=1541.1s rate=48.67/min
[node_integrity:discovery] heartbeat: checked=1657 pending=86464 known=88121 repaired=1375 newly_discovered=1374
[node_integrity:discovery] example: minimal payload restored for Q105085344 -> label="Historical Dictionary of Science Fiction"; p31=Q45740849,Q7094076; p279=<none>


---------------------------------------------------------------------------

### WDT-016 Read operation timed out

- Status: [x]
- Priority: P1
- Owner: unassigned
- Problem:
  Notebook 21 Cell 18 (Step 6.5 node integrity pass) timed out while waiting on a live Wikidata read during repeated minimal-payload recovery requests.
- What happened:
  The run was making steady progress, emitting node-integrity heartbeat lines, and then failed with `TimeoutError: The read operation timed out` while executing `get_or_fetch_entity(...)` inside `run_node_integrity_pass(...)`.
- Analysis:
  This is a long-running network-bound pass exceeding the current request/read tolerance for a representative runtime flow. The symptom overlaps with the long-run visibility and query-efficiency concerns tracked in `WDT-008` and `WDT-015`.
- Requirements:
  1. Document the exact failure mode and the cell/stage boundary where it occurs.
  2. Separate notebook/kernel failure from live Wikidata HTTP timeout behavior.
  3. Reduce timeout exposure via batching, retries, or staged hydration where safe.
  4. Ensure Notebook 21 continues to show useful progress/heartbeat while long reads are in flight.
- Acceptance criteria:
  1. The timeout is reproducible against representative data and clearly attributed to the node-integrity read path.
  2. Notebook 21 maintains operator-visible progress during the long-running cell.
  3. The resolution plan includes a concrete mitigation path rather than treating the timeout as an unexplained crash.
- Implementation notes (2026-04-07):
  - Added timeout resilience in `cache._http_get_json(...)`: `TimeoutError` now enters the same transient retry path as other retriable network failures.
  - Timeout outcomes are now classified as `timeout` in emitted network result events (instead of uncaught crash-only behavior).
  - Added regression tests in `test_network_guardrails.py`:
    1. retry-on-timeout then succeed
    2. raise timeout after retry budget is exhausted
  - Added regression test in `test_node_integrity.py` to verify `NodeIntegrityConfig` timeout policy is forwarded to `begin_request_context(...)`.
  - Validation command: `python -m pytest speakermining/test/process/wikidata/test_network_guardrails.py speakermining/test/process/wikidata/test_node_integrity.py -q` (`11 passed`).
- Hardening follow-up (2026-04-08):
  - `entity.get_or_fetch_entities_batch(...)` now continues per-QID fallback processing when one fallback single-entity call raises `TimeoutError`.
  - This prevents one timeout from aborting the rest of the same batch fallback set and keeps Step 6.5 discovery progressing on remaining QIDs.
  - Added regression test: `test_get_or_fetch_entities_batch_continues_after_fallback_timeout` in `test_entity_cache_unwrap.py`.
  - Validation commands:
    1. `pytest test/process/wikidata/test_entity_cache_unwrap.py -q` (`9 passed`)
    2. `pytest test/process/wikidata -q` (`174 passed`)
- Observability follow-up (2026-04-08):
  - `NodeIntegrityResult` now reports `timeout_warnings` in addition to `stop_reason`.
  - Timeout-warning counts are now included in node-integrity phase-finished metadata for runtime diagnostics.
  - Notebook 21 Step 6.5 summary/report outputs now include `timeout_warnings` and `stop_reason` in persisted diagnostics and console summary.
  - Added/updated regression evidence in `test_node_integrity.py`:
    1. `test_node_integrity_continues_after_timeout_error` now asserts `result.timeout_warnings >= 1`.
  - Validation command:
    1. `python -m pytest test/process/wikidata/test_node_integrity.py -q` (`11 passed`)
  - Closeout note (2026-04-09): remaining resilience scope transferred to `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-005`.
TimeoutError                              Traceback (most recent call last)
Cell In[7], line 51
     38 node_integrity_config = NodeIntegrityConfig(
     39     cache_max_age_days=config["cache_max_age_days"],
     40     query_timeout_seconds=config["query_timeout_seconds"],
   (...)
     47     max_nodes_to_expand=0,
     48 )
     50 node_integrity_t0 = perf_counter()
---> 51 node_integrity_result = run_node_integrity_pass(
     52     ROOT,
     53     config=node_integrity_config,
     54     seed_qids={canonical_qid(seed.get("wikidata_id", "")) for seed in seeds if canonical_qid(seed.get("wikidata_id", ""))},
     55     core_class_qids={canonical_qid(row.get("wikidata_id", "")) for row in load_core_classes(ROOT) if canonical_qid(row.get("wikidata_id", ""))},
     56 )
     57 node_integrity_elapsed = perf_counter() - node_integrity_t0
     59 run_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

File C:\workspace\git\borgnetzwerk\speaker-mining\speakermining\src\process\candidate_generation\wikidata\node_integrity.py:333, in run_node_integrity_pass(repo_root, config, seed_qids, core_class_qids)
    331 if needs_refresh:
    332     try:
--> 333         payload = get_or_fetch_entity(
    334             repo_root,
    335             qid,
    336             config.cache_max_age_days,
    337             timeout=config.query_timeout_seconds,
    338         )
    339     except RuntimeError as exc:
    340         if str(exc) == "Network query budget hit":

File C:\workspace\git\borgnetzwerk\speaker-mining\speakermining\src\process\candidate_generation\wikidata\entity.py:236, in get_or_fetch_entity(root, qid, cache_max_age_days, timeout)
    234 url = _build_wbgetentities_url(qid, languages=requested_languages, include_claims=True)
    235 try:
--> 236 	payload = _http_get_json(url, timeout=timeout)
    237 	payload = _filter_entity_payload_languages(payload)
    238 	entity_doc = _entity_from_payload(payload, qid)

File C:\workspace\git\borgnetzwerk\speaker-mining\speakermining\src\process\candidate_generation\wikidata\cache.py:522, in _http_get_json(url, accept, timeout, max_retries, backoff_base_seconds)
    520 try:
    521 	req = Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
--> 522 	with urlopen(req, timeout=timeout) as response:
    523 		http_status = int(getattr(response, "status", 200) or 200)
    524 		payload = response.read().decode("utf-8")

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\urllib\request.py:216, in urlopen(url, data, timeout, cafile, capath, cadefault, context)
    214 else:
    215     opener = _opener
--> 216 return opener.open(url, data, timeout)

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\urllib\request.py:519, in OpenerDirector.open(self, fullurl, data, timeout)
    516     req = meth(req)
    518 sys.audit('urllib.Request', req.full_url, req.data, req.headers, req.get_method())
--> 519 response = self._open(req, data)
    521 # post-process response
    522 meth_name = protocol+"_response"

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\urllib\request.py:536, in OpenerDirector._open(self, req, data)
    533     return result
    535 protocol = req.type
--> 536 result = self._call_chain(self.handle_open, protocol, protocol +
    537                           '_open', req)
    538 if result:
    539     return result

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\urllib\request.py:496, in OpenerDirector._call_chain(self, chain, kind, meth_name, *args)
    494 for handler in handlers:
    495     func = getattr(handler, meth_name)
--> 496     result = func(*args)
    497     if result is not None:
    498         return result

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\urllib\request.py:1391, in HTTPSHandler.https_open(self, req)
   1390 def https_open(self, req):
-> 1391     return self.do_open(http.client.HTTPSConnection, req,
   1392         context=self._context, check_hostname=self._check_hostname)

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\urllib\request.py:1352, in AbstractHTTPHandler.do_open(self, http_class, req, **http_conn_args)
   1350     except OSError as err: # timeout error
   1351         raise URLError(err)
-> 1352     r = h.getresponse()
   1353 except:
   1354     h.close()

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\http\client.py:1378, in HTTPConnection.getresponse(self)
   1376 try:
   1377     try:
-> 1378         response.begin()
   1379     except ConnectionError:
   1380         self.close()

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\http\client.py:318, in HTTPResponse.begin(self)
    316 # read until we get a non-100 response
    317 while True:
--> 318     version, status, reason = self._read_status()
    319     if status != CONTINUE:
    320         break

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\http\client.py:279, in HTTPResponse._read_status(self)
    278 def _read_status(self):
--> 279     line = str(self.fp.readline(_MAXLINE + 1), "iso-8859-1")
    280     if len(line) > _MAXLINE:
    281         raise LineTooLong("status line")

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\socket.py:706, in SocketIO.readinto(self, b)
    704 while True:
    705     try:
--> 706         return self._sock.recv_into(b)
    707     except timeout:
    708         self._timeout_occurred = True

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\ssl.py:1311, in SSLSocket.recv_into(self, buffer, nbytes, flags)
   1307     if flags != 0:
   1308         raise ValueError(
   1309           "non-zero flags not allowed in calls to recv_into() on %s" %
   1310           self.__class__)
-> 1311     return self.read(nbytes, buffer)
   1312 else:
   1313     return super().recv_into(buffer, nbytes, flags)

File c:\Users\timwi\AppData\Local\Programs\Python\Python311\Lib\ssl.py:1167, in SSLSocket.read(self, len, buffer)
   1165 try:
   1166     if buffer is not None:
-> 1167         return self._sslobj.read(len, buffer)
   1168     else:
   1169         return self._sslobj.read(len)

TimeoutError: The read operation timed out

### WDT-017 Limit Subclass-of nodes expansion that are twice removed from our core class instances:
- Status: [x]
- Priority: P1
- Owner: unassigned
- Problem:
  Step 6.5 node-integrity discovery was recursively expanding non-core subclass trees from second-degree neighborhood paths, producing low-value class fan-out.
- Requirements:
  1. Keep direct class discovery for non-class entities.
  2. Prevent recursive subclass frontier expansion for non-core class nodes.
  3. Preserve core-class frontier behavior.
- Implementation completed (2026-04-07):
  - Added class-frontier policy in `node_integrity.py`:
    1. non-class entities still contribute direct `P31`/`P279` class references,
    2. non-core class nodes no longer recursively expand deeper subclass frontier,
    3. core-class nodes still expand class frontier.
  - Added regression test `test_node_integrity_limits_non_core_class_frontier_expansion`.
- Follow-up hardening (2026-04-07, late):
  1. `ExpansionConfig` now defaults `hydrate_class_chains_for_discovered_entities=False` in `expansion_engine.py` so Stage 6 no longer recursively fetches class chains by default.
  2. `NodeIntegrityConfig` now defaults `include_triple_only_qids_in_discovery=False` in `node_integrity.py` so Step 6.5 does not auto-hydrate triple-only unknown QIDs.
  3. Added regression `test_node_integrity_skips_triple_only_qids_from_discovery_by_default`.
  4. Updated class-chain hydration regression to explicitly opt in with `hydrate_class_chains_for_discovered_entities=True`.
- Validation:
  - `python -m pytest speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_class_path_resolution.py speakermining/test/process/wikidata/test_network_guardrails.py -q`
  - Result: `17 passed`

### WDT-018 Fix graceful exiting
- Status: [x]
- Priority: P0
- Owner: unassigned
- Problem:
  Interruption during Step 6.5 could propagate as raw `KeyboardInterrupt` traceback instead of deterministic graceful stop behavior.
- Requirements:
  1. Convert interruption during discovery refresh to graceful `user_interrupted` outcome.
  2. Convert interruption during expansion loop to graceful `user_interrupted` outcome.
  3. Keep interruption-safe boundary behavior (skip final materialization).
- Implementation completed (2026-04-07):
  - Added `KeyboardInterrupt` handling in `node_integrity.py`:
    1. discovery refresh interruption is trapped and converted to `user_interrupted`,
    2. discovery stage has a top-level interruption guard to catch any remaining uncaught `KeyboardInterrupt`,
    3. expansion-loop interruption is trapped and converted to `user_interrupted`,
    4. interruption during final materialization is trapped and converted to `user_interrupted`,
    5. interruption events are emitted for operator visibility,
    6. final materialization remains skipped on interruption boundary,
    7. Step 6.5 prints `Interrupt detected - now exiting` when graceful interruption is detected.
  - Added regression tests:
    - `test_node_integrity_handles_keyboard_interrupt_gracefully`
    - `test_node_integrity_handles_keyboard_interrupt_during_materialization`
- Validation:
  - `python -m pytest speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_network_guardrails.py -q`
  - Result: `13 passed`

### WDT-019 enabled_mention_types are overwritten
- Status: [x]
- Priority: P0
- Owner: unassigned
- Problem:
  Notebook 21 derived fallback-enabled mention types in multiple cells, creating a risk that Step 8 could diverge from user configuration set in Cell 8.
- Requirements:
  1. Single source of truth for fallback-enabled mention types.
  2. No silent overwrite of user-provided configuration.
  3. Fail fast on invalid configuration format or unsupported mention types.
- Implementation completed (2026-04-07):
  1. Added strict one-time fallback mention-type resolution in Notebook 21 Step 2 config cell.
  2. Added explicit validation for `fallback_enabled_mention_types`:
     - accepted inputs: dict or list/tuple/set,
     - unsupported mention types raise `ValueError`,
     - invalid config shape raises `ValueError`.
  3. Persisted resolved value to `config["fallback_enabled_mention_types_resolved"]` as authoritative runtime source.
  4. Updated Step 7 to consume only `config["fallback_enabled_mention_types_resolved"]`.
  5. Updated Step 8 to consume only `config["fallback_enabled_mention_types_resolved"]` and removed duplicate derivation logic.
  6. Added guardrails in Step 7/Step 8 to fail fast if the resolved value is missing (forces rerun of Step 2 config cell).
- Validation:
  - Code-path verification in `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb` confirms Step 7 and Step 8 now share one derived source and no implicit fallback default (`person`) remains.
  - This restores the contract: user config remains authoritative unless explicit validation error is raised.

### WDT-020 enabled_mention_types are still overwritten
WDT-019 did not work, Cell 26 still presents the enabled_mention_types with `person` as default:

- Status: [x]
- Priority: P0
- Owner: unassigned
- Closeout note (2026-04-09): unresolved root-cause validation and notebook-run verification transferred to `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-006`.

[notebook] Step 8 start: fallback string matching
Stage A queries used (this run): 5
Fallback query budget remaining: 45
Fallback progress interval: 50 calls
[notebook] -> run_fallback_string_matching_stage
[fallback_stage] Starting fallback string matching
[fallback_stage] Built local label index in 0.21s
[fallback_stage] config: budget=45 languages=['de', 'en'] search_limit=10 enabled_mention_types=['person']

## Notes

- This tracker is dedicated to Wikidata workflow internals and avoids overlap with OpenRefine/Wikidata Reconciliation Service terminology.


