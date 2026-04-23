# Migration Test Run Evaluation

Date: 2026-03-31
Evaluator role: Migration meta evaluator (post-first-notebook-run safety review)
Scope: Notebook 21 first-run behavior, runtime guard-rail hardening, and anti-regression controls

## Incident Summary

During a first constrained run of Notebook 21 (`max_queries_per_run=10`), Stage B fallback behavior exposed a severe control risk:

1. Stage A (graph expansion) consumed the request budget correctly.
2. Stage B (fallback string matching) still issued many additional network calls in the same run.
3. Runtime behavior created the impression of an unbounded live-call loop and unacceptable pressure risk toward Wikidata services.

This is a high-severity operational issue because it can violate expected rate/budget limits and increase lockout risk.

## Root Cause Analysis

Primary root cause:
1. The low-level HTTP function allowed network requests without requiring an explicitly initialized request-budget context.

Contributing factors:
1. Request budget guard rails were context-based but not mandatory at network-call entry.
2. Fallback-stage budget handoff was config-driven and therefore susceptible to missing/inconsistent keys.
3. User-facing progress visibility for long-running endpoint traffic was insufficient.

## Remediation Implemented

### 1) Hard low-level guard rail (mandatory context)

Implemented in:
- speakermining/src/process/candidate_generation/wikidata/cache.py

Changes:
1. `begin_request_context` now requires explicit keyword `budget_remaining`.
2. `_http_get_json` now raises immediately if no request context is active:
   - `RuntimeError("Network request guard rails not initialized: begin_request_context must be called with explicit budget_remaining")`
3. Budget exhaustion remains enforced via `RuntimeError("Network query budget hit")`.

Effect:
1. Network calls cannot occur unless budget context is explicitly initialized.
2. Silent budget bypass paths are blocked at the lowest possible layer.

### 2) Common budget handoff across stages

Implemented in:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
- speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb

Changes:
1. Added `network_progress_every` to `ExpansionConfig` and passed into context initialization.
2. Fallback stage now reads `network_budget_remaining` (with compatibility fallback) from config.
3. Notebook Stage B now computes and passes remaining budget using common key `network_budget_remaining`.

Effect:
1. Stage B receives explicit residual budget from Stage A accounting.
2. Budget identifier usage is consistent and explicit across orchestrated stage handoff.

### 3) Runtime progress prints for notebook users

Implemented in:
- speakermining/src/process/candidate_generation/wikidata/cache.py

Changes:
1. Added progress emission controlled by `progress_every_calls` (default 50).
2. Output format includes context label and usage counter:
   - `[context_label] Network calls used: N / budget`
3. Stage contexts are labeled (`graph_seed:<qid>`, `fallback_stage`) to clarify active behavior.

Effect:
1. Notebook users receive recurring visibility into live call consumption.
2. Long calls are distinguishable from runaway call volume.

## Regression Protection Added

Implemented in:
- speakermining/test/process/wikidata/test_network_guardrails.py
- speakermining/test/process/wikidata/test_fallback_stage.py

Added/updated test coverage:
1. Hard-fail when low-level HTTP is called without request context.
2. Budget enforcement at HTTP layer (second call fails when budget is 1).
3. Progress-print emission after configured call interval.
4. Fallback-stage context initialization asserts explicit budget + progress settings.

## Residual Risk

1. Request budget controls number of calls, not total elapsed wall-clock duration.
2. Slow endpoints can still produce long run time under a small budget.

## Additional Follow-Up From Live Notebook Diagnosis

Observed in latest Notebook 21 run:
1. Notebook Step 8 previously printed `Stage A queries used: 0` even when Stage A had consumed query budget.
2. Cell-level runtime looked disproportionate (for example, long post-network time), but transitions were not explicit enough to isolate function-level bottlenecks.
3. Fallback scope needed stricter functional gating to avoid broad class coverage while labels remain noisy.

Implemented follow-up fixes:
1. Stage A summary now always carries `total_queries` and `stage_a_network_queries` from runtime accounting.
2. Added `stage_a_network_queries_this_run` and `total_queries_before_run` so append-mode runs report per-run usage correctly.
3. Runtime transition/timing logging was added to graph stage, fallback stage, and materializer functions (including sub-step timings and >20s warnings for materialization).
4. Notebook output now prints explicit step/function transitions and elapsed times for Step 6 and Step 8.
5. Notebook fallback configuration now explicitly enables only `person` mention type.
6. Fallback runtime now enforces mention-type allow-list from config (`fallback_enabled_mention_types`), defaulting to `person`.
7. Explicit fallback budget `0` now disables endpoint search (instead of being treated as unlimited).

Latest validation evidence (Notebook 21 rerun):
1. Step 6 printed `stage_a_network_queries_this_run: 10` with `max_queries_per_run=10`.
2. Step 8 printed `Stage A queries used (this run): 10` and `Fallback query budget remaining: 0`.
3. Fallback stage printed `Endpoint search disabled because explicit network budget is 0` and completed without endpoint-call progress lines.
4. Materializer timing diagnostics identified major bottleneck in `_build_instances_df`:
   - checkpoint materialization: ~84s
   - final materialization: ~85s
   - both stages emitted >20s warning lines.

## Materialization Deep-Dive (Iterative Optimization)

Goal:
1. Reduce materialization wall time to practical exploratory-run latency and remove hidden bottlenecks.

### Iteration 0 (Baseline Diagnosis)

Method:
1. Notebook-only profiling with cProfile and concise timers in Notebook 21.

Evidence:
1. `_build_instances_df` dominated runtime (~88-91s).
2. cProfile showed repeated calls into `_latest_cached_record` during class-path resolution.
3. `_latest_cached_record` repeatedly scanned and parsed raw query records, causing massive repeated I/O/JSON overhead.

### Iteration 1 (Design)

Optimization strategy:
1. Replace per-entity raw cache scans with a one-time index of latest `entity_fetch` records by QID.
2. Reuse in-memory `iter_items` snapshot (`item_by_id`) for parent lookups before touching raw cache.
3. Keep semantic behavior unchanged: class resolution still uses node-store entity first, then latest cached entity payload fallback.

### Iteration 2 (Implementation + Validation)

Implemented in:
1. speakermining/src/process/candidate_generation/wikidata/materializer.py

Key changes:
1. Added `_latest_entity_cache_paths(repo_root)` to build a latest-file index from filename tokens.
2. Removed `_latest_cached_record` calls from `_build_instances_df` fallback path.
3. Added in-memory `item_by_id` map and iterated over a single in-memory items list.
4. Loaded fallback record payload via `_load_raw_record(path)` only when needed for specific missing parent class QIDs.

Notebook re-measurement (same workspace state, module reloaded):
1. `build_instances`: from ~88.50s down to ~0.045s.
2. Full `_materialize`: from ~91.40s down to ~0.615s.
3. Fresh-kernel Notebook Step 6 rerun: stage elapsed ~20.02s with query budget 10.

Interpretation:
1. Materialization is no longer the dominant runtime bottleneck.
2. Remaining Step 6 time is now primarily graph-stage network execution and orchestration overhead, not materializer internals.

Regression validation:
1. Notebook-only test execution: `python -m pytest speakermining/test/process/wikidata -q`.
2. Result: 39 passed.

Open engineering tasks (tracked for next iteration):
1. Add dedicated performance regression test/benchmark for materializer (fixture-bound threshold).
2. Split Step 6 runtime into explicit network vs non-network aggregates in checkpoint summary for easier SLA tracking.
3. Gradually re-enable additional fallback mention types only after label-quality gates are validated.

Operational recommendation:
1. Keep low `query_timeout_seconds` during exploratory notebook runs.
2. Keep `network_progress_every` enabled (default 50) for transparency.

## Final Safety Verdict

Status: Remediated and hardened with materialization bottleneck substantially resolved.

The identified guard-rail gap has been closed with mandatory low-level enforcement, stage-wide explicit budget handoff, and user-visible progress reporting. Materializer bottleneck root cause was identified and fixed with validated iteration measurements. Regression tests are in place to prevent reintroduction.
