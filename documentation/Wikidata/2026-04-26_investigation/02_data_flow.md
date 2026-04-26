# Notebook 21 — Data Flow
> Generated: 2026-04-26

---

## Storage Layers

The notebook uses four distinct storage layers:

```
┌──────────────────────────────────────────────────────────┐
│  Setup / Config (read-only input)                        │
│  data/00_setup/                                          │
│    broadcasting_programs.csv  ← seeds                   │
│    core_classes.csv           ← 7 core classes           │
│    relevancy_relation_contexts.csv  ← propagation rules  │
│    rewiring.csv               ← P279 overrides           │
└──────────────────────────────────────────────────────────┘
              │ read at steps 2.4, 4, 6
              ▼
┌──────────────────────────────────────────────────────────┐
│  Event Store  (append-only, authoritative)               │
│  data/20_.../wikidata/chunks/                            │
│    eventstore_chunk_2026-04-10_0001.jsonl  (550 MB)      │
│    eventstore_chunk_2026-04-24_0001.jsonl  (104 MB)      │
│  56,466 events total                                     │
│  Event types: query_response, entity_discovered,         │
│  entity_expanded, triple_discovered,                     │
│  class_membership_resolved, relevance_assigned, …        │
└──────────────────────────────────────────────────────────┘
              │ read by _materialize (full scan)
              │ written by expansion + bootstrap
              ▼
┌──────────────────────────────────────────────────────────┐
│  Node Store  (mutable JSON cache)                        │
│  data/20_.../wikidata/                                   │
│    (in-memory dict flushed to checkpoint entity store)   │
│  36,890 entity documents                                 │
│  Written: upsert_discovered_item                         │
│  Read: iter_items, get_item                              │
└──────────────────────────────────────────────────────────┘
              │ read by _write_core_instance_projections
              │ written by steps 2.4.2, 6
              ▼
┌──────────────────────────────────────────────────────────┐
│  Projections  (derived, rebuildable)                     │
│  data/20_.../wikidata/projections/                       │
│  Written exclusively by _materialize (step 6 + 6.5)     │
└──────────────────────────────────────────────────────────┘
```

---

## Per-Step Read/Write Map

### Step 2.4 (crawl_subclass_expansion — first pass)

**Reads:**
- Node store (all items via `iter_items`) — to find active classes
- P279 cache files (raw Wikidata subclass query results)
- `class_resolution_map.csv` (existing)

**Writes:**
- `projections/class_resolution_map.csv` (updated class→core mappings)
- `projections/class_hierarchy.csv` (updated class BFS result)
- `projections/classes.csv` (updated class list)
- Node store (new class nodes discovered via P279 walk, marked active)

**Does NOT write:** `core_*.json`, `relevancy.csv`, `instances.csv`, `triples.csv`

---

### Step 2.4.2 (run_property_value_hydration)

**Reads:**
- Node store (all items via `iter_items`) — to find property value QIDs
- Triple events (for whitelisted predicates P106/P102/P108/P21/P527/P17)
- Wikidata API (cache-first, for unhydrated QIDs)

**Writes:**
- Node store only (`upsert_discovered_item` for role/party/employer QIDs)

**Does NOT write:** Any CSV/JSON projections.

---

### Step 2.4.3 (crawl_subclass_expansion — second pass)

**Reads:** Same as step 2.4, but also uses P106/P102/P108/P527/P17 objects as additional BFS seeds.

**Writes:** Same as step 2.4 — updates `class_resolution_map.csv`, `class_hierarchy.csv`.

Note: After this step, role subclass QIDs (journalist Q1930187 etc.) should have entries in `class_resolution_map.csv` with `resolved_core_class_id = Q214339`.

---

### Step 6 (run_graph_expansion_stage → materialize_final → _materialize)

**Reads:**
- All 56,466 events from event store (multiple full scans)
- Node store (all 36,890 entity documents via `iter_items`)
- `data/00_setup/relevancy_relation_contexts.csv` (propagation rules)
- `data/00_setup/core_classes.csv`

**Writes (all projections):**
- `projections/instances.csv` + `.parquet`
- `projections/aliases_de.csv`, `aliases_en.csv` + parquets
- `projections/triples.csv` + `.parquet`
- `projections/class_hierarchy.csv` + `.parquet`
- `projections/class_resolution_map.csv` + parquet (may override step 2.4 output)
- `projections/properties.csv`
- `projections/relevancy.csv` (via RelevancyHandler after bootstrap_relevancy_events)
- `projections/relevancy_relation_contexts.csv`
- `projections/entity_lookup_index.csv` + parquet
- `projections/core_roles.json`, `core_persons.json`, etc. (7 core classes × 2 = 14 JSON files)
- `projections/instances_leftovers.csv`
- `projections/graph_stage_resolved_targets.csv`
- `projections/graph_stage_unresolved_targets.csv`
- `projections/fallback_stage_*.csv`
- Checkpoint snapshot (full copy of all the above)

**Internal computation flow in _materialize:**
```
flush_node_store + flush_triple_events
        │
        ▼
_build_instances_df ← iter_all_events (scan #1)
_build_triples_df   ← iter_all_events (scan #2, or separate iterator)
_build_properties_df
_build_class_hierarchy_df
_build_class_resolution_map_df
        │
        ▼ write tabular artifacts
        │
        ▼
bootstrap_relevancy_events
  ├── _load_existing_relevance_qids ← iter_all_events (scan #3)
  ├── Build qid_to_core_class from instances_df
  ├── Build class_qid_to_core_class from class_hierarchy_df  ← NEW (2026-04-26)
  ├── Scan triples_df for relation contexts
  └── BFS relevancy propagation → emit relevance_assigned events
        │
        ▼
run_handlers (incremental)
  └── RelevancyHandler processes new relevance_assigned events
      → writes relevancy.csv
        │
        ▼
_write_entity_lookup_artifacts
        │
        ▼
_write_core_instance_projections
  ├── iter_items(repo_root) ← load all 36,890 entity docs
  ├── _apply_core_output_boundary_filter
  │     └── iter_unique_triples ← scan #4 (again!)
  ├── read relevancy.csv → relevant_qids
  └── for each core class:
        filter instances by resolved_core_class_id
        filter by relevant_qids → core_*.json
        filter by NOT relevant → not_relevant_core_*.json
```

**Full event-store scan count per `_materialize` call: 4+**

---

### Step 6.5 (run_node_integrity_pass → materialize_final again)

Reads and writes same as Step 6. **Identical output if no repairs needed.**

---

## The Relevancy Gate

`core_roles.json` is gated by TWO conditions:

1. Role QIDs must appear in `class_nodes_df` — requires:
   - Being in the node store (satisfied by step 2.4.2 hydration)
   - Being in `class_hierarchy_df` with `resolved_core_class_id = Q214339` (satisfied by step 2.4.3)

2. Role QIDs must appear in `relevant_qids` — requires:
   - `bootstrap_relevancy_events` emitting `relevance_assigned` events for them
   - The P106 context `(Q215627, P106, Q214339)` being in approved_contexts
   - **Both were missing before 2026-04-26 fix**

---

## Checkpoint System

```
data/20_.../wikidata/checkpoints/
├── checkpoints.json        ← manifest of all checkpoints
└── snapshots/
    ├── checkpoint_..._0001.zip   ← old zipped snapshots
    ├── ...
    └── checkpoint_..._0016/      ← current unzipped snapshot
        ├── eventstore/           ← copy of chunk files (603 MB)
        ├── files/                ← copy of all projections (1.6 GB)
        └── checkpoint_....json   ← manifest
```

A checkpoint is written after each seed's expansion completes. It copies ALL projection files and the full event store. This means:
- 16 checkpoints × ~600 MB each = ~7.3 GB checkpoint storage
- Every checkpoint write re-copies 600 MB of eventstore + 1.6 GB of projections
- Old checkpoints are never pruned automatically

The checkpoint system provides resilience (can resume after crash) but at the cost of enormous disk usage.
   * **Clarification:** This checkpoint system should be deprecated. All we should back up is our event store. Everything else should be retrievable from there. If something in our code is not retrievable from the event store, we must change our code so it can be retrieved from the event store, by emitting the correct events.
