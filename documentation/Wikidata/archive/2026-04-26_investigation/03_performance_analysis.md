# Notebook 21 — Performance Analysis
> Generated: 2026-04-26  
> Observed: ~20 minutes for a full "Run All" with `max_queries_per_run = 0` (no network calls)

---

## Where the Time Goes

The 20-minute runtime with zero network calls comes almost entirely from local I/O and computation. Major bottlenecks in order of estimated cost:

---

### Bottleneck 1 — Full event-store scan × N per `_materialize`

**Cost estimate: ~10–12 minutes total (5–6 min × 2 calls)**

`_materialize` is called twice per run (step 6 + step 6.5). Each call scans the full event store at least 4 times:

| Scan | Who calls it | Event store size |
|------|-------------|-----------------|
| `_build_instances_df` | `iter_all_events` | 654 MB JSONL |
| `_build_triples_df` | `iter_all_events` | 654 MB JSONL |
| `_load_existing_relevance_qids` (bootstrap_relevancy) | `iter_all_events` | 654 MB JSONL |
| `_apply_core_output_boundary_filter` (×2) | `iter_unique_triples` | 654 MB JSONL |

Each full pass through 56,466 JSONL events requires JSON parsing of a 654 MB file. At typical Python JSONL parsing speeds (~50–100 MB/s for mixed-size records), a single pass is 7–13 seconds. Four passes per `_materialize` × two `_materialize` calls = **8 full scans of 654 MB each**.

The event store contains 50,001 events in the first chunk (April 10, from the main expansion run) and 6,465 in the second (April 24, from recent re-runs). The bulk is the April 10 chunk which grows with every checkpoint.

**Note:** `_build_instances_df` and `_build_triples_df` likely use the same underlying `iter_all_events` iterator, but are called separately, resulting in two full passes rather than one combined pass.

---

### Bottleneck 2 — `iter_items` loading 36,890 entity docs

**Cost estimate: ~2–3 minutes per `_materialize` call**

`_write_core_instance_projections` calls `iter_items(repo_root)` to build `entity_by_qid` — loading ALL entity documents from the node store. With 36,890 entities (persons, organizations, episodes, roles, topics) and many having hundreds of Wikidata claims, this is a large in-memory load. The node store is split across multiple JSONL files in the checkpoint.

---

### Bottleneck 3 — Double preflight (steps 2.4 + 2.4.3)

**Cost estimate: ~4–6 minutes total**

Each `crawl_subclass_expansion` call:
- Iterates all known items in the node store to find "active classes" (items used as P31/P279 targets) — scans all 36,890 items
- Runs superclass branch walks from active classes upward
- Rewrites `class_resolution_map.csv` and `class_hierarchy.csv`

With `superclass_branch_discovery_max_depth=5` and many active classes (potentially thousands from P106/P102 objects), the upward branch walk is substantial even if most results are cached. The second pass (step 2.4.3) with `additional_active_class_predicates` adds even more seeds for the upward walk.

---

### Bottleneck 4 — Unconditional `materialize_final` in step 6.5

**Cost estimate: same as Bottleneck 1 but avoidable**

Step 6.5 (node integrity) calls `materialize_final` at the end, regardless of whether any integrity repairs were made. With `max_queries_per_run=0`, there are ALWAYS zero repairs. This means the entire `_materialize` pipeline runs a second time, producing **identical output to step 6**, for zero benefit.

Fix: only call `materialize_final` from node integrity if `len(newly_discovered_qids) > 0 or len(expanded_qids) > 0`.

---

### Bottleneck 5 — Checkpoint write at step 6 completion

**Cost estimate: ~1–2 minutes**

After step 6 (if a seed boundary is crossed), a checkpoint snapshot is written. This copies:
- The full eventstore (654 MB)
- All projection files (~1.6 GB based on latest snapshot)

Total I/O per checkpoint write: ~2.3 GB. With fast local disk this is 1–2 minutes.

---

### Bottleneck 6 — Node integrity scan

**Cost estimate: ~1 minute**

Even with zero repairs, `run_node_integrity_pass` checks every one of the ~36,890 known QIDs for integrity (e.g., checking if items in triples but not in entity_store). It calls `iter_items` (full node store load) and `seed_neighbor_degrees` (reads all triples). With budget=0 it does no network calls but the scan still takes time.

---

## Summary Table

| Bottleneck | Est. Cost | Avoidable? |
|------------|-----------|-----------|
| Event store scan × 8 (2× _materialize × 4 passes each) | ~10–12 min | Partially — reduce scans per call; avoid second call |
| `iter_items` in `_write_core_instance_projections` (×2) | ~4–6 min | Partially — load entity docs once, cache |
| Double preflight (steps 2.4 + 2.4.3) | ~4–6 min | Partially — single pass with combined seed set |
| Unconditional step 6.5 `materialize_final` | ~5–6 min | **Fully avoidable** — skip if no repairs |
| Checkpoint write | ~1–2 min | Unavoidable if checkpointing enabled |
| Node integrity scan | ~1 min | Partially — skip if budget=0 and no repair needed |

**Total estimated removable time (low-hanging fruit):** 5–10 minutes from fixing the unconditional step-6.5 materialization and reducing duplicate event-store scans.

---

## Projection Build Cost vs. Benefit

The projection files are rebuilt completely from scratch on EVERY `_materialize` call. This is correct for robustness (projections are always consistent with the event store) but expensive when nothing changed. The projections include:

- `instances.csv` (36,890 rows, re-derived from all events)
- `triples.csv` (120,930 rows, re-derived from all events)
- `class_hierarchy.csv` (class BFS result)
- `class_resolution_map.csv` (potentially overwritten from step 2.4 output)
- All 14 `core_*.json` / `not_relevant_core_*.json` files
- Aliases, properties, entity lookup index

In a pure cache replay run where the event store is identical to the previous run, all output is identical to the previous run. The system has no way to skip writing if inputs haven't changed.

---

## Event Store Growth

The event store grows with every run because it is append-only. Each `bootstrap_relevancy_events` call emits new `relevance_assigned` events for the same entities. These are "idempotent" in effect (existing relevant QIDs are already in `existing_relevant_qids` and skipped) but **not idempotent in storage** — the events are still appended.

After 16 runs the April 10 chunk has 50,001 events (from the main expansion) and the April 24 chunk has 6,465 events from re-runs. At current growth rate, another 10 re-runs will add another ~40,000+ events, growing the store by several hundred MB more.

The 550 MB April 10 chunk is likely dominated by `query_response` events (each holding the full Wikidata API response payload for one entity). Each entity document can be 1–10 KB of JSON. With ~36,890 entities × 2 fetch rounds (outlinks + inlinks) × ~5 KB average = ~370 MB minimum just for query responses.

---

## Root Cause of 20-minute Runtime

**The architecture assumes the event store stays small (thousands of events). At 56,466 events and 654 MB, every full scan is expensive. The store has grown beyond the design assumption.**

The design is correct for the case where the event store is small (early development, frequent rebuilds). At production scale (one complete expansion run + many re-runs), the event store accumulates bulk that makes every subsequent `_materialize` call pay the full O(n_events) cost regardless of what changed.

A projection cache keyed on event-store checksum, or an incremental projection update system, would reduce the per-run cost to O(new_events_since_last_materialize).
