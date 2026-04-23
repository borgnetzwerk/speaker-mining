# WDT Issue Analysis (Codebase)

This analysis maps each WDT item to current behavior in Notebook 21 orchestration and Wikidata process modules.

## Orchestration Surface (Notebook 21)

Primary flow in `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`:

1. Setup and config
2. Resume decision (`append`/`restart`/`revert`)
3. Seed/bootstrap load
4. Target build
5. Stage A graph expansion (`run_graph_expansion_stage`)
6. Step 6.5 node integrity pass (`run_node_integrity_pass`)
7. Fallback stage (`run_fallback_string_matching_stage`)
8. Fallback re-entry expansion
9. Artifact review

Key implication:
- Most backlog items are not notebook-only tasks; they sit in `process/candidate_generation/wikidata` and are orchestrated from Notebook 21.

## Cross-Cutting Requirement: Documentation Overhaul

Program-level requirement:
- After implementation waves, documentation must be fully overhauled to one accurate clean state.

Why this is necessary:
- Active work spans both migration tracks:
  - v2 logic-rework continuity expectations
  - v3 event-sourcing migration/architecture behavior
- Multiple docs currently describe overlapping concerns and can drift when code changes quickly.

Minimum completion condition:
- Governed docs and Wikidata-specific docs are synchronized with actual runtime behavior, storage formats, projection model, and notebook operation.

---

## WDT-007 Graceful Exit Without Hard Interrupt Corruption (P0)

Current state:
- `graceful_shutdown.py` exists with signal flag and shutdown file support.
- `event_writer.EventStore.append_event` already blocks appends when shutdown requested (`should_terminate(...)`).
- Long-running loops in `expansion_engine.run_seed_expansion`, `node_integrity.run_node_integrity_pass`, and `fallback_matcher.run_fallback_string_matching_stage` do not consistently check cooperative shutdown before expensive operations and before materialization boundaries.
- `STOP_REASONS` already includes `user_interrupted`, but stage flows mostly produce budget/queue/crash reasons.

Gap vs requirement:
- Partial integration exists, but full cooperative stop path through stage loops and checkpoint/log stop reason propagation is incomplete.

Primary touchpoints:
- `graceful_shutdown.py`
- `expansion_engine.py`
- `node_integrity.py`
- `fallback_matcher.py`
- `checkpoint.py` (manifest reason propagation)
- Notebook Step 6 / 6.5 / 8 messaging

Risk:
- Mid-run interruptions still likely to appear as generic failures or crash-recovery rather than clean deterministic stop.

---

## WDT-008 Restore Heartbeat And Progress Visibility (P0)

Current state:
- Heartbeats already exist in:
  - `expansion_engine.run_seed_expansion` (queue/seen/discovered/expanded)
  - `node_integrity` discovery and expansion loops
  - `fallback_matcher` target processing
  - `cache._http_get_json` network call counters/rate
- Notebook event logger exists (`notebook_event_log.py`) and receives many network decision events via cache request context emitter.

Gap vs requirement:
- Operator visibility is better than tracker suggests, but coverage is uneven and partly log-line based instead of event-derived summaries.
- Heartbeat content can still be limited by sparse domain events (`WDT-009`).

Primary touchpoints:
- `cache.py` request context + network progress prints
- `expansion_engine.py`, `node_integrity.py`, `fallback_matcher.py`
- `notebook_event_log.py`

Risk:
- Regressions can reappear if heartbeat logic remains distributed and not validated by tests.

---

## WDT-009 Expand Event Model Beyond query_response (P1, promoted to near-term unlock)

Current state:
- `event_log.py` supports only `query_response` and `candidate_matched` as domain-like events.
- Additional eventstore lifecycle events exist in `event_writer.py` (`eventstore_opened`, `eventstore_closed`).
- Core decision events (entity discovered/expanded, triple discovered, class membership resolution, eligibility transition) are not first-class event types.

Gap vs requirement:
- Strongly open. Current stream cannot fully reconstruct important decision transitions without re-derivation.
- Migration review context indicates this should be treated as a core unlock rather than a late deferred task.

Primary touchpoints:
- `event_log.py`
- `event_writer.py`
- `triple_store.py`, `node_store.py`, `expansion_engine.py`, `node_integrity.py`
- handler stack under `handlers/`

Risk:
- Analytics and heartbeat derivation remain coupled to ad-hoc reconstruction and projection state.

---

## WDT-001 Re-evaluate Eligibility With Improved Class Lineage (P0)

Current state:
- `node_integrity.run_node_integrity_pass` computes `eligible_unexpanded_qids` across all known items.
- Uses direct seed-link checks and subclass-aware matching via `_p31_core_match_with_subclass_resolution` and projected class hierarchy fallback.
- Expands eligible unexpanded nodes using `run_seed_expansion`.

Gap vs requirement:
- Core behavior appears substantially implemented.
- Missing explicit transition audit payload (old state/new state/path evidence) that WDT-002 asks for.

Primary touchpoints:
- `node_integrity.py`
- `class_resolver.py`
- `materializer.py` (`class_hierarchy.csv` projection used as helper input)

Risk:
- Without explicit transition records, it is hard to prove monotonic reclassification behavior over multiple runs.

---

## WDT-002 Persist Reclassification Diagnostics (P0)

Current state:
- Notebook Step 6.5 writes summary and events artifacts under:
  - `data/20_candidate_generation/wikidata/node_integrity/`
  - `documentation/context/node_integrity/`
- Recorded event types are coarse (`repaired_discovery`, `newly_discovered`, `expanded_by_integrity`).

Gap vs requirement:
- Missing required transition fields:
  - prior eligibility reason
  - new eligibility reason
  - path-to-core evidence
  - explicit transition rows

Primary touchpoints:
- Notebook Step 6.5 cell
- `node_integrity.py` data model (should emit structured transition list)

Risk:
- Longitudinal quality analysis remains low fidelity.

---

## WDT-003 Regression Tests For Reclassification Edge Cases (P1)

Current state:
- Very limited Wikidata test coverage found in repo (`test_wikidata_language_policy.py`).
- No dedicated tests around node-integrity reclassification transitions.

Reworked planning stance:
- Keep this as a cross-wave validation gate rather than a standalone large implementation stream.
- If event-level invariant and replay coverage fully subsumes the original concern, close or merge WDT-003 explicitly in tracker governance.

Primary touchpoints:
- New tests under `speakermining/test/process/wikidata/`
- Event replay/invariant tests for reclassification transitions

Risk:
- Silent regressions remain possible if WDT-003 is closed without equivalent invariant coverage.

---

## WDT-010 Differentiate Core Classes And Root Classes

Current state:
- Core-vs-root distinction exists in code:
  - `common.effective_core_class_qids` removes `Q35120` (`entity`) from core matching.
  - `materializer._build_class_hierarchy_df` outputs `is_core_class` and `is_root_class`.
- Notebook 21 does not have an explicit educational/control cell early on that communicates this distinction to operators.

Gap vs requirement:
- Mostly UX/orchestration and guardrail communication gap.

Primary touchpoints:
- Notebook 21 markdown/config section
- Optional config validation helper in process module

Risk:
- Misconfiguration can still accidentally broaden expansion scope.

---

## WDT-011 Full Eventsourcing Implementation Identification

Current state:
- Event handler framework exists (`event_handler.py`, `handler_registry.py`, `handlers/*`, `handlers/orchestrator.py`).
- Active runtime still relies heavily on materializer rebuilds (`materializer.py`) and direct projection writes after stages.
- Notebook remains imperative/orchestration-heavy rather than handler-replay centered.

Gap vs requirement:
- Partially prepared architecture, not yet realized in runtime control flow.

Primary touchpoints:
- `handlers/orchestrator.py`
- `materializer.py`
- `expansion_engine.py`
- Notebook Step 6/6.5/8 orchestration

Risk:
- Dual architecture (handlers + full rebuild materializer) increases complexity and drift.

---

## WDT-012 More Projections (Per Core Class + Leftovers)

Current state:
- Existing projections: instances/classes/properties/triples/class_hierarchy/query_inventory + alias files.
- No per-core-class instance projections or explicit leftovers projection.

Gap vs requirement:
- Open but low-to-medium complexity once classification signals are trusted.

Primary touchpoints:
- `materializer.py` (or future handler-based projection pipeline)
- `classes.csv` / `class_hierarchy.csv` semantics

Risk:
- If implemented before core-vs-root and reclassification correctness are stabilized, projections may encode wrong membership.

---

## WDT-013 Transition CSV -> Parquet (except Phase 3 input CSV)

Current state:
- Path schema and writers are CSV-centric:
  - `schemas.py` defines many `*_csv` artifacts.
  - `materializer.py` writes all projections as CSV.
  - handlers materialize CSV outputs.

Gap vs requirement:
- Broad migration required across paths, writers, readers, docs, and tests.

Primary touchpoints:
- `schemas.py`
- `materializer.py`
- `handlers/*`
- Notebook read/review cell(s)
- docs/contracts/workflow

Risk:
- Breaking downstream expectations unless transition adapters and explicit exceptions are defined.

---

## WDT-014 Deprecate Non-Eventsourced File Writing

Current state:
- Many projection files are rebuilt from stores via `materializer.py` at checkpoint/final boundaries.
- Notebook Step 6.5 writes diagnostics files directly.
- Handler system exists but is not yet canonical runtime materialization path.

Gap vs requirement:
- Major architectural migration still open.

Primary touchpoints:
- `materializer.py`
- `expansion_engine.py` stage materialization calls
- `handlers/orchestrator.py`
- diagnostics write paths

Risk:
- Performance overhead and non-incremental rebuild costs remain high.

---

## WDT-015 Query Easier For Wikidata (Reduce Massive Minimal Fetch Fan-Out)

Current state:
- Implemented `entity.get_or_fetch_entities_batch(...)` for cache-aware multi-QID refreshes in one `wbgetentities` request.
- `node_integrity.run_node_integrity_pass(...)` now supports batched discovery refresh through `NodeIntegrityConfig.discovery_batch_fetch_size`.
- Notebook 21 now exposes `node_integrity_batch_fetch_size` (currently set to `25`) and forwards it into Step 6.5 config.
- Compatibility retained: when only one QID is being refreshed, runtime still uses `get_or_fetch_entity(...)`.

Gap vs requirement:
- Batch retrieval is now implemented for Step 6.5 discovery, but representative runtime closure evidence (throughput and timeout reduction on live workload) still needs to be recorded.

Primary touchpoints:
- `entity.py` (`get_or_fetch_entity`, `get_or_fetch_entities_batch`, URL builder)
- `node_integrity.py` discovery queue
- `cache.py` request context and budget/rate logic
- Notebook 21 Step 6.5 config wiring
- event model/provenance requirements (`WDT-009`) (preserved via per-entity query events)

Risk:
- Without explicit live benchmark evidence, batching may be functionally correct but still under-tuned for best timeout/throughput behavior.

---

## WDT-016 Read Operation Timed Out During Notebook 21 Cell 18

Current state:
- Notebook 21 Cell 18 is the Step 6.5 node integrity pass.
- The recorded failure occurred after many minutes of steady progress and repeated node-integrity heartbeat output.
- The stack trace ends in `TimeoutError: The read operation timed out` while `node_integrity.run_node_integrity_pass` is waiting on `get_or_fetch_entity(...)`.

Gap vs requirement:
- The runtime does not yet distinguish this kind of long-running live-read timeout from a generic notebook crash in operator-facing documentation.
- There is no documented mitigation path yet for keeping the node-integrity pass observable and tolerant enough under representative data volume.

Primary touchpoints:
- `node_integrity.py` discovery loop
- `entity.py` / `cache.py` live Wikidata read path
- Notebook 21 Step 6.5 cell
- `WDT-008` heartbeat/progress path
- `WDT-015` query-efficiency path

Risk:
- Operators may interpret a network-bound timeout as a notebook/kernel failure, even though the underlying work was progressing.
- Without a mitigation plan, Cell 18 remains vulnerable to long-read stalls on representative runs.

Current mitigation status (2026-04-07):
- Implemented: `cache._http_get_json(...)` now treats `TimeoutError` as transient/retriable and classifies it explicitly as `timeout` in network events.
- Added regression coverage for timeout retry success and timeout exhaustion behavior in `test_network_guardrails.py`.
- Remaining: validate behavior in a representative long-running Notebook 21 Step 6.5 execution and tune retry/time-budget policy if needed.

---

## WDT-017 Limit Subclass-Of Expansion Two Hops Away From Core-Class Instances

Current state:
- `run_node_integrity_pass(...)` discovery previously expanded class frontier by recursively queuing both `P31` and `P279` references for all refreshed nodes.
- In representative long runs, this allowed deep traversal into broad non-core subclass trees, inflating pending queue size and low-value class churn.

Gap vs requirement:
- The previous discovery policy did not distinguish between core-class frontier expansion and non-core class-tree drift.
- There was no guardrail to stop recursive `P279` expansion from non-core class nodes discovered via second-degree neighborhood paths.

Primary touchpoints:
- `node_integrity.py` discovery queue expansion policy

Risk:
- Excessive traversal and low-value class fan-out increases runtime, query load, and queue pressure without proportionate candidate quality gains.

Resolution status (2026-04-07):
- Implemented class-frontier limiter in `node_integrity.py`:
  - non-class nodes still contribute direct class references (`P31`/`P279`),
  - non-core class nodes no longer recursively expand their own subclass frontier,
  - core-class nodes retain class-frontier expansion behavior.
- Added regression test in `test_node_integrity.py` to prove non-core class-chain recursion is capped.

---

## WDT-018 Fix Graceful Exiting In Step 6.5

Current state:
- During live Step 6.5 runs, interrupt behavior could surface as raw `KeyboardInterrupt` traceback while blocked in live HTTP reads.
- This bypassed deterministic "graceful stop" semantics at the notebook operator level.

Gap vs requirement:
- Interruption was not consistently converted into `user_interrupted` stop semantics in Step 6.5 when interruption arrived during blocking entity refresh.

Primary touchpoints:
- `node_integrity.py` discovery refresh error handling
- `node_integrity.py` per-node expansion loop interruption handling

Risk:
- Operators experience apparent crash behavior instead of deterministic stop with interruption-safe materialization boundaries.

Resolution status (2026-04-07):
- Implemented explicit `KeyboardInterrupt` handling in Step 6.5 runtime:
  - discovery refresh path now converts interruption to `user_interrupted` and exits loop deterministically,
  - node-integrity expansion loop now traps interruption and exits with `user_interrupted`,
  - interruption event is emitted for operator/audit visibility,
  - final materialization remains skipped for `user_interrupted` boundary.
- Added regression test in `test_node_integrity.py` asserting interruption returns `stop_reason == "user_interrupted"` and skips final materialization.

---

## WDT-019 enabled_mention_types Are Overwritten In Notebook 21

Current state:
- Notebook 21 now resolves fallback mention types once in Step 2 and persists the resolved value.
- Step 7 and Step 8 both consume that exact resolved value.
- Invalid or unsupported config values now fail fast with explicit `ValueError`.

Gap vs requirement:
- Remaining gap is limited to regression monitoring during representative notebook runs; implementation gap is closed.

Primary touchpoints:
- Notebook 21 Step 7 cell (class scope + enabled mention type derivation)
- Notebook 21 Step 8 cell (fallback config assembly)
- `fallback_matcher.py` config parsing/default behavior

Risk:
- If future edits reintroduce duplicate fallback derivation, fallback metrics and candidate sets can drift from user intent.

Resolution status (2026-04-07):
- Implemented single-source fallback config derivation in Step 2 (`config["fallback_enabled_mention_types_resolved"]`).
- Step 7 and Step 8 now consume only the resolved value and no longer derive independently.
- Added explicit validation/fail-fast behavior for unsupported mention types and invalid config shapes.

---

## Completed Baseline Items (Regression-Control Analysis)

### WDT-004 Language Selection Policy

Observed in code:
- `common.set_active_wikidata_languages` enforces explicit opt-in and raises `ValueError("Please define at least one language")`.
- `entity.py` filters payload literals by active languages + fallback (`mul`).

Assessment:
- Implemented and aligned with tracker notes. Keep as hard guard.

### WDT-005 Alias Language Leakage

Observed in code:
- `materializer._alias_pipe` composes aliases from selected language plus fallback `mul`, not all languages.

Assessment:
- Implemented fix appears present. Keep regression tests and sample checks.

### WDT-006 Checkpoint Snapshot Eventstore Preservation

Observed in code:
- `checkpoint.write_checkpoint_snapshot` and `restore_checkpoint_snapshot` copy/restore chunks, catalog, and checksums.
- Timeline append and retention logic are present.

Assessment:
- Implemented. Keep revert/restore regression checks in CI.
