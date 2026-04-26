# Notebook 21 — Cell-by-Cell Analysis
> Generated: 2026-04-26

Each cell is analyzed under three headings:
- **Goal** — what is this cell trying to achieve, and why does it exist?
- **Rules** — what constraints govern this cell (rate limits, budget, correctness invariants)?
- **Implementation** — how does it do it, and what are the issues?

---

## Cell 1 — Project Setup (find_repo_root)

**Goal:** Make the source package importable in the Jupyter session regardless of the working directory from which the notebook is opened.

**Rules:** Must be idempotent (re-running must not break the path). Must not mutate global state other than `sys.path`.

**Implementation:** Walks up the directory tree looking for `data/` + `speakermining/src/`. Appends the `src/` path to `sys.path`. Straightforward. No issues.

---

## Cell 2 — Graceful Stop Handler

**Goal:** Allow the user to press the stop button (or Ctrl-C) mid-run without corrupting the event store. A user-interruption should cause the expansion engine to complete the current network call cleanly and then stop, rather than being killed mid-write.

**Rules:** Must not install twice (idempotent). Must only intercept `KeyboardInterrupt` and the specific `RuntimeError("Termination requested")` sentinel — not other exceptions.

**Implementation:** Installs a custom IPython exception handler that calls `request_termination()` and returns an empty handler list (suppresses the traceback). Marks `_compact_graceful_stop_installed` in globals. Correct.

---

## Cell 3 — Workflow Config

**Goal:** Centralize all operator-configurable parameters in one place before any computation starts.

**Rules:**  
- `max_queries_per_run = 0` → pure cache mode, no network calls  
- `max_queries_per_run = -1` → unlimited  
- Query delay must be positive (rate limiting)  
- Budget is tracked as `query_budget_remaining` and decremented across steps

**Implementation:** Large dict literal covering 30+ parameters. Budget tracking is manual: each step decrements `config["query_budget_remaining"]` with its used queries. This is error-prone (if a step forgets to decrement, the budget is wrong). The config also sets environment variables for env-based config consumers (`WIKIDATA_SUBCLASS_EXPANSION_MAX_DEPTH` etc.), mixing two config styles. `recommend_query_delay_from_history` reads backoff history to provide delay guidance — this is a good adaptive feature.

**Issue:** No validation that the combined step budgets are consistent with `max_queries_per_run`. If `max_queries_per_run = 0` but network calls leak through, there's no hard enforcement in this cell.

---

## Cell 4 — Step 2.4: First-Pass Subclass Expansion (crawl_subclass_expansion)

**Goal:** Refresh the class hierarchy and subclass resolution map from the Wikidata P279 (subclass-of) graph, breadth-first from each core class. This ensures `class_resolution_map.csv` accurately maps every class node seen in entity P31 claims to its core class (person/org/episode/etc.). This must run before Step 6 so the expansion engine can correctly classify newly fetched entities.

**Rules:**  
- Cache-first: only issue network calls for P279 subclass queries not already cached  
- Budget-safe: uses config budget (typically 0 for a pure replay run)  
- Must complete before Step 6 (Step 6 checks `if "preflight_stats" not in globals()`)  
- Depth bounded by `subclass_expansion_max_depth` (default 3)

**Implementation:** Calls `materializer.crawl_subclass_expansion`. Internally does a breadth-first P279 inlink walk from each core class QID up to the configured depth. Cache-first for each page of results. Updates `class_resolution_map.csv` and `class_hierarchy.csv`. Also runs a superclass branch walk from active instance classes (via `superclass_branch_discovery_max_depth=5`), which walks UP the P279 chain from classes seen in P31 triples to connect them to a core class. **This is the expensive part**: at scale it iterates all items in the node store to find active classes.

Reloads `materializer_module` before the call. Does NOT reload `relevancy` — a consistent but dangerous pattern.

**Issue:** After this step runs, `class_resolution_map.csv` is updated — but `bootstrap_relevancy_events` inside `_materialize` (step 6) will rebuild the class_resolution_map independently. There is no caching contract that the class_resolution_map from step 2.4 is reused in step 6; step 6 recomputes everything from the event store.

---

## Cell 5 — Step 2.4.1: Conflict Analysis (inspect_class_resolution_conflicts)

**Goal:** Diagnostic cell. Show cases where the same class QID resolves to multiple different core classes (ambiguous classification). Helps operators identify rewiring rules to add.

**Rules:** Read-only. Purely diagnostic, produces no pipeline artifacts.

**Implementation:** Calls `conflict_analysis_module.inspect_class_resolution_conflicts` which reads `class_resolution_map.csv` and groups by `class_id` to find multi-core mappings. Prints a report. Correct.

**Issue:** None structurally. Could be moved to a separate analysis notebook.
   * **Clarification:** Can be moved to a separate analysis notebook.
---

## Cell 6 — Step 2.4.2: Property-Value Basic Hydration (run_property_value_hydration)

**Goal:** Ensure every QID referenced as a property value (via whitelisted predicates: P106 occupation, P102 party, P108 employer, P21 gender, P527 has-parts, P17 country) on an expanded core-class instance has entity data (labels, P31/P279) in the local entity store. Without this, role QIDs from persons' P106 claims would be unknown entities — invisible to class resolution and relevancy bootstrapping.

**Rules:**  
- Cache-first: skip QIDs already in the entity store with labels  
- Budget-bounded  
- Must run BEFORE step 2.4.3 (second-pass subclass expansion) so the hydrated occupation QIDs are available for the superclass branch walk

**Implementation:** Reloads `materializer_module`. Iterates core instance QIDs, reads their property triples for the whitelisted predicates, fetches missing entity docs from Wikidata API or cache, upserts into the entity store. For `hydrate_all_core_instance_objects=True` (default), also hydrates ALL objects of all expanded instance nodes.

**Issue:** With `hydrate_all_core_instance_objects=True` and 36,890 instances, this potentially checks a large number of object QIDs. The default is appropriate for completeness but adds time. The hydration itself writes to the node store (entity_store.jsonl / property_store.jsonl) via upsert — it does NOT write projections CSV files. Only the node store changes.
   * **Clarification:** It is fine if the CSV projections are only written once all is set and done. Everything that is only an output, not an intermediate storage, can be done at the end.

---

## Cell 7 — Step 2.4.3: Second-Pass Superclass Branch Discovery (crawl_subclass_expansion)

**Goal:** Re-run the subclass preflight with an extended seed set that includes objects from P106/P102/P108/P527/P17 triples in addition to P31 objects. This is specifically needed for occupation QIDs: after step 2.4.2 hydrates journalist Q1930187, this step walks UP Q1930187's P279 chain to connect it to Q214339 (role) in `class_resolution_map.csv`. Without this step, role subclass nodes would not appear in the class hierarchy.

**Rules:** Same as step 2.4. Must run AFTER step 2.4.2 (needs hydrated occupation nodes).

**Implementation:** Calls the same `crawl_subclass_expansion` function but passes `additional_active_class_predicates=("P106", "P102", ...)`. Internally this extends the set of "active classes" seeded for the upward branch walk to include objects of those predicates from expanded instances.

**Issue:** Steps 2.4 and 2.4.3 are the same function called twice. Together they dominate the non-step-6 runtime. The first call is needed to set up class hierarchy; the second is needed because step 2.4.2 hydrates new nodes. A single call with both passes included would be equivalent but require restructuring. The two calls are architecturally correct given the sequential dependency (2.4 → 2.4.2 → 2.4.3) but add runtime.
   * **Clarification:** This is a prime example of the need for redesign.

---

## Cell 8 — Step 2.5: Class Hierarchy Clarification

**Goal:** Runtime validation that core classes and root classes are disjoint. Prevents a configuration error where e.g. Q35120 (entity) was accidentally listed as a core class, which would cause the expansion engine to enumerate essentially all of Wikidata.

**Rules:** Core ∩ Root must be empty. Raises `ValueError` if violated.

**Implementation:** Loads `core_classes.csv`, defines `root_class_qids = {'Q35120', 'Q1'}`, checks intersection. Prints a summary. Stores `core_class_qids` and `root_class_qids` in config. Correct guard.

---

## Cell 9 — Step 3: Decide Resume Mode

**Goal:** Choose between `append` (continue from latest checkpoint) and `revert` (roll back one checkpoint then continue). Append is the safe default for normal continuation; revert is only for suspected-corrupted-checkpoint recovery.

**Rules:**  
- `append`: deterministic, non-destructive  
- `revert`: destructive (rolls back event store state); must only be used intentionally  
- Result stored as `resume_decision` dict used by step 6

**Implementation:** Calls `decide_resume_mode(ROOT, "append")`. Reads checkpoint manifests to find the latest valid state. Returns a dict with `mode`, `has_checkpoint`, and related metadata. Correct.

**Issue:** This step runs AFTER the preflight steps (2.4–2.5). Logically resume mode could affect preflight behavior (e.g., if revert mode rolls back the entity store, preflight should see the rolled-back state). In practice, preflight writes to `class_resolution_map.csv` directly, not through the checkpoint system, so revert/append doesn't affect preflight output. But the ordering is confusing — step 3 logically should precede step 2.4.
   * **Clarification:** This whole cell seems like a very, very dangerous and outdated artifact. Fundamentally, events must be preserved. If we want to rebuild our projections, we reset our projection caching and rerun the entire algorithm. No code, ever, should be able to delete an event. We can only build upon events, not delete them. If we change events, we write a new event handler that can convert the old events to new events and starting then only emits the new events. At no point in time do we ever want to delete events. 
   * **Clarification:** Generally, the whole concept of checkpoints seems counter-intuitive to correct event-handlers with correct event log. If the event log is correct, then every step is "continue where we left of last time" - this should be the default, not needing some kind of checkpoint system. Every event is a checkpoint. 
   * **Clarification:** This must be clearly differentiated from backups: Backing up the event log is a very good thing. Again: Loosing the event store is the worst thing that can happen to our system.

---

## Cell 10 — Step 4: Bootstrap and Load Seeds

**Goal:** Initialize required artifact files from setup data (core_classes.csv, broadcasting_programs.csv) and load seed instances (the specific Markus Lanz Wikidata QID). Seeds are the starting points for graph expansion.

**Rules:** Must run before step 5 (targets) and step 6 (expansion). Seeds must have valid wikidata_id values.

**Implementation:** `initialize_bootstrap_files` creates missing files from setup data. `load_seed_instances` reads `data/00_setup/broadcasting_programs.csv`. Seeds are the root QIDs for the BFS traversal. Correct.

---

## Cell 11 — Step 5: Build Mention Targets

**Goal:** Load the Phase 1 mention targets (persons, episodes, topics, etc.) that the expansion engine should try to match. These are the QID candidates that will be written to `graph_stage_resolved_targets.csv`.

**Rules:** Requires `data/20_candidate_generation/episodes.csv` and `broadcasting_programs.csv` to exist (from Notebook 20). Raises `FileNotFoundError` if missing.

**Implementation:** Calls `build_targets_from_phase2_lookup(ROOT)`. Returns target rows grouped by mention type. Correct.

---

## Cell 12 — Step 6: Graph Expansion Stage (run_graph_expansion_stage) ← CORE CELL

**Goal:** The main work cell. Expand the Wikidata graph from seed(s), discover all reachable entities matching core classes, match mention targets to discovered entities, and produce the final projection artifacts. This is the ONLY step that writes `core_*.json`, `relevancy.csv`, `triples.csv`, `instances.csv`, and all other full projection files.

**Rules:**  
- Must run after step 2.4 (preflight_stats check)  
- Budget-bounded; with `max_queries_per_run=0`, no network calls (pure cache replay)  
- Append mode: scans seeds in order, skips completed ones
   * **Clarification:** What does it mean for a seed to be "complete"? What happens if the status of a seed changed in the meantime? This may be another situation where a whole bunch of reworked logic may be skipped because "we've already done that seed, let's skip it" logic is applied.
- Must NOT be interrupted by user to get final materialization (graceful stop blocks `materialize_final`)
   * **Clarification:** Graceful stops should be the default at any step. Any kind of file writing should be guarded. This is not unique to this step - graceful stop is a fundamental requirement everywhere - in every cell, in every notebook.

**Implementation:**  
1. `run_graph_expansion_stage` iterates seeds. For each seed, calls `run_seed_expansion` which does BFS through the graph (cache-first or network). Emits events for each discovery/expansion/triple.  
2. After all seeds: if not user-interrupted, calls `materialize_final(repo_root, run_id=run_id)`.  
3. `materialize_final` → `_materialize`:
   - `flush_node_store` and `flush_triple_events` (flush in-memory caches to disk)
   - `_build_instances_df` — reads ALL events, builds DataFrame of known instances
   - `_build_properties_df` — reads all property events
   - `_build_triples_df` — reads all triple events
   - `_build_class_hierarchy_df` — builds class hierarchy from entity P279 claims
   - `_build_class_resolution_map_df` — maps all class nodes to their core class
   - Writes `triples.csv`, `class_hierarchy.csv`, `class_resolution_map.csv`, `instances.csv`, `properties.csv`
   - `bootstrap_relevancy_events` — BFS relevancy propagation, emits `relevance_assigned` events
   - `run_handlers(incremental)` — processes new events through handlers including `RelevancyHandler` → writes `relevancy.csv`
   - `_write_entity_lookup_artifacts` — entity lookup index
   - `_write_core_instance_projections` — reads `relevancy.csv`, writes `core_*.json` and `not_relevant_core_*.json`

**Issues:**  
- No reload of `relevancy` module (F2 from overview)
- All projection building is from scratch on every call — no incremental computation
- `_apply_core_output_boundary_filter` (called from within `_write_core_instance_projections`) calls `iter_unique_triples(repo_root)` which scans the full event store again — a third full event-store scan in a single `_materialize` call
- `iter_items(repo_root)` loads all entity docs from the node store into memory for the `entity_by_qid` dict — 36,890 items

---

## Cell 13 — Step 6 Heartbeat

**Goal:** Emit a summary heartbeat event recording what happened during step 6 for monitoring/audit purposes.

**Rules:** Read-only diagnostic. Does not affect pipeline state.

**Implementation:** `emit_event_derived_heartbeat` reads recent events and summarizes activity. Correct.
   * **Clarification:** Heartbeat - just like graceful shutdown - should be universal rule applied to every cell of every notebook. Whenever a cell runs for longer than a minute, the user must be able to see what it has been doing in the past minute. Whenever it makes an additional 50 network calls total, the user must informed. This heartbeat is at the center of runs that sometimes take hours to complete.

---

## Cell 14 — Step 6.5: Node Integrity Pass (run_node_integrity_pass) ← SECOND FULL MATERIALIZATION

**Goal:** Scan all known entities for integrity issues:
- Items that appear in triple events but have no discovery event (discovered only via triples, not as standalone entities)
- Items that are eligible for expansion but not yet expanded  
Repair found issues with targeted network calls (budget-permitting), then call `materialize_final` again to update projections.

**Rules:**  
- Budget-bounded (uses remaining budget after step 6)  
- Default `discovery_query_budget=0` and `total_expansion_query_budget=0` at budget=0 config → scan-only, no network repairs  
- Must run after step 6 (`result` global required)

**Implementation:**  
1. Calls `run_node_integrity_pass`, which iterates ALL known QIDs from the node store and checks each one.  
2. For missing nodes: issues batch `wbgetentities` calls (budget permitting).  
3. At end: calls `materialize_final` again → **second full `_materialize` call**.

**Issues:**  
- With 0 budget and no repairs needed, this step still calls `materialize_final` — **doubling the 20-minute I/O cost** for zero benefit.  
- Even with 0 repairs, the integrity scan still iterates all items (`iter_items`) and all triples (`iter_unique_triples`).  
- Writes diagnostics to `documentation/context/node_integrity/` — a documentation directory mixed with operational diagnostics.  
- The `materialize_final` at the end of node integrity will produce identical output to step 6's `materialize_final` (nothing changed) unless repairs occurred.

**Recommendation:** Step 6.5 should only call `materialize_final` if it actually made repairs (newly discovered or expanded QIDs > 0).
   * **Clarification:** In a redesign, such a mending step should not be needed. If we do our rules and planning and approach correctly, there will never be a state where our output requires an integrity pass. Yes, we can have a final, concluding, integrity check at the very end, evaluating all we did and if it meets our rules and expectations - but the way this integrity check is currently implemented treats it as a fundamental step to even get to the right result. Correctly, all rules it would apply are already applied when we get here.

---

## Cell 15 — Step 6.5 Heartbeat

Same as Cell 13. Diagnostic only.

---

## Cell 16 — Step 7: Build Unresolved Handoff

**Goal:** Prepare the list of mention targets not matched by graph expansion for the fallback string-matching stage.

**Rules:** Requires `result.unresolved_targets` from step 6. Must filter by `fallback_enabled_mention_types` (all False by default → no fallback runs).

**Implementation:** Reads `result.unresolved_targets`, builds `class_scope_hints` mapping mention type → core class QID for focused SPARQL searches. Checks that the `_fallback_enabled_mention_types_snapshot` hasn't changed since step 2 config (guards against cell-order bugs). Correct.

---

## Cell 17 — Step 8: Fallback String Matching
   * **Clarification:** VERY IMPORTANT NOTE: Fallback String matching should be completely postponed from this PHASE. If we ever re-implement such a thing, it will be part of its own notebook in Phase 3. As of right now, phase 2 should have only root node based behaviour, and any string matching - or really any interaction with sources not wikikdata - should be left to phase 3. This is an important aspect of this redesign. 

**Goal:** For unresolved mention targets, run scoped SPARQL label search and/or generic `wbsearchentities` to find Wikidata candidates that weren't reachable via the graph path. This is the "name search" fallback.

**Rules:**  
- All fallback types disabled by default (`person: False`, `topic: False`, etc.)  
- Budget-bounded: remaining budget after stage 6  
- Class-scoped search first if `fallback_prefer_class_scoped_search=True` (default False)

**Implementation:** Calls `run_fallback_string_matching_stage`. With all types disabled and `max_queries_per_run=0`, this cell does nothing meaningful in the typical run. Correct when fallback is enabled.

**Issue:** With all fallback types disabled, this cell still runs, does nothing, and takes a few seconds for overhead. Could be skipped entirely with a guard.

---

## Cell 18 — Step 9: Re-enter Eligible Fallback Discoveries

**Goal:** Fallback-discovered QIDs that are eligible for graph expansion (connected to core classes) are fed back into the expansion queue, so their neighborhoods are also explored.

**Rules:** Requires `fallback_result` from step 8. Uses same expansion config as step 6.

**Implementation:** Calls `enqueue_eligible_fallback_qids`. With no fallback discoveries, this is a no-op. Correct.

---

## Cell 19 — Step 10: Review Artifacts

**Goal:** Operator review cell. Load and display `instances.csv`, `triples.csv`, `query_inventory.csv`, `class_resolution_map.csv` for visual inspection.

**Rules:** Read-only. No side effects.

**Implementation:** Loads CSVs into DataFrames and calls `display()`. Useful for interactive inspection but adds memory pressure in large runs.

---

## Cell 20 — Step 11: Handler Benchmark

**Goal:** Run a reproducible timing benchmark of incremental vs. full-rebuild handler materialization, to track performance regressions.

**Rules:** Disabled by default (`handler_benchmark_run` not in config). Optional.

**Implementation:** Skipped by default due to missing config key. No-op in normal runs.

---

## Cell 21 — Step 12: Runtime Evidence Bundle

**Goal:** Write a structured closeout artifact capturing the full configuration, stage outcomes, and runtime metrics for this run. Used for reproducibility validation (GRW-005/006/009 requirements).

**Rules:** Reads globals from all previous steps. Should not fail if any step was skipped (all `globals().get(...)` with fallbacks).

**Implementation:** Calls `write_notebook21_runtime_evidence(ROOT, ...)`. Writes to `data/20_candidate_generation/wikidata/evidence/`. Correct.

**Issue:** Step 12 accesses `result.checkpoint_stats` but with `if "result" in globals() else {}` fallback — resilient to missing step 6. However it is at the bottom of the notebook so by convention always runs last.

---

## Summary of Cell-Level Issues

| Cell | Issue |
|------|-------|
| 3 (config) | Manual budget tracking; two config styles (dict + env vars) |
| 4, 7 (preflight) | `importlib.reload(materializer)` does NOT reload `relevancy` |
| 9 (resume) | Logically should precede preflight but is ordered after |
| 12 (expansion) | No reload; calls `_materialize` which rebuilds ALL projections from scratch every run |
| 14 (integrity) | Calls `materialize_final` unconditionally even when no repairs were made — **doubles 20-minute cost** |
| 17, 18 (fallback) | No-op when all types disabled, but still runs |
| All | No mechanism to verify that code changes in source files are reflected in the running kernel |
