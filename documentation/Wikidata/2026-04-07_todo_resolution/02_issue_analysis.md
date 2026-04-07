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
- `entity.get_or_fetch_entity` uses single-ID `wbgetentities` calls (`ids=<single qid>`).
- Node integrity discovery loop can trigger huge volume of small calls.
- Caching and query inventory dedupe are present, but fetch pattern is still mostly per-node.

Gap vs requirement:
- Open optimization space for batched retrieval and staged hydration.

Primary touchpoints:
- `entity.py` (`get_or_fetch_entity` + URL builder)
- `node_integrity.py` discovery queue
- `cache.py` request context and budget/rate logic
- event model/provenance requirements (`WDT-009`)

Risk:
- Naive batching can reduce traceability if event payloads lose per-entity provenance semantics.

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
