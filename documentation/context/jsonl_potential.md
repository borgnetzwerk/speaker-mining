# JSONL Potential Assessment (JSON/CSV Migration)

Date: 2026-04-01
Scope: repository-wide persistence patterns in `speakermining/src/process/**` and active data artifacts.

## Goal

Assess potential and risk of replacing current JSON/CSV persistence solutions with JSONL,
with preliminary recommendations per artifact family.

## Method

1. Code inventory of read/write callsites in process modules.
2. Artifact footprint checks in `data/**`.
3. Pattern grouping by persistence semantics:
	- append-only events
	- mutable state snapshots
	- tabular data contracts
	- checkpoints and archival snapshots
	- diagnostics and notebook observability

## Evidence Snapshot

Repository file counts (2026-04-01):

1. `csv=335`
2. `json=16061`
3. `jsonl=1`

Data-phase concentration:

1. `data/20_candidate_generation`: `csv=273`, `json=16061`, `jsonl=0`
2. `data/logs`: `jsonl=1`

Wikidata raw query volume:

1. `data/20_candidate_generation/wikidata/raw_queries`: `3755` JSON files
2. total size ~`180,947,336` bytes (~`181 MB`)
3. average file size ~`48,188` bytes

Checkpoint usage:

1. `checkpoint__*.json` manifests: `18`
2. snapshot directories: `18`

## Current Format Patterns

### A) Tabular phase contracts (CSV)

Representative modules:

1. `speakermining/src/process/mention_detection/*.py`
2. `speakermining/src/process/candidate_generation/persistence.py`
3. `speakermining/src/process/entity_disambiguation/selection.py`
4. `speakermining/src/process/entity_deduplication/selection.py`
5. `speakermining/src/process/link_prediction/inference.py`

Semantics: overwrite/replace full table snapshots, strong column contracts, manual review-friendly.

### B) Mutable graph/state stores (JSON objects/lists)

Representative modules:

1. `.../wikidata/node_store.py` (`entities.json`, `properties.json`)
2. `.../wikidata/triple_store.py` (`triple_events.json`)
3. `.../wikidata/materializer.py` (`summary.json`)

Semantics: current code reads full object/list, mutates, rewrites canonical file.

### C) Raw query event archive (many JSON files)

Representative modules:

1. `.../wikidata/event_log.py`
2. `.../wikidata/cache.py`

Semantics: append-only by file creation (`one event per file`), immutable historical records.

### D) Checkpoint manifests and snapshots

Representative module:

1. `.../wikidata/checkpoint.py`

Semantics: append-only manifest files + full snapshot copy directories.

### E) Notebook runtime observability (JSONL)

Representative module:

1. `speakermining/src/process/notebook_event_log.py`

Semantics: append-only line events, corruption repair path, run-spanning history.

## JSONL Migration Analysis By Case

### Case 1: Phase contract tables currently in CSV

Potential:

1. JSONL could preserve richer per-row metadata and nested fields.

Risks:

1. Breaks existing contracts in `documentation/contracts.md` and downstream notebook/manual workflows.
2. Loses easy spreadsheet/open-refine interoperability currently used by project workflows.
3. Adds conversion overhead for every consumer expecting stable columns.

Preliminary recommendation:

1. Keep CSV as canonical for phase contract outputs.
2. Only add JSONL companions when row-level nested provenance is required and cannot be represented in columns.

Status: do not migrate.

### Case 2: Mutable entity/property stores (`entities.json`, `properties.json`)

Potential:

1. JSONL could represent change-log style updates (one upsert event per line).
2. Better append ergonomics compared with whole-file rewrite.

Risks:

1. Current read paths require latest merged state; JSONL would require replay/index layer.
2. Replay cost grows with run history unless compaction/checkpointing is added.
3. Existing recovery merge logic is built around full JSON snapshots.

Preliminary recommendation:

1. Keep canonical state snapshot JSON files for runtime reads.
2. Optionally add a separate JSONL change journal as secondary audit stream.

Status: needs additional architecture work before any migration.

### Case 3: `triple_events.json` (list of edge events)

Potential:

1. Strong candidate for JSONL because data is event-like append stream.
2. Could reduce repeated full-list rewrite during edge recording.

Risks:

1. `iter_unique_triples` currently assumes full list in memory from one JSON file.
2. Dedup and read helpers would need streaming parser/refactor.

Preliminary recommendation:

1. Medium-high migration potential.
2. Convert only with paired reader refactor and benchmark.

Status: candidate for pilot after raw query decision.

### Case 4: Raw query events (`raw_queries/*.json`, one-file-per-event)

Potential:

1. Very high: append-only semantics match JSONL naturally.
2. Could reduce file-count overhead (currently thousands of files).
3. Easier chronological scanning and aggregation for diagnostics.

Risks:

1. Single hot append file increases lock contention risk on Windows.
2. Corruption risk from abrupt interruption requires robust repair/quarantine (already implemented for notebook JSONL logger but not raw queries).
3. Existing code relies on filename tokens for fast lookup (`materializer` and cache scans); JSONL migration needs index strategy.

Preliminary recommendation:

1. Keep runtime raw query writes as current per-file JSON for now (safer under lock contention).
2. Evaluate hybrid design:
	- runtime writes remain one-file-per-event
	- post-run compaction job builds append-only JSONL archive and optional index
3. If direct JSONL runtime writes are tested, require rotation (for example daily/per-run files), corruption repair, and index sidecar before default adoption.

Status: high potential, needs controlled pilot.

### Case 5: Checkpoint manifests (`checkpoint__*.json`)

Potential:

1. Could become one append-only `checkpoints.jsonl` timeline.

Risks:

1. Current manifest-per-file aligns naturally with snapshot directory naming and restore mechanics.
2. Operationally simple and low volume (18 manifests observed); migration benefit is limited.

Preliminary recommendation:

1. Keep current per-manifest JSON files.

Status: no migration recommended.

### Case 6: Summary/config JSON (`summary.json`, `.contact-info.json`)

Potential:

1. Minimal; these are object snapshots, not event streams.

Risks:

1. JSONL is awkward for single-object configuration/state snapshots.

Preliminary recommendation:

1. Keep JSON object files.

Status: no migration recommended.

### Case 7: Notebook event logs (`*.events.jsonl`)

Potential:

1. Already implemented and well aligned with append-only network observability requirements.

Risks:

1. Corruption and external edits; mitigated by startup repair/quarantine and `log_repaired` event.

Preliminary recommendation:

1. Keep JSONL as canonical for notebook runtime events.
2. Standardize same envelope for additional notebooks.

Status: continue rollout.

### Case 8: Notebook diagnostics snapshots (CSV/JSON side outputs)

Potential:

1. Optional JSONL for event-style diagnostics where records are inherently appendable.

Risks:

1. Existing diagnostics are frequently table snapshots intended for immediate review/export.

Preliminary recommendation:

1. Keep CSV/JSON for snapshot diagnostics.
2. Use JSONL only when diagnostics are event logs rather than point-in-time tables.

Status: selective only.

## Cross-Cutting Risks If JSONL Adoption Expands

1. Lock contention on shared append file during long runs (Windows-specific sensitivity).
2. Need for file rotation and retention policy to avoid unbounded log growth.
3. Need for reader/index utilities to preserve fast lookups currently achieved via filenames.
4. Need for corruption-tolerant startup checks on every JSONL writer (repair/quarantine).
5. Need for explicit schema versioning and backward-compatibility rules across notebooks/modules.

## Cross-Cutting Benefits If Applied Selectively

1. True append-only history with lower metadata/file-system overhead for high-event streams.
2. Easier longitudinal analytics and cross-notebook comparisons.
3. Simpler ingestion by stream processors and tooling expecting one-record-per-line logs.

## Preliminary Decision Matrix

1. Keep as-is (CSV): phase contracts and manual gate files.
2. Keep as-is (JSON object/list): config/state snapshot stores (`summary.json`, `.contact-info.json`, checkpoint manifests, `entities.json`/`properties.json` as canonical state).
3. Keep and expand (JSONL): notebook observability events.
4. Pilot candidate (high potential): raw query events via hybrid compaction-first approach.
5. Pilot candidate (medium potential): triple events (`triple_events`) with reader refactor.

## Clarifications Needed Before Any Migration Pilot

1. Is runtime write contention or analytical ergonomics the primary optimization target?
2. For raw queries, is strict per-event immutability with filename provenance required for audits?
3. What maximum acceptable recovery complexity is allowed during notebook runtime?
4. Which downstream tools depend on current file-per-event naming conventions?

## Recommended Next Step

1. Run a constrained pilot for raw query JSONL compaction (not runtime replacement):
	- keep existing runtime writes,
	- produce per-run compacted JSONL + query index,
	- compare lookup speed, storage overhead, and operational reliability.
