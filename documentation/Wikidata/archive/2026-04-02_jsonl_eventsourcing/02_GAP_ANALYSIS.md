# Gap Analysis: V2 → V3 (JSONL Event-Sourcing)

**Date:** 2026-04-02  
**Status:** Analysis Complete (post-implementation reference)  

---

## Executive Summary

The v2 system is a **mature checkpoint-based pipeline** with append-only raw query files. It successfully implements graph-first expansion, class-driven eligibility, and deterministic seeded traversal.

V3 proposes **transitioning to event-sourcing**, which fundamentally changes:
- **Event storage model** (scattered JSON files → centralized JSONL)
- **State recovery mechanism** (snapshot restore → event replay)
- **Projection rebuilding** (ad-hoc aggregates → handler-driven)

The **good news**: All v2 semantics (graph expansion, eligibility rules, class resolution) are preserved. The **gap** is architectural: v2 stores state as files; v3 stores state as event sequences.

---

## 1. Event Storage Architecture Gap

### Current State (V2)
```
data/20_candidate_generation/wikidata/
├── raw_queries/                    # ~695 JSON files, one per query
│   ├── 20260326T145224278856Z__entity__Q1499182.json
│   ├── 20260326T145230123456Z__entity__Q1587023.json
│   └── ...
├── checkpoints/                    # Snapshot manifests + state files
│   ├── checkpoint__<run_id>__<ts>__<hash>.json
│   └── snapshots/                  # Full directory copies at milestones
│       ├── checkpoint_<ts>/
│       │   ├── files/              # Copies of all projection CSVs + JSON
│       │   └── raw_queries/        # Copy of entire raw_queries dir
│       └── ...
├── query_inventory.csv             # Dedup summary of all queries
├── instances.csv                   # Entity metadata
├── triples.csv                     # Relationships
├── classes.csv                     # Class hierarchy
├── candidates.csv                  # Fallback matches (Phase 3)
└── entities.json                   # Full entity payloads
```

**Characteristics:**
- Events (query responses) stored as individual JSON files
- No explicit sequence numbers; ordering is implicit (filesystem, execution order)
- Checkpoint manifests track run state (seeds completed, nodes discovered, etc.)
- Snapshot restoration requires copying entire raw_queries directory
- File-per-event creates filesystem clutter (~695 files for typical run)
- No built-in checksums or corruption detection

### Proposed State (V3)
```
data/20_candidate_generation/wikidata/
├── chunks/                         # Active + closed chunks (closed chunks are immutable)
│   ├── eventstore_chunk_YYYY-MM-DD_0001.jsonl
│   └── eventstore_chunk_YYYY-MM-DD_0002.jsonl
├── chunk_catalog.csv               # Derived chunk index (rebuildable)
├── eventhandler.csv                # Handler progress (seq markers)
├── eventstore_checksums.txt        # SHA256 per chunk
├── instances.csv                   # [SAME] Handler-maintained
├── triples.csv                     # [SAME] Handler-maintained
├── classes.csv                     # [SAME] Handler-maintained
├── query_inventory.csv             # [SAME] Handler-maintained
├── candidates.csv                  # [SAME] Handler-maintained
├── entities.json                   # [SAME] Handler-maintained
└── snapshots/                      # Handler snapshots at checkpoints
    └── checkpoint__YYYYMMDDTHHMMSSZ__seq1250.json
```

**Characteristics:**
- Events stored in a chunk chain of append-only JSONL files
- Explicit sequence numbers per event; never reset across chunks
- Canonical chunk linkage defined by boundary events (`eventstore_closed` / `eventstore_opened`)
- `chunk_catalog.csv` is a convenience index, not canonical; it is rebuildable
- Handler tracking in CSV; minimal checkpoint overhead
- Chunk snapshots are metadata-only (event sequence marker)
- No filesystem clutter; events are lines, not files
- Built-in checksums for corruption detection

### Gap Impact

| Aspect | V2 | V3 | Risk |
|--------|----|----|------|
| Event discovery | Filesystem scan + sort | Read chunks in sequence order via boundary links (catalog as fast index) | Low - faster and cleaner |
| Checkpoint restore | Copy raw_queries dir + files | Load event sequence marker | Low - simpler |
| Corruption recovery | Per-file restore | Last-line truncation | **Medium** - need new logic |
| Event ordering | Implicit in filesystem | Explicit sequence numbers | Low - more reliable |
| New event discovery | Automatic (new files) | Append to current chunk file in `chunks/` | **Medium** - different write pattern |
| Catalog drift | N/A | Catalog may diverge from canonical chain | **Low** - rebuild catalog from boundary events |

---

## 2. Event Schema Gap

### Current V2 Event Format
```json
{
  "event_version": "v2",
  "event_type": "query_response",
  "endpoint": "wikidata_api",
  "normalized_query": "entity Q1499182",
  "query_hash": "abc123def456",
  "timestamp_utc": "2026-03-26T14:52:24Z",
  "source_step": "entity_fetch",
  "status": "success",
  "key": "Q1499182",
  "http_status": 200,
  "error": null,
  "payload": { ... }
}
```

**V2 Characteristics:**
- Single timestamp (`timestamp_utc`)
- No explicit sequence number
- No recording time distinction
- Event version hardcoded; no validation

### Proposed V3 Event Format
```json
{
  "sequence_num": 1247,                        # NEW
  "event_version": "v3",
  "event_type": "query_response",
  "endpoint": "wikidata_api",
  "normalized_query": "entity Q1499182",
  "query_hash": "abc123def456",
  "timestamp_utc": "2026-03-26T14:52:24Z",
  "recorded_at": "2026-03-26T14:52:30Z",      # NEW
  "source_step": "entity_fetch",
  "status": "success",
  "key": "Q1499182",
  "http_status": 200,
  "error": null,
  "payload": { ... }
}
```

**V3 Differences:**
- Explicit `sequence_num` (mandatory, unique, monotonic)
- Dual timestamps: `timestamp_utc` (event happened) vs. `recorded_at` (stored)
- Event version changed to "v3"
- Runtime will reject events missing `sequence_num` or with version != "v3"

### Gap Impact & Data Migration

| Aspect | Gap | Impact | Mitigation |
|--------|-----|--------|-----------|
| Missing `sequence_num` | V2 events lack it | Cannot directly append to eventstore | Assign seq numbers during import (Phase 3) |
| Single timestamp | V2 doesn't distinguish event time vs. record time | Loss of record-time fidelity | Use migration timestamp as `recorded_at` |
| Event version | V2 says "v2"; V3 requires "v3" | Runtime rejects v2 events | Convert all v2→v3 during migration |
| New event types | V3 includes `entity_discovered`, `class_resolved`, etc. | V2 only has `query_response` | New handlers will emit these in Phase 2/3 |

**Migration Strategy:**
1. Load each v2 JSON file from `raw_queries/`
2. Transform to v3 schema:
   - Assign monotonically increasing `sequence_num`
   - Set `event_version = "v3"`
   - Preserve `timestamp_utc`
   - Set `recorded_at` to import time (or estimate from file modification time)
3. Write to the current chunk file under `chunks/`
4. Validate: no sequence gaps, all events parse as JSON

---

## 3. State Management Gap

### Current V2: Checkpoint-Based Resume

**Current Flow:**
```
1. Load checkpoint manifest (last seeds completed, last seq for inlinks cursor)
2. Restore snapshot state: copy checkpoint/snapshots/<id>/files/* → wikidata dir
3. Restore raw_queries: copy checkpoint/snapshots/<id>/raw_queries/ → raw_queries/
4. Resume from inlinks_cursor position
```

**Resume Modes:**
- `append`: Continue from last checkpoint (idempotent reruns)
- `restart`: Delete all state; start from seed 1
- `revert`: Delete latest checkpoint; restore previous checkpoint

**State Files Used:**
- `checkpoint__<run_id>__<ts>__<hash>.json` — Manifest
- `checkpoints/snapshots/<id>/files/` — All CSVs, JSON files
- `checkpoints/snapshots/<id>/raw_queries/` — All query files

### Proposed V3: Sequence-Based Resume

**Proposed Flow:**
```
1. Load eventhandler.csv: Which handlers, what was their last_processed_sequence?
2. For each handler:
    - Read chunk files starting from (last_processed_sequence + 1)
   - Process events in order
   - Update handler's last_processed_sequence
   - Atomically rewrite eventhandler.csv
3. Handlers produce output CSVs (deterministically)
```

**Resume Modes:**
- `append`: Continue from eventhandler.csv state (no snapshot needed)
- `restart`: Truncate eventhandler.csv to all sequences = 0; reprocess all events
- `revert`: Load snapshot metadata (which sequences were processed); restore eventhandler.csv

**State Files Used:**
- `eventhandler.csv` — Handler progress only (tiny, <1KB)
- Chunk chain in `chunks/` — Source of truth (read-only once a chunk is closed)
- Optional: `snapshots/<id>/` — Metadata-only (which seq is frozen, when)

### Gap Impact

| Aspect | V2 | V3 | Benefit | Risk |
|--------|----|----|---------|------|
| Checkpoint size | 100s of MB (full dir copy) | <1 KB (progress markers) | **Fast restore** | New logic needed |
| State restoration | Copy files | Read/replay events | **Determinism** | Handlers must be idempotent |
| Resume time | Slow (copy large dirs) | Fast (read metadata + replay) | **Speed** | Must validate handlers can replay |
| Snapshot granularity | Per-seed or milestone | Per-batch or handler completion | **More options** | More frequent writes |
| Disk space | Snapshots accumulate; cleanup needed | No snapshot requirement; only ~1KB per handler | **Much less space** | Must validate checksums |

---

## 4. Projection Rebuilding Gap

### Current V2: Ad-Hoc Aggregation

**Current Pattern:**
```
1. BFS expansion writes query results to raw_queries/
2. After expansion complete (or periodically):
   - aggregates.py reads all raw_queries/*.json
   - Scans each: extract entities, relationships, matches
   - Groups, deduplicates, writes to instances.csv, triples.csv, etc.
3. For resume: reload raw_queries/, recompute aggregates
```

**Characteristics:**
- No formalized "handler" pattern; aggregation is embedded in orchestration
- Aggregates are derived lazily (only when needed)
- No tracking of which events were used for which projection
- Hard to reason about: "if I change aggregate logic, which data is affected?"

### Proposed V3: Handler-Driven Projections

**Proposed Pattern:**
```
1. Graph expansion writes events to the current chunk file in `chunks/`
2. Handlers (InstancesHandler, TripleHandler, etc.) subscribe to events
3. For each unprocessed event (seq > last_processed_seq):
   - Handler reads event
   - Updates in-memory state (entity map, triple set, etc.)
   - Flushes to CSV/JSON at batch boundaries
4. Handler updates eventhandler.csv with new last_processed_seq
```

**Characteristics:**
- Formalized handler interface (clear contract)
- Projections are actively maintained (not rebuilt on-demand)
- Easy to add new projections (implement new handler, register it)
- Clear audit trail: "InstancesHandler processed events 1000-1247"

### Gap Impact

| Aspect | V2 | V3 | Benefit | Risk |
|--------|----|----|---------|------|
| Projection logic | Spread across modules | Centralized per handler | **Maintainability** | Must refactor code |
| State tracking | Implicit (in checkpoint) | Explicit (per-handler seq) | **Clarity** | New data structure |
| Incremental updates | Not really; full rebuild | True incremental (per-batch) | **Efficiency** | Handlers must be stateless |
| Determinism | Achieved but fragile | Guaranteed by design | **Reliability** | Handler logic must be pure |
| Testing | Integration tests only | Unit test per handler + integration | **Easier testing** | More test code |

---

## 5. Write-Side Changes Gap

### Current V2: Embedded Event Writing

**Current Flow:**
```
bfs_expansion.py:
  for query_response in wikidata_api.fetch(...):
      if cache_hit:
          _increment_cache_hit_counter()
      else:
          entity_data = _fetch_entity_or_sparql(...)
          
      event = build_query_event(...)
      _write_query_event(event)  # Writes individual JSON file
      
      # Immediately scan for matches
      for mention_target in all_targets:
          if _matches(entity_data, mention_target):
              candidate_rows.append((mention_target, entity))
```

**Characteristics:**
- Event writing is embedded in expansion logic
- One write per query; filesystem I/O for each event
- No explicit sequence number; order determined by execution order
- Handlers (aggregates.py) consume after expansion is done

### Proposed V3: Decoupled Event Production

**Proposed Flow:**
```
expansion_engine.py:
  for seed in seeds:
      for entity in bfs_get_entities(seed):
          query_response = _fetch_from_wikidata_or_cache(entity)
          
          # Emit event (appends to the current chunk file)
          event = build_query_event(
              sequence_num=_next_seq(),
              timestamp_utc=<when it happened>,
              recorded_at=<now>,
              ...
          )
          event_writer.append(event)
          
          # Optionally notify handlers (in separate process/thread?)
          # event_bus.publish(event)

# Separate handler process
handler_runner.py:
  for handler in [instances_handler, classes_handler, ...]:
      for event in event_reader.iter_events_from(handler.last_seq + 1):
          handler.process(event)
      handler.update_progress()
```

**Characteristics:**
- Event writing is isolated (single writer)
- Sequence numbers are explicit and controlled
- Handlers consume asynchronously (can be in separate process)
- Clear separation of concerns

### Gap Impact

| Aspect | V2 | V3 | Change | Risk |
|--------|----|----|--------|------|
| Write location | Embedded in expansion | Isolated event writer | **Code restructuring** | Must extract to module |
| Write pattern | One file per event | Append to current chunk file in `chunks/` | **I/O pattern change** | Atomic append logic needed |
| Sequence control | Implicit (order) | Explicit (seq num) | **Different numbering** | Requires counter sync |
| Handler execution | After expansion done | Asynchronously (next phase) | **Process timing** | Handlers may lag expansion |
| Error handling | Per-file error | Per-line error in JSONL | **Recovery logic** | Need truncation/validation |

---

## 6. Graceful Shutdown Gap

### Current V2: File-Based Checkpoints
- No explicit shutdown handling
- Process can be killed at any time
- On restart: load latest checkpoint and resume
- Risk: If process dies mid-file-write, one checkpoint snapshot may be unfinished

### Proposed V3: Signal Handlers + Monitor Files
- Install SIGINT/SIGTERM handlers
- Check `terminate_requested` flag before each write
- Periodically check monitor file (external control)
- Save handler progress atomically before exit
- On restart: resume from saved handler sequences

### Gap Impact

**Risk Level: Medium**

| Aspect | V2 | V3 | Change | Mitigation |
|--------|----|----|--------|-----------|
| Shutdown handling | Implicit (checkpoint on exit) | Explicit (signal handlers) | **Code addition** | Need signal.signal() setup |
| Termination signal | Process kill | Graceful SIGINT/SIGTERM | **Implementation** | Each phase must check flag |
| Handler state | Implicit in snapshot | Explicit in eventhandler.csv | **Atomic updates** | Use temp file + rename |
| Monitor file | Not present | .shutdown file | **New mechanism** | Must document usage |

---

## 7. Chunk Management Gap

### Current V2: Single-File Raw Queries
- `raw_queries/` grows indefinitely
- No archival, compression, or chunking
- Filesystem scales to thousands of files (may be slow on some systems)
- No versioning or boundary markers

### Proposed V3: Chunking with Compression
- The current chunk grows to N events, then a new chunk is opened
- Old chunks compressed to `.jsonl.gz`
- Checksums stored for validation
- Sequence numbers never reset across chunks

### Gap Impact

**Risk Level: Low**

| Aspect | V2 | V3 | Benefit | Implementation |
|--------|----|----|---------|-----------------|
| File growth | Unlimited | Chunked at threshold | **Manageability** | Monitor line count; close at boundary |
| Compression | None | gzip/xz on closed chunks | **Storage savings** | Implement compression writer |
| Checksums | None | Per-chunk SHA256 | **Corruption detection** | Hash on chunk close |
| Cross-chunk reads | N/A | Via chunk iterator | **Transparency** | Hide chunking in reader |

---

## 8. Class Resolution & Eligibility Gap

### Current Status (No Gap!)
Both v2 and v3 use the **same** class resolution and eligibility semantics:
- Core classes: Q215627 (person), Q43229 (organization), etc.
- Eligibility: see canonical contract in `documentation/Wikidata/expansion_and_discovery_rules.md`
- Lineage resolution: Build transitive P279 path to core class

**No changes needed** — ClassesHandler in v3 implements the same logic as v2.

---

## 9. Data Integrity & Validation Gap

### Current V2: File-Level Validation
- When aggregate is read: validate CSV headers
- When raw query is read: validate JSON parse
- No checksums
- No per-event validation

### Proposed V3: Event-Level Validation

**Validation at Write Time:**
```python
def _validate_event(event: dict) -> None:
    assert "sequence_num" in event, "Missing sequence_num"
    assert isinstance(event["sequence_num"], int), "sequence_num not int"
    assert event["event_version"] == "v3", "event_version must be v3"
    assert "endpoint" in event, "Missing endpoint"
    # ... check all required fields
```

**Validation at Read Time:**
```python
def _read_event_line(line: str) -> dict:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON: {line}")
    _validate_event(event)
    return event
```

**Checksum Validation:**
```python
def _validate_chunk(chunk_path: Path) -> bool:
    actual_hash = compute_sha256(chunk_path)
    expected_hash = _load_checksum(chunk_path)
    assert actual_hash == expected_hash, f"Checksum mismatch for {chunk_path}"
```

### Gap Impact

**Risk Level: Low**

| Aspect | V2 | V3 | Benefit | Cost |
|--------|----|----|---------|------|
| Event validation | Implicit | Explicit schema validation | **Catch errors early** | Validation code needed |
| Checksum coverage | None | Per-chunk checksums | **Corruption detection** | Checksum storage |
| Parse failures | Per-file | Per-line | **Granular recovery** | Truncate to last valid line |

---

## 10. Testing & Determinism Gap

### Current V2: Limited Determinism Testing
- Contract smoke tests (artifact existence, header validation)
- No determinism tests (run twice, compare outputs)
- Resume semantics tested manually

### Proposed V3: Strict Determinism Guarantees
- **Determinism tests**: Same eventstore → identical CSVs
- **Idempotency tests**: Run handlers twice → no changes on second run
- **Resume tests**: Resume from middle → same output as fresh run
- **Chunk tests**: Cross-chunk reads produce same data as single-file reads

### Gap Impact

**Risk Level: Medium (Important for Migration Success)**

| Aspect | V2 | V3 | Requirement | Implementation |
|--------|----|----|------------|-----------------|
| Test coverage | Smoke tests | Determinism + idempotency | **Comprehensive** | Significant test writing |
| Golden data | Few test cases | Full dataset reference | **Validation** | Baseline capture + comparison |
| Resume validation | Ad-hoc | Automated tests | **Confidence** | CI/automation |
| Chunk integrity | N/A | Cross-chunk equivalence | **Validation** | Read same events from single vs. chunked |

---

## Summary: Gap Severity & Mitigation

### Critical Gaps (Must Address)
1. **Event schema transformation** (Phase 3): Assign seq numbers to v2 events
   - Cost: Medium (straightforward conversion)
   - Mitigation: Batch script to migrate all raw_queries files
   
2. **Handler implementation** (Phase 1): Implement 5 core handlers
   - Cost: High (substantial code)
   - Mitigation: Start with reference implementations; test on small dataset

3. **Write-side refactoring** (Phase 2): Extract event writer from expansion logic
   - Cost: Medium (refactor existing code)
   - Mitigation: Create event_writer module; stub in existing code

### Medium Gaps (Should Address Before Release)
1. **Graceful shutdown** (Phase 1): Add signal handlers + monitor file
   - Cost: Low (< 100 LOC)
   - Mitigation: Use signal.signal(); poll monitor file in main loop

2. **Checksum validation** (Phase 1): Generate + verify checksums
   - Cost: Low (use hashlib)
   - Mitigation: Reference implementation in materializer

3. **Testing framework** (Phase 1): Determinism + idempotency tests
   - Cost: Medium (test infrastructure)
   - Mitigation: Use existing test patterns; automate with pytest

### Minor Gaps (Nice to Have)
1. **Chunk management** (Phase 3): Implement automatic chunking
   - Cost: Low (mostly logic)
   - Mitigation: Defer to Phase 3; manual chunking for Phase 2

2. **Monitoring/observability** (Phase 3): Dashboards, metrics
   - Cost: Low (optional)
   - Mitigation: Log end metrics; add dashboards later

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|-----------|
| Event schema incompatibility | Low | High (data loss) | Thorough schema validation + tests |
| Handler determinism failure | Medium | High (wrong output) | Extensive unit + integration tests |
| Data corruption from interruption | Medium | High (recovery needed) | Signal handlers + atomic writes |
| Checkpoint/resume logic errors | Medium | High (lost state) | Automated resume tests |
| Performance regression | Low | Medium (slower pipeline) | Benchmarking on full dataset |
| Migration data loss (v2 → v3) | Low | Critical | Dual-run validation (v2 vs v3 output) |

---

## Conclusion

The migration from v2 to v3 is **architecturally sound** but **requires significant implementation work**:

✅ **Preserved:** All semantic guarantees (graph expansion, class resolution, eligibility)  
❌ **Changed:** Storage model (files → JSONL), state recovery (snapshots → event replay), projection logic (embedded → handlers)  
⚠️  **Risk:** Implementation complexity, testing rigor, data migration validation

The phased approach (Phases 1, 2, 3) spreads implementation burden and allows validation at each gate. Success depends on rigorous determinism testing and thorough migration validation.
