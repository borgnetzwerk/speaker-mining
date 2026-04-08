# Execution Progress Log (Wave-Driven)

Date: 2026-04-07, updated 2026-04-08
Scope: Notebook 21 orchestration and modules under `speakermining/src/process/candidate_generation/wikidata/`

## 1) Codebase Analysis Snapshot (current)
3. Extended Notebook 21 heartbeat coverage to Stage A graph expansion and fallback re-entry, and added a Step 9 guard so re-entry cannot run after an interrupted Step 8.
Validated orchestration entrypoint:
- `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`

- `expansion_engine.py` (Stage A, checkpointing/materialization boundaries)
- `node_integrity.py` (Step 6.5 integrity discovery + expansion)
- `fallback_matcher.py` (Stage B fallback)
- `checkpoint.py`, `schemas.py`, `event_writer.py`, `graceful_shutdown.py`

Validated test surface (representative, not exhaustive):
- checkpoint/resume and stop reason contracts
- node-integrity behavior
- fallback stage behavior
Key analysis conclusion:
- Existing shutdown primitives were present, but cooperative stop checks were not consistently enforced at long-loop boundaries in Stage A / Step 6.5 / Stage B, and interruption paths could collapse into generic crash-like behavior.

## 2) Wave 1 (`WDT-007`) Implementation Progress

Status: **completed**

Implemented in this slice:
1. Added cooperative interruption checks in long-running loops:
   - `run_seed_expansion` (`expansion_engine.py`)
   - seed filtering + seed loop orchestration (`run_graph_expansion_stage`)
   - `run_node_integrity_pass` discovery and expansion loops (`node_integrity.py`)
   - `run_fallback_string_matching_stage` target/search loops (`fallback_matcher.py`)
2. Standardized interruption handling to produce `user_interrupted` instead of generic crash paths where applicable.
3. Added checkpoint/manifest interruption persistence in graph stage when interruption happens during seed processing.
4. Skipped expensive final materialization steps when interruption is already requested (safe boundary behavior).

## 3) Test Evidence For This Slice

Targeted test command executed:
- `python -m pytest speakermining/test/process/wikidata/test_checkpoint_resume.py speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_fallback_stage.py -q`

Result:
- `27 passed`

New regression tests added:
1. graceful stop in `run_seed_expansion`
2. graceful stop in fallback stage loop
3. graceful stop in node-integrity pass with materialization skip

## 4) WDT-007 Closure Evidence (updated)

1. Integration-level graceful-shutdown suite added (`test_wdt_007_graceful_shutdown_integration.py`).
2. Verified interruption-safe boundaries and operator-visible interruption summaries.
## 5) Wave 2 Progress (current)

Completed after Wave 1 closure:
1. Introduced first promoted domain events (`entity_discovered`, `entity_expanded`, `expansion_decision` builder).
2. Wired domain event emission into Stage A, Step 6.5, and Stage B runtime flows.
3. Added Notebook 21 event-derived heartbeat helper and initial wiring after node integrity and fallback stages.

## 6) WDT-016 Timeout Mitigation Progress (current)

Problem observed:
- Notebook 21 Cell 18 (Step 6.5 node integrity pass) failed with `TimeoutError: The read operation timed out` after sustained live-read progress.

Implemented mitigation in this slice:
1. `cache._http_get_json(...)` now treats `TimeoutError` as transient/retriable and emits timeout-classified result events.
2. `run_node_integrity_pass(...)` now handles per-entity timeout failures by logging a warning event and continuing with the next qid instead of aborting the entire pass.
3. Added regression tests for timeout retry success/failure behavior and node-integrity timeout continuation.

Validation:
- `python -m pytest speakermining/test/process/wikidata/test_network_guardrails.py speakermining/test/process/wikidata/test_node_integrity.py -q`
- Result: `11 passed`

Remaining for WDT-016 closure:
1. Representative long-running Notebook 21 Step 6.5 validation with live network behavior.
2. Retry/backoff tuning based on observed runtime profile and operator feedback.

## 7) WDT-017/WDT-018 Follow-Up Fixes (current)

New issues surfaced during representative Step 6.5 runtime:
1. WDT-017: non-core subclass trees were expanding too aggressively from second-degree neighborhood paths.
2. WDT-018: interrupt behavior in Step 6.5 could surface as raw `KeyboardInterrupt` traceback instead of deterministic graceful stop behavior.
   - non-class nodes still add direct class references,
   - non-core class nodes no longer recursively expand deeper subclass frontier,
   - core-class nodes retain subclass frontier expansion behavior.
2. Added explicit `KeyboardInterrupt` handling in Step 6.5 runtime:
   - discovery refresh interruption now exits with `user_interrupted`,
   - any uncaught discovery-loop interruption now exits with `user_interrupted` (stage-level catch),
   - expansion-loop interruption now exits with `user_interrupted`,
   - final materialization interruption now exits with `user_interrupted` instead of traceback,
   - operator-facing runtime confirmation now prints: `Interrupt detected - now exiting`.
   - interruption events emitted for operator/audit visibility,
   - final materialization remains skipped on interruption boundary.
3. Added regression tests:
   - limit non-core class-chain recursion,
   - convert keyboard interruption into graceful `user_interrupted` result with materialization skip.
4. Added additional WDT-017 leaf-policy hardening:
   - Stage 6 graph expansion now defaults to non-recursive class handling via `ExpansionConfig.hydrate_class_chains_for_discovered_entities=False`.
   - Step 6.5 node integrity now defaults to skipping triple-only unknown QIDs via `NodeIntegrityConfig.include_triple_only_qids_in_discovery=False`.
   - Added regression to prove triple-only QIDs are not auto-hydrated in discovery by default.
   - Existing class-chain hydration regression now uses explicit opt-in (`hydrate_class_chains_for_discovered_entities=True`) for intentional class-chain runs.

Validation:
- `python -m pytest speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_class_path_resolution.py speakermining/test/process/wikidata/test_network_guardrails.py -q`
- Result: `17 passed`

## 8) WDT-015 Query-Efficiency Slice (current)

Implemented in this slice:
1. Added batch entity hydration primitive in `entity.py`:
   - `get_or_fetch_entities_batch(...)` performs cache-first evaluation and issues one `wbgetentities` call for multi-QID refreshes when needed.
   - Per-entity query events are still written (`normalized_query=entity:<qid>`) to preserve provenance semantics.
2. Wired Step 6.5 node-integrity discovery to batch-refresh consecutive missing-minimal-payload QIDs:
   - new `NodeIntegrityConfig.discovery_batch_fetch_size` (default `1` for compatibility),
   - compatibility fallback retained for single-QID refresh path (`get_or_fetch_entity(...)`).
3. Notebook 21 Step 6.5 config now forwards batch size:
   - added `node_integrity_batch_fetch_size` (set to `25`) in notebook config,
   - forwarded to `NodeIntegrityConfig.discovery_batch_fetch_size`.
4. Added regression coverage in `test_node_integrity.py` for batching behavior.

Validation:
- `python -m pytest speakermining/test/process/wikidata/test_node_integrity.py speakermining/test/process/wikidata/test_network_guardrails.py speakermining/test/process/wikidata/test_class_path_resolution.py -q`
- Result: `18 passed`

## 9) WDT-019 Notebook Config-Integrity Fix (current)

Implemented in this slice:
1. Notebook 21 now resolves fallback-enabled mention types exactly once in Step 2 and stores the authoritative value in `config["fallback_enabled_mention_types_resolved"]`.
2. Added strict validation:
   - unsupported mention types raise `ValueError`,
   - invalid config shape raises `ValueError`.
3. Removed duplicate derivation in Step 7 and Step 8:
   - both now consume `config["fallback_enabled_mention_types_resolved"]`,
   - no implicit fallback default is applied,
   - both cells fail fast if resolved config is missing.

Commit handoff state:
- Codebase includes latest WDT-015 batching, WDT-017 leaf-policy hardening, WDT-018 graceful interrupt handling, and WDT-019 config-integrity enforcement.
- Focused validation remains green (`18 passed` on node-integrity/network/class-path suites).
- Documentation and tracker now reflect WDT-019 as implemented.

## 10) Wave 2 Domain Event Follow-Up (current)

Implemented in this slice:
1. Added new domain event types/builders in `event_log.py`:
   - `triple_discovered`
   - `class_membership_resolved`
2. Added `class_resolver.resolve_class_path(...)` callback support and wired `class_membership_resolved` emissions into:
   - Stage A seed-class filtering path in `expansion_engine.py`
   - Step 6.5 class-resolution checks in `node_integrity.py`
3. Wired `triple_discovered` emission at triple recording boundaries in `triple_store.record_item_edges(...)` and propagated runtime event emitters from Stage A / Step 6.5 call sites.
4. Finalized runtime `expansion_decision` emissions in:
   - Stage A candidate expansion eligibility decisions
   - Stage B fallback matched-candidate expansion eligibility decisions
5. Added focused regression coverage:
   - new event schema tests for `triple_discovered` and `class_membership_resolved`
   - triple-store event emission hook test
   - class resolver callback emission test

Validation:
- `python -m pytest speakermining/test/process/wikidata/test_event_schema.py speakermining/test/process/wikidata/test_store_buffering.py speakermining/test/process/wikidata/test_class_path_resolution.py -q`
- Result: `12 passed`
- `pytest test/process/wikidata/test_orchestrator_handlers.py -q`
- Result: `4 passed`

Wave 2 closure update:
1. Added orchestrator-level replay/invariant tests with interleaved promoted domain events and query events.
2. Fixed handler orchestrator replay rehydration so domain-only incremental appends do not clear projections.
3. WDT-009 scope is now complete; WDT-014 remains a separate follow-on stream.

## 11) Wave 3 Transition Diagnostics (current)

Implemented in this slice:
1. Added new domain event type/builder in `event_log.py`:
   - `eligibility_transition`
2. Extended node-integrity runtime to compute eligibility snapshots before and after integrity repairs:
   - pre/post decision evaluation captures eligibility status and reason per known node,
   - transitions are detected for ineligible -> eligible changes,
   - transition evidence includes `previous_reason`, `current_reason`, and `path_to_core_class`.
3. Node-integrity now emits `eligibility_transition` events for each detected transition.
4. Extended `NodeIntegrityResult` with structured `eligibility_transitions` rows for deterministic artifact persistence at notebook layer.
5. Added focused regression coverage:
   - event schema test for `eligibility_transition`,
   - node-integrity transition detection test for ineligible -> eligible reclassification.

Validation:
- `pytest test/process/wikidata/test_event_schema.py test/process/wikidata/test_node_integrity.py -q`
- Result: `17 passed`

Remaining Wave 3 follow-up:
1. Wire Notebook 21 Step 6.5 diagnostics artifact writing to consume `NodeIntegrityResult.eligibility_transitions` directly.

## 12) Wave 3 Notebook Integration Complete (2026-04-08)

Status: **completed**

Implemented in this slice:
1. Extended Notebook 21 Step 6.5 (Run Node Integrity Pass) to write eligibility transitions:
   - Added transitions JSONL output path: `transitions_jsonl_path = diagnostics_dir / f"node_integrity_transitions_{run_ts}.jsonl"`
   - Implemented conditional transition writing: iterates over `node_integrity_result.eligibility_transitions` and writes each row as JSON
   - Updated artifact documentation to list transitions in markdown reports
   - Added transition count summary to notebook output
2. Cross-validated transition writing logic with deterministic test cases (mock data)
3. Confirmed `NodeIntegrityResult.eligibility_transitions` field availability in runtime class definition

Wave 3 Acceptance Criteria Status:
- ✅ Reclassification is auditable through event-sourced transitions
- ✅ Transition diagnostics persisted to append-only JSONL at stable paths
- ✅ Heartbeat/progress views are stable across runs
- ✅ Artifact location: `data/20_candidate_generation/wikidata/node_integrity/node_integrity_transitions_{timestamp}.jsonl`
- ✅ Transition row structure includes: `qid`, `previous_eligible`, `current_eligible`, `previous_reason`, `current_reason`, `path_to_core_class`, `timestamp_utc`

**Wave 3 Complete**: WDT-001 and WDT-002 closed. Reclassification diagnostics now observable and persistent end-to-end.

## 13) Wave 4 Priority Items

Targets: WDT-010, WDT-012

Next focus:
1. **WDT-010**: Add clear differentiation between "core classes" (Person, Organization, Episode, etc.) and "root classes" (Entity, Thing, etc.) in early notebook cell
   - Currently, conflating these could explore thousands of unnecessary nodes
   - Need dedicated documentation and runtime validation in Notebook 21 Step 1-2

2. **WDT-012**: Add additional core-class projections and leftovers projection
   - One projection per core class for all instances of that core class
   - One projection for non-class/non-core-instance leftover rows

## 14) Wave 4 Semantics Consistency - WDT-010 Complete (2026-04-08)

Status: **in progress** (WDT-010 complete, WDT-012 next)

### WDT-010: Core-vs-Root Class Differentiation - COMPLETED

Implemented in this slice:
1. Added Notebook 21 Step 2.5: "Class Hierarchy Clarification" cell after workflow configuration
   - Inserted as markdown documentation section + code validation cell
   - Positioned after Step 2 (Configure Workflow Parameters) before Step 3 (Decide Resume Mode)
   - Ensures validation occurs before any graph expansion logic
2. Markdown section differentiates:
   - **Core classes** (PRIMARY DISCOVERY TARGETS): Person (Q5), Organization (Q43229), Episode (Q1983062), Season (Q7725310), Topic (Q26256810), Broadcasting Program (Q11578774)
   - **Root classes** (UNIVERSAL SUPERCLASSES): Entity (Q35120), Thing (Q1) - nearly everything descends from these, used only for contrast/avoidance logic
   - **Why it matters**: Conflating root with core means exploring thousands of low-value nodes without meaningful discovery gain
3. Code cell validates and documents:
   - Loads core classes from bootstrap configuration (7 total: person, organization, episode, season, topic, broadcasting_program, and roles)
   - Defines root_class_qids explicitly: {'Q35120' (Entity), 'Q1' (Thing)}
   - **Validation**: Raises `ValueError` if overlap detected (core and root classes must be disjoint)
   - Prints clear differentiation and scope contract for operator visibility
   - Stores `config["core_class_qids"]` and `config["root_class_qids"]` for downstream runtime guards

Validation:
- Step 2.5 cell executes successfully after Step 2 config
- Output confirms 7 core classes, 2 root classes, disjoint validation passed
- Clear scope contract printed before graph expansion begins:
  - "Instances of core classes are discovery targets → will trigger expansion"
  - "Instances of root classes are universal → expansion limited by core-class-connection rules"
- WDT-010 acceptance criteria fully met

## 15) Wave 4 Projection Expansion - WDT-012 Complete (2026-04-08)

Status: **completed**

Implemented in this slice:
1. Added per-core-class instance projections in materializer:
   - `instances_core_<core_filename>.csv` is generated for each configured core class.
   - Rows include non-class entities resolved to that core class via class-path resolution.
2. Added leftovers projection:
   - `instances_leftovers.csv` contains non-class entities that do not resolve to any configured core class.
3. Added deterministic projection hygiene:
   - stale `instances_core_*.csv` files are removed when core configuration changes.
4. Added bootstrap coverage:
   - bootstrap now creates empty deterministic files for per-core and leftovers projections.
5. Added checkpoint durability support:
   - snapshot now includes dynamic projection files (`instances_core_*.csv`).
   - restore now rebuilds projection files directly from snapshot payload (including dynamic projections).

Validation:
- `python -m pytest test/process/wikidata/test_bootstrap_outputs.py test/process/wikidata/test_class_path_resolution.py test/process/wikidata/test_checkpoint_resume.py -q`
- Result: `23 passed`

New regression tests:
1. `test_materializer_writes_per_core_and_leftovers_projections`
2. `test_checkpoint_snapshot_restores_dynamic_core_instance_projections`
3. bootstrap projection creation assertions in `test_bootstrap_outputs.py`

Wave 4 closure:
- ✅ WDT-010 complete
- ✅ WDT-012 complete

### Next: Wave 5 Query Efficiency + Storage Migration

Targets for next implementation slice:
- WDT-015 query-efficiency improvements
- WDT-016 timeout mitigation hardening
- WDT-013 staged CSV -> Parquet transition planning

## 16) Wave 5 Timeout Hardening Increment (2026-04-08)

Status: **in progress** (WDT-016 hardening increment complete; Wave 5 remains open)

Implemented in this slice:
1. Hardened batched entity fallback timeout behavior in `entity.py`:
   - `get_or_fetch_entities_batch(...)` now continues processing remaining QIDs when one fallback per-QID fetch raises `TimeoutError`.
   - This prevents single timeout failures from aborting the entire batch fallback set.
2. Added targeted regression coverage in `test_entity_cache_unwrap.py`:
   - `test_get_or_fetch_entities_batch_continues_after_fallback_timeout`
   - verifies timeout on one QID does not block successful fallback retrieval for subsequent QIDs.

Validation:
- `pytest test/process/wikidata/test_entity_cache_unwrap.py -q`
- Result: `9 passed`
- `pytest test/process/wikidata -q`
- Result: `174 passed`

## 17) Wave 5 Query-Efficiency Increment (2026-04-08)

Status: **in progress** (WDT-015 increment complete; Wave 5 remains open)

Implemented in this slice:
1. Added Stage A neighbor prefetch batching in `expansion_engine.py`:
   - When a seed-expansion frontier yields multiple neighbor QIDs, Stage A now performs a best-effort `get_or_fetch_entities_batch(...)` prefetch before per-neighbor processing.
   - Prefetch is intentionally cache-warming only; the existing per-neighbor `get_or_fetch_entity(...)` loop remains authoritative for deterministic behavior and compatibility with existing expansion semantics.
2. Added regression coverage in `test_checkpoint_resume.py`:
   - `test_run_seed_expansion_prefetches_neighbors_with_batch_fetch`
   - verifies multi-neighbor frontiers trigger one batch prefetch while preserving per-neighbor discovery flow.

Validation:
- `pytest test/process/wikidata/test_checkpoint_resume.py -q`
- Result: `17 passed`
- `pytest test/process/wikidata -q`
- Result: `175 passed`

## 18) Wave 5 Query-Efficiency Instrumentation (2026-04-08)

Status: **in progress** (WDT-015 measurement support increment complete)

Implemented in this slice:
1. Added Stage A runtime counters in `run_seed_expansion(...)` and graph-stage rollup in `run_graph_expansion_stage(...)`:
   - `neighbor_prefetch_batches_attempted`
   - `neighbor_prefetch_batches_succeeded`
   - `neighbor_prefetch_candidates_total`
2. Exposed stage-level aggregates in checkpoint stats for Notebook/operator visibility:
   - `stage_a_neighbor_prefetch_batches_attempted`
   - `stage_a_neighbor_prefetch_batches_succeeded`
   - `stage_a_neighbor_prefetch_candidates_total`
3. Extended regression coverage in `test_checkpoint_resume.py` to assert the new counters under the existing multi-neighbor prefetch scenario.

Validation:
- `pytest test/process/wikidata/test_checkpoint_resume.py -q`
- Result: `17 passed`
- `pytest test/process/wikidata/test_class_path_resolution.py test/process/wikidata/test_contract_matrix_closure.py -q`
- Result: `10 passed`

## 19) Wave 5 Notebook Measurement Evidence (2026-04-08)

Status: **in progress** (WDT-015 evidence collection started)

Representative Notebook 21 Step 6 execution (append mode):
1. Executed Stage A graph expansion from Notebook 21 with current checkpoint state (`start_seed_index=11`, `seed_count=12`).
2. Captured Stage A query and prefetch counters from `result.checkpoint_stats`.

Observed counters:
1. `stage_a_network_queries_this_run = 0`
2. `stage_a_neighbor_prefetch_batches_attempted = 1`
3. `stage_a_neighbor_prefetch_batches_succeeded = 1`
4. `stage_a_neighbor_prefetch_candidates_total = 66`

Interpretation note:
1. This run was cache-dominant (`stage_a_network_queries_this_run = 0`) but still exercised prefetch orchestration paths and confirms counters are emitted in real notebook execution.
2. Next evidence slice should include a run context with non-zero Stage A network activity to estimate incremental network impact under fresher-cache or expanded frontier conditions.

Validation command:
- Notebook: `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb` Step 6 (`run_graph_expansion_stage(...)`)
- Outcome: successful execution with the counters above and no runtime errors.

## 20) Wave 5 Node-Integrity Timeout Observability (2026-04-08)

Status: **in progress** (WDT-016 observability increment complete; Wave 5 remains open)

Implemented in this slice:
1. Extended `NodeIntegrityResult` runtime observability in `node_integrity.py`:
   - added `timeout_warnings` to return payload,
   - surfaced `timeout_warnings` in node-integrity phase-finished metadata,
   - retained `stop_reason` propagation for deterministic interruption diagnostics.
2. Extended Notebook 21 Step 6.5 diagnostics/reporting to persist and print timeout observability:
   - summary outputs now include `timeout_warnings` and `stop_reason` in JSON/CSV record content,
   - markdown diagnostics now include `timeout_warnings` and `stop_reason` in the summary block,
   - notebook console summary now prints both fields.
3. Extended node-integrity timeout continuation regression coverage:
   - `test_node_integrity_continues_after_timeout_error` now asserts `result.timeout_warnings >= 1`.

Validation:
- `python -m pytest test/process/wikidata/test_node_integrity.py -q`
- Result: `11 passed`

## 21) Wave 5 Storage Migration Sidecars (2026-04-08)

Status: **in progress** (WDT-013 migration slice complete; Wave 5 remains open)

Implemented in this slice:
1. Added Parquet sidecars for the runtime tabular projections and bootstrap artifacts while keeping CSV files as compatibility outputs.
2. Updated checkpoint snapshot/restore to carry `.parquet` sidecars from the projections directory.
3. Extended bootstrap cleanup so stale Parquet sidecars are removed when their CSV counterparts are retired.
4. Added regression coverage for bootstrap creation and checkpoint restore of the Parquet sidecars.

Validation:
- `python -m pytest test/process/wikidata/test_bootstrap_outputs.py test/process/wikidata/test_checkpoint_resume.py test/process/wikidata/test_class_path_resolution.py -q`
- Result: `24 passed`
- `python -m pytest test/process/wikidata -q`
- Result: `175 passed`
