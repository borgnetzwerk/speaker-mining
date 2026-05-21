# Notebook 21 Investigation — Overview
> Generated: 2026-04-26  
> Subject: `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`

---

## Purpose

Notebook 21 is the Wikidata candidate-generation phase of the speaker-mining pipeline. It takes broadcasting program seeds (Markus Lanz), expands the Wikidata graph outward through episodes → persons/organizations/topics → related entities, and produces a set of candidate matches for the Phase 1 mention targets. Output: per-class JSON files (`core_persons.json`, `core_roles.json`, etc.) plus CSV projections in `data/20_candidate_generation/wikidata/projections/`.

**Current scale:**  
- 9.6 GB total on disk in `data/20_candidate_generation/wikidata/`  
- 36,890 entities in the node store  
- 56,466 events across 2 JSONL chunks totalling **654 MB**  
- 120,930 triples  
- 16 checkpoint snapshots (7.3 GB, mostly zipped)

---

## Architecture (What It Is)

The notebook is built around an **event-sourced, append-only** design:

1. Every discovery (entity_discovered, entity_expanded, triple_discovered, relevance_assigned, …) is appended as a JSON event to chunk files under `chunks/`.
2. Projection files in `projections/` (CSVs, parquets, JSON) are **derived artifacts** rebuilt from the event store on demand.
3. A node store (`entity_store.jsonl`, `property_store.jsonl`) caches entity documents separately from the event log.
4. Checkpoints snapshot the full projection state periodically so a partial run can resume.

This architecture has clear correctness advantages (append-only, rebuildable) but significant **performance costs at current scale**.

---

## Step Summary

| Step | Cell | Function | Writes projections? | Notes |
|------|------|----------|---------------------|-------|
| Setup | 1–3 | path resolution, stop handler, config | No | |
| 2.4 | 4 | `crawl_subclass_expansion` | Some (class_resolution_map) | Cache-first P279 BFS |
| 2.4.1 | 5 | `inspect_class_resolution_conflicts` | No | Diagnostic only |
| 2.4.2 | 6 | `run_property_value_hydration` | Node store only | Hydrates P106/P102/P108/P21/P527/P17 objects |
| 2.4.3 | 7 | `crawl_subclass_expansion` (again) | Some (class_resolution_map) | Second pass with predicate-extended seeds |
| 2.5 | 8 | Class hierarchy validation | No | Diagnostic/guard only |
| 3 | 9 | `decide_resume_mode` | No | append vs revert |
| 4 | 10 | `initialize_bootstrap_files`, load seeds | Minimal | bootstrap CSVs |
| 5 | 11 | `build_targets_from_phase2_lookup` | No | Loads mention targets |
| **6** | 12 | `run_graph_expansion_stage` → `materialize_final` → `_materialize` | **All projections** | **Only step that writes core_*.json** |
| 6 heartbeat | 13 | `emit_event_derived_heartbeat` | No | Diagnostic |
| **6.5** | 14 | `run_node_integrity_pass` → `materialize_final` | **All projections again** | Integrity + second full materialization |
| 6.5 heartbeat | 15 | `emit_event_derived_heartbeat` | No | |
| 7 | 16 | Prepare unresolved handoff | No | Reads step 6 result |
| 8 | 17 | `run_fallback_string_matching_stage` | Fallback CSVs | String-match fallback |
| 9 | 18 | `enqueue_eligible_fallback_qids` | Node store | Re-entry for fallback hits |
| 10 | 19 | Load + display projections | No | Review cell |
| 11 | 20 | `run_handler_materialization_benchmark` | Benchmarks | Optional, skipped by default |
| 12 | 21 | `write_notebook21_runtime_evidence` | Evidence JSONL | Closeout artifact |

**Key finding:** `core_*.json` files are only written by `_materialize`, which is only called from `materialize_final`, which is called from `run_graph_expansion_stage` (step 6) and `run_node_integrity_pass` (step 6.5). The preflight steps (2.4–2.5) do **not** call `_materialize`.

---

## Major Findings

### F1 — 20-minute runtime is almost entirely IO on the event store

`_materialize` reads the full 654 MB event log at least twice per call:
- `_load_existing_relevance_qids` (in `bootstrap_relevancy_events`) scans all events for `relevance_assigned` type
- `_build_instances_df` iterates all events for entity state
- `_build_triples_df` iterates all events for triple state
- `_apply_core_output_boundary_filter` iterates `iter_unique_triples` **once per invocation** (called twice per `_materialize`)

With `run_node_integrity_pass` also calling `materialize_final`, the event store is fully scanned **twice per notebook run**. At 654 MB of JSONL parsing that alone accounts for most of the 20 minutes.

### F2 — Module reload pattern silently uses stale code

Cells 6 and 7 do `importlib.reload(materializer_module)` but do **not** reload `relevancy`. The expansion stage cell (step 6) does not reload anything. `expansion_engine` binds `materialize_final` at first import; that bound function carries whatever `bootstrap_relevancy_events` was loaded at kernel start. Any edits to `relevancy.py` require a **kernel restart** to take effect.

### F3 — roles are empty because class-node targets were never reachable

`bootstrap_relevancy_events` built `qid_to_core_class` only from instance nodes (items without P279). Role subclasses (journalist Q1930187, politician Q82955, …) have P279 and are excluded from instance space, so they had no core-class mapping. The triple `(person, P106, journalist)` had `object_core = ""` → skipped. Relevancy never propagated into class-node space. **Fix applied 2026-04-26**: see `relevancy.py` and `data/00_setup/relevancy_relation_contexts.csv`.

### F4 — Double preflight adds unnecessary time

Steps 2.4 and 2.4.3 both call `crawl_subclass_expansion`. The second call is intentional (it uses `additional_active_class_predicates` to connect occupation nodes via P106/P102/etc.) but still re-runs the full BFS with cache-first policy. Combined they account for a significant portion of the 20-minute run even without network calls.

### F5 — Checkpoint bloat

16 snapshots (7.3 GB). The 2 latest unzipped snapshots alone are 2.2 GB + 603 MB. Each snapshot is a full copy of all projection data. Old snapshots are never pruned automatically.

### F6 — Step numbering reflects organic growth, not design

Steps go 2.4 → 2.4.1 → 2.4.2 → 2.4.3 → 2.5 → 3 → 4 → 5 → 6 → 6.5 → 7 → 8 → 9 → 10 → 11 → 12. Steps 1 is missing; step 6 contains all the real work; steps 10–12 are review/benchmarking. The step numbering is a historical accident from incremental additions, not a logical sequencing.

---

## Files in This Investigation

| File | Content |
|------|---------|
| `00_overview.md` | This file — architecture, scale, major findings |
| `01_cell_analysis.md` | Cell-by-cell: goal, rules, implementation, issues |
| `02_data_flow.md` | What data flows where, what each step reads/writes |
| `03_performance_analysis.md` | Where the 20 minutes goes and why |
| `04_redesign_goals.md` | Goals, rules, and design principles for a redesign |
| `Clarification.md` | Aggregated user clarifications establishing the conceptual baseline |
| `05_related_tasks.md` | All open tasks and findings that must be considered in the redesign |
| `06_old_code_strategy.md` | Options for handling existing code; decision required before implementation |
| `07_glossary.md` | Vocabulary definitions; open questions marked ❓ require decisions before design |
| `08_known_rules.md` | All known rules in plain language; retired rules explicitly listed |
| `09_last_run_reference.md` | Final v3 notebook run (2026-04-26, 5000-call budget) — output preserved as design reference |
| `10_redesign_roadmap.md` | Stage-wise plan: what's done, what's next, what's blocked — authoritative progress tracker |
| `11_naming_decisions.md` | Final names for every ambiguous concept; one name per concept, with reasoning |
| `12_event_catalogue.md` | All event types: emitters, readers, payload fields, v3→v4 name decisions, backward-compat status |
