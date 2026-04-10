# Wikidata Great Rework Backlog

Date: 2026-04-09

Note:

1. This file is a retained source inventory.

## Priority Legend

- P0: blocks safe high-volume rerun
- P1: major efficiency/reliability gain
- P2: structural/cleanup improvement

## Migrated Unresolved Items

### GRW-001 (P1): Event-sourcing execution model simplification

Origin: WDT-011

Goal:

- Reduce notebook orchestration toward handler-driven event processing where feasible, minimizing imperative orchestration code outside setup.

Acceptance:

1. Clear target architecture for handler-first execution flow.
2. Identified notebook cells that can be replaced by event dispatch + projection readout.
3. One concrete vertical slice implemented and validated.

### GRW-002 (P1): CSV to Parquet transition completion

Origin: WDT-013

Goal:

- Finish runtime-internal transition to Parquet-first while preserving required CSV contracts for Phase 3 handoff.

Acceptance:

1. Runtime readers use Parquet by default.
2. CSV remains contract output only where required.
3. Snapshot/restore parity proven for Parquet-first runtime.

### GRW-003 (P0): Deprecate non-event-sourced rewrite paths

Origin: WDT-014

Goal:

- Remove or reduce rebuild-everything materialization paths that rewrite large projections unaffected by new events.
Acceptance:

1. Identify each non-incremental full-rebuild writer path.
2. Convert high-cost rebuild paths to incremental/event-driven projection updates.
3. Runtime logs show major reduction in repeated materialization durations.

Progress (2026-04-09):

1. Implemented handler-governance subset in orchestrator: stale unmanaged handlers are now pruned from `eventhandler.csv` before runs.
2. Added per-handler run summary artifact with before/after sequence visibility, processed-event counts, and artifact paths.
3. Added focused tests for orchestrator summary artifact and stale-handler pruning behavior.
4. Remaining work: migrate remaining non-incremental writer paths and collect throughput benchmark evidence.
5. Added explicit handler orchestrator materialization modes (`incremental` default, `full_rebuild` override).
6. Incremental mode now skips replay/materialization when no events are pending and projection artifacts already exist, reducing no-op rerun cost.
7. Added focused tests to validate incremental no-op skip behavior and full-rebuild override behavior.
8. Added handler bootstrap support for pending incremental runs so orchestrator can hydrate state from existing projections (or node store for classes) and avoid historical replay.
9. Added focused orchestrator coverage asserting pending incremental runs report bootstrap usage and zero historical replay for projection-backed handlers.
10. Captured first benchmark evidence bundle using the new helper on a non-zero-event replay workload (`handler_materialization_summary_20260409T212657Z.json` + companion CSV files).

Closure Notes (in progress):

1. Task completion marked: Workstream 1 governance subset (auditable handler progress) is implemented and tested.
2. Remaining tasks listed: incremental writer-path conversion and benchmark proof remain open under Workstream 2.
3. Lessons learned documented: per-run handler summaries improve deterministic resume/replay debugging substantially.
4. Further potential captured: extend summary artifact with per-handler duration and projection delta metrics.
5. Additional tasks captured: add notebook rerun evidence artifact that demonstrates real-run handler before/after sequence governance.
6. Task completion marked: incremental-default no-op skip slice is implemented and test-covered.
7. Remaining tasks listed: reduce replay cost for pending-event runs and collect throughput benchmark evidence.
8. Lessons learned documented: replay-safe event sourcing still needs explicit no-op short-circuiting to realize incremental gains.
9. Further potential captured: hydrate handler state from existing projections before applying pending event ranges.
10. Additional tasks captured: publish comparative benchmark artifacts for `incremental` vs `full_rebuild` mode.
11. Task completion marked: pending-run bootstrap hydration is now implemented for handler orchestration.
12. Remaining tasks listed: add benchmark and parity evidence proving measurable throughput gains and output equivalence against full-rebuild controls.
13. Lessons learned documented: bootstrap source must align with handler state shape to preserve deterministic replay semantics.
14. Further potential captured: add projection checksum/sequence guards before bootstrap to fail closed on stale projections.
15. Additional tasks captured: record one non-zero-network replay artifact showing reduced historical replay count per handler.
16. Task completion marked: first comparative benchmark evidence is now captured with the shared run/summary artifact contract.
17. Remaining tasks listed: retain focus on writer-path conversion and parity evidence against full-rebuild outputs.
18. Lessons learned documented: benchmark rounds should include at least one pending-event cycle to expose replay differences.
19. Further potential captured: add explicit per-handler delta columns (duration and artifact bytes) to strengthen attribution.
20. Additional tasks captured: publish one byte-equivalence parity artifact at identical event sequence for incremental bootstrap vs controlled full-rebuild.
21. Task completion marked: deterministic parity-reporting support now exists for comparing incremental/bootstrap snapshots against full-rebuild snapshots.
22. Remaining tasks listed: publish one real parity artifact bundle once the end-of-rework evaluation phase begins.
23. Lessons learned documented: parity helpers are most useful when they normalize artifact ordering rather than comparing raw CSV bytes.
24. Further potential captured: extend parity checks to include optional JSON summaries and checksum sidecars.
25. Additional tasks captured: wire the parity helper into the final evaluation flow when notebook reruns are allowed.
26. Task completion marked: the benchmark helper now emits parity JSON/CSV artifacts when a control snapshot root is supplied.
27. Remaining tasks listed: produce one real end-to-end parity evidence bundle during the final evaluation phase.
28. Lessons learned documented: parity support becomes operational only once helper output is promoted into a persisted benchmark artifact.
29. Further potential captured: extend parity emission to include digest-only sidecars for large snapshot sets.
30. Task completion marked: shared io_guardrails text/CSV writers now skip identical rewrites across callers.
31. Remaining tasks listed: broader Workstream 2 throughput and cost reduction work remains open.
32. Lessons learned documented: the shared write helper is the highest-leverage place to eliminate redundant rewrite churn across multiple modules.
33. Further potential captured: extend the same no-op pattern to any remaining non-shared writer helpers.
34. Task completion marked: benchmark run and parity CSV outputs now use the shared atomic CSV helper.
35. Remaining tasks listed: Workstream 2 still has broader throughput and cost reduction work open beyond shared writer coverage.
36. Lessons learned documented: benchmark artifact generation should follow the same guarded write path as the primary projections to keep operational behavior consistent.
37. Further potential captured: route any remaining benchmark-style CSV outputs through the shared atomic helper.
38. Task completion marked: handler progress registry persistence now uses the shared atomic CSV writer path instead of a local temp-file writer.
39. Remaining tasks listed: convert remaining non-shared writer helpers (for example cache/materializer/node-store local atomics) when safe under projection-only contracts.
40. Lessons learned documented: centralizing registry persistence into shared guardrails keeps replay bookkeeping behavior aligned with projection artifact writers.
41. Task completion marked: cache writer helpers (`_atomic_write_text`, `_atomic_write_df`) now delegate to shared guarded IO writers.
42. Task completion marked: node-store recovery merge now accepts both metadata-wrapped and direct shared-writer recovery payload forms.
43. Remaining tasks listed: finish any residual local writer-helper conversions outside append-only event logs.
44. Task completion marked: cache parquet writer helper (`_atomic_write_parquet_df`) now delegates to shared guarded parquet IO helper.
45. Remaining tasks listed: finish remaining non-shared writer-helper conversion in materializer/node-store surfaces where safe under projection-only contracts.

### GRW-004 (P1): High-volume Wikidata query efficiency

Origin: WDT-015

Goal:

- Reduce network calls for minimal payload restoration at large scale.

Acceptance:

1. Benchmark baseline vs rework on representative non-zero-network run.
2. Material reduction in calls and wall-clock for Step 6.5.
3. Provenance/event semantics preserved.

Progress (2026-04-09):

1. Added `handler_benchmark.py` benchmark helper for reproducible throughput comparison between `incremental` and `full_rebuild` orchestrator modes.
2. Benchmark helper now emits timestamped run-level CSV, summary CSV, summary JSON, plus a stable `handler_materialization_summary_latest.json` artifact under `data/20_candidate_generation/wikidata/benchmarks`.
3. Added focused tests validating benchmark artifact emission and replay-delta capture semantics.
4. Executed benchmark helper on a representative non-zero-event replay workload and published artifacts:
	- `data/20_candidate_generation/wikidata/benchmarks/handler_materialization_runs_20260409T212657Z.csv`
	- `data/20_candidate_generation/wikidata/benchmarks/handler_materialization_summary_20260409T212657Z.csv`
	- `data/20_candidate_generation/wikidata/benchmarks/handler_materialization_summary_20260409T212657Z.json`
5. Evidence snapshot from that run: `incremental` historical replay mean = 0.0 vs `full_rebuild` historical replay mean = 205.0, with both modes at latest event sequence 41.
6. Integrated benchmark execution into Notebook 21 closeout flow as Step 11 so evidence can be generated in normal operator workflow.
7. Remaining work: execute benchmark helper on representative non-zero-network workloads and publish the same evidence structure in closure notes.
8. Added benchmark `run_context` support in `handler_benchmark.py` and wired Notebook 21 Step 11 to persist runtime context metadata (budget/cache/toggle/workload counts) directly into benchmark summary JSON.

Closure Notes (in progress):

2. Remaining tasks listed: collect real non-zero-network benchmark evidence and quantify call/wall-time reductions.
3. Lessons learned documented: benchmark evidence is easier to reuse when both per-run and aggregated artifacts are persisted.
4. Further potential captured: add per-handler duration and artifact-size delta columns for attribution-quality diagnostics.
5. Additional tasks captured: wire benchmark helper into Notebook 21 closeout flow and publish one representative evidence bundle.
6. Task completion marked: first evidence bundle is published with reproducible JSON/CSV outputs and metrics.
7. Remaining tasks listed: non-zero-network benchmark evidence and Step 6.5 call/wall-time reduction proof are still open.
8. Lessons learned documented: no-op-only benchmark rounds understate incremental advantages; include pending-event rounds deliberately.
9. Further potential captured: add a notebook wrapper cell that stamps benchmark context (budget, cache mode, and workload size) into summary JSON.
10. Additional tasks captured: run one cache-first and one non-zero-network benchmark pair with comparable workload metadata.
11. Task completion marked: benchmark helper execution is now available directly in Notebook 21 Step 11 closeout.
12. Remaining tasks listed: collect and publish one non-zero-network Step 11 benchmark artifact bundle.
13. Lessons learned documented: embedding benchmark generation in the notebook reduces evidence drift between ad-hoc scripts and operational runs.
14. Further potential captured: include run-context metadata (query budget, mode, and workload counts) in benchmark summary JSON from notebook execution.
15. Additional tasks captured: add one closure-note link to the first Step 11 runtime artifact bundle when captured.
16. Task completion marked: benchmark summary artifacts now include notebook-provided run-context metadata.
17. Remaining tasks listed: capture and publish one non-zero-network Step 11 artifact bundle that includes the new run-context metadata fields.
18. Lessons learned documented: embedding context metadata at artifact write-time avoids post-hoc ambiguity when comparing benchmark runs.
19. Further potential captured: expand benchmark run-context with per-stage event counts and optional checksum references.
20. Additional tasks captured: link first non-zero-network Step 11 artifact bundle and verify run-context comparability against the existing local replay baseline.

### GRW-005 (P0): Long-run timeout resilience at scale

Origin: WDT-016

Goal:

- Ensure long node-integrity runs survive transient and repeated read timeouts without catastrophic failure or operator blindness.

Acceptance:

1. Reproducible stress scenario and resilience test harness.
2. Bounded retry/backoff policy validated under sustained timeout conditions.
3. Clear stop-reason and warning telemetry for operators.

Progress (2026-04-09):

1. Notebook 21 heartbeat monitoring now uses a reusable process module and emits periodic progress lines for long-running stages.
2. Remaining work: stress-test harness, end-to-end timeout validation, and stop-reason telemetry verification.
3. The support code was split into task-based modules for heartbeat monitoring and mention-type config normalization to keep the notebook orchestration-only.
4. Focused node-integrity timeout tests now verify timeout-warning events and phase-finish timeout/stop-reason summaries.
5. Added a reproducible timeout stress harness test for repeated batched refresh timeouts, validating resilient completion and accumulated warning telemetry.
6. Remaining work narrowed to end-to-end runtime evidence collection (cache-first + non-zero-network).

Closure Notes (in progress):

1. Task completion marked: timeout telemetry, stress harness, and heartbeat instrumentation slices are implemented and test-covered.
2. Remaining tasks listed: publish one cache-first and one non-zero-network runtime rerun artifact bundle demonstrating timeout-resilient completion behavior.
3. Lessons learned documented: operator validation is more reliable when notebook closeout writes structured evidence bundles instead of requiring manual log extraction.
4. Further potential captured: include optional phase-duration and retry-attempt histograms in runtime evidence payloads.
5. Additional tasks captured: link the first Step 12 runtime evidence bundle directly in GRW-005 closure notes when runtime reruns are executed.

### GRW-006 (P0): Final root-cause closure for mention-type overwrite concern

Origin: WDT-020

Goal:

- Prove that fallback mention-type config cannot silently revert to `person`, including notebook execution-order edge cases.

Acceptance:

1. Reproduce original reported behavior (or prove stale-cell artifact cause).
2. Add notebook-order guardrails/tests to prevent stale config leakage.
3. Operational evidence from rerun showing configured mention types are respected.

Progress (2026-04-09):

1. Notebook configuration now resolves fallback mention types once and enforces immutable snapshot checks before fallback usage.
2. Mention-type guardrail support module tests now verify snapshot-drift rejection deterministically.
3. Remaining work: runtime rerun evidence (cache-first and non-zero-network) showing configured mention types are respected end-to-end.
4. Added Notebook 21 Step 12 runtime evidence closeout so each run can persist mention-type configuration context and stage outcomes in one structured artifact.

Closure Notes (in progress):

1. Task completion marked: mention-type resolution and snapshot guardrail enforcement are implemented and test-covered.
2. Remaining tasks listed: collect cache-first and non-zero-network runtime evidence bundles proving configured mention types are respected end-to-end.
3. Lessons learned documented: immutable config snapshots reduce stale-cell drift risk, but operational closure still depends on publishing rerun artifacts.
4. Further potential captured: add explicit mention-type decision counters to runtime evidence output for faster closure review.
5. Additional tasks captured: publish one Step 12 evidence artifact link that includes `fallback_enabled_mention_types_resolved` and fallback-stage outcome counts.

### GRW-007 (P1): Legacy JSON cutover completion

Origin: design step 05_legacy_json_cutover.md

Goal:

- Remove active runtime dependency on `entities.json` / `properties.json` after complete reader migration to chunk/index lookup.

Acceptance:

1. Consumer inventory complete and migrated.
2. Legacy writers removed.
3. Snapshot schema cleaned and verified.

Progress (2026-04-10):

1. Added `legacy_artifact_inventory.py` to generate machine-readable consumer inventories for `entities.json`, `properties.json`, and `triple_events.json` references.
2. Inventory output now persists as timestamped CSV/JSON artifacts plus a stable latest JSON pointer under `data/20_candidate_generation/wikidata/inventory`.
3. Active node-store runtime persistence now writes projection-backed `entity_store.jsonl` and `property_store.jsonl` paths.
4. Runtime node/triple store paths now run projection-only; legacy JSON read fallback paths were removed under clean-slate rework policy.
5. Retired artifact inventories now classify each reference by `access_mode` and include a local context window to prioritize high-risk runtime dependencies first.
6. v2->v3 migration entrypoints are now explicitly disabled to enforce clean-slate runtime policy.

Closure Notes (in progress):

1. Task completion marked: inventory automation exists and can drive deterministic cutover planning.
2. Task completion marked: node-store runtime write-path cutover to projection-backed store artifacts is implemented.
3. Task completion marked: legacy runtime consumers and fallback read branches are removed from active node/triple store paths.
4. Lessons learned documented: clean-slate cutovers are clearer when runtime paths are fully projection-only rather than carrying optional legacy branches.
5. Lessons learned documented: automated consumer inventories reduce migration blind spots compared with ad-hoc reference hunting.
6. Task completion marked: inventory rows now include access-mode classification to support risk-prioritized migration sequencing.
7. Task completion marked: pre-rework import entrypoints are now disabled to prevent accidental legacy data reintroduction.

### GRW-008 (P1): `triple_events.json` retain-or-remove decision

Origin: design step 06_triple_events_decision.md

Goal:

- Make explicit lifecycle decision for `triple_events.json` with replay requirements evidence.

Acceptance:

1. Consumer inventory with keep/remove disposition.
2. Decision record and implementation.
3. Tests/documentation aligned to final lifecycle.

Progress (2026-04-10):

1. Implemented projection-first triple-store lifecycle: runtime writes now persist through `triples.csv` instead of `triple_events.json`.
2. Removed legacy-read fallback from active runtime path so triple lifecycle is projection-only.
3. Updated checkpoint runtime-state snapshot inventory to stop treating `triple_events.json` as an active runtime state artifact.

Closure Notes (in progress):

1. Task completion marked: lifecycle implementation decision is now encoded in runtime behavior (projection-first write path).
2. Task completion marked: runtime lifecycle is projection-only and no longer supports legacy fallback reads.
3. Lessons learned documented: lifecycle cutovers are safest when runtime writes and reads are both switched to the same projection contract.
4. Further potential captured: remove residual documentation references that still imply transitional fallback behavior.

### GRW-009 (P1): Context-aware fallback for unknown strings

Origin: rework intake 2026-04-09

Goal:

- Add a faster, class-scoped candidate acquisition path for long unknown-string sets, especially when the class is already known but the Wikidata match is not.

Acceptance:

1. Identify at least one class-scoped retrieval strategy that reduces pressure compared with the current fallback string matching stage.
2. Define how the known class context is supplied to the lookup path and how the result re-enters graph expansion.
3. Document when SPARQL-style or equivalent class-aware queries should be preferred over generic fallback matching.

Progress (2026-04-09):

1. Added a new class-scoped retrieval strategy in `entity.py` using SPARQL-backed exact label/alias lookup constrained by known class context.
2. Fallback stage now supports class-aware preference before generic `wbsearchentities` lookup when class-scope hints are present (opt-in via config flags).
3. Focused tests validate cache/network behavior for class-scoped retrieval and fallback-stage preference/compatibility behavior.
4. Remaining work: notebook-level operator configuration guidance plus end-to-end cache-first and non-zero-network runtime evidence.
5. Notebook 21 now exposes operator-facing Step 2 config flags and Step 8 markdown guidance for class-scoped fallback behavior (`fallback_prefer_class_scoped_search`, `fallback_allow_generic_search_after_class_scoped`, `fallback_class_scoped_search_limit`) and forwards these values into fallback runtime config.
6. Fallback stage now emits class-scoped vs generic mode counters (`class_scoped_search_queries`, `generic_search_queries`, `class_scoped_hits`, `generic_hits`), and Notebook 21 Step 12 persists them in runtime evidence closeout artifacts.
7. Added ranked class-scoped lookup helper that prefers exact matches and then relaxed prefix matches before dropping to generic fallback.

Closure Notes (in progress):

1. Task completion marked: first class-aware retrieval slice is implemented and test-covered.
2. Remaining tasks listed: notebook runtime evidence and operator-facing config documentation still pending.
3. Lessons learned documented: opt-in rollout preserves baseline behavior while enabling targeted class-aware gains.
4. Further potential captured: extend class-scoped retrieval ranking and predicate strategy before generic fallback.
5. Additional tasks captured: add notebook flags/markdown, collect comparative query-pressure metrics, and promote from opt-in to default after evidence.
6. Task completion marked: notebook operator configuration guidance slice is now implemented in Notebook 21 and wired to Step 8 runtime execution.
7. Remaining tasks listed: publish cache-first and non-zero-network runtime evidence showing class-scoped preference effects under both strict-scoped and scoped-then-generic toggle modes.
8. Lessons learned documented: class-scoped retrieval controls are safer to roll out when operators can explicitly choose strict vs hybrid fallback behavior.
9. Further potential captured: add Stage 12 evidence counters for class-scoped hit rate vs generic-search fallback rate per mention type.
10. Additional tasks captured: attach first two Step 12 evidence bundles (cache-first and non-zero-network) to GRW-009 closure notes with class-scoped toggle settings included.
11. Task completion marked: mode-split fallback counters are implemented in runtime stage output and Step 12 evidence artifacts.
12. Remaining tasks listed: publish cache-first and non-zero-network rerun artifacts that demonstrate measurable pressure shift between class-scoped and generic fallback counters.
13. Lessons learned documented: explicit runtime counters reduce ambiguity compared with post-hoc log interpretation during closure review.
14. Further potential captured: extend mode-split counters with per-mention-type and per-language dimensions for attribution-quality analysis.
15. Additional tasks captured: add closure-note links to first artifacts that include both toggle-state context and mode-split counter deltas.

### GRW-010 (P1): Notebook architecture reconsideration and consolidation

Origin: rework intake 2026-04-09

Goal:
- Re-evaluate the notebook structure as a whole and allow major consolidation, including the possibility of collapsing currently scattered orchestration into fewer cells when that improves clarity, maintainability, or event-sourcing alignment.

Acceptance:

1. Define the notebook-architecture principles that justify consolidation or decomposition.
2. Identify which existing cells remain essential and which can be deprecated or merged once full event-sourcing potential is in place.
3. Establish a decision path for future restructuring so large-scale redesign is treated as an explicit rework option, not an exception.

Progress (2026-04-10):

1. Added `notebook_orchestrator.py` with shared budget-planning helpers for stage-level query-budget wiring.
2. Notebook 21 Step 6.5 now uses orchestration helpers for node-integrity budget planning instead of duplicating inline budget logic.
3. Notebook 21 Step 8 now uses orchestration helpers for fallback budget planning instead of duplicating inline budget logic.
4. Notebook 21 Step 11 now uses shared orchestration helper `build_benchmark_run_context(...)` for benchmark context assembly.
5. Notebook 21 Step 12 now uses shared orchestration helper `build_runtime_evidence_payload_parts(...)` for runtime-evidence context and stage-summary assembly.
6. Notebook 21 Step 12 now uses consolidated shared orchestration helper `build_runtime_evidence_payload(...)`, including explicit phase-outcome assembly for runtime evidence closeout payloads.
7. Shared benchmark/runtime-evidence context payload builders now include lineage resolution policy fields for cutover-attribution clarity.
8. Notebook 21 Steps 6/6.5/8/11 now use shared orchestration helpers for heartbeat interval/window and benchmark setting resolution.
9. Notebook 21 Steps 6.5 and 8 now use a shared `resolve_stage_a_queries_this_run(...)` helper for stage-budget counter derivation.
10. Notebook 21 Step 12 now uses shared `build_runtime_evidence_inputs(...)` wiring for fallback/reentry/node-integrity counter assembly.

Closure Notes (in progress):

1. Task completion marked: first consolidation slice moved orchestration math out of the notebook into reusable module code.
2. Task completion marked: Stage 11/12 context assembly is now extracted into shared orchestration helpers.
3. Remaining tasks listed: continue collapsing repeated notebook setup/runtime wiring into module-level orchestration helpers.
4. Lessons learned documented: budget-planning and closeout payload assembly are high-leverage extraction points because they are reused across stages and easy to drift when left inline.
5. Further potential captured: migrate remaining notebook closeout dispatch wiring and evidence-link rendering into the same orchestration module.
6. Lessons learned documented: shared stage-setting helpers reduce stale rerun drift because rerun-order dependencies now resolve from one module path.
7. Task completion marked: stage-budget and runtime-input counter wiring are now centralized in shared orchestration helpers used by Steps 6.5/8/12.
8. Task completion marked: heartbeat-setting reuse now resolves through shared orchestration helper `resolve_heartbeat_settings(...)` across repeated Step 6/6.5/8/9/11 heartbeat wiring.

## Workstream 4 — Architecture Simplification (phase-contract start)

Scope:

- Introduce explicit phase-contract payload structures in module code so orchestration events consistently expose contract and outcome semantics.

Progress (2026-04-10):

1. Added `phase_contracts.py` with shared phase-contract and phase-outcome payload builders.
2. Wired `heartbeat_monitor.py` lifecycle emissions to include explicit `phase_contract` and `phase_outcome` payloads.
3. Runtime evidence closeout now records explicit `phase_outcomes` assembled by shared orchestration helper logic.
4. Stage A graph expansion, Stage B fallback matching, and node-integrity discovery/expansion now emit explicit phase-contract declarations and structured `phase_outcome` payloads in lifecycle events.
5. Shared closeout context payloads now include migration-critical lineage-policy metadata.
6. Heartbeat monitor interruption/failure/stop lifecycle events now include explicit phase-contract payloads.

Closure Notes (in progress):

1. Task completion marked: initial phase-contract foundation and first integration point are implemented.
2. Task completion marked: phase-contract payloads now propagate across core stage lifecycle modules (expansion, fallback, node-integrity).
3. Remaining tasks listed: extend explicit phase-contract payload usage to any remaining orchestration/event modules outside the primary stage paths.
4. Task completion marked: runtime-evidence closeout payload now includes explicit Step 9 fallback re-entry phase outcome records.
5. Task completion marked: heartbeat monitor terminal lifecycle events now carry explicit phase-contract payloads.
6. Task completion marked: fallback re-entry helper now emits explicit Step 9 phase-contract declaration and completion outcome payloads.

### GRW-011 (P1): Recover subclass logic from reverse-engineered class hierarchy

Origin: reverse_engineering_potential/class_hierarchy.csv

Goal:

- Reconstruct the lost subclass and lineage logic from preserved reverse-engineering artifacts so class-aware eligibility, rollups, and context-scoped retrieval can rely on a locally derivable hierarchy instead of ad hoc checks.

Acceptance:

1. Derive subclass closure and `path_to_core_class` behavior from the reverse-engineering hierarchy evidence.
2. Reconcile recovered lineage with the normative Wikidata contracts before any rewrite of runtime behavior.
3. Document exactly which old subclass logic is recovered, which parts remain intentionally deprecated, and which gaps still require live Wikidata evidence.

Implementation detail plan:

1. `documentation/Wikidata/2026-04-10_great_rework/05_grw_011_lineage_recovery_implementation_plan.md`

Progress (2026-04-09):

1. Slices 1-5 implemented (loader, policy-aware resolver integration, materializer wiring + diagnostics, expansion/node-integrity consumption, runtime lineage telemetry + rollback guardrail).
2. Focused lineage tests pass; one broader test run still reports known unrelated checkpoint snapshot collision guard.
3. GRW-005 notebook runtime helpers are now extracted into a reusable process module and Notebook 21 emits periodic heartbeats during long-running stages.

Closure Notes:

1. Task completion: GRW-011 is implemented at the code path level and documented in the canonical map.
2. Remaining tasks: broader validation sweep, follow-on work in Workstreams 1-6, and separate tracking of the checkpoint snapshot collision guard.
3. Lessons learned: evidence-driven lineage recovery and policy-based rollback were lower-risk than heuristic reconstruction.
4. Further potential: reuse the lineage loader/policy pattern for future class-scoped acquisition work.
5. Additional tasks: keep adding workstream closure notes as the remaining backlog is retired.

## Suggested Execution Order

1. GRW-011
2. GRW-006
3. GRW-005
4. GRW-009
5. GRW-004
6. GRW-003
7. GRW-002
8. GRW-001
9. GRW-007
10. GRW-008
11. GRW-010

## Cross-Pipeline Input

Implementation patterns reusable from fernsehserien_de are documented in:

- `documentation/Wikidata/2026-04-10_great_rework/03_fernsehserien_de_event_learnings.md`
- `documentation/Wikidata/2026-04-10_great_rework/04_fernsehserien_transfer_execution_plan.md`
