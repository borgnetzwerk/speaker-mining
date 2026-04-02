# Event-Sourcing Potential Unlock (v3) - Overview

Date: 2026-04-03  
Scope: Notebook 21, Step 6 graph-first expansion runtime behavior  
Focus: Convert v3 from event-log persistence to true event-driven runtime performance

---

## Executive Summary

The current v3 runtime is functionally event-backed but still behaves like a v2 mutable-store pipeline in hot paths. This causes severe throughput collapse in Step 6, with observed rates around 0.8 to 1.9 network calls per minute despite a configured request delay that should allow much higher throughput.

Primary unlock direction:

1. Stop repeated full event-store scans per cache lookup.
2. Stop re-initializing event writer per append.
3. Stop full JSON store rewrites inside the expansion loop.
4. Stop full projection rebuilds after each seed.
5. Move to incremental handler-driven projection updates using eventhandler progress.

This folder provides a concrete remediation sequence with quick wins first, expected speedups per change, and an implementation and validation protocol.

---

## Documents In This Folder

- 01_REMEDIATION_MAP.md
  - Prioritized refactor order.
  - Concrete file-level change scopes.
  - Expected speedup range per change and cumulative effect.

- 02_EXECUTION_CHECKLIST.md
  - Commit-sized execution order.
  - Validation gates, rollback rules, and acceptance criteria.
  - Benchmark protocol for Notebook 21 Step 6.

---

## Success Criteria For This Unlock Wave

1. Step 6 first progress heartbeat appears in less than 10 seconds on warm-cache runs.
2. Step 6 sustained network throughput improves by at least 5x versus current baseline on same data.
3. No behavioral regression in graph-first semantics, seed ordering, and checkpoint-resume contracts.
4. Projection artifacts remain deterministic and reproducible.
5. New domain events are emitted for discovery and expansion decisions, not only query_response.

---

## Progress Update

Completed and validated:

1. Cache lookup indexing now avoids repeated full event-history scans.
2. Event writes reuse a cached EventStore per repository root.
3. Node and triple store updates are buffered and flushed at stage boundaries.
4. Query inventory is maintained incrementally instead of being rebuilt from all events.
5. Empty JSON sidecar bootstrap has been removed; the stores are now lazy.
6. InstancesHandler no longer writes a compatibility entities.json sidecar; the CSV projection is the remaining handler output.

Validation completed:

- Notebook 21 ran end-to-end with `max_queries_per_run = 5` after the cleanup.
- Regression tests passed for buffering, checkpoint reset, bootstrap, and append-only event writing.
- Handler output tests now pass with `InstancesHandler` writing only `instances.csv`.

Next cleanup target:

1. Remove the remaining runtime mutable JSON sidecar compatibility path entirely once every consumer can read from event-backed or handler-backed projections.
2. Delete sidecar-specific restore and fallback logic after the final consumer cutover.
3. Retain only replayable event logs plus deterministic projections as the runtime contract.

Untapped event-sourcing potential (important):

1. Runtime still logs mostly `query_response`, which is insufficient for rich operational statistics and decision-level replay diagnostics.
2. Because domain decision events are missing, heartbeat and minute-level runtime summaries are weaker than they should be.
3. This gap affects observability, performance analysis, and historical reasoning about why expansion decisions happened.
4. Commit F (domain events) remains a major architecture unlock and should be treated as a deliberate later-wave deliverable, not expected to be fully closed this month.

Correct event sourcing would mean every decision that has future implications is logged: Candidate found for expansion, candidate matched, instance found to be a class, path to core class found, etc.
These are the fundamental building blocks of eventsourcing: eventhandlers reading AND WRITING events.

---

## Policy Alignment

This plan follows migration policy for v3 rollout:

- Preserve v2 behaviors that are already correct.
- Prioritize low-risk, high-impact fixes first.
- Separate legacy issues from true v3 regressions.
- Do not block rollout on known non-critical legacy defects if performance and correctness gates are met.
