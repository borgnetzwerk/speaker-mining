# Step 3: Canonical Event Schema

Date: 2026-03-31
Status: Design and implementation contract
Scope: Canonical raw query event schema, normalization rules, hashing rules, process-step and status taxonomy, and legacy raw-file archive procedure

---

## 1. Objective

Step 3 defines the authoritative event envelope for every Wikidata network response and derived query event so that:
- cache-first behavior remains deterministic,
- query inventory dedup is correct,
- checkpoint/resume can continue safely,
- materialization can rebuild artifacts from raw events without ambiguity.

This step also defines the migration handling for existing legacy raw files:
- no schema adapters,
- move to archive,
- external backup,
- archive cleanup after backup.

---

## 2. Inputs and Dependencies

Authoritative upstream inputs:
- documentation/Wikidata/2026-03-31_transition/wikidata_future_V2.md
- documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md
- documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md

Implementation modules impacted:
- speakermining/src/process/candidate_generation/wikidata/cache.py
- speakermining/src/process/candidate_generation/wikidata/entity.py
- speakermining/src/process/candidate_generation/wikidata/inlinks.py
- speakermining/src/process/candidate_generation/wikidata/outlinks.py
- speakermining/src/process/candidate_generation/wikidata/event_log.py (new)
- speakermining/src/process/candidate_generation/wikidata/query_inventory.py (new)
- speakermining/src/process/candidate_generation/wikidata/checkpoint.py (new)

---

## 3. Current vs Target Event Shape

## 3.1 Current legacy raw record shape

Legacy raw files currently use a minimal envelope:
- query_type
- key
- requested_at_utc
- source
- payload

Limitations:
- endpoint is missing,
- normalized query descriptor is missing,
- query hash is missing,
- status taxonomy is missing,
- process-step taxonomy is not explicit.

## 3.2 Target canonical shape (v2)

All new raw records must use this canonical envelope:

```json
{
  "event_version": "v2",
  "event_type": "query_response",
  "endpoint": "wikidata_api|wikidata_sparql|derived_local",
  "normalized_query": "canonical string",
  "query_hash": "md5 hex",
  "timestamp_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "source_step": "enum",
  "status": "enum",
  "key": "stable key",
  "http_status": 200,
  "error": null,
  "payload": {}
}
```

---

## 4. Canonical Field Contract

## 4.1 Required fields

1. event_version
- Type: string
- Allowed: v2
- Purpose: freeze schema generation for Step 3+

2. event_type
- Type: string
- Allowed: query_response
- Purpose: reserve future event families without changing this envelope

3. endpoint
- Type: string
- Allowed:
  - wikidata_api
  - wikidata_sparql
  - derived_local
- Purpose: dedup and provenance grouping

4. normalized_query
- Type: string
- Purpose: deterministic query identity independent of runtime noise

5. query_hash
- Type: string
- Format: lowercase md5 hex
- Rule: md5(endpoint + "|" + normalized_query)

6. timestamp_utc
- Type: string
- Format: UTC ISO second precision, example 2026-03-31T11:22:33Z

7. source_step
- Type: string
- Allowed:
  - entity_fetch
  - inlinks_fetch
  - outlinks_build
  - property_fetch
  - materialization_support

8. status
- Type: string
- Allowed:
  - success
  - cache_hit
  - http_error
  - timeout
  - fallback_cache

9. key
- Type: string
- Purpose: human-readable stable target key (for example Q1499182, Q1499182_limit200)

10. http_status
- Type: integer or null
- Rule:
  - required integer for network responses,
  - null for derived_local events

11. error
- Type: string or null
- Rule:
  - null on success and cache_hit,
  - short error message on http_error or timeout

12. payload
- Type: object
- Rule: full response payload or derived payload needed for deterministic rebuild

## 4.2 Optional extension fields

Optional fields may be added later only if they do not alter dedup semantics:
- attempt_count
- duration_ms
- request_id

These are explicitly non-authoritative for identity and dedup.

---

## 5. Normalized Query Rules

## 5.1 Entity fetch

Pattern:
- endpoint: wikidata_api
- normalized_query: entity:QID
- key: QID

Example:
- normalized_query = entity:Q1499182

## 5.2 Inlinks fetch

Pattern:
- endpoint: wikidata_sparql
- normalized_query: inlinks:target=QID;page_size=N;offset=K;order=source_prop
- key: QID_limitN_offsetK

Mandatory ordering token:
- order=source_prop means ORDER BY ?source ?prop

## 5.3 Outlinks build

Pattern:
- endpoint: derived_local
- normalized_query: outlinks_from_entity:QID
- key: QID

## 5.4 Property fetch (when applicable)

Pattern:
- endpoint: wikidata_api
- normalized_query: property:PID
- key: PID

---

## 6. Process Step and Status Semantics

## 6.1 process step usage matrix

- entity_fetch
  - endpoint: wikidata_api
  - payload: entity response payload

- inlinks_fetch
  - endpoint: wikidata_sparql
  - payload: SPARQL response page

- outlinks_build
  - endpoint: derived_local
  - payload: extracted outlinks structure

- property_fetch
  - endpoint: wikidata_api
  - payload: property response payload

- materialization_support
  - endpoint: derived_local
  - payload: only if a deterministic rebuild dependency must be persisted

## 6.2 status usage rules

- success
  - network call succeeded, payload is fresh

- cache_hit
  - no network request, payload sourced from valid cache event

- http_error
  - network call failed with HTTP error code

- timeout
  - network call exceeded timeout

- fallback_cache
  - network call failed, cached payload used

Status constraints:
- query_inventory dedup keeps latest successful response for a given hash and endpoint.
- non-success records remain valuable for diagnostics but are not preferred for inventory freshness.

---

## 7. Inlinks Paging Contract (Frozen)

This section fully parameterizes paging behavior for Step 3 implementation.

Chosen strategy:
- hybrid

Frozen parameters:
- page_size_default: 200
- page_size_max: 1000
- ordering_clause: ORDER BY ?source ?prop
- page query template: LIMIT {page_size} OFFSET {offset}
- dedup key across pages: (source_qid, pid)

Checkpoint cursor schema:
- inlinks_cursor.target_qid: string
- inlinks_cursor.seed_qid: string
- inlinks_cursor.page_index: integer
- inlinks_cursor.offset: integer
- inlinks_cursor.last_source_qid: string or null
- inlinks_cursor.last_pid: string or null
- inlinks_cursor.page_size: integer
- inlinks_cursor.exhausted: boolean

Retry and resume behavior:
- max_retries_per_page: 4
- retry policy: exponential backoff with jitter
- cursor is persisted only after successful parse and dedup merge of a page
- if retries exhaust: write incomplete checkpoint and stop_reason=crash_recovery
- resume continues from persisted cursor without replaying successful pages

---

## 8. Legacy Raw Files: Archive and Cleanup Procedure

Policy decision:
- No version adapters.
- No schema translation layer.
- Legacy files are removed from active runtime immediately after archive handoff.

## 8.1 Scope of legacy files

Legacy directory:
- data/20_candidate_generation/wikidata/raw_queries

Legacy detection rule:
- any record not containing event_version=v2 is legacy

## 8.2 Archive procedure

1. Create archive directory:
- data/20_candidate_generation/wikidata/archive/raw_queries_legacy_YYYYMMDDTHHMMSSZ

2. Move legacy raw files into archive directory.

3. Write archive manifest file in the archive directory:
- archive_manifest.json containing:
  - archived_at_utc
  - source_directory
  - files_archived_count
  - sample_file_names
  - reason: schema_migration_step_3

4. Perform external backup of archive directory outside repository.

5. After backup confirmation, delete archived legacy files from repository archive folder.

Operational note:
- external backup is an operational action and intentionally outside git history.

## 8.3 Non-goals

- Do not implement runtime compatibility readers for legacy event files.
- Do not attempt in-place mutation of legacy records.

---

## 9. Acceptance Tests for Step 3

Target test location:
- speakermining/test/process/wikidata

Required tests:

1. test_event_schema_required_fields
- verifies all required v2 fields exist in emitted events

2. test_query_hash_is_deterministic
- verifies md5(endpoint|normalized_query) remains stable

3. test_normalized_query_patterns
- verifies entity/inlinks/outlinks/property normalized descriptors

4. test_status_semantics_success_and_fallback
- verifies status transitions and inventory preference behavior

5. test_inlinks_paging_no_duplicates_across_offsets
- verifies dedup correctness for paged inlinks

6. test_inlinks_resume_from_cursor_no_missing_rows
- verifies checkpoint cursor resume continuity

7. test_inlinks_retry_failure_writes_incomplete_checkpoint
- verifies crash-recovery checkpoint behavior

8. test_archive_legacy_raw_files_without_adapters
- verifies legacy files are archived and not consumed by v2 readers

---

## 10. Implementation Action Plan

1. Create event_log.py with strict v2 writer and reader validation.
2. Refactor cache.py and entity.py to emit v2 events for network and derived operations.
3. Implement deterministic normalized_query builders in one shared helper location.
4. Implement query inventory dedup by query_hash + endpoint with latest success rule.
5. Implement legacy archive utility command for Step 3 migration execution.
6. Run Step 3 acceptance tests.
7. Update step outputs in migration_sequence.md.

---

## 11. Decision Log

Decisions made in Step 3:
- Canonical event envelope is frozen at v2.
- query_hash formula is fixed to md5(endpoint + "|" + normalized_query).
- Inlinks paging contract is fully parameterized.
- Legacy raw files are archive-and-remove, with no adapter layer.

---

## 12. Definition of Done (Step 3)

Step 3 is complete when:
1. All newly emitted raw query records conform to the v2 schema contract.
2. Inlinks paging behavior matches frozen parameters and resume cursor semantics.
3. query_inventory dedup operates on query_hash + endpoint and keeps latest success.
4. Legacy raw files are archived, externally backed up, and removed from active repository archive folder.
5. Step 3 acceptance tests pass.
