# V3 JSONL Event-Sourcing — Technical Specification

**Date:** 2026-04-02  
**Status:** Specification (pre-implementation)  
**Author:** Based on analysis of v2 system and jsonl_potential_for_eventsourcing.md

---

## 1. Event Store Architecture

### 1.1 Core Concept
The **event store** is a single, append-only JSONL file that records all persistent state changes. Each line is a complete JSON event object. State is derived by replaying events and updating projections.

### 1.2 Event Store Location & Structure
```
data/20_candidate_generation/wikidata/
├── chunk_catalog.csv             # Derived index for fast chunk lookup (not canonical)
├── eventstore_checksums.txt      # Checksums per closed chunk
├── eventhandler.csv              # Handler progress tracking
├── chunks/                       # Closed chunks (immutable, usually compressed)
│   ├── eventstore_chunk_YYYY-MM-DD_0001.jsonl
│   ├── eventstore_chunk_YYYY-MM-DD_0002.jsonl
│   └── ...
└── snapshots/                    # Optional rollback snapshots
```

`chunk_catalog.csv` is a derived convenience index for replay acceleration:
```csv
chunk_id,file_name,first_sequence,last_sequence,status,compression,checksum_sha256,opened_at,closed_at
chunk_000001,eventstore_chunk_YYYY-MM-DD_0001.jsonl,1,50000,closed,none,abc123...,YYYY-MM-DDTHH:MM:SSZ,YYYY-MM-DDTHH:MM:SSZ
chunk_active,eventstore_chunk_YYYY-MM-DD_0002.jsonl,50001,,active,none,,YYYY-MM-DDTHH:MM:SSZ,
```

Canonical continuity is in chunk boundary events:
- last event of old chunk: `eventstore_closed` with `chunk_id` and `next_chunk_id`
- first event of new chunk: `eventstore_opened` with `chunk_id` and `prev_chunk_id`

Important:
- Canonical source of chunk linkage = boundary events in chunk files.
- `chunk_catalog.csv` can be regenerated from chunk files and boundary events at any time.
- If catalog and boundary events disagree, boundary events win and catalog must be rebuilt.

### 1.2.1 Chunk File Naming Convention

Closed chunk files use a human-readable date-based name:

- Format: `eventstore_chunk_YYYY-MM-DD_NNNN.jsonl`
- Example: `eventstore_chunk_2026-04-02_0001.jsonl`
- Date is UTC calendar date at chunk close time.
- `NNNN` is a zero-padded per-day counter starting at `0001`.

Rules:
- The current writable chunk file lives in `chunks/` and uses the same date-based naming convention as closed chunks.
- Chunk files are immutable once closed.
- File names are for readability and operations only.
- Canonical chunk identity is `chunk_id` from boundary events.
- Canonical chunk linkage is from `eventstore_closed` and `eventstore_opened` events.
- Sequence numbers remain continuous across all chunks and never reset.
- If file name, catalog, and boundary-event linkage disagree, boundary-event linkage is canonical.

Operational notes:
- Lexicographic order of file names matches chronological order for the same naming scheme.
- Multiple chunks created on the same day are represented by increasing `NNNN`.
- `chunk_catalog.csv` stores `file_name` as a derived index and can always be rebuilt from chunk files plus boundary events.

### 1.3 Event Schema (Common Envelope + Type-Specific Payload)

Every event in the chunk chain is a JSON object with two layers:

1. A **common envelope** shared by every event type.
2. A **type-specific payload** whose shape depends on `event_type`.

The JSON below is one concrete example (`query_response`), not the universal shape of all events:

```json
{
    "sequence_num": 1247,
    "event_version": "v3",
    "event_type": "query_response",
    "event_id": "evt_01hr...",
    "timestamp_utc": "2026-04-02T10:15:32Z",
    "recorded_at": "2026-04-02T10:15:45Z",
    "payload": {
        "endpoint": "wikidata_api",
        "normalized_query": "entity Q1499182",
        "query_hash": "abc123def456...",
        "source_step": "entity_fetch",
        "status": "success",
        "key": "Q1499182",
        "http_status": 200,
        "error": null,
        "entity": {
            "entity-type": "item",
            "id": "Q1499182",
            "labels": { ... },
            "claims": { ... }
        }
    }
}
```

**Common Envelope Fields:**
- `sequence_num` (integer): Unique, monotonic, continuous across chunks and never reset. Starts at 1 for new eventstore.
- `event_version` (string): "v3" (enforced; reject if not present or != "v3")
- `event_type` (string): Discriminator for the event shape and handler routing.
- `event_id` (string, optional but recommended): Stable event identifier for diagnostics and cross-reference.
- `timestamp_utc` (ISO 8601 string): When the event occurred (application time).
- `recorded_at` (ISO 8601 string): When the event was written to the store (server time).
- `payload` (dict): Event-specific data whose schema depends on `event_type`.

**Type-Specific Fields:**
- The contents of `payload` vary by `event_type`.
- For `query_response`, `payload` contains `endpoint`, `normalized_query`, `query_hash`, `source_step`, `status`, `key`, `http_status`, `error`, and the raw Wikidata response.
- For `entity_discovered`, `payload` contains entity metadata.
- For `candidate_matched`, `payload` contains mention-to-candidate match information.
- For `eventstore_imported_legacy` (or similar migration events), `payload` contains the original legacy event reference plus import metadata.

**Query-Response Payload Fields:**
- `endpoint` (string): "wikidata_api", "wikidata_sparql", "derived_local"
- `normalized_query` (string): Canonical query descriptor (whitespace normalized)
- `query_hash` (string): MD5(endpoint + "|" + normalized_query); used for dedup
- `source_step` (string): Frozen enum: "entity_fetch", "inlinks_fetch", "outlinks_fetch", "property_fetch", "class_resolution", "fallback_search", "expansion_decision", "candidate_match"
- `status` (string): "success", "cache_hit", "http_error", "timeout", "not_found", "skipped"
- `key` (string): Query-specific identifier (e.g., QID for entity fetch)
- `http_status` (integer | null): HTTP status code if applicable
- `error` (string | null): Error message if status is not "success"
- `entity` (dict): Raw Wikidata JSON response for query-response events

**Schema Rule:**
- All events must contain the common envelope.
- Only the `payload` structure changes by event type.
- Handlers must validate the subset of `payload` they consume and ignore unrelated event types.

### 1.4 Event Types

**Current Event Types (Phase 3 will add more):**

| Event Type | Source | Payload | Purpose |
|---|---|---|---|
| `query_response` | Graph expansion engine | Wikidata entity/SPARQL response | Log all queries; base for rebuilding everything |
| `entity_discovered` | Handler (derived) | Entity metadata (QID, labels, aliases) | Track discovered entities |
| `class_membership` | Handler (derived) | Entity QID, class QID, evidence | Track P31 assignments |
| `class_resolved` | Handler (derived) | Class QID, resolves parent class, path to core | Track class hierarchies |
| `triple_discovered` | Handler (derived) | Subject QID, property, object QID, source | Track discovered relationships |
| `candidate_matched` | Phase 3 | Mention ID, candidate QID, confidence | Log fallback matches |
| `expansion_decision` | Phase 3 | Entity QID, queue action (enqueue/skip/reject) | Audit expansion logic |
| `handler_checkpoint` | Handler (internal) | Handler name, last_seq_num, timestamp | Track handler progress |

---

## 2. Event Handlers

### 2.1 Handler Pattern

Each handler is a state machine that:
1. Reads events in sequence order across `chunks/`, using boundary-event linkage as canonical and `chunk_catalog.csv` as an index
2. Tracks its progress in `eventhandler.csv` (column: `last_processed_sequence`)
3. Maintains derived artifacts (CSVs, JSON files, indexes)
4. Updates its progress row after processing a batch of events atomically

`eventhandler.csv` Structure:
```csv
handler_name,last_processed_sequence,artifact_path,updated_at
InstancesHandler,1247,data/20_candidate_generation/wikidata/instances.csv,2026-04-02T10:16:00Z
ClassesHandler,1245,data/20_candidate_generation/wikidata/classes.csv,2026-04-02T10:15:55Z
TripleHandler,1247,data/20_candidate_generation/wikidata/triples.csv,2026-04-02T10:16:00Z
QueryInventoryHandler,1247,data/20_candidate_generation/wikidata/query_inventory.csv,2026-04-02T10:16:00Z
CandidatesHandler,1000,data/20_candidate_generation/wikidata/candidates.csv,2026-04-02T10:10:00Z
```

### 2.2 Core Handlers (Reference Implementation)

#### 2.2.1 InstancesHandler
**Responsibility:** Track discovered entities and their metadata

**Input Events:** `query_response` with payload.entity-type == "item"

**Processing:**
1. For each `query_response` event with successful status
2. Extract entity metadata (QID, labels, aliases, descriptions) from payload
3. Update in-memory entity index: `{qid: {label, labels_de, labels_en, aliases, ...}}`
4. Record discovery timestamp and expansion timestamp (if expanded)

**Output:**
- `instances.csv`: Rows with QID, label, labels_all, aliases, description, discovered_at, expanded_at
- `entities.json`: Full entity payloads keyed by QID

**Idempotency:** If same QID encountered, preserve oldest timestamp; merge new aliases only if novel

#### 2.2.2 ClassesHandler
**Responsibility:** Resolve class hierarchies; track which entities are persons, organizations, etc.

**Input Events:** `query_response`, `class_membership` (Phase 3)

**Processing:**
1. Watch for P31 claims in entity payloads
2. For each P31 claim: mark entity as instance of class; enqueue class QID for fetching
3. Watch for P279 claims in class entities
4. Build transitive closure: reach core classes (Q43229, Q215627, etc.)
5. Mark nodes with `subclass_of_core_class = true/false` and `path_to_core_class`

**Output:**
- `classes.csv`: QID, label, P279 (parent classes), subclass_of_core, path_to_core
- `core_classes.csv`: Filtered to only core class subtrees

**Idempotency:** Regenerate from scratch; class relationships are immutable from Wikidata

#### 2.2.3 TripleHandler
**Responsibility:** Extract and persist all discovered relationships

**Input Events:** `query_response` (outlinks), `triple_discovered` (Phase 3)

**Processing:**
1. For each entity query: scan all claims
2. For each claim: extract subject QID, property PID, object QID
3. Build dedup key: (subject, property, object)
4. Track source query (which event led to discovery)

**Output:**
- `triples.csv`: Columns: subject_qid, property, object_qid, source_event_seq, source_query_file

**Constraint:** ALL discovered triples must be present, including P31 class membership links

#### 2.2.4 QueryInventoryHandler
**Responsibility:** Maintain audit log of all queries with dedup semantics

**Input Events:** All events

**Processing:**
1. Watch for `query_response` events
2. Extract: endpoint, normalized_query, query_hash, status, payload_size, timestamp
3. Dedup by query_hash (only one row per unique query)
4. If same query appears multiple times: success > http_error > timeout > (success with older timestamp)
5. Track query count, success rate

**Output:**
- `query_inventory.csv`: Columns: query_hash, endpoint, normalized_query, status, first_seen, last_seen, count

**Idempotency:** Deterministic; same input events → same inventory

#### 2.2.5 CandidatesHandler (Phase 3)
**Responsibility:** Emit matching candidates for mentions

**Input Events:** `candidate_matched` (Phase 3)

**Processing:**
1. For each `candidate_matched` event
2. Write row to candidates CSV with mention_id, candidate_qid, mention_label, other context

**Output:**
- Candidates CSV (format TBD based on current fallback_matcher output)

**Note:** Depends on Phase 2 fallback matching implementation

### 2.3 Handler Execution
Handlers are run **sequentially** in a deterministic order:
1. InstancesHandler
2. ClassesHandler
3. TripleHandler
4. QueryInventoryHandler  
5. CandidatesHandler (Phase 3)

Each handler processes all unhandled events (where event.sequence_num > handler.last_processed_sequence).

**Batching:** Handlers can process events in batches (e.g., 1000 events per batch) to manage memory and provide incremental progress.

---

## 3. Write-Side: Event Producer (Graph Expansion Engine)

### 3.1 Single-Writer Constraint
Only the **graph expansion engine** writes to the current chunk file in `chunks/`. All other processes are readers.

### 3.2 Event Writing
```python
def write_query_event(
    event_type: str,
    endpoint: str,
    normalized_query: str,
    source_step: str,
    status: str,
    key: str,
    payload: dict,
    http_status: int | None = None,
    error: str | None = None,
) -> None:
    # Read current sequence number from last event in the latest chunk
    # or from an in-memory counter if first write
    next_seq = _get_next_sequence_num()
    
    event = {
        "sequence_num": next_seq,
        "event_version": "v3",
        "event_type": event_type,
        "timestamp_utc": <when it occurred>,
        "recorded_at": <now>,
        "source_step": source_step,
        "endpoint": endpoint,
        "normalized_query": normalized_query,
        "query_hash": compute_query_hash(endpoint, normalized_query),
        "status": status,
        "key": key,
        "http_status": http_status,
        "error": error,
        "payload": payload,
    }
    
    # Atomic append: write JSON line, fsync, verify
    _atomic_append_jsonl(event, chunk_path)
```

### 3.3 Atomic Write Guarantees
- **All-or-nothing**: If write is interrupted, only complete lines remain in eventstore
- **fsync after write**: Ensure event is on disk before acknowledging to caller
- **Verify on read**: After resuming, validate that last line is well-formed JSON

### 3.4 Sequence Number Management
**Option A (Recommended):** In-memory counter
- Load last event from eventstore on startup
- Extract its sequence_num; start counter at +1
- Increment counter before each write
- On crash: resume from last event's seq + 1

**Option B:** File-based lock + incremental counter
- Use a `.seq` marker file to track current sequence
- Lock before reading/incrementing/writing
- More complex but handles multi-process scenarios (future)

---

## 4. Checkpointing & Resume

### 4.1 Handler Checkpoints
Unlike v2 (which uses file snapshots), v3 uses **pure sequence-based resume**:
```csv
handler_name,last_processed_sequence
InstancesHandler,1247
QueryInventoryHandler,1247
ClassesHandler,1245
TripleHandler,1247
CandidatesHandler,1000
```

On startup:
- Read `eventhandler.csv`
- For each handler, read events from (last_processed_sequence + 1) onward
- Process events; update last_processed_sequence

### 4.2 Resume Modes
**Append:** Continue from last handler sequence
**Restart:** Truncate eventhandler.csv; reprocess all events
**Revert:** Load previous checkpoint snapshot; continue from there (advanced)

### 4.3 Snapshot Checkpoints (Required)
Take one snapshot before every run:
```
checkpoints/
├── checkpoint__YYYYMMDDTHHMMSSZ__seq1250.json
│   ├── metadata.json
│   └── handlers/
│       ├── InstancesHandler.csv
│       ├── ClassesHandler.csv
│       └── ...
└── snapshots/
    └── eventstore_snapshot_YYYYMMDDTHHMMSSZ.jsonl.gz
```

If needed, restore by:
1. Extract snapshot
2. Reset eventhandler.csv to snapshot's state
3. Restart with "append" resume mode

---

## 5. Graceful Shutdown & Interruption Handling

### 5.1 Signal Handlers (SIGINT / Ctrl+C)
```python
terminate_requested = False

def signal_handler(signum, frame):
    global terminate_requested
    terminate_requested = True
    logger.info("Shutdown requested. Finishing current event...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
```

Before each write operation:
```python
if terminate_requested:
    logger.info("Gracefully stopping. Last handler progress saved.")
    _save_handler_progress()
    sys.exit(0)
```

### 5.2 Monitor File Pattern (External Control)
```python
shutdown_file = Path(ROOT) / "data/20_candidate_generation/wikidata/.shutdown"

# Periodically check (e.g., every 100 events processed)
if shutdown_file.exists() and shutdown_file.read_text().strip():
    logger.info("Shutdown file detected. Stopping gracefully.")
    _save_handler_progress()
    sys.exit(0)
```

External process can signal shutdown:
```bash
echo "initiated by: admin" > .shutdown
```

### 5.3 Handler Progress Persistence
After processing a batch of events (e.g., 100 events), atomically write:
```python
def _save_handler_progress(handler_name: str, last_seq: int):
    # Read current eventhandler.csv
    # Update row for handler_name
    # Atomic write (write to temp, rename)
    _atomic_write_csv(eventhandler_csv, updated_rows)
```

On restart, handlers resume from their last saved sequence.

---

## 6. Chunking & Archival

### 6.1 Chunking Strategy
Chunks are closed when:
- A predetermined number of events is reached (e.g., 50,000 events per chunk)
- OR a time-based boundary is crossed (e.g., daily chunks)
- OR manually triggered (e.g., before major restructuring)

### 6.2 Chunk Boundaries
When rolling from one chunk to the next:
1. Append `eventstore_closed` event to the current chunk (with current `chunk_id`).
2. Finalize the chunk and compute its checksum.
3. Write/update `chunk_catalog.csv` row with `first_sequence`, `last_sequence`, checksum, and `status=closed`.
4. Open the next chunk file in `chunks/` using the date-based naming convention.
5. Add/update `chunk_catalog.csv` row for the new chunk as `status=active`.
6. Append `eventstore_opened` as first event in the new chunk.

When closing/opening chunks, links are by immutable `chunk_id` (not by filenames):
```python
# Last event in chunk_000001
{
  "sequence_num": 50000,
  "event_type": "eventstore_closed",
    "chunk_id": "chunk_000001",
  "reason": "chunk_limit_reached",
    "next_chunk_id": "chunk_000002",
    "recorded_at": "YYYY-MM-DDTHH:MM:SSZ"
}

# First event in chunk_000002 (new active chunk)
{
  "sequence_num": 50001,
  "event_type": "eventstore_opened",
    "chunk_id": "chunk_000002",
    "prev_chunk_id": "chunk_000001",
    "recorded_at": "YYYY-MM-DDTHH:MM:SSZ"
}
```

**Critical:** Sequence numbers NEVER reset across chunks.

**Canonical Rule:**
- The chunk chain is defined by boundary events (`eventstore_closed` and `eventstore_opened`) plus continuous sequence numbers.
- `chunk_catalog.csv` must reflect that chain; it does not define it.

### 6.3 Compression  & Checksums
After a chunk is closed (no more writes):
```bash
# Compute checksum
sha256sum eventstore_chunk_YYYY-MM-DD_0001.jsonl > eventstore_checksums.txt
```

Append to `eventstore_checksums.txt`:
```
eventstore_chunk_YYYY-MM-DD_0001.jsonl=abc123def456...
eventstore_chunk_YYYY-MM-DD_0002.jsonl=xyz789...
```

### 6.4 Reading Across Chunks
When a handler needs to read events:
```python
def iter_events_from(start_seq: int):
    # Resolve candidate chunk order from chunk_catalog.csv (fast path).
    chunk_rows = _load_chunk_catalog_sorted_by_first_sequence()

    # Validate index against canonical boundary-event links; rebuild catalog if needed.
    if not _catalog_matches_boundary_chain(chunk_rows):
        chunk_rows = _rebuild_catalog_from_boundary_events()

    for row in chunk_rows:
        first_seq = row["first_sequence"]
        last_seq = row["last_sequence"] or float("inf")  # open chunk has no last yet
        if last_seq < start_seq:
            continue

        chunk_path = _resolve_chunk_path(row["file_name"])
        _validate_checksum_if_closed(row, chunk_path)
        with open(chunk_path) as f:
            for line in f:
                event = json.loads(line)
                if event["sequence_num"] >= start_seq:
                    yield event
```

Rebuild-from-scratch behavior is therefore explicit: handlers start at `start_seq=1` and consume every cataloged chunk in sequence order, then the open chunk.

### 6.5 Catalog Regeneration and Consistency
`chunk_catalog.csv` is derived and must be reproducible:

1. Scan chunk files in `chunks/` in sequence order.
2. For each chunk, read first/last event sequence and boundary-event metadata.
3. Reconstruct chain by `prev_chunk_id`/`next_chunk_id` and verify continuous sequence numbers.
4. Rewrite `chunk_catalog.csv` atomically.

Consistency checks required at startup:
- No sequence gaps across linked chunks.
- Every closed chunk has matching checksum.
- Boundary links are bidirectionally consistent (`next_chunk_id` and `prev_chunk_id`).

If checks fail: stop processing, report mismatch, and require manual recovery or catalog rebuild.

---

## 7. Data Corruption Protection

### 7.1 Corruption Scenarios
- **In-flight write failure**: Last line in JSONL is incomplete
- **Silent corruption**: Bit flip in middle of file (rare but possible)
- **Lost writes**: Power loss before fsync

### 7.2 Detection Mechanisms

**Line-Level:**
- Only the last line might be incomplete; prior lines are guaranteed safe
- Validation: Parse each line as JSON; skip unparseable last line

**Chunk-Level:**
- Checksum validation on startup for compressed chunks
- If checksum mismatch: alert, refuse to proceed, require manual intervention

**Schema-Level:**
- Reject events with missing required fields
- Reject events with event_version != "v3"

### 7.3 Recovery Strategy

**For Incomplete Last Line:**
```python
# If last line fails JSON parse
if not _is_valid_json(last_line):
    logger.warning("Last line incomplete. Truncating.")
    # Truncate file to last complete line
    _truncate_to_last_valid_line(eventstore_path)
    # Handlers resume from last_processed_sequence
```

**For Checksum Mismatch (Compressed Chunk):**
```
ALERT: Chunk eventstore_chunk_3.jsonl.gz checksum mismatch!
Expected: abc123...
Actual:   def456...
Action: Restore from backup before this timestamp.
```
Requires manual intervention and backup restoration.

**For Corruption During Expansion:**
- Truncate to last valid event
- Restart with "append" resume mode
- Handlers reprocess from saved sequence

### 7.4 Backups
Maintain backups:
- **Before each run**: Full snapshot of eventstore + handler state
- **Periodic**: Daily/weekly full backups
- **Off-site**: Archive to separate storage

---

## 8. Determinism & Idempotency

### 8.1 Deterministic Event Processing
For a given set of input events, handlers MUST produce identical output:
- Same row order in CSVs
- Same field values
- Same aggregate counts

This requires:
- Stable sorting (e.g., by QID for instances)
- Canonical JSON serialization (consistent key order)
- No randomness in handler logic

### 8.2 Idempotent Reruns
Running the handler suite twice on the same eventstore MUST produce identical CSVs:
1. Handler reads all events from seq=1
2. Processes all events
3. Writes output CSV
4. Updates eventhandler.csv

If run again:
1. Handler reads events from seq=(last_processed_seq + 1), which is empty
2. Skips processing
3. Overwrites output CSV with identical content

### 8.3 Testing for Determinism
- Save eventstore + eventhandler snapshot
- Run handlers → capture output CSVs
- Restore snapshot
- Run handlers again → verify output CSVs are byte-identical

---

## 9. Configuration & Tuning

### 9.1 Handler Batch Size
How many events to process before saving progress:
- Default: 1000 events
- Tuning: Balance memory usage vs. checkpoint frequency
- Smaller batches → more frequent checkpoints, less memory, slower
- Larger batches → less frequent checkpoints, more memory, faster

### 9.2 Chunk Size Threshold
When to close a chunk:
- Default: 50,000 events
- Tuning: Balance file size vs. compression ratio
- Consider typical event size (~2KB) → 100MB chunk

### 9.3 Checksum Validation
Validate checksums on:
- **Always:** When opening a compressed chunk for reading
- **Optionally:** On periodic audits

### 9.4 Logging Verbosity
Log levels per component:
- EventStore writer: INFO for every event (too verbose? → DEBUG)
- Handlers: INFO for handler startup/completion, DEBUG for per-event processing
- Checksum validation: WARNING for mismatches, INFO for successes

---

## 10. Transitions from V2

### 10.1 Data Migration (Phase 3)
For each event in v2 `raw_queries/`:
```python
v2_event = _load_raw_query_file(path)  # Current v2 format

# Convert to v3
v3_event = {
    "sequence_num": next_seq(),
    "event_version": "v3",
    "event_type": "query_response",
    "endpoint": v2_event["endpoint"],
    "normalized_query": v2_event["normalized_query"],
    "query_hash": v2_event["query_hash"],
    "timestamp_utc": v2_event["timestamp_utc"],
    "recorded_at": <now>,  # Assign recording time to import time
    "source_step": v2_event["source_step"],
    "status": v2_event["status"],
    "key": v2_event["key"],
    "http_status": v2_event.get("http_status"),
    "error": v2_event.get("error"),
    "payload": v2_event["payload"],
}

_write_event_to_eventstore(v3_event)
```

### 10.2 Artifact Regeneration
After migration:
1. Truncate all projection CSVs
2. Reset eventhandler.csv to all sequences = 0
3. Run handlers to rebuild from eventstore
4. Validate rebuilt CSVs match v2 originals

### 10.3 v3-Only Policy
Like v2, establish a v3-only policy post-migration:
- Do not implement v2 compatibility readers
- Do not branch on old artifact formats
- Remove v2-specific code paths
- Test only against v3 events

---

## 11. API/Contract Surface

### 11.1 Producer API (Event Writer)
```python
# Interface for graph expansion engine
def write_event(event_dict: dict) -> None:
    """Append event to the current chunk file atomically."""
    ...

def get_next_sequence_num() -> int:
    """Return next sequence number to assign."""
    ...
```

### 11.2 Consumer API (Handlers)
```python
class EventHandler:
    def name(self) -> str: ...
    
    def last_processed_sequence(self) -> int:
        """Read from eventhandler.csv"""
        ...
    
    def process_events(self, events: Iterable[dict]) -> None:
        """Override to consume events."""
        ...
    
    def materialize(self, output_path: Path) -> None:
        """Write projection to disk."""
        ...
    
    def update_progress(self, last_seq: int) -> None:
        """Atomically update eventhandler.csv"""
        ...
```

### 11.3 Query API (Chunk Reader)
```python
def iter_events_from(start_seq: int) -> Iterable[dict]:
    """Iterate all events from start_seq onward, across chunks."""
    ...

def get_event_by_sequence(seq: int) -> dict:
    """Random access (may require scanning if in compressed chunk)."""
    ...

def validate_chunk(chunk_path: Path) -> bool:
    """Verify checksum and parse integrity."""
    ...
```

---

## 12. Resolved Design Decisions

See [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) for the finalized decision register. Key decisions already fixed for implementation:

1. **Event Type Taxonomy**
    - Maintain a dedicated handler/event taxonomy file and define event types as early as possible.
2. **Handler Ordering**
    - Use explicit dependency ordering (not only fixed sequence), because class-resolution and expansion decisions feed later handlers.
3. **Backward Compatibility with v2**
    - Use a one-time transition/import handler for legacy `raw_queries/*.json` query-response files into v3 events.
    - Treat non-response legacy artifacts as rebuildable projections, not canonical source data.
4. **Snapshot Granularity**
    - Take one snapshot before every run.
5. **Monitoring & Observability**
    - Implement only low-effort baseline metrics now; expand observability later using replay-derived metrics.

---

## 13. Success Criteria

**Phase 1 Completion (Event Store Scaffolding):**
- ✅ Atomic chunk writer with explicit sequence numbers
- ✅ Handler progress tracking (eventhandler.csv)
- ✅ Reference handlers (Instances, Classes, Triples, QueryInventory) fully implemented
- ✅ Handlers rebuild v2 artifacts from test event dataset byte-for-byte
- ✅ Graceful shutdown (signal handlers + monitor file) tested
- ✅ Checksum generation and validation working
- ✅ Documentation complete (this spec)

**Phase 2 Completion (Handler Integration):**
- ✅ Graph expansion engine emits events to the chunk chain (not raw_queries/)
- ✅ Fallback matcher emits candidate_matched events
- ✅ Checkpoint/resume using handler sequence numbers functional
- ✅ New pipeline produces identical output to v2 for full dataset
- ✅ Determinism tests pass (same input → identical output)

**Phase 3 Completion (Migration & Cleanup):**
- ✅ All v2 raw_queries/ migrated to the chunk chain
- ✅ Checksums validated; no data loss
- ✅ v3-only policy established; v2 code paths removed
- ✅ Production run successful; no regressions
- ✅ v2 documentation archived; v3 docs finalized
