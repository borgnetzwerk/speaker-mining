# JSONL Event-Sourcing Migration (v3) — Overview

**Date:** 2026-04-02  
**Previous Release:** 2026-03-31 (v2, graph-first expansion)  
**Migration Status:** Implementation Complete (commit preparation)

---

## Executive Summary

**Policy Clarification (effective immediately):**
- v2 runtime is decommissioned and will not be executed again.
- Migration work proceeds as v3-only from this point forward.
- Legacy v2 query-response data is used only as import input into v3.

This migration evolves the Wikidata candidate generation pipeline from a v2 **checkpoint-based system** with append-only raw query files to a full **JSONL event-sourcing architecture**. The goal is to:

1. **Centralize event management**: Replace scattered JSON files (`raw_queries/`) and CSV aggregates with a single authoritative chunk chain under `chunks/`
2. **Improve data integrity**: Implement checksums, continuous sequence numbering, and corruption detection
3. **Enable reliable recovery**: Use event-driven handlers to rebuild state from events rather than file mosaics
4. **Maintain continuity**: Preserve the graph-first expansion semantics and class-driven eligibility rules established in v2

Explicitly **Out of Scope (Future Work):**
**Parallel processing patterns** (future): While we establish the foundation for multi-handler event processing without losing determinism, **parallel processing is explicitly NOT PART OF THIS MIGRATION**. We maintain a linear workflow to preserve simplicity.

---

## Key Differences: v2 → v3

| Aspect | v2 (Current) | v3 (Proposed) |
|--------|---|---|
| **Event Storage** | Per-query JSON files in `raw_queries/` dir | Date-stamped chunk files in `chunks/` |
| **Event Schema** | V2 envelope with versioning | Enhanced v2 envelope with explicit sequence numbers, timestamps |
| **State Recovery** | Rebuild aggregates from raw query files | Replay events through registered handlers |
| **Sequence Tracking** | Implicit (filesystem order); no sequence numbers | Explicit, monotonic sequence numbers (never reset) |
| **Timestamps** | Single `timestamp_utc` | Both event occurrence time + recording time |
| **Handler Tracking** | Implicit in checkpoint manifests | Explicit in `eventhandler.csv` per handler |
| **Data Corruption** | Per-file backup snapshots | Checksums + continuous backups + chunking |
| **Chunking** | No chunking; single growing raw_queries dir | Explicit chunk boundaries with continuous sequence numbers and boundary-event links |
| **Projection Rebuilding** | From raw_queries/ + aggregates | From chunk chain via handlers |
| **Checkpointing** | Snapshot-based manifests + files | Event-handler sequence markers + event snapshots |

---

## Architectural Principles

### 1. Event-Produced Data Registry
All persistent state derives from events. Events in the chunk chain are the source of truth:
- Query responses → `query_response` events
- Entity discovery → `entity_discovered` events
- Class assignments → `class_membership` events
- Expansion decisions → `expansion_decision` events
- Fallback matches → `candidate_matched` events

All event types share the same common envelope (`sequence_num`, `event_version`, `event_type`, `timestamp_utc`, `recorded_at`, optional `event_id`), while the `payload` structure is specific to the event type.

### 2. Handler-Driven Projections
Event handlers subscribe to events and maintain derived files:
- `InstancesHandler`: Reads `entity_discovered` → updates `instances.csv` + `entities.json`
- `ClassesHandler`: Reads `class_membership` + `class_resolved` → updates `classes.csv`
- `TripleHandler`: Reads `triple_discovered` → updates `triples.csv`
- `CandidatesHandler`: Reads `candidate_matched` → updates candidate CSVs
- `QueryInventoryHandler`: Reads all events → updates `query_inventory.csv`

### 3. Single-Writer Constraint
Only one process/thread writes to the current chunk file at any time:
- Graph expansion engine is the sole event producer
- Event handlers are pure readers (update projections only)
- Append-only writes guarantee no in-file reordering or corruption from multiple writers

### 4. Sequence-Based Handlers
Each handler tracks its progress:
```csv
handler_name,last_processed_sequence
InstancesHandler,1247
ClassesHandler,1245
TripleHandler,1247
QueryInventoryHandler,1247
CandidatesHandler,987
```
When a handler starts, it reads events starting from `last_processed_sequence + 1`.

### 5. Graceful Shutdown & Recovery
- **Incremental checkpoints**: After each handler processes a batch of events, write its new sequence number
- **Signal handling**: On SIGINT/Ctrl+C, set a "terminate" flag; writers check it before write operations
- **Monitor file pattern**: External process can signal shutdown by writing a non-empty "shutdown" file
- **Idempotent recovery**: Re-running the workflow re-processes only unhandled events

### 6. Chunk Continuity Model
- Canonical chunk linkage is stored in events themselves:
	- last event of old chunk: `eventstore_closed`
	- first event of new chunk: `eventstore_opened`
- Sequence numbers remain continuous across chunks and never reset.
- `chunk_catalog.csv` is a derived index for fast lookup/replay and can be rebuilt from chunk files + boundary events.
- If catalog data conflicts with boundary events, boundary events are canonical.

### 7. Chunk Naming Convention

For operator readability, closed chunks are named by UTC creation date plus daily counter:

- `eventstore_chunk_YYYY-MM-DD_NNNN.jsonl`
- Example: `eventstore_chunk_YYYY-MM-DD_0001.jsonl`

Important:
- This naming is operational, not canonical.
- Canonical chain is still boundary events plus continuous sequence numbers.
- `chunk_catalog.csv` records these names for fast lookup and can be regenerated.

---

## Migration Phases

This migration is planned in three phases:

### Phase 1: Event Store Scaffolding (Specification & Foundation)
- Freeze event schema (extends v2 envelope with sequence numbers + dual timestamps)
- Implement atomic append to the current chunk file
- Implement event reader with sequence tracking
- Implement `eventhandler.csv` tracking mechanism
- Create reference handlers for core projections (instances, classes, triples)
- **Completion gate**: Handlers successfully rebuild v2 artifacts from test events

### Phase 2: Handler Integration (Gradual Switch)
- Wire graph expansion engine to emit events to the chunk chain
- Migrate query_inventory rebuilding from current process to InventoryHandler
- Implement checkpoint/resume using handler sequence numbers
- Add checksum generation and validation for closed chunks
- **Completion gate**: New pipeline satisfies v3 quality gates and mismatch classification policy

### Phase 3: Data Migration + Cleanup
- Migrate all v2 `raw_queries/` events into the new chunk chain as legacy import events
- Validate projections against v3 quality gates and classified mismatch outcomes
- Archive old `raw_queries/` for reference
- Document the transition and establish a v3-only policy
- **Completion gate**: Full production run successful; v2 code paths already removed

---

## Scope of v3

**In Scope:**
- Event store architecture (single JSONL file with explicit sequence numbers)
- Event handler pattern (tracks sequence, updates projections)
- Graceful shutdown mechanisms (signal handlers + monitor files)
- Checkpoint/recovery using handler seq numbers (not snapshot-based)
- Data migration from v2 raw_queries to eventstore
- Checksums and compression for archived chunks
- All existing v2 semantics preserved (graph expansion, eligibility rules, class resolution)

**Out of Scope (Future Work):**
- Parallel write handlers (single-writer constraint must be maintained)
- Distributed event processing (would require distributed consensus/versioning)
- Real-time event streaming (batch-oriented, event-driven only)
- Event deletion or retroactive modifications (append-only only)
- Multiple event stores (one canonical store per pipeline)

---

## Success Criteria

1. **Events Authoritative**: All persistent state is reproducible from the chunk chain
2. **Deterministic Rebuild**: Running handlers multiple times produces identical projections
3. **Sequence Continuity**: Sequence numbers are unbroken across chunks; never reset
4. **Boundary-Event Canonicality**: Chunk linkage is recoverable from boundary events alone
5. **Catalog Rebuildability**: `chunk_catalog.csv` can be regenerated and matches canonical chunk links
6. **Handler Correctness**: Default reference handlers rebuild all v2 projections byte-for-byte
7. **Migration Integrity**: Legacy v2 data migrates without loss; checksums validate on rebuild
8. **Graceful Termination**: Process can be interrupted and resumed without state corruption
9. **Performance Parity**: Event-sourced pipeline is as fast or faster than v2 for typical runs
10. **No Legacy Cruft**: v3 runtime contains no v2 code paths or compatibility shims

---

## Related Documents

- [01_SPECIFICATION.md](01_SPECIFICATION.md) — Detailed technical specification (event schema, handlers, artifacts)
- [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) — Current v2 system vs. proposed v3 (what changes, risks, dependencies)
- [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) — Step-by-step implementation plan (phases, testing gates, rollout)
- [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) — Questions requiring clarification before implementation starts
- [../context/jsonl_potential_for_eventsourcing.md](../context/jsonl_potential_for_eventsourcing.md) — High-level event-sourcing principles

---

## Quick Links to Key Files

**Current v2 Implementation:**
- Notebook: `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`
- Modules: `speakermining/src/process/candidate_generation/wikidata/{event_log,checkpoint,materializer,*.py}`
- Data: `data/20_candidate_generation/wikidata/raw_queries/`, `data/20_candidate_generation/wikidata/checkpoints/`

**v2 Reference Contracts:**
- `documentation/Wikidata/2026-03-31_transition/MIGRATION_FINAL_DECISION.md` (design contracts, module API)
- `documentation/Wikidata/Wikidata_specification.md` (core classes, class lineage, triple requirements)

**Event-Sourcing Principles:**
- `documentation/context/jsonl_potential_for_eventsourcing.md` (event store design, chunking, checksums)
