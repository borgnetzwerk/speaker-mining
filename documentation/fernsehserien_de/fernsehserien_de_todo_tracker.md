# Fernsehserien.de ToDo Tracker

Last updated: 2026-04-08

Status legend:
- OPEN: not implemented or not verified
- BLOCKED: needs decision
- DONE: completed and verified

## Conversation carry-over tasks

### FST-001 Legacy cache/events import compatibility (DONE)
Goal:
1. Ensure older cached files remain usable even when newer implementations rely on newer event types.

Problem pattern:
1. Files exist in cache from old runs.
2. New code expects creation/discovery events that old runs never emitted.
3. Pipeline ignores valid old files because event evidence is missing.

Acceptance:
1. Existing cache files can be discovered and processed without deleting or re-fetching.
2. Legacy-origin evidence is represented via explicit migration/import event type or metadata marker.
3. Re-run remains idempotent.

Resolution note:
1. Implemented `legacy_cache_page_imported` emission with inferred leaf URL import and `episode_url_discovered` backfill path `legacy_cache_import`.

## Stage-2 specification tasks (fermsehserien_de_specification.md)

### FST-002 Contract alignment: minimum event type set vs discovered/normalized model (DONE)
Gap:
1. Stage-2 spec still lists `episode_leaf_parsed` as required minimum event type.
2. Current implementation emits discovered + normalized families instead.

Options:
1. Update spec to make discovered/normalized event families normative.
2. Emit a compatibility `episode_leaf_parsed` event projection-level alias.

Acceptance:
1. Spec and implementation define one consistent canonical contract.

Resolution note:
1. Stage-2 spec updated to v1 decision-locked contract and minimum event types now include discovered/normalized families.
2. Compatibility `episode_leaf_parsed` emission removed; discovered/normalized events are canonical.

### FST-003 Representative-sample parsing evidence for 5 information groups (DONE)
Gap:
1. Spec completion criterion requires representative sample evidence.
2. Current runs validated architecture and cache-first behavior, but no explicit sampled quality report is tracked.

Acceptance:
1. Add reproducible sample QA artifact (for example CSV/markdown) proving extraction coverage for metadata, description, publication, cast/crew, sendetermine.

Resolution note:
1. Added representative QA report in `documentation/fernsehserien_de/representative_sample_qa_2026-04-08.md` with row counts and sample records.

### FST-004 Open decisions from Stage-2 spec (DONE)
Decisions required before broader rollout:
1. Raw HTML persistence strategy: full HTML in event payload vs cache file reference + content hash.
2. Request budget semantics: `-1` unlimited vs explicit cap only.
3. Future of `episode_facts.csv`: keep text-heavy compatibility table vs fully normalized contract.
4. Fallback traversal policy: always integrity check vs only on detected gaps.

Resolution note:
1. Raw HTML persistence: cache path + hash in events, no full body in payloads.
2. Budget semantics: `-1` means unlimited.
3. `episode_facts.csv`: removed from canonical projection set.
4. Fallback traversal: `on_gap` only.

## Episode extraction logic tasks (episode_extraction_logic.md)

### FST-005 Broadcast normalization edge cases (DONE)
Gap:
1. Midnights/day-rollover handling is documented but not fully implemented.
2. Broadcaster normalization strategy (for example lowercased canonical key + future entity link) is still basic.

Acceptance:
1. Normalize broadcasts with deterministic rollover handling.
2. Add broadcaster normalization field(s) and rule versioning.

Resolution note:
1. Normalizer now handles end-time rollover (`end <= start` => next day) and emits broadcaster key normalization.

### FST-006 Confidence granularity and parser-rule traceability (DONE)
Gap:
1. Extraction currently uses mostly shared/static confidence values.
2. Logic doc describes per-structure confidence expectations.

Acceptance:
1. Confidence derives from extraction path/quality checks per record type.
2. Rule names remain explicit and versioned for discovered and normalized layers.

Resolution note:
1. Parser now emits per-record confidence (metadata, guest, broadcast) based on structural evidence.
2. Versioned parser/normalizer rule fields remain persisted in events and projections.

### FST-007 Raw-overflow and schema evolution policy hardening (DONE)
Gap:
1. `raw_extra_json` exists but schema-evolution usage policy is not yet formalized.

Acceptance:
1. Document what belongs in stable columns vs `raw_extra_json`.
2. Add regression checks to prevent accidental dropping of unknown raw attributes.

Resolution note:
1. Added raw-overflow governance section in extraction logic doc.
2. Added regression tests covering `raw_extra_json` persistence and related parser contract behavior.


### FST-008 Issues with the projections (DONE)
The current program_pages.csv contains three entries of Markus Lanz:
```
program_name	fernsehserien_de_id	root_url	fetched_at_utc	source_event_sequence
Markus Lanz	markus-lanz	https://www.fernsehserien.de/markus-lanz/	2026-04-08T11:41:46Z	3
Markus Lanz	markus-lanz	https://www.fernsehserien.de/markus-lanz/	2026-04-08T11:50:11Z	988
Markus Lanz	markus-lanz	https://www.fernsehserien.de/markus-lanz/	2026-04-08T12:12:25Z	996
```

It is very likely that this is an error and they were supposed to be one row only.

Also, all other projections are linked via program_name (Markus Lanz). However, this may not be unique, while fernsehserien_de_id (markus-lanz) is always unique. We should only reference via unique IDs - in this case, via fernsehserien_de_id.

Resolution note:
1. Projection replay now deduplicates program pages by `fernsehserien_de_id`.
2. All derived projection rows now carry `fernsehserien_de_id` and use it as the stable join key.
3. Projections were rebuilt from the immutable event log after clearing derived projection state.

### FST-009 Notebook promotion to full orchestrator and projection contract cleanup (DONE)
Goal:
1. Promote the notebook from validation slice to repeatable full pipeline orchestrator.
2. Remove redundant aggregate projection artifacts not required by canonical discovered/normalized contract.

Acceptance:
1. Notebook supports all eligible programs (not hard-coded to one row).
2. Runtime network behavior is controlled by `MAX_NETWORK_CALLS` (`0` cache-only, `>0` bounded, `<0` unlimited).
3. Canonical projection contract excludes `episode_facts.csv` and related generation code.

Resolution note:
1. Notebook now runs one production workflow execution via `run_fernsehserien_pipeline`.
2. Notebook runtime configuration was simplified to core parameters (`MAX_NETWORK_CALLS`, `QUERY_DELAY_SECONDS`, `USER_AGENT`).
3. Pipeline verification cell now validates behavior directly against `MAX_NETWORK_CALLS` semantics.
4. `episode_facts.csv` generation and handler paths were removed from projection/orchestrator code.
5. Stage-2 docs were updated to canonical discovered/normalized projection artifacts.

### FST-010 Notebook lifecycle completion event (`run_finished`) is not yet emitted (DONE)
Gap:
1. Stage-2 spec requires notebook observability to include both `run_started` and `run_finished`.
2. Current fernsehserien notebook logging emits `run_started` but does not append a `run_finished` event at the end of a successful run.

Acceptance:
1. Notebook appends one `run_finished` event with final summary context after workflow completion.
2. Event is emitted once per run and does not duplicate on repeated cell execution in the same run unless explicitly restarted.

Resolution note:
1. Notebook execution now appends `run_finished` with final run summary metrics.
2. Emission is deduplicated per `run_id` in the notebook session, so repeated execution of the workflow cell does not write duplicate `run_finished` events.

### FST-011 Output heartbeat (DONE)
Cell 9 (`## 3) Execute Workflow`) needs to print some output during execution. Right now, we only have outputs once everything is done - but we need heartbeat outputs every minute as well as every 50 network calls.

Resolution note:
1. Cell 9 now passes a heartbeat callback into `run_fernsehserien_pipeline(...)`.
2. Runtime emits heartbeat events to notebook output every minute and at each 50-network-call milestone.
3. Normalization and checkpoint creation also emit progress heartbeat lines.

### FST-012 Backup Event Store (DONE)
From the wikidata logic:

Checkpoint snapshot retention policy:

1. Checkpoint snapshots are written under `checkpoints/snapshots/<checkpoint_stem>/`.
2. Each snapshot directory contains a copy of its manifest file (`checkpoint__...json`) so the manifest is preserved in the same lifecycle as the snapshot and included in any zip archive.
2. The 3 most recent snapshots remain unzipped directories.
3. When a new snapshot would increase unzipped snapshots above 3, the oldest unzipped snapshot is compressed into `checkpoints/snapshots/<checkpoint_stem>.zip`.
4. Zipped snapshots keep one protected "daily latest" snapshot per creation day with no hard cap.
5. Additional zipped snapshots (those that are not the protected daily latest) are capped to the 7 most recent; older ones are deleted.
6. Restore/revert must work from either an unzipped snapshot directory or a zipped snapshot archive.
7. Snapshot payload must include runtime projections, legacy raw query snapshot content, and eventstore artifacts (`chunks/`, `chunk_catalog.csv`, `eventstore_checksums.txt`).
8. Checkpoint creation history is append-only JSONL in `checkpoints/checkpoint_timeline.jsonl`.

This should also be added to the coding-principles. Every eventsourced system should backup their events like this.

Resolution note:
1. Added fernsehserien checkpoint snapshot module with Wikidata-aligned retention policy and append-only `checkpoint_timeline.jsonl`.
2. Snapshot payload now includes projections, `raw_queries/` snapshot content (when present), and eventstore artifacts (`chunks/`, `chunk_catalog.csv`, `eventstore_checksums.txt`).
3. Restore supports both unzipped snapshot directories and zipped snapshot archives.
4. Pipeline now writes a checkpoint manifest and snapshot automatically at run completion and returns checkpoint references.
5. Repository event-sourcing principles now require this backup policy for all event-sourced workflows.

### FST-013 Graceful Exit required (DONE)
This should also be added to the coding-principles. Every Notebook cell should always exit gracefully when interrupt signal is sent.

Resolution note:
1. Notebook runtime now catches `KeyboardInterrupt` and exits cleanly with an interrupted result payload instead of an unhandled traceback.
2. A terminal lifecycle event is emitted for interrupted runs (`run_finished` with `status=interrupted`) to keep observability append-only and auditable.
3. Coding principles now require graceful interrupt handling for notebook pipeline cells.

### FST-014 OS write overhead significant. (DONE)
We keep writing to the eventsore JSONL, which always seems to create a chunk_000001.jsonl.tmp file. This seems to be very time-intensive. It appears like most of our time is not spent fetching or processing data, but writing to the eventstore.

Resolution note:
1. Fernsehserien eventstore writes were moved from full-file atomic rewrite-per-event to buffered append-only JSONL writes.
2. Eventstore now flushes in batches and on read/close boundaries, removing repeated `chunk_000001.jsonl.tmp` churn in the hot path.
3. Extraction/normalization phases now explicitly close the eventstore to guarantee buffered data is flushed at phase boundaries.

### FST-015 Heartbeat not really meaningful (DONE)
See context below, we have minutes on end where all info we get is "still running".
What we need is statistics of what is being done, what kind of events were stored in the last minute, and what was the most recent event (show it and it's content explicitly). Compared this to the wikidata implementation, where it was much more insightful.

Resolution note:
1. Heartbeat events now include per-minute event throughput, recent event-type counts, and the latest event summary including payload snapshot.
2. Network milestone and normalization heartbeat lines now also include recent activity context.
3. Local fallback heartbeat output now prints the same progress/activity snapshot fields so long waits remain informative.

[heartbeat] workflow started
[heartbeat:pipeline] +0s network_calls_used=0 programs_processed=0
[heartbeat:local] +60s still running network_calls_used=0 programs_processed=0
[heartbeat:extraction] +63s network_calls_used=3 programs_processed=1
[heartbeat:local] +120s still running network_calls_used=3 programs_processed=1
[heartbeat:extraction] +126s network_calls_used=20 programs_processed=1
[heartbeat:local] +180s still running network_calls_used=20 programs_processed=1
[heartbeat:extraction] +186s network_calls_used=38 programs_processed=1
[heartbeat:extraction] network milestone reached: network_calls_used=50
[heartbeat:local] +240s still running network_calls_used=50 programs_processed=1
[heartbeat:extraction] +247s network_calls_used=57 programs_processed=1
[heartbeat:local] +300s still running network_calls_used=57 programs_processed=1
[heartbeat:extraction] +308s network_calls_used=75 programs_processed=1
[heartbeat:local] +360s still running network_calls_used=75 programs_processed=1
[heartbeat:extraction] +368s network_calls_used=92 programs_processed=1
[heartbeat:extraction] network milestone reached: network_calls_used=100
[heartbeat:local] +420s still running network_calls_used=100 programs_processed=1
[heartbeat:local] +480s still running network_calls_used=100 programs_processed=1
[heartbeat:local] +540s still running network_calls_used=100 programs_processed=1
[heartbeat:local] +600s still running network_calls_used=100 programs_processed=1
[heartbeat:local] +660s still running network_calls_used=100 programs_processed=1
[heartbeat:normalization] normalization progress: normalized_events_emitted=1172
[heartbeat:pipeline] checkpoint snapshot written: C:\workspace\git\borgnetzwerk\speaker-mining\data\20_candidate_generation\fernsehserien_de\checkpoints\snapshots\checkpoint__20260408T204013Z_f5350daf__20260408T204013Z__d49af0ad\checkpoint__20260408T204013Z_f5350daf__20260408T204013Z__d49af0ad.json
programs_processed=12 network_calls_used=100 max_network_calls=100 normalized_events_emitted=1172
checkpoint_manifest_path=C:\workspace\git\borgnetzwerk\speaker-mining\data\20_candidate_generation\fernsehserien_de\checkpoints\snapshots\checkpoint__20260408T204013Z_f5350daf__20260408T204013Z__d49af0ad\checkpoint__20260408T204013Z_f5350daf__20260408T204013Z__d49af0ad.json
Lifecycle event already emitted for this run_id; skipping duplicate run_finished
Fragment cleanup summary: {}
Observed URL fragments (1): ['Cast-Crew']

### nothing is happening (Done)
[heartbeat] workflow started
[heartbeat:pipeline] +0s network_calls_used=0 programs_processed=0 events_last_minute=0 event_types_last_minute=none last_event=<none>
[heartbeat:local] +60s still running network_calls_used=0 programs_processed=0 events_last_minute=0 event_types_last_minute=none
[heartbeat:local] +120s still running network_calls_used=0 programs_processed=0 events_last_minute=0 event_types_last_minute=none
[heartbeat:local] +180s still running network_calls_used=0 programs_processed=0 events_last_minute=0 event_types_last_minute=none
[heartbeat:local] +240s still running network_calls_used=0 programs_processed=0 events_last_minute=0 event_types_last_minute=none
[heartbeat:local] +300s still running network_calls_used=0 programs_processed=0 events_last_minute=0 event_types_last_minute=none

5 minues of nothing - what's going on here?