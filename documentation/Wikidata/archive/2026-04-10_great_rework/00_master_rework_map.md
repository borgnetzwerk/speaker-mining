# Wikidata Great Rework - Master Map

Date created: 2026-04-09
Status: Canonical navigation and execution map
Scope: single top-to-bottom map covering backlog, findings, learnings, and implementation flow

## How To Use This Document

1. Start here for all planning and execution decisions.
2. Treat linked documents as source inventories and detail appendices.
3. Add new issues to the Intake section first, then map them into the ordered workstreams below.
4. Keep this map updated whenever priorities, dependencies, or closure evidence changes.

## Source Documents (Retained)

1. Backlog inventory: `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md`
2. Codebase findings inventory: `documentation/Wikidata/2026-04-10_great_rework/02_additional_codebase_findings.md`
3. Fernsehserien transfer learnings: `documentation/Wikidata/2026-04-10_great_rework/03_fernsehserien_de_event_learnings.md`
4. Fernsehserien transfer implementation slices: `documentation/Wikidata/2026-04-10_great_rework/04_fernsehserien_transfer_execution_plan.md`
5. GRW-011 code-level implementation plan: `documentation/Wikidata/2026-04-10_great_rework/05_grw_011_lineage_recovery_implementation_plan.md`
6. Closeout baseline: `documentation/Wikidata/2026-04-10_great_rework/00_status_quo_closeout.md`

## Mission And Constraints

Mission:

1. Rebuild Wikidata candidate-generation workflow to maximize determinism, observability, and efficiency before high-volume rerun.
2. Use the rework window to remove pre-rework shape constraints when a cleaner architecture is justified by the coding principles and specification contracts.

Constraints:

1. No destructive or ambiguous runtime behavior.
2. Event history and query provenance remain first-class assets.
3. Operator-visible progress must remain clear during long-running phases.
4. Changes must be testable and checkpoint-safe.
5. The notebook structure is provisional; architecture may be consolidated when that better serves the workflow contract.

## Rework Philosophy

1. Treat this rework as a clean slate, not a patch-only exercise.
2. Prefer the simplest architecture that still preserves provenance, replayability, and operator clarity.
3. Reconsider open tasks continuously; if a broader redesign is lower-risk and higher-value than piecemeal edits, document it and take it seriously.
4. Optimize around the authoritative contracts in `documentation/Wikidata/expansion_and_discovery_rules.md`, `documentation/Wikidata/Wikidata_specification.md`, and `documentation/coding-principles.md`.
5. Keep pre-rework structures only when they are still justified by the current contract.

## Reverse-Engineering Evidence To Harvest

1. `data/20_candidate_generation/wikidata/reverse_engineering_potential/class_hierarchy.csv` is the most valuable preserved evidence artifact for this rework because it can recover subclass closure, `path_to_core_class`, parent counts, and core-class rollups that are otherwise expensive to infer repeatedly at runtime.
2. `classes.csv` and `core_classes.csv` remain the authoritative contract inputs; reverse-engineering artifacts are only for reconstructing missing structure, not for redefining the contract.
3. `triples.csv`, `instances.csv`, `fallback_stage_candidates.csv`, and `query_inventory.csv` are useful for debugging and validation, but they should be mined for evidence rather than preserved as runtime architecture.
4. The reverse-engineering folder is not part of runtime architecture, yet it is still valuable as a recovery lens when it reveals contract-aligned structure.
5. Ignore pre-rework forms that do not improve the current contracts; keep only the parts that help recover lineage, eligibility, provenance, or replay safety.

## Core Candidate-Generation Principles

1. Contract first: expansion eligibility, class lineage, and output schemas are governed by the Wikidata specification docs, not by notebook convenience.
2. Graph-first authority: graph evidence decides expansion; string matching only proposes candidates that must be re-validated against graph and class rules.
3. Class context is first-class: when the class is known, acquisition should use that context explicitly instead of treating every unknown string as a generic label search.
4. Event history is the durable record: all long-running decisions, discoveries, and repairs should be explainable from append-only event history and replayable projections.
5. Cache-first and incremental: reuse local state before network calls, and prefer deltas over full rebuilds wherever a projection can be updated safely.
6. Notebook as orchestrator: the notebook should explain and sequence workflow phases; the actual candidate-generation logic belongs in modules that can be tested and reused.
7. Operator clarity is part of correctness: every mode, flag, and fallback path must state its consequences explicitly in code and nearby markdown.
8. Clean-slate redesign is allowed: when a larger structural simplification reduces complexity without breaking contracts, it should be treated as a primary option rather than a last resort.

## Lineage Recovery Principle

1. Rebuild subclass logic from preserved evidence before inventing new heuristics.
2. Use the reverse-engineered hierarchy to recover local class closure, then validate it against the authoritative Wikidata contracts.
3. Let recovered class lineage drive both expansion eligibility and class-scoped acquisition paths.
4. Keep lineage recovery modular so it can be reused by expansion, fallback, node integrity, and notebook review steps.

## Highest-Potential Solution Hypothesis

Current best direction:

1. Recover and centralize class-lineage logic first, using `reverse_engineering_potential/class_hierarchy.csv` to rebuild subclass closure and core-class rollups locally.
2. Split candidate acquisition into a staged, context-aware strategy layer that can consume the recovered lineage.
3. Keep Stage A graph-first and authoritative.
4. Replace the current generic fallback-only mindset with a class-scoped acquisition path for long unresolved string sets, especially where the mention type or class is already known.
5. Make generic fallback string matching the last-resort branch, not the main growth path.
6. Re-enter all successful discoveries into the existing graph-first expansion and integrity flow.
7. Use a thin notebook shell to orchestrate setup, stage selection, and review, while moving more decision logic into testable modules.
8. Preserve append-only event history and handler progress so the new acquisition layer remains replay-safe.

Why this is the strongest opportunity:

1. It directly reduces pressure on Wikidata by narrowing search to known class context.
2. It recovers lost subclass logic from evidence instead of recreating it by hand or repeating network calls.
3. It reuses the existing expansion/eligibility machinery instead of bypassing it.
4. It scales to the user’s stated future case: thousands of known-class but unknown-identifier strings.
5. It creates a cleaner seam for later notebook consolidation because orchestration and acquisition logic become more modular.
6. It aligns with the fernsehserien_de lessons on clear phase boundaries, evented repair, and explicit handler/projection progress.

Analysis loop for the rework:

1. Inspect existing code and docs for the strictest governing rule, not just the easiest path.
2. Identify the smallest change that unlocks the highest downstream leverage.
3. Prefer solutions that improve both operator experience and runtime cost.
4. Re-evaluate whether the notebook shape itself should shrink whenever the module layer becomes more expressive.
5. Record the current best hypothesis here and revise it as implementation evidence improves.

## Workstream 0: Lineage Recovery Foundation

Priority: P0/P1

Status: complete

Objectives:

1. Reconstruct the lost subclass closure and class rollup logic from preserved reverse-engineering evidence.
2. Make recovered lineage available to expansion, fallback, integrity, and notebook review paths.
3. Keep the recovered model aligned with the normative Wikidata contracts.

Primary items:

1. GRW-011

Completion gate:

1. Class hierarchy recovery is available as a reusable local module or documented derivation path.
2. Recovered subclass logic matches the specification contracts on representative classes.
3. The lineage recovery layer can be consumed by Workstream 5 without duplicating logic.

Implementation detail:

1. Use `documentation/Wikidata/2026-04-10_great_rework/05_grw_011_lineage_recovery_implementation_plan.md` for code-level slicing, tests, rollout gates, and rollback policy.

## Ordered Workstreams (Top To Bottom)

### Workstream 1: Safety And Correctness Gate (must pass before large rerun)

Priority: P0

Objectives:

1. Eliminate silent misconfiguration risk in fallback mention-type behavior.
2. Ensure long-run timeout resilience and non-silent runtime progress.
3. Enforce handler-progress governance for deterministic resume/replay.

Primary items:

1. GRW-006
2. GRW-005
3. GRW-003 (handler-governance subset)
4. FND-001
5. FND-005

Completion gate:

1. Notebook 21 runs with explicit config behavior and no silent fallback to unintended defaults.
2. Long-run Step 6.5 emits regular heartbeat and survives transient timeout patterns.
3. Handler progress is auditable per run with before/after sequence visibility.

### Workstream 2: Runtime Cost And Throughput Gate

Priority: P0/P1

Objectives:

1. Reduce avoidable full rebuild costs.
2. Reduce query volume/wall-time for large refresh workloads.

Primary items:

1. GRW-003 (incremental materialization core)
2. GRW-004
3. FND-002
4. FND-003
5. FND-004

Completion gate:

1. Incremental mode is default and measurable.
2. Non-zero-network benchmark shows improved throughput and lower redundant calls.
3. Full rebuild retained only as explicit maintenance/recovery path.

### Workstream 3: Artifact Lifecycle Cutover

Priority: P1

Objectives:

1. Finish retired pre-rework JSON consumer cutover and writer removal.
2. Decide final lifecycle of `triple_events.json` with evidence.

Primary items:

1. GRW-007
2. GRW-008

Completion gate:

1. Consumer inventory complete with zero active runtime dependency on retired artifacts.
2. Triple-events retain/deprecate decision implemented and documented.

### Workstream 4: Architecture Simplification And Contract Hardening

Priority: P1/P2

Objectives:

1. Move toward clearer handler-first event workflow.
2. Formalize event-phase contracts.
3. Complete Parquet-first internal transition while preserving external contracts.

Primary items:

1. GRW-001
2. GRW-002
3. Phase-contract actions from transfer plan (Slice 4)

Completion gate:

1. Handler-first execution paths are demonstrably simpler and replay-safe.
2. Event phase contract is documented and test-enforced.
3. Runtime is Parquet-first where intended, with contract CSV outputs preserved.

### Workstream 5: Context-Aware Candidate Acquisition

Priority: P1

Objectives:

1. Add a faster lookup path for long string sets when the class context is known but the Wikidata identifier is not.
2. Reduce pressure on Wikidata by preferring class-scoped lookup strategies over generic fallback matching where appropriate.
3. Re-enter any successful discoveries into the existing graph-first expansion flow.

Primary items:

1. GRW-009

Completion gate:

1. At least one class-aware retrieval path is implemented and documented.
2. The notebook can choose between generic fallback and class-scoped retrieval based on context.
3. Successful results are merged back into the authoritative graph workflow without bypassing expansion rules.

### Workstream 6: Notebook Architecture Re-evaluation

Priority: P1/P2

Objectives:

1. Reassess the notebook’s cell boundaries and orchestration shape against the current event-sourcing direction.
2. Consolidate functionality where that reduces complexity and improves maintainability.
3. Deprecate unnecessary code paths once a cleaner architecture is proven.

Primary items:

1. GRW-010

Completion gate:

1. Notebook structure is intentionally justified rather than inherited.
2. Major orchestration can live in fewer cells or a more centralized control flow when that is the better fit.
3. Structural changes are documented against the rework philosophy and contract docs.

## Crosswalk Matrix (Backlog + Findings + Learnings)

1. GRW-006 <- WDT-020 <- Safety gate <- no direct fernsehserien dependency.
2. GRW-005 <- WDT-016 <- Workstream 1 <- fernsehserien heartbeat pattern (Learning 1).
3. GRW-003 <- WDT-014 <- Workstream 1 and 2 <- handler-progress + evented-repair patterns (Learning 2 and 3).
4. GRW-004 <- WDT-015 <- Workstream 2 <- observability support from Learning 1.
5. GRW-007 <- design step 05 <- Workstream 3 <- lifecycle discipline from Learning 5.
6. GRW-008 <- design step 06 <- Workstream 3 <- phase-boundary and event-contract guidance from Learning 4.
7. GRW-002 <- WDT-013 <- Workstream 4 <- independent of fernsehserien traversal model.
8. GRW-001 <- WDT-011 <- Workstream 4 <- handler-first orchestration patterns from Learning 2 and 4.

9. FND-001 supports Workstream 1 hygiene.
10. FND-002 supports Workstream 2 incremental materialization.
11. FND-003 supports Workstream 2 deterministic decision-cost controls.
12. FND-004 supports Workstream 2 graph-neighborhood performance optimization.
13. FND-005 supports Workstream 1 operator contract clarity.
14. FND-006 supports Workstream 1 external-caller compatibility hardening.
15. GRW-009 supports Workstream 5 class-scoped lookup efficiency.
16. GRW-010 supports Workstream 6 notebook consolidation and architecture review.
17. GRW-011 supports Workstream 0 lineage recovery and Workstream 5 class-aware acquisition.

## Execution Sequence (Canonical)

0. Workstream 0
1. Workstream 1
2. Workstream 5
3. Workstream 2
4. Workstream 4
5. Workstream 3
6. Workstream 6

Execution logic:

1. Recover lineage first (Workstream 0) so class-aware decisions have stable local structure.
2. Lock safety/correctness next (Workstream 1) so later optimization does not amplify bad assumptions.
3. Add class-aware acquisition early (Workstream 5) because it directly addresses high-volume unknown-string workloads.
4. Optimize throughput once acquisition direction is clear (Workstream 2).
5. Simplify and harden architecture after core behavior stabilizes (Workstream 4).
6. Perform retired pre-rework artifact cutover after new architecture paths are proven (Workstream 3).
7. Consolidate notebook shape last to avoid repeated orchestration churn during upstream redesign (Workstream 6).

## Rework Status And Notes

Completed:

1. GRW-011 lineage recovery foundation has been implemented across resolver, materializer, expansion, and node-integrity paths.
2. Slice-level validation for lineage recovery passed on focused tests.
3. Runtime telemetry and rollback control were added so recovered lineage can be observed and disabled without code changes.
4. GRW-005 timeout warning telemetry is now validated in focused node-integrity tests, including phase-finish timeout/stop-reason summary evidence.
5. GRW-006 mention-type drift guardrail is now covered by focused support-module tests.
6. GRW-009 class-aware retrieval slice is implemented in fallback matching with a SPARQL-backed class-scoped lookup path and focused tests.
7. GRW-005 now includes a reproducible timeout stress-harness test that validates repeated timeout handling across batched node-integrity refreshes.
8. GRW-003 handler-governance subset is implemented: orchestrator now prunes stale handler registry rows and writes per-handler before/after sequence run summaries.
9. GRW-003 incremental materialization default slice is implemented in handler orchestration: no-op reruns now skip replay and projection rewrites in `incremental` mode, with explicit `full_rebuild` override.
10. GRW-003 pending-run bootstrap slice is implemented for replay-safe handlers: incremental mode now hydrates handler state from projections/node store so pending-event runs avoid full historical replay where the bootstrap source is trustworthy.
11. GRW-004 benchmark-helper slice is implemented: reproducible handler materialization benchmark artifacts (`incremental` vs `full_rebuild`) are now generated under `data/20_candidate_generation/wikidata/benchmarks`.
12. GRW-004 now includes first benchmark evidence artifacts from a representative non-zero-event local replay workload (`handler_materialization_summary_20260409T212657Z.json` and companion CSV files), showing zero historical replay in `incremental` mode versus replay in `full_rebuild` mode.
13. GRW-004 notebook closeout integration slice is implemented: Notebook 21 now includes Step 11 to run handler materialization benchmark evidence in normal workflow execution.
14. GRW-005/GRW-006 runtime-evidence automation slice is implemented: Notebook 21 now includes Step 12 plus `runtime_evidence.py` support module to emit structured closeout evidence bundles (`json` + `csv`) for configuration and stage outcomes.
15. GRW-009 notebook operator wiring slice is implemented: Notebook 21 now exposes class-scoped fallback controls (`fallback_prefer_class_scoped_search`, `fallback_allow_generic_search_after_class_scoped`, `fallback_class_scoped_search_limit`) and forwards them into Step 8 execution config.
16. GRW-009 runtime evidence mode-counter slice is implemented: fallback stage now emits class-scoped versus generic search/hit counters, and Notebook 21 Step 12 persists these counters in runtime evidence artifacts.
17. GRW-004 benchmark context-metadata slice is implemented: `run_handler_materialization_benchmark` now persists `run_context` in summary JSON artifacts, and Notebook 21 Step 11 passes runtime context metadata into benchmark evidence output.
18. GRW-003 parity support slice is implemented: a deterministic materialization snapshot comparison helper now compares incremental/bootstrap output trees against full-rebuild trees for future evidence capture.
19. GRW-003 parity artifact wiring slice is implemented: the benchmark helper can now write JSON/CSV parity reports when provided a control snapshot root.
20. GRW-009 class-scoped ranking slice is implemented: exact class-scoped search now falls back to ranked prefix search before generic lookup.
21. GRW-003 throughput-metrics slice is implemented: handler run summaries now record per-handler materialization duration and artifact size bytes for benchmark aggregation.
22. GRW-003 no-op text/CSV writer slice is implemented: shared atomic writers now skip identical rewrites for unchanged text and CSV artifacts.
23. GRW-003 local catalog/checksum writer slice is implemented: chunk catalog and checksum registry writers now skip identical rewrites as well.
24. GRW-003 shared io_guardrails writer slice is implemented: the common text/CSV helpers now skip identical rewrites across all callers.
25. GRW-004 benchmark CSV writer slice is implemented: benchmark run, summary, and parity CSV artifacts now use the shared atomic CSV helper.
26. GRW-008 lifecycle cutover slice is implemented: `triple_store` now persists runtime triples to `triples.csv` under projection-only semantics.
27. GRW-007 consumer-inventory slice is implemented: retired-artifact inventory automation now emits machine-readable inventories for retired artifact references (`entities.json`, `properties.json`, `triple_events.json`).
28. GRW-007 node-store cutover slice is implemented: runtime entity/property persistence is projection-backed (`entity_store.jsonl`, `property_store.jsonl`) and no longer depends on pre-rework JSON stores.
29. GRW-010 notebook-context extraction slice is implemented: Step 11 benchmark context and Step 12 runtime-evidence context assembly now use shared orchestration helpers.
30. Workstream 4 phase-contract slice has started: shared `phase_contracts.py` structures now emit explicit contract/outcome payloads from heartbeat orchestration.
31. GRW-010/Workstream 4 closeout slice is implemented: Step 12 runtime evidence now uses a consolidated shared payload helper that emits explicit phase-outcome records.
32. Workstream 4 phase-contract propagation slice is implemented: Stage A graph expansion, Stage B fallback matching, and node-integrity discovery/expansion now emit explicit phase contract declarations and phase outcomes in lifecycle events.
33. GRW-007 clean-slate lifecycle slice is implemented: runtime node/triple stores now operate projection-only with no pre-rework JSON read fallback path.
34. GRW-007 inventory-prioritization slice is implemented: retired artifact inventories now classify references by access mode and include local context windows for migration-risk triage.
35. GRW-010/Workstream 4 run-context hardening slice is implemented: shared benchmark/runtime-evidence payload helpers now include lineage policy context for deterministic attribution.
36. GRW-007/GRW-008 clean-slate enforcement slice is implemented: v2->v3 migration entrypoints are now explicitly disabled and cannot be invoked in runtime workflows.
37. GRW-003 writer-path hygiene slice is implemented: runtime evidence CSV emission now uses guarded atomic writer paths.
38. GRW-003 writer-path hygiene slice is implemented: checksum registry, chunk catalog, and checkpoint-manifest preservation now use shared guarded atomic text writers.
39. GRW-007 inventory clean-slate naming slice is implemented: retired-artifact inventory internals now use retired-artifact terminology consistently.
40. GRW-003 writer-path hygiene slice is implemented: handler progress registry (`eventhandler.csv`) now uses shared guarded atomic CSV writes instead of local temp-writer logic.
41. GRW-010 orchestration extraction slice is implemented: Notebook 21 now resolves heartbeat interval/window and benchmark toggles via shared notebook-orchestrator helpers.
42. Workstream 4 closeout payload coverage slice is implemented: Step 12 runtime evidence now includes explicit Step 9 fallback re-entry phase outcome payloads.
43. GRW-003 writer-path conversion slice is implemented: cache-layer `_atomic_write_text` and `_atomic_write_df` now delegate to shared guarded io helpers.
44. GRW-010 orchestration extraction slice is implemented: shared helpers now resolve stage-A query counters and runtime evidence input counters consumed by Notebook 21 Steps 6.5/8/12.
45. Workstream 4 lifecycle payload standardization slice is implemented: heartbeat monitor interruption/failure/stop lifecycle events now include explicit phase-contract payloads.
46. GRW-003 writer-path conversion slice is implemented: cache-layer `_atomic_write_parquet_df` now delegates to shared guarded parquet writer helper.
47. GRW-010 orchestration extraction slice is implemented: Notebook 21 heartbeat-setting reuse now resolves through shared `resolve_heartbeat_settings(...)` helper across repeated stage/heartbeat cells.
48. Workstream 4 lifecycle payload standardization slice is implemented: Step 9 fallback re-entry helper now emits explicit phase-contract and phase-outcome lifecycle payloads.
49. Clean-slate terminology sweep slice is implemented: status closeout wording now reflects retired-artifact terminology and clean-slate execution framing.

In Progress:

1. GRW-006 notebook configuration guardrail has been added to the Notebook 21 workflow cell and fallback-consumer cells.
2. Syntax validation for the edited notebook cells passed, and Step 12 runtime-evidence bundle automation is in place; execution-order and runtime rerun validation still need to be completed.
3. GRW-005 heartbeat and timeout monitoring now use reusable support modules (`heartbeat_monitor.py` and `mention_type_config.py`), and Notebook 21 emits periodic heartbeat progress for long-running stages.
4. GRW-009 rollout wiring is in progress: class-scoped search is operator-visible and mode counters are now emitted.
5. GRW-003 remains in progress overall: governance subset, no-op skip, pending-run bootstrap, and shared writer-path migration slices are complete, but broader non-event-sourced writer migration is still pending under Workstream 2.
6. GRW-010 notebook consolidation has progressed: shared budget-planning, heartbeat-settings, benchmark-settings, stage-A query resolution, and runtime-input builders now live in a dedicated orchestration module and Notebook 21 consumes them across Steps 6/6.5/8/11/12.

Remaining:

1. Workstream 2 throughput and cost reduction work remains open.
2. GRW-003 incremental materialization core still needs conversion of remaining non-event-sourced writer paths (parity evidence is deferred to final evaluation).
3. Workstream 4 architecture simplification remains open (phase-contract foundation started).
4. Workstream 6 notebook consolidation remains open after module-level design stabilizes.

Deferred (Execution-Policy Blocked):

1. GRW-006 end-to-end runtime rerun evidence proving configured fallback mention types in notebook execution-order edge cases.
2. GRW-005 end-to-end runtime timeout-resilience validation artifacts from notebook reruns.
3. GRW-004 notebook/non-zero-network benchmark runs and evidence publication using the same benchmark artifact contract.
4. GRW-009 end-to-end notebook evidence (cache-first and non-zero-network) showing class-scoped lookup preference and generic-fallback pressure shift.

Remaining Coding Tasks Before Full Notebook Rerun:

1. No remaining coding tasks in GRW-003/GRW-010/Workstream 4 are open after the coding-only closure pass.
2. Remaining pre-rerun work is execution-policy blocked evidence capture (listed above under Deferred), not additional code edits.

Code-Only Closure Mapping (Completed Items -> Files):

1. GRW-003 writer-helper closure: `speakermining/src/process/candidate_generation/wikidata/cache.py`, `speakermining/src/process/io_guardrails.py`, `speakermining/src/process/candidate_generation/wikidata/node_store.py`, `speakermining/src/process/candidate_generation/wikidata/materializer.py`.
2. GRW-010 notebook extraction closure: `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`, `speakermining/src/process/candidate_generation/wikidata/notebook_orchestrator.py`.
3. Workstream 4 lifecycle payload closure: `speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py`, `speakermining/src/process/candidate_generation/wikidata/heartbeat_monitor.py`, `speakermining/src/process/candidate_generation/wikidata/node_integrity.py`, `speakermining/src/process/candidate_generation/wikidata/phase_contracts.py`.
4. Clean-slate terminology closure: `documentation/Wikidata/2026-04-10_great_rework/00_master_rework_map.md`, `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md`, `documentation/Wikidata/2026-04-10_great_rework/00_status_quo_closeout.md`.

Lessons Learned:

1. Recovering structure from preserved evidence is safer than inventing new heuristics when the preserved evidence artifact already captures the missing lineage.
2. Policy-based precedence made rollout easier because runtime-only rollback stayed one switch away throughout the implementation.
3. The most stable validation path was a focused slice-by-slice test sweep rather than a broad all-at-once rerun.
4. Documentation stayed more useful when it tracked implementation state as it changed instead of waiting for a final summary pass.
5. Timeout telemetry tests that depend on notebook logger output must control logger global cache state to stay deterministic across test runs.
6. Guardrail checks become easier to validate when implemented in support modules rather than repeated inline notebook cell code.
7. Class-aware lookup should be introduced as an explicit opt-in switch first; this keeps baseline behavior stable while enabling targeted efficiency rollout.
8. Stress tests for timeout resilience are most stable when they simulate repeated batch failures without relying on live network timing.
9. Handler progress becomes materially easier to audit when every run emits deterministic before/after sequence summaries per handler.
10. Incremental mode must explicitly short-circuit no-pending reruns, otherwise handler replay/materialization overhead persists despite event-sourcing.
11. Handler bootstrap sources should match each handler's state model (`projection CSV` for tabular projections, `node_store` for class-resolution docs) to remain replay-safe.
12. Benchmark collection is more reusable when run-level rows and aggregated summaries are emitted together in stable machine-readable artifacts (JSON + CSV).
13. First benchmark captures should include pending-event rounds, otherwise `incremental` and `full_rebuild` can appear deceptively similar on pure no-op reruns.
14. Runtime validation is easier to operationalize when notebook closeout emits one structured evidence bundle instead of relying on manual log scraping.
15. Class-aware retrieval adoption is smoother when notebook-level operator toggles are explicit and printed in stage startup logs.
16. GRW-009 closure review is faster when runtime artifacts include explicit mode-split counters instead of inferring behavior from unstructured logs.
17. Benchmark evidence becomes significantly more reviewable when run-context metadata is embedded at artifact generation time rather than reconstructed later.

Further Potential:

1. GRW-011 can be extended into richer class-scoped acquisition helpers for the known-class/unknown-identifier case in Workstream 5.
2. The lineage evidence loader can become a reusable utility for additional notebook review and repair paths if future work needs local hierarchy reasoning.
3. The same policy pattern can be used for other risky recovery features that need a quick rollback path.
4. The timeout telemetry assertions can be generalized into shared test helpers for other long-running phases.
5. The mention-type config support module can be reused by other candidate-generation notebooks to enforce consistent fallback behavior.
6. Class-scoped lookup can be expanded with additional class predicates and language-aware ranking before generic fallback is attempted.
7. Handler run summaries can be extended with per-handler duration and changed-artifact byte counts for stronger throughput diagnostics.
8. Handlers can load state from existing projections to avoid full historical replay even when pending events exist.
9. Add bootstrap integrity checksums to detect projection/state divergence before incremental bootstrap is accepted.
10. Extend benchmark artifacts with per-handler duration breakdown and file-size deltas so GRW-004 evidence can attribute wins to specific projections.
11. Extend runtime evidence bundles with optional digest/checksum fields so parity claims can be compared across cache-first and non-zero-network runs.
12. Extend mode-split fallback counters with per-mention-type breakdowns to quantify class-scope gains at finer granularity.

Additional Tasks:

1. Run a broader targeted validation sweep to strengthen the GRW-011 closure evidence.
2. Add a closure note to the backlog for each workstream as it completes, not only for GRW-011.
3. Keep the checkpoint snapshot collision issue tracked separately so it is not conflated with lineage work.
4. Convert GRW-006 focused test evidence into a closure note once runtime rerun artifacts are captured.
5. Add one cache-first and one non-zero-network notebook rerun artifact proving GRW-006/GRW-005 behavior under real execution order.
6. Capture one cache-first and one non-zero-network run using opposite class-scoped toggle states and publish Step 12 evidence links proving the new mode-split counters and pressure-shift behavior for GRW-009 closure.
7. Promote GRW-005 stress harness into a reusable helper for other long-running notebook phases.
8. Add one rerun evidence artifact showing stale-handler pruning and before/after handler sequences in real notebook execution.
9. Extend the completed local replay benchmark evidence with a representative non-zero-network counterpart using the same artifact format.
10. Add parity validation artifacts proving bootstrap-assisted incremental runs are byte-equivalent to controlled full-rebuild outputs at the same event sequence.
11. Capture one non-zero-network Notebook 21 benchmark evidence run through Step 11 and publish it with the same JSON/CSV artifact contract.
12. Capture one cache-first and one non-zero-network Step 12 runtime evidence bundle and link both in GRW-005/GRW-006/GRW-009 closure notes.

Inside Workstream 1 and 2, use the detailed slices and code touchpoints from:

1. `documentation/Wikidata/2026-04-10_great_rework/04_fernsehserien_transfer_execution_plan.md`

## Intake Process For New Issues (Growth Mechanism)

When a new issue is discovered:

1. Assign new ID using prefix:
   - `GRW-XXX` for backlog-level work item
   - `FND-XXX` for codebase finding
2. Record it in source inventory document first.
3. Add a crosswalk row in this master map.
4. Place it into one workstream with priority and dependency notes.
5. Update execution sequence only if it changes critical path.

## Tracking Fields For Ongoing Updates

For each mapped item, maintain:

1. Status: not-started, in-progress, blocked, complete
2. Owner
3. Evidence link (test output, notebook run, docs)
4. Last updated date
5. Blocking dependency (if any)

## Change Log

1. 2026-04-09: Created canonical master map; source documents retained as referenced inventories.
2. 2026-04-09: GRW-011 implementation started; slices 1-3 completed with tests, slices 4-5 pending.
3. 2026-04-09: GRW-011 implementation completed; telemetry and rollback guardrails added, focused validation passed, and remaining workstreams preserved as follow-on items.
4. 2026-04-09: GRW-006 safety guardrail implementation started; Notebook 21 mention-type configuration now carries a frozen snapshot guard and downstream drift checks.
5. 2026-04-09: GRW-005 heartbeat implementation started; Notebook 21 heartbeat helpers moved into a reusable process module and long-run stage wrappers now emit periodic progress.
6. 2026-04-09: GRW-005 support module naming aligned with coding principles; helper code split into task-based support modules for heartbeat monitoring and mention-type config normalization.
7. 2026-04-09: GRW-005 timeout telemetry validation added; focused node-integrity tests now assert timeout-warning events and phase-finish stop-reason summaries.
8. 2026-04-09: GRW-006 guardrail testing added; support-module tests now assert mention-type snapshot drift is rejected deterministically.
9. 2026-04-09: GRW-009 class-scoped fallback slice added; fallback stage now supports SPARQL-backed class-scoped lookup with focused coverage for preference and generic fallback compatibility.
10. 2026-04-09: GRW-005 timeout stress harness added; focused node-integrity tests now cover repeated batched timeout behavior and confirm resilient completion semantics.
11. 2026-04-09: GRW-003 handler-governance subset completed; orchestrator now writes per-handler before/after sequence summaries and prunes unmanaged registry rows with focused tests.
12. 2026-04-09: GRW-003 incremental materialization default slice added; orchestrator now supports explicit `incremental`/`full_rebuild` modes and skips no-op rebuilds in incremental mode with focused tests.
13. 2026-04-09: GRW-003 pending-run bootstrap slice added; handlers now hydrate state from projections/node store so incremental pending runs avoid full historical replay with focused orchestrator coverage.
14. 2026-04-09: GRW-004 benchmark-helper slice added; new benchmark module now emits incremental-vs-full-rebuild run/summary artifacts with focused tests.
15. 2026-04-09: GRW-004 first benchmark evidence bundle captured on local non-zero-event replay workload; artifacts published under `data/20_candidate_generation/wikidata/benchmarks` and non-zero-network run remains open.
16. 2026-04-09: GRW-004 notebook closeout benchmark step added to Notebook 21 so benchmark evidence can be emitted from the standard run flow.
17. 2026-04-09: GRW-005/GRW-006 runtime evidence closeout slice added; Notebook 21 now emits standardized runtime evidence bundles via Step 12 and `runtime_evidence.py`.
18. 2026-04-10: GRW-009 notebook operator wiring slice added; Notebook 21 now surfaces class-scoped fallback toggles and passes them explicitly into Step 8 runtime config.
19. 2026-04-10: GRW-009 runtime evidence counters added; fallback stage now emits class-scoped/generic mode counts and Notebook 21 Step 12 persists them for closure evidence.
20. 2026-04-10: GRW-004 benchmark context metadata added; Step 11 now forwards run context into benchmark summary JSON artifacts for attribution-ready evidence.
21. 2026-04-10: GRW-003 parity helper added; materialization snapshot comparison now normalizes CSV artifacts for deterministic bootstrap vs full-rebuild parity checks.
22. 2026-04-10: GRW-003 parity report writer added; benchmark helper can now emit parity JSON/CSV artifacts for a reference root comparison.
23. 2026-04-10: GRW-009 ranked class-scoped search added; fallback stage now tries exact class-scoped lookup before a prefix-ranked fallback inside the same class scope.
24. 2026-04-10: GRW-003 throughput metrics added; handler summaries now track materialization duration and artifact size for benchmark aggregation.
25. 2026-04-10: GRW-003 no-op writer skip added; shared atomic text/CSV writers now avoid rewriting unchanged artifacts.
26. 2026-04-10: GRW-003 local catalog/checksum writer skip added; chunk catalog and checksum registry writers now avoid identical rewrites.
27. 2026-04-10: GRW-003 shared io_guardrails writer skip added; the common text/CSV helpers now avoid identical rewrites across all callers.
28. 2026-04-10: GRW-004 benchmark CSV writer added; benchmark run, summary, and parity CSV artifacts now use the shared atomic CSV helper.
29. 2026-04-10: GRW-008 triple-events lifecycle cutover added; triple store is now projection-only (`triples.csv`) for runtime state.
30. 2026-04-10: GRW-010 notebook orchestration refactor started; budget planning moved into shared module helpers consumed by Notebook 21 Step 6.5 and Step 8.
31. 2026-04-10: GRW-007 consumer inventory automation added; retired artifact references are now exportable as JSON/CSV inventory artifacts for cutover planning.
32. 2026-04-10: GRW-007 node-store projection cutover added; runtime entity/property persistence now writes `entity_store.jsonl` and `property_store.jsonl` under projection-only semantics.
33. 2026-04-10: GRW-010 context assembly extraction added; Notebook 21 Step 11/12 now use shared orchestration helpers for benchmark and runtime-evidence payload construction.
34. 2026-04-10: Workstream 4 phase-contract structures started; heartbeat orchestration now emits explicit phase contract/outcome payloads via `phase_contracts.py`.
35. 2026-04-10: GRW-010 + Workstream 4 closeout consolidation added; Notebook 21 Step 12 now uses shared payload assembly that includes explicit phase outcomes in runtime evidence artifacts.
36. 2026-04-10: Workstream 4 phase-contract propagation added; expansion/fallback/node-integrity stage lifecycle events now carry explicit phase contract declarations and structured phase outcomes.
37. 2026-04-10: GRW-007 clean-slate hardening added; node-store and triple-store now run projection-only with legacy JSON fallback paths removed.
38. 2026-04-10: GRW-007 inventory prioritization added; retired artifact inventory rows now include access-mode classification and local context excerpts for cutover planning.
39. 2026-04-10: GRW-010 + Workstream 4 run-context hardening added; benchmark and runtime-evidence payload builders now persist lineage-policy runtime context fields.
40. 2026-04-10: GRW-007/GRW-008 clean-slate enforcement added; v2->v3 migration entrypoints are now explicitly disabled.
41. 2026-04-10: GRW-003 writer hygiene added; runtime evidence CSV emission now uses guarded atomic writer paths.
42. 2026-04-10: GRW-003 writer hygiene expanded; checksum registry, chunk catalog, and checkpoint manifest-preservation writes now use shared guarded atomic text writers.
43. 2026-04-10: GRW-007 inventory clean-slate naming refined; retired-artifact inventory internals now use retired terminology consistently.
44. 2026-04-10: Added explicit coding-only completion checklist that must be closed before full notebook rerun and runtime evidence collection.
45. 2026-04-10: GRW-003 writer hygiene expanded; handler progress registry persistence now uses the shared guarded atomic CSV writer.
46. 2026-04-10: GRW-010 orchestration extraction expanded; Notebook 21 now uses shared heartbeat and benchmark-settings helpers across repeated stage wiring.
47. 2026-04-10: Workstream 4 closeout payload coverage expanded; runtime evidence phase outcomes now include explicit Step 9 fallback re-entry results.
48. 2026-04-10: GRW-003 writer conversion expanded; cache-layer atomic text/CSV helper implementations now delegate to shared guarded io helpers.
49. 2026-04-10: GRW-010 extraction expanded; Notebook 21 Step 6.5/8/12 counter wiring now uses shared stage-A and runtime-input orchestration helpers.
50. 2026-04-10: Workstream 4 lifecycle payload standardization expanded; heartbeat monitor interruption/failure/stop events now include phase-contract payloads.
51. 2026-04-10: Added explicit file-level code-only closure mapping for the remaining open workstream items prior to rerun evidence capture.
52. 2026-04-10: Closed the coding-only checklist; GRW-003/GRW-010/Workstream 4 now map to completed file-level notes and remaining pre-rerun items are execution-policy-blocked evidence capture only.
