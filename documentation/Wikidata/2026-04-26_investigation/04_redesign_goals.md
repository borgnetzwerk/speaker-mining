# Notebook 21 — Redesign Goals and Principles
> Generated: 2026-04-26

This document captures what a redesign must preserve, what it must fix, and design principles that should guide it. It does not implement anything — it is the specification baseline.

---

## Goals We Must Keep
* **Clarification:** We must also explicitly acknowledge our fundamental principle files:
  * documentation/coding-principles.md
  * documentation/Wikidata/Wikidata.md
  * (add more if more apply)

### G1 — Correct candidate discovery
Given seeds (broadcasting programs), correctly discover all Wikidata entities reachable via the graph that match our core classes (persons, organizations, episodes, roles, topics, series, broadcasting programs). This is the primary output and must remain correct.

### G2 — Cache-first, Wikidata-respectful
Never issue a network call if a cached result exists. Honor rate limits. Respect the Wikidata usage policy. This is a hard constraint — the pipeline must be runnable with `max_queries_per_run=0` once data is cached.

### G3 — Append-only event store
Keep the event store append-only. Never mutate or delete events. Projections are derived artifacts; the event store is the single source of truth. This enables rebuildability and auditability.
   * **Clarification:** Let us explicitly formalize: Projections are only written from EventHandlers. Event handlers read events and react based on them. Event handlers cache the information what events they have read already.

### G4 — Resumable / fault-tolerant
A run interrupted mid-way must be resumable from the last checkpoint without losing work. Seeds already fully expanded must not be re-fetched.
   * **Clarification:** This rule / goal does not seem quite aligned with our overall goals. If our event-sourcing is applied correctly, we should be able to infer all current and future todos just from our event store state alone. We do not need an artifical checkpoint wrapper that additionally tries to preserve a kind of state, yet somehow different from our events.

### G5 — Correct relevancy propagation into class-node space
Role QIDs (journalist Q1930187, politician Q82955, etc.) are class nodes (P279) not instance nodes (P31). The relevancy engine must correctly propagate relevancy from relevant persons via P106 into the role class hierarchy. The `core_roles.json` file must contain role entities after a complete run.
   * **Clarification:** This is currently just one example. Long term, we must be able to propagate from any relevant subject A (meeting the requirement: is relevant) via some property P (meeting some requirements, e.g. "when subject is instance of human: allow P106 to propagate requirement to object) to some object (maybe also meeting some requirements, e.g. "must be instance/subclass of "episode"). The main idea is: Given some rules, propagate relevancy via a triple. Technically, there could also be a case where a subject gets the relevancy from the object (e.g. a season says it "has part" some relevant episode - so now the season is also relevant).

### G6 — Operator-controllable via config
All behavioral parameters (query budget, depths, predicates, fallback flags) must be configurable from the config cell without code changes.
   * **Clarification:** Technically, it must be configurable via a config, which can be a cell. If it is a cell, this has the downside of every config change changing the git state and the notebook appears changed, when only the config was changed. The correct solution would be to  modify a provided config file that is read by the config cell (and also initially created by with default parameters, raising an error to please look inside and configure it). This file should be self-explanatory enough that users know how to configure it just by opening and reading it.

### G7 — Auditable/reproducible outputs
Runtime evidence bundles (step 12) capture configuration and stage outcomes. Checkpoint manifests provide run history. These must be maintained.

---

## Rules We Must Follow

### R1 — No direct Wikidata reads outside the event store pattern
Every Wikidata network call must go through the cache/event-log system. No ad-hoc `requests` calls or SPARQL bypassing the cache.

### R2 — No destructive operations on the event store
No deleting, truncating, or rewriting event chunks. Repairs must be additive.

### R3 — Projections must be rebuildable from the event store alone
If all projection files are deleted, running `_materialize` must reconstruct them exactly. This rules out storing derived state only in projections.

### R4 — Core class identity is stable
The set of core classes (Q214339=role, Q215627=person, etc.) and their QIDs are defined in `data/00_setup/core_classes.csv`. Code must not hardcode these QIDs.

### R5 — Relevancy rules are config-driven
The `data/00_setup/relevancy_relation_contexts.csv` file defines which subject→property→object triples can propagate relevancy. Adding a new propagation rule must require only a CSV change, not a code change.

### R6 — Kernel restart required when source files change
There is currently no safe way to hot-reload deeply-nested module dependencies in a live Jupyter kernel. A kernel restart is required after any source file change. The notebook should document this clearly.

---

## Problems to Fix in a Redesign

### P1 — Unconditional double materialization (QUICK WIN)
Step 6.5 calls `materialize_final` unconditionally. With `max_queries_per_run=0` this always produces zero repairs and a redundant `_materialize` call (~5–6 min). Fix: only call `materialize_final` from node integrity if `len(newly_discovered_qids) + len(expanded_qids) > 0`.

### P2 — Multiple full event-store scans per `_materialize` (MEDIUM)
`_materialize` scans the event store 4+ times per call. The main opportunities:
- Combine `_build_instances_df` and `_build_triples_df` into a single event-store pass
- Remove the redundant `_apply_core_output_boundary_filter` → `iter_unique_triples` call (use `triples_df` that was already built)
- Pre-compute `existing_relevant_qids` from `relevancy.csv` (projection) instead of scanning the event log

### P3 — `_apply_core_output_boundary_filter` calls `iter_unique_triples` (MEDIUM)
This function builds an adjacency dict from all triples to compute the 2-hop neighborhood of seeds, then filters instances to that neighborhood. It's called twice (for instance df and class_nodes df). But `triples_df` was already built earlier in `_materialize`. Pass `triples_df` to this function instead of re-scanning.

### P4 — Event store growth makes every run more expensive (LONG TERM)
The store accumulates duplicate `relevance_assigned` events on every run. `bootstrap_relevancy_events` is designed to skip already-relevant QIDs but still scans the full log to determine which are already relevant. Options:
- Use `relevancy.csv` (the projection) as the "already-relevant" cache instead of re-scanning events
- Compact/archive old chunks after a complete successful run
- Move relevancy state to a dedicated lightweight store (e.g., a single CSV, updated in-place)

### P5 — Module reload does not cascade to sub-dependencies (OPERATIONAL)
`importlib.reload(materializer_module)` does NOT reload `relevancy.py`. Code changes to `relevancy.py` require a kernel restart. Add a comment or guard to make this explicit. In a redesign, the relevant modules should be reloaded in the correct dependency order, or the pipeline should use a single top-level module instead of deeply nested imports.

### P6 — Step ordering is confusing (MEDIUM)
Steps 3 (resume mode) and 4 (load seeds) should logically precede the preflight steps (2.4), since preflight could theoretically depend on the resume state. Reorder: setup → resume decision → seeds → preflight → expansion.

### P7 — Double crawl_subclass_expansion (MINOR)
Steps 2.4 and 2.4.3 call the same function twice. A single call with both seed sets (P31 objects + whitelisted predicate objects) would be equivalent and faster. The current structure exists because step 2.4.2 (hydration) must run between them to populate occupation nodes. A possible redesign: merge hydration into the preflight crawl.

### P8 — Checkpoint bloat (OPERATIONAL)
16 snapshots totalling 7.3 GB. Each checkpoint copies the full event store (654 MB) and all projections (~1.6 GB). Consider:
- Compressing snapshots automatically after N days
- Pruning to keep only the last 3 snapshots
- Using delta snapshots (only changed files)

---

## Design Principles for a Redesign

### DP1 — One full event-store scan per `_materialize` call
All derived DataFrames (instances, triples, properties) should be built in a single pass through the event store, not in separate passes. This requires a combined event dispatcher that routes events to multiple consumers simultaneously.

### DP2 — Use projections as caches where possible
`relevancy.csv` is the authoritative projection of relevancy state. `bootstrap_relevancy_events` should load `relevant_qids` from `relevancy.csv` instead of re-scanning the event log. Only scan events if the projection is stale or missing.

### DP3 — Conditional materialization
`materialize_final` should accept a `force=False` parameter. When called with `force=False`, it should hash/checksum the input state (event store size + node store mtime) and skip writing if nothing has changed since the last successful materialize. Write a materialization marker (e.g., `.last_materialized.json`) recording the input state.

### DP4 — Pass already-computed data rather than re-reading
`_apply_core_output_boundary_filter` should accept `triples_df` as a parameter rather than calling `iter_unique_triples` again. Anywhere a function currently re-reads a file that was already computed earlier in the same call chain, pass the data instead.

### DP5 — Explicit module reload order or kernel restart gate
Either:
(a) At the top of each cell that calls into the module hierarchy, reload dependencies in order: `relevancy → materializer → expansion_engine`, or
(b) Add a kernel-restart guard (check `sys.modules` timestamps vs file mtimes) and warn if stale modules are detected.

### DP6 — Node integrity materialization is conditional
Only call `materialize_final` from node integrity if repairs were made. The integrity scan itself is valuable; the unconditional re-materialization is not.

### DP7 — Notebook step numbering should reflect logical sequence
Renumber steps after a redesign: 1 (setup) → 2 (config) → 3 (resume/seeds) → 4 (preflight) → 5 (expansion) → 6 (integrity, conditional) → 7 (fallback) → 8 (re-entry) → 9 (review). Eliminate the mid-decimal sub-steps.

---

## What a Successful Redesign Looks Like

A well-functioning Notebook 21 should:
1. Complete a full "Run All" (cache-only) in under **5 minutes** on current data
   * **Clarification:** Speed is a good indicator, but overall, it is not our goal. Yes, a correct run should conclude almost instantly if we need to change nothing, since all event handlers would just say "I am up to date, no new events, I don't need to do anyhting" - yet keep in mind that runtime is only a symptom of our design. If we do a great design that ends up taking 7 minutes, but meets our goals perfectly, this is a non-issue. 
2. Write `core_roles.json` with journalist/politician/etc. entries
   * **Clarification:** This is very specific example of a current shortcoming. What this should be is "writes every relevant core class entity (instance or otherwise) into it's own core_*.json, for example entities such as "journalist" or "politician" to "core_roles.json"
3. Have a single clear "all projections updated" step with no duplicate runs
   * **Clarification:** This should be done by event-handlers all the time, not at one single point. The only thing that needs to be done at the very end is outwards facing projections only, such has handover csv that are generated as output-only and never used internally in any way. This - yes - can be done one time at the very end.
4. Require kernel restart only when explicitly changing code (with a visible warning)
   * **Clarification:** Non-issue, that is already expected behaviour
5. Prune old checkpoints automatically (keep last 3)
   * **Clarification:** Keep coding principles in mind. Also consider all clarifications regarding checkpoints.
6. Pass `triples_df` to sub-functions instead of re-reading from the event store
   * **Clarification:** This is quite focussed on the current implementation. if we do a proper redesign, we should not focus on how things are done right now.
7. Load `existing_relevant_qids` from `relevancy.csv` rather than scanning 654 MB of events
   * **Clarification:** EXACTLY the wrong assumptions at play here. If we want to get existing_relevant_qids, we ask the relevancy event handler. This one scans the events - BUT: Since the event handler remembers what events it read already, it will only read the last few events it hadn't had the chance to uptate on yet. It will then grant a new projection and give this as a response to our question. We MUST do everything via the event log - we just must not do it all over and over again from the very begining, only the new events since any given event handler last had the chance to catch up.