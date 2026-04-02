# V3 Migration Sequence — Implementation Plan

**Date:** 2026-04-02  
**Status:** Specification (pre-implementation)  
**Phases:** 3 (Scaffolding, Integration, Migration)

---

## Overview

This plan breaks the v3 migration into three sequential phases, each with explicit completion gates. Phases are **not parallel** to minimize integration risk.

Policy clarification (effective immediately):
- v2 runtime is decommissioned and will not be executed again.
- No dual-write mode is permitted.
- Legacy v2 query-response data is import-only input into v3.

### Canonical Chunk Rule (Applies To All Phases)

- Canonical chunk linkage is stored in boundary events, not in catalog rows:
    - last event of old chunk: `eventstore_closed`
    - first event of new chunk: `eventstore_opened`
- Sequence numbers must stay continuous across all chunks and must never reset.
- `chunk_catalog.csv` is a derived index for speed and operability only.
- If `chunk_catalog.csv` conflicts with boundary-event linkage, boundary events are canonical and the catalog must be rebuilt.

### Event Schema Rule (Applies To All Phases)

- The event store contains many event types in the same file.
- Every event shares the common envelope (`sequence_num`, `event_version`, `event_type`, `timestamp_utc`, `recorded_at`, optional `event_id`).
- Type-specific information lives in `payload`.
- Handlers must route on `event_type` and validate only the payload fields relevant to that type.

### Chunk Naming Convention (Implementation Requirement)

All implementations in this migration must use the same closed-chunk file naming rule:

- `eventstore_chunk_YYYY-MM-DD_NNNN.jsonl`
- UTC date at close time
- `NNNN` is zero-padded per-day counter (`0001`, `0002`, ...)

Implementation constraints:
- The current writable chunk file lives in `chunks/`.
- Chunks are immutable once closed.
- `chunk_catalog.csv` stores the resulting `file_name` as derived metadata.
- Boundary events remain canonical for chain reconstruction.
- Validation gates must include at least one test with two chunks on the same day (counter increment check).

| Phase | Effort | Gate | Outcome |
|-------|--------|------|---------|
| Phase 1: Scaffolding | High | Event store + 5 handlers working on test data | Proof of concept for event-driven architecture |
| Phase 2: Integration | High | Graph expansion emits events; full dataset runs pass v3 quality gates | Production-ready on new machinery |
| Phase 3: Migration | Medium | All v2 data migrated; v2 code removed | v3-only production system |

---

## Phase 1: Event Store Scaffolding

**Goal:** Build the foundational event-sourcing infrastructure. By end of Phase 1, handlers can replay events and rebuild projections deterministically.

### Phase 1.1: Event Store Writer

**Files to Create:**
- `speakermining/src/process/candidate_generation/wikidata/event_writer.py`
- `speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py`

**Responsibilities:**
- Atomic append to the current chunk file in `chunks/`
- Sequence number management (in-memory counter from the latest chunk tail)
- Event validation (schema check, sequence increment)
- fsync after each write
- Incomplete line recovery (on startup)
- Emit canonical boundary events on rotation (`eventstore_closed`, `eventstore_opened`)
- Build and rebuild derived `chunk_catalog.csv` from chunk files + boundary events

**Key Functions:**
```python
class EventStore:
    def __init__(self, path: Path):
        self.path = path
        self._sequence_num = self._load_last_sequence() + 1
    
    def append_event(self, event: dict) -> int:
        """Validate, assign seq num, atomically append, return seq."""
        event["sequence_num"] = self._sequence_num
        event["event_version"] = "v3"
        event["recorded_at"] = _iso_now()
        _validate_event(event)
        
        line = json.dumps(event, separators=(',', ':'))
        _atomic_append_line(self.path, line)
        
        self._sequence_num += 1
        return event["sequence_num"]
    
    def iter_events_from(self, start_seq: int):
        """Iterate events from start_seq onward."""
        with open(self.path) as f:
            for line in f:
                try:
                    event = json.loads(line)
                    if event.get("sequence_num", 0) >= start_seq:
                        yield event
                except json.JSONDecodeError:
                    # Last line incomplete; skip
                    continue
```

**Testing:**
- Unit test: write 100 events, read back, verify all present and ordered
- Unit test: simulate crash (truncate last line), restart, verify recovery
- Unit test: sequence numbers are consecutive and never reused
- Unit test: chunk rotation writes consistent `next_chunk_id` and `prev_chunk_id`
- Unit test: rebuilding catalog from chunks reproduces `chunk_catalog.csv`

**Acceptance Criteria:**
- ✅ Events persistently written to chunk files in `chunks/`
- ✅ Sequence numbers are explicit and monotonic
- ✅ Atomic write guarantees (no partial writes)
- ✅ Recovery from incomplete last line
- ✅ Chunk linkage is recoverable from boundary events without catalog
- ✅ `chunk_catalog.csv` is reproducible from canonical chunk events

### Phase 1.2: Event Handler Base Class & Progress Tracking

**Files to Create:**
- `speakermining/src/process/candidate_generation/wikidata/event_handler.py` (base)
- `speakermining/src/process/candidate_generation/wikidata/handler_registry.py`

**Base Handler Interface:**
```python
class EventHandler:
    def name(self) -> str:
        """Unique handler identifier."""
        ...
    
    def last_processed_sequence(self) -> int:
        """Read from eventhandler.csv."""
        ...
    
    def process_batch(self, events: list[dict]) -> None:
        """Process a batch of unhandled events."""
        ...
    
    def materialize(self, output_path: Path) -> None:
        """Write projection to disk."""
        ...
    
    def update_progress(self, last_seq: int) -> None:
        """Atomically update eventhandler.csv with new sequence."""
        ...
```

**Handler Registry:**
- Maintains `eventhandler.csv`: handler_name, last_processed_sequence, artifact_path, updated_at
- Loads/saves registry to CSV
- Provides atomic row updates (read entire CSV, update row, atomic write)

**Key Functions:**
```python
class HandlerRegistry:
    def __init__(self, path: Path):
        self.path = path
        self.handlers: dict[str, HandlerProgress] = self._load_registry()
    
    def get_progress(self, handler_name: str) -> int:
        """Return last_processed_sequence for handler."""
        return self.handlers.get(handler_name, HandlerProgress(handler_name, 0)).last_seq
    
    def update_progress(self, handler_name: str, last_seq: int):
        """Atomically update handler row."""
        self.handlers[handler_name].last_seq = last_seq
        self.handlers[handler_name].updated_at = _iso_now()
        self._write_registry()
```

**Testing:**
- Unit test: initialize empty registry, add handlers, verify CSV created
- Unit test: update one handler, verify others unchanged
- Unit test: simulate crash mid-write, verify recovery

**Acceptance Criteria:**
- ✅ EventHandler base class with standard interface
- ✅ eventhandler.csv tracking all handlers
- ✅ Atomic progress updates (no partial writes)

### Phase 1.3: Core Handler Implementations (5)

Implement the five reference handlers from spec section 2.2:

#### 1.3.1 InstancesHandler
**File:** `speakermining/src/process/candidate_generation/wikidata/handlers/instances_handler.py`

**Responsibilities:**
- Read `query_response` events with entity payloads
- Extract: QID, labels (de/en), aliases, descriptions
- Update in-memory entity map
- Materialize to `instances.csv` and `entities.json`

**Key Methods:**
```python
class InstancesHandler(EventHandler):
    def __init__(self, repo_root: Path):
        self.entities: dict[str, dict] = {}  # QID -> entity data
    
    def process_batch(self, events: list[dict]):
        for event in events:
            if event["status"] == "success" and event.get("payload", {}).get("entity-type") == "item":
                qid = event["key"]
                self.entities[qid] = self._extract_entity_data(event["payload"])
    
    def materialize(self, output_path: Path):
        # Sort by QID for determinism
        instances = sorted(self.entities.items())
        df = pd.DataFrame([{
            'qid': qid,
            'label': data.get('label'),
            'labels_de': data.get('labels_de'),
            'labels_en': data.get('labels_en'),
            'aliases': data.get('aliases'),
            'description': data.get('description'),
            'discovered_at': data.get('discovered_at'),
            'expanded_at': data.get('expanded_at'),
        } for qid, data in instances])
        df.to_csv(output_path, index=False)
```

**Output:** `instances.csv` with columns: qid, label, labels_de, labels_en, aliases, description, discovered_at, expanded_at

**Testing:**
- Unit test: feed EventHandler 10 entity_response events, verify instances.csv matches expected
- Unit test: reprocess same events independently, verify output is byte-identical
- Unit test: feed subset of events, then additional events, verify incremental correctness

#### 1.3.2 ClassesHandler
**File:** `speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py`

**Responsibilities:**
- Read `query_response` events; watch for P31 and P279 claims
- Build entity-to-class and class-to-superclass mappings
- Resolve transitive paths to core classes
- Materialize to `classes.csv` and `core_classes.csv`

**Key Methods:**
```python
class ClassesHandler(EventHandler):
    def __init__(self, repo_root: Path):
        self.entities: dict[str, dict] = {}  # QID -> entity data
        self.core_classes = effective_core_class_qids()  # From spec
    
    def process_batch(self, events: list[dict]):
        for event in events:
            if event["status"] == "success":
                qid = event["key"]
                # Extract P31 claims (instance of)
                p31_targets = self._extract_claim_qids(event["payload"].get("claims", {}), "P31")
                # Extract P279 claims (subclass of)
                p279_targets = self._extract_claim_qids(event["payload"].get("claims", {}), "P279")
                
                self.entities[qid] = {
                    'p31_targets': p31_targets,
                    'p279_targets': p279_targets,
                }
    
    def materialize(self, output_path: Path):
        # For each entity, resolve class lineage
        classes_list = []
        for qid, data in self.entities.items():
            # Compute subclass_of_core and path_to_core via BFS on p279
            core_path = self._resolve_to_core_class(qid, data['p279_targets'])
            classes_list.append({
                'qid': qid,
                'label': self._load_label(qid),
                'p279_targets': '|'.join(data['p279_targets']),
                'subclass_of_core': bool(core_path),
                'path_to_core': core_path,
            })
        
        # Output deterministically sorted
        df = pd.DataFrame(sorted(classes_list, key=lambda x: x['qid']))
        df.to_csv(output_path, index=False)
```

**Output:** `classes.csv` with columns: qid, label, p279_targets, subclass_of_core, path_to_core

**Testing:**
- Unit test: Feed Q5 (human) entity → verify path_to_core includes Q215627 (person)
- Unit test: Feed multiple class hierarchies → verify transitive closure correct
- Unit test: Determinism → reprocess → identical output

#### 1.3.3 TripleHandler
**File:** `speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py`

**Responsibilities:**
- Read `query_response` events; extract all claims (subject-property-object triples)
- Deduplicate by (subject, property, object)
- Materialize to `triples.csv`

**Key Methods:**
```python
class TripleHandler(EventHandler):
    def __init__(self, repo_root: Path):
        self.triples: set[tuple[str, str, str]] = set()  # (subject, property, object)
        self.triple_sources: dict[(str, str, str), int] = {}  # Triple → event_seq
    
    def process_batch(self, events: list[dict]):
        for event in events:
            if event["status"] == "success":
                subject_qid = event["key"]
                claims = event["payload"].get("claims", {})
                
                for property_id, property_claims in claims.items():
                    for claim in property_claims:
                        object_qid = self._extract_object_qid(claim)
                        if object_qid:
                            triple = (subject_qid, property_id, object_qid)
                            self.triples.add(triple)
                            self.triple_sources[triple] = event["sequence_num"]
    
    def materialize(self, output_path: Path):
        df = pd.DataFrame([{
            'subject_qid': s,
            'property': p,
            'object_qid': o,
            'source_event_seq': self.triple_sources.get((s, p, o)),
        } for s, p, o in sorted(self.triples)])
        df.to_csv(output_path, index=False)
```

**Output:** `triples.csv` with columns: subject_qid, property, object_qid, source_event_seq

**Constraint:** ALL discovered triples must be included (including P31 class membership)

**Testing:**
- Unit test: Feed 3 entities with various claims → verify all triples present
- Unit test: Feed same entities again → verify no duplicates in triples.csv
- Unit test: Determinism → identical output regardless of event order

#### 1.3.4 QueryInventoryHandler
**File:** `speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py`

**Responsibilities:**
- Read all `query_response` events
- Deduplicate by query_hash (only one row per unique query)
- Track status, timestamps, count

**Key Methods:**
```python
class QueryInventoryHandler(EventHandler):
    def __init__(self, repo_root: Path):
        self.queries: dict[str, QueryRecord] = {}  # query_hash → record
    
    def process_batch(self, events: list[dict]):
        for event in events:
            if event["event_type"] == "query_response":
                qh = event["query_hash"]
                
                # Dedup by hash; preserve best status (success > error > timeout)
                if qh not in self.queries:
                    self.queries[qh] = QueryRecord(
                        query_hash=qh,
                        endpoint=event["endpoint"],
                        normalized_query=event["normalized_query"],
                        status=event["status"],
                        first_seen=event["timestamp_utc"],
                        count=1,
                    )
                else:
                    self.queries[qh].count += 1
                    self.queries[qh].last_seen = event["timestamp_utc"]
                    # Status preference: success > cache_hit > http_error > timeout
                    if self._status_rank(event["status"]) > self._status_rank(self.queries[qh].status):\n                        self.queries[qh].status = event["status"]
    
    def materialize(self, output_path: Path):\n        df = pd.DataFrame([{\n            'query_hash': r.query_hash,\n            'endpoint': r.endpoint,\n            'normalized_query': r.normalized_query,\n            'status': r.status,\n            'first_seen': r.first_seen,\n            'last_seen': r.last_seen,\n            'count': r.count,\n        } for r in sorted(self.queries.values(), key=lambda x: x.query_hash)])\n        df.to_csv(output_path, index=False)\n```\n\n**Output:** `query_inventory.csv` with columns: query_hash, endpoint, normalized_query, status, first_seen, last_seen, count\n\n**Testing:**\n- Unit test: Feed same query 3 times (success, error, success) → verify one row with count=3, status=success\n- Unit test: Feed 100 unique queries → verify 100 rows in output\n\n#### 1.3.5 CandidatesHandler (Phase 3 Stub)\n**File:** `speakermining/src/process/candidate_generation/wikidata/handlers/candidates_handler.py`\n\n**For Phase 1:** Create a stub that accepts events but doesn't process them (fallback matching events don't exist yet).\n\n```python\nclass CandidatesHandler(EventHandler):\n    def __init__(self, repo_root: Path):\n        self.candidates: list[dict] = []\n    \n    def process_batch(self, events: list[dict]):\n        for event in events:\n            if event[\"event_type\"] == \"candidate_matched\":\n                # Phase 3: Implement\n                pass\n    \n    def materialize(self, output_path: Path):\n        # Phase 3: Implement\n        if not self.candidates:\n            # For now, write empty file with headers\n            pd.DataFrame([], columns=['mention_id', 'candidate_qid']).to_csv(output_path, index=False)\n```\n\n**Acceptance Criteria:**\n- ✅ Stub present and registered\n- ✅ No-op processing (doesn't crash)\n- ✅ Outputs dummy CSV for now\n\n### Phase 1.4: Handler Orchestrator\n\n**File:** `speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py`\n\n**Responsibilities:**\n- Load event store and handler registry\n- Execute handlers in order (Instances → Classes → Triples → QueryInventory → Candidates)\n- For each handler: iter events from (last_seq + 1), process in batches\n- Update handler progress after each batch\n- Materialize all projections\n\n**Key Functions:**\n```python\ndef run_handlers(repo_root: Path, batch_size: int = 1000):\n    \"\"\"Execute all handlers, updating projections.\"\"\"\n    event_store = EventStore(repo_root / \"data/20_candidate_generation/wikidata/chunks\")\n    handler_registry = HandlerRegistry(repo_root / \"data/20_candidate_generation/wikidata/eventhandler.csv\")\n    \n    handlers = [\n        InstancesHandler(repo_root),\n        ClassesHandler(repo_root),\n        TripleHandler(repo_root),\n        QueryInventoryHandler(repo_root),\n        CandidatesHandler(repo_root),\n    ]\n    \n    for handler in handlers:\n        logger.info(f\"Running {handler.name()}...\")\n        start_seq = handler_registry.get_progress(handler.name()) + 1\n        \n        # Read and process events in batches\n        batch = []\n        for event in event_store.iter_events_from(start_seq):\n            batch.append(event)\n            if len(batch) >= batch_size:\n                handler.process_batch(batch)\n                handler_registry.update_progress(handler.name(), batch[-1][\"sequence_num\"])\n                batch = []\n        \n        # Process remainder\n        if batch:\n            handler.process_batch(batch)\n            handler_registry.update_progress(handler.name(), batch[-1][\"sequence_num\"])\n        \n        # Materialize\n        output_path = _artifact_path(handler.name(), repo_root)\n        handler.materialize(output_path)\n        logger.info(f\"✓ {handler.name()} complete. Output: {output_path}\")\n```\n\n**Testing:**\n- Integration test: Write 100 test events to eventstore, run orchestrator, verify all handlers complete\n- Integration test: Run again with append mode, verify handlers skip reprocessing\n- Integration test: Resume from middle (manually truncate eventhandler.csv), verify everything rebuilds correctly\n\n**Acceptance Criteria:**\n- ✅ All 5 handlers execute in order\n- ✅ Handler progress tracked and persisted\n- ✅ All output CSVs created with correct content\n- ✅ Determinism tests pass (2 runs → identical outputs)\n\n### Phase 1.5: Signal Handlers & Graceful Shutdown\n\n**File:** `speakermining/src/process/candidate_generation/wikidata/graceful_shutdown. py`\n\n**Responsibilities:**\n- Install SIGINT/SIGTERM handlers\n- Monitor `.shutdown` file\n- Set global `terminate_requested` flag\n- Check flag before writes\n\n**Key Functions:**\n```python\nterminate_requested = False\n\ndef install_shutdown_handlers():\n    def signal_handler(signum, frame):\n        global terminate_requested\n        terminate_requested = True\n        logger.warning(\"Shutdown requested. Finishing current batch...\")\n    \n    signal.signal(signal.SIGINT, signal_handler)\n    signal.signal(signal.SIGTERM, signal_handler)\n\ndef check_shutdown_file(shutdown_path: Path) -> bool:\n    if shutdown_path.exists() and shutdown_path.read_text().strip():\n        logger.warning(\"Shutdown file detected. Stopping gracefully.\")\n        return True\n    return False\n\n# In event_writer.append_event():\nif terminate_requested or check_shutdown_file(...):\n    logger.warn(\"Termination requested. Stopping.\")\n    return  # Don't write; caller handles gracefully\n```\n\n**Testing:**\n- Integration test: Start orchestrator in background, send SIGINT, verify handler progress saved\n- Integration test: Start orchestrator, create `.shutdown` file, verify graceful exit\n- Integration test: Resume after interrupt, verify correct continuation\n\n**Acceptance Criteria:**\n- ✅ SIGINT/SIGTERM captured and handled\n- ✅ Handler progress saved before exit\n- ✅ Shutdown file monitoring working\n- ✅ Resume after interrupt validates\n\n### Phase 1.6: Checksums & Data Integrity\n\n**File:** `speakermining/src/process/candidate_generation/wikidata/checksums.py`\n\n**Responsibilities:**\n- Compute SHA256 for closed chunks\n- Store checksums in `eventstore_checksums.txt`\n- Validate checksums on chunk open\n\n**Key Functions:**\n```python\ndef compute_checksum(chunk_path: Path) -> str:\n    \"\"\"Compute SHA256 of chunk file.\"\"\"\n    sha256_hash = hashlib.sha256()\n    with open(chunk_path, \"rb\") as f:\n        for byte_block in iter(lambda: f.read(4096), b\"\"):\n            sha256_hash.update(byte_block)\n    return sha256_hash.hexdigest()\n\ndef write_checksum_record(checksums_path: Path, chunk_name: str, hash_value: str):\n    \"\"\"Append checksum to registry.\"\"\"\n    with open(checksums_path, \"a\") as f:\n        f.write(f\"{chunk_name}={hash_value}\\n\")\n\ndef validate_chunk_checksum(chunk_path: Path, checksums_path: Path) -> bool:\n    \"\"\"Verify chunk checksum matches registry.\"\"\"\n    expected = _load_checksum_registry(checksums_path).get(chunk_path.name)\n    actual = compute_checksum(chunk_path)\n    if expected and expected != actual:\n        logger.error(f\"Checksum mismatch for {chunk_path}!\")\n        logger.error(f\"  Expected: {expected}\")\n        logger.error(f\"  Actual:   {actual}\")\n        return False\n    return True\n```\n\n**Testing:**\n- Unit test: Compute checksum of file, verify consistency\n- Unit test: Modify file byte, verify checksum changes\n- Unit test: Validate CheckSum record; tampered file fails\n\n**Acceptance Criteria:**\n- ✅ Checksums computed for active and archived chunks\n- ✅ Validation blocks on mismatch  (with clear error)\n- ✅ Checksum registry persisted and readable\n\n### Phase 1.7: Testing Suite & Validation\n\n**Files to Create:**\n- `speakermining/test/process/wikidata/test_event_store.py`\n- `speakermining/test/process/wikidata/test_handlers.py`\n- `speakermining/test/process/wikidata/test_orchestrator.py`\n- `speakermining/test/process/wikidata/test_determinism.py`\n- `speakermining/test/process/wikidata/test_shutdown.py`\n\n**Test Strategy:**\n1. **Unit tests:** Each component (EventStore, handlers, checksum validator)\n2. **Integration tests:** Full orchestrator with test data\n3. **Determinism tests:** Same events → identical outputs (2+ runs)\n4. **Stress tests:** Large event batches (50K+ events)\n5. **Resume tests:** Interrupt, resume, verify continuation\n\n**Target Coverage:**\n- All handlers: >90% code coverage\n- Critical paths: 100% coverage\n- Integration scenarios: 80%+ coverage\n\n**Acceptance Criteria for Phase 1:**\n- ✅ test_event_store.py: All tests pass\n- ✅ test_handlers.py: All handlers produce correct output for test data\n- ✅ test_orchestrator.py: Full run on ~1000 test events completes successfully\n- ✅ test_determinism.py: 3 independent runs of same event set produce byte-identical outputs\n- ✅ test_shutdown.py: Interrupt and resume scenarios validated\n- ✅ Code coverage: >85% for all new modules\n\n### Phase 1 Completion Gate\n\n**Deliverables:**\n- ✅ Event store with atomic writes and sequence numbering\n- ✅ Handler registry and base class\n- ✅ 5 core handlers (Instances, Classes, Triples, QueryInventory, Candidates stub)\n- ✅ Orchestrator for sequential handler execution\n- ✅ Graceful shutdown (signal handlers + monitor file)\n- ✅ Checksum generation and validation\n- ✅ Comprehensive test suite\n- ✅ 01_SPECIFICATION.md (this file)\n- ✅ Design documentation complete\n\n**Success Criteria:**\n1. All tests pass (unit + integration + determinism)\n2. Handlers rebuild v2-like artifacts from test events\n3. Event store survives crash recovery scenarios\n4. Graceful shutdown works (SIGINT, SIGTERM, monitor file)\n5. Checksums correctly detect corruption\n6. Two independent runs produce identical output (byte-for-byte)\n\n**Responsible Party:**\n- TBD (assign engineer)\n\n**Review Gate:**\n- Code review: Architecture consistency, test coverage\n- Functional review: Test suite passes, determinism verified\n- Documentation review: Spec Matches implementation\n\n---\n\n## Phase 2: Handler Integration\n\n**Goal:** Wire the graph expansion engine to use event-sourcing. By end of Phase 2, the new pipeline processes the full dataset and produces identical output to v2.\n\n### Phase 2.1: Extract Event Writer from Expansion Logic\n\n**Scope:**\n- Refactor `expansion_engine.py` to emit events instead of writing raw_queries files\n- Maintain backward compatibility during transition (dual-write: eventstore + raw_queries)\n\n**Changes:**\n```python\n# OLD: bfs_expansion.py\ndef _process_entity(entity_qid):\n    response = fetch_entity(entity_qid)\n    _write_raw_query_file(response)  # Old way\n    return response\n\n# NEW: expansion_engine.py\ndef _process_entity(entity_qid):\n    response = fetch_entity(entity_qid)\n    event = build_query_event(...)\n    event_store.append_event(event)  # New way\n    return response\n```\n\n**Dual-Write Phase (Optional):**\nFor safety, write to both eventstore and raw_queries during Phase 2. Allows rapid rollback if issues discovered.\n\n**Acceptance Criteria:**\n- ✅ Expansion engine emits events to chunks\n- ✅ Graph traversal semantics unchanged (same candidates found)\n- ✅ Performance comparable to v2 (no major slowdown)\n\n### Phase 2.2: Checkpoint/Resume Using Handler Sequences\n\n**Scope:**\n- Replace v2's snapshot-based checkpoints with handler sequence markers\n- Implement resume modes using handler registry\n\n**Changes:**\n```python\n# OLD notebook cell: Resume decision\nresume_decision = decide_resume_mode(ROOT, \"append\")\nif resume_decision[\"mode\"] == \"append\":\n    restore_checkpoint_snapshot(...)  # Copy large dirs\n\n# NEW notebook cell: Resume decision\nhandler_registry = HandlerRegistry(ROOT / \"data/.../eventhandler.csv\")\nif handler_registry.are_all_handlers_complete():\n    logger.info(\"All handlers caught up. Run complete.\")\nelse:\n    logger.info(f\"Handlers will resume from saved sequences...\")\n    run_handlers(ROOT)\n```\n\n**Acceptance Criteria:**\n- ✅ Handler registry tracks all handlers' progress\n- ✅ Resume modes: append (continue), restart (re-process all), revert (load snapshot)\n- ✅ No snapshot directory copying needed\n- ✅ Resume time < 1 second (reading metadata only)\n\n### Phase 2.3: Fallback Matcher Integration\n\n**Scope:**\n- Integrate `fallback_matcher.py` to emit `candidate_matched` events\n- Candidates are discovered, emitted as events, and handled by CandidatesHandler\n\n**Changes:**\n```python\n# fallback_matcher.py\ndef run_fallback_matching(...):\n    for mention_target in unresolved_targets:\n        for candidate in string_match(mention_target):\n            event = build_event(\n                event_type=\"candidate_matched\",\n                ...\n            )\n            event_store.append_event(event)\n```\n\n**Acceptance Criteria:**\n- ✅ Fallback matches emit events (not directly to CSV)\n- ✅ Output candidates match v2 fallback_matcher results\n- ✅ Handler correctly rebuilds candidates CSV from events\n\n### Phase 2.4: Full Dataset Run & Validation\n\n**Scope:**\n- Run new v3 pipeline on full dataset (all seeds, all mentions)\n- Compare outputs with v2 to verify correctness\n\n**Validation Steps:**\n1. Run v3 pipeline end-to-end\n2. Compare `instances.csv`: same rows, same columns, same values\n3. Compare `classes.csv`: same class hierarchies, same subclass lineages\n4. Compare `triples.csv`: same deduplicated triples\n5. Compare `query_inventory.csv`: same queries, same dedup semantics\n6. Compare `candidates.csv`: same candidates, same confidence scores (if applicable)\n7. Checksum full eventstore; validate all chunks\n\n**Acceptance Criteria:**\n- ✅ All projections byte-identical between v2 and v3\n- ✅ Query counts, entity counts, triple counts match\n- ✅ No data loss in migration\n- ✅ Full run completes without errors\n- ✅ Determinism: run pipeline twice, get identical outputs\n\n### Phase 2.5: Performance Benchmarking\n\n**Scope:**\n- Measure execution time, memory usage, I/O for v3 vs. v2\n- Identify and fix any major bottlenecks\n\n**Metrics:**\n- Total runtime (v3 vs. v2)\n- Memory peak usage\n- Disk I/O (bytes written)\n- Query latency (per-query, per-batch)\n\n**Acceptance Criteria:**\n- ✅ v3 runtime within 10% of v2 (ideally faster due to handler batching)\n- ✅ Memory usage comparable or less\n- ✅ No major regressions in query latency\n\n### Phase 2.6: Integration Tests & CI\n\n**Scope:**\n- Add integration tests for full pipeline (expansion + handlers + fallback)\n- Add CI/CD job to validate on every commit\n\n**Tests:**\n- `test_full_pipeline.py`: Run on smaller dataset (100 events), verify output\n- `test_determinism_full.py`: Run full pipeline 2x, compare outputs\n- `test_resume_scenarios.py`: interrupt/resume tests on full data\n\n**CI Job:**\n- Daily run of full dataset (external to PR CI, due to runtime)\n- Alert on data loss, performance regression, regressions in determinism\n\n**Acceptance Criteria:**\n- ✅ Unit tests pass (all handlers)\n- ✅ Integration tests pass (full pipeline)\n- ✅ Determinism guarantees hold\n- ✅ CI/CD jobs configured\n\n### Phase 2 Completion Gate\n\n**Deliverables:**\n- ✅ Graph expansion engine emits events to chunks\n- ✅ Handler-based resume using sequence markers\n- ✅ Full pipeline runs on complete dataset\n- ✅ Outputs identical to v2\n- ✅ Performance validated (no major regressions)\n- ✅ Integration test suite\n\n**Success Criteria:**\n1. v3 and v2 outputs byte-identical for full dataset\n2. Resume/interrupt scenarios tested and working\n3. Performance benchmarks show no major regression\n4. Determinism guaranteed: 2 independent runs → identical outputs\n5. CI/CD job passes regularly\n6. No data loss or corruption\n\n**Responsible Party:**\n- TBD (assign engineer)\n\n**Review Gate:**\n- Code review: Integration with expansion engine\n- Validation: Output comparison (v2 vs. v3)\n- Performance: Benchmark results reviewed\n\n---\n\n## Phase 3: Data Migration & v3-Only Cutover\n\n**Goal:** Migrate all v2 historical data to eventstore, validate, remove v2 code, and establish v3-only policy.\n\n### Phase 3.1: Migrate v2 Raw Queries to Eventstore\n\n**Scope:**\n- Load all v2 `raw_queries/*.json` files\n- Convert to v3 event format\n- Write to chunk files under `chunks/` with sequential numbering\n\n**Migration Script:**\n```python\ndef migrate_v2_to_v3(repo_root: Path):\n    \"\"\"Import all v2 raw_queries as v3 events.\"\"\"\n    raw_queries_dir = repo_root / \"data/20_candidate_generation/wikidata/raw_queries\"\n    event_store = EventStore(repo_root / \"data/.../ chunks\")\n    \n    seq_num = 1\n    for v2_file in sorted(raw_queries_dir.glob(\"*.json\")):\n        v2_event = json.load(open(v2_file))\n        \n        # Convert v2 to v3\n        v3_event = {\n            \"sequence_num\": seq_num,\n            \"event_version\": \"v3\",\n            \"event_type\": \"query_response\",\n            \"endpoint\": v2_event[\"endpoint\"],\n            \"normalized_query\": v2_event[\"normalized_query\"],\n            \"query_hash\": v2_event[\"query_hash\"],\n            \"timestamp_utc\": v2_event[\"timestamp_utc\"],\n            \"recorded_at\": datetime.fromisoformat(v2_event[\"timestamp_utc\"]).isoformat(),  # Use v2's timestamp as recorded_at\n            \"source_step\": v2_event[\"source_step\"],\n            \"status\": v2_event[\"status\"],\n            \"key\": v2_event[\"key\"],\n            \"http_status\": v2_event.get(\"http_status\"),\n            \"error\": v2_event.get(\"error\"),\n            \"payload\": v2_event[\"payload\"],\n        }\n        \n        # Write to eventstore\n        # (bypass normal append mechanism to control seq numbers)\n        _append_event_with_seq(event_store, v3_event, seq_num)\n        seq_num += 1\n    \n    logger.info(f\"Migrated {seq_num - 1} events from v2 to v3.\")\n```\n\n**Validation:**\n1. Count v2 files: X\n2. Count v3 events: must be X\n3. Spot-check: random v2 file → v3 event conversion is correct\n4. Sequence numbers: 1 to X, no gaps\n\n**Acceptance Criteria:**\n- ✅ All v2 events converted and written\n- ✅ No sequence gaps\n- ✅ Event version is \"v3\"\n- ✅ All required fields present\n\n### Phase 3.2: Validate Migrated Data\n\n**Scope:**\n- Rebuild projections from eventstore (newly migrated v3 events)\n- Compare against v2 originals\n\n**Validation Steps:**\n1. Truncate `eventhandler.csv` (reset all handlers to seq 0)\n2. Run orchestrator to rebuild all projections from eventstore\n3. Diff `instances.csv`: v2 original vs. v3 rebuilt\n4. Diff `classes.csv`, `triples.csv`, `query_inventory.csv`\n5. Ensure counts match exactly\n\n**Acceptance Criteria:**\n- ✅ Rebuilt instances.csv matches v2 original (byte-identical or value-identical with row order adjustment)\n- ✅ All classes recovered; class lineages correct\n- ✅ All triples present; dedup semantics preserved\n- ✅ Query inventory matches\n- ✅ No data loss\n\n### Phase 3.3 Remove v2 Code Paths\n\n**Scope:**\n- Delete or deprecate v2-specific modules and code\n- Remove dual-write logic (if implemented in Phase 2)\n- Clean up raw_queries directory (archive or delete)\n\n**Files to Remove/Update:**\n- `bfs_expansion.py`: Replaced by `expansion_engine.py`\n- `cache.py` (v2 raw file writing logic): Update to remove raw_queries writes\n- `aggregates.py` (v2 ad-hoc aggregation): Remove, replaced by handlers\n- Any v2 event schema validators: Update to reject v2 events\n\n**Establish v3-Only Policy:**\n- Add runtime check: reject any event with `event_version != \"v3\"`\n- Add code comment: \"v3-only policy established 2026-04-XX; legacy compatibility removed\"\n- Document in `documentation/Wikidata/2026-04-02_jsonl_eventsourcing/V3_ONLY_POLICY.md`\n\n**Acceptance Criteria:**\n- ✅ v2 modules removed or clearly deprecated\n- ✅ No runtime code branches for v2 compatibility\n- ✅ Runtime rejects v2 event format\n- ✅ v3-only policy document created\n\n### Phase 3.4: Archive Old Data\n\n**Scope:**\n- Archive v2 raw_queries directory for reference\n- Create checksums of archive\n- Document archive location\n\n**Actions:**\n```bash\n# Archive v2 data\ntar -czf data/20_candidate_generation/wikidata/archive/raw_queries_v2_20260402.tar.gz \\\n    data/20_candidate_generation/wikidata/raw_queries/\n\n# Create checksum\nsha256sum archive/raw_queries_v2_20260402.tar.gz > archive/raw_queries_v2_20260402.tar.gz.sha256\n\n# Document\necho \"Archived v2 raw_queries on 2026-04-02\" > archive/README.md\n```\n\n**Acceptance Criteria:**\n- ✅ Archive created and checksummed\n- ✅ Archive location documented\n- ✅ Old raw_queries directory can be deleted (archive is backup)\n\n### Phase 3.5: Production Cutover\n\n**Scope:**\n- Run v3 pipeline on production dataset one final time\n- Validate all outputs\n- Switch notebook orchestration to v3-only \n- Monitor for any issues\n\n**Pre-Cutover Checklist:**\n- ✅ Phase 2 completion gate passed\n- ✅ Data migration validated\n- ✅ v2 code removed\n- ✅ v3-only policy established\n- ✅ v3 archive (eventstore) backed up\n- ✅ All tests passing\n\n**Cutover Steps:**\n1. Backup eventstore (pre-production snapshot)\n2. Run v3 pipeline on production dataset\n3. Validate outputs (compare with v2 if available)\n4. Publish new artifacts\n5. Monitor for 24-48 hours\n6. Declare v3 production-ready\n\n**Acceptance Criteria:**\n- ✅ Production run completes successfully\n- ✅ All output artifacts generated\n- ✅ No errors or warnings\n- ✅ Backup created\n- ✅ All tests passing\n\n### Phase 3.6: Documentation & Knowledge Transfer\n\n**Scope:**\n- Finalize v3 documentation\n- Update workflow.md, contracts.md, README.md\n- Create runbooks for common tasks (resume, interrupt, migration)\n- Retire v2 documentation\n\n**Documents to Update/Create:**\n- `documentation/Wikidata/2026-04-02_jsonl_eventsourcing/V3_RUNBOOK.md` — How to run, resume, interrupt\n- `documentation/Wikidata/2026-04-02_jsonl_eventsourcing/V3_ARCHITECTURE.md` — High-level design\n- `documentation/workflow.md` — Update candidate generation section\n- `documentation/contracts.md` — Update v3 contracts\n- `documentation/Wikidata/wikidata_v3_only_policy.md` — No legacy support\n\n**Acceptance Criteria:**\n- ✅ All documentation updated\n- ✅ Runbooks written and tested\n- ✅ v2 docs archived/retired\n- ✅ Team trained on v3 operations\n\n### Phase 3 Completion Gate\n\n**Deliverables:**\n- ✅ All v2 data migrated to chunks\n- ✅ Migrated data validated (projections match v2)\n- ✅ v2 code removed\n- ✅ v3-only policy established and enforced\n- ✅ v2 archive created and backed up\n- ✅ Production cutover successful\n- ✅ Documentation finalized\n- ✅ Team trained\n\n**Success Criteria:**\n1. All v2 raw_queries migrated to v3 chunk chain\n2. Rebuilt projections match v2 originals exactly\n3. v3-only runtime enforced (rejects v2 events)\n4. Production dataset processed successfully\n5. No data loss or corruption\n6. Documentation complete and accurate\n7. Team understands v3 operations\n\n**Responsible Party:**\n- TBD (assign engineer)\n\n**Final Review Gate:**\n- Data integrity: migrations validated\n- Code quality: v2 removed cleanly\n- Documentation: complete and accurate\n- Operations: runbooks tested by team\n\n---\n\n## Cross-Phase Concerns\n\n### Testing Strategy\n- **Unit tests:** Each handler, event store, checksum validator (Phase 1)\n- **Integration tests:** Full orchestrator on test data (Phase 1)\n- **Determinism tests:** Same input → identical output, 2+ runs (Phase 1 + Phase 2)\n- **Full-dataset tests:** v2 vs. v3 comparison (Phase 2)\n- **Migration tests:** v2 → v3 conversion validation (Phase 3)\n- **Regression tests:** Production run validation (Phase 3)\n\n### Risk Mitigation\n1. **Data loss**: Comprehensive backups at each phase; dual-run validation\n2. **Corruption**: Atomic writes, checksums, crash recovery tests\n3. **Performance regression**: Benchmarking at Phase 2 gate\n4. **Incomplete migration**: Data validation step; full audit trail\n5. **Cutover failure**: Backup snapshots; rollback plan if needed\n\n### Timeline\n- Phase 1 (Scaffolding): 2-3 weeks\n- Phase 2 (Integration): 2-3 weeks\n- Phase 3 (Migration): 1-2 weeks\n- **Total**: ~5-8 weeks\n\n### Resource Allocation\n- **1 primary engineer**: Architecture, design, core implementation (Phases 1-3)\n- **1 secondary engineer**: Testing, validation, documentation (Phases 2-3)\n- **Part-time**: Code review, architectural guidance\n\n### Communication Plan\n- Weekly status updates to stakeholders\n- Phase completion announcements\n- Post-migration retrospective\n\n---\n\n## Summary\n\nThis migration plan converts the Wikidata pipeline from v2 (checkpoint-based) to v3 (event-sourced) in three phased, gated steps. Each phase builds on the previous; each gate ensures quality before proceeding.\n\n**Phase 1** builds the foundational event-sourcing machinery.  \n**Phase 2** integrates the machinery with the existing pipeline.  \n**Phase 3** migrates historical data and establishes v3 as production-only.\n\nBy the end, the system will have:\n- ✅ Centralized, immutable event store\n- ✅ Handler-driven, deterministic projections\n- ✅ Graceful shutdown and recovery\n- ✅ Built-in corruption detection (checksums)\n- ✅ All v2 semantic guarantees preserved\n- ✅ No legacy code or compatibility cruft\n


