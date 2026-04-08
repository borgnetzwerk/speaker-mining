# Fernsehserien.de Stage-2 Candidate Generation Specification

Date: 2026-04-08
Status: v1 (decision-locked baseline)
Scope: Retrieval and extraction contract for `22_candidate_generation_fernsehserien_de.ipynb`

## 1. Purpose

This specification defines how Stage 2 (candidate generation) retrieves and structures data from fernsehserien.de with a precision-first, low-burden, event-sourced workflow.

Primary goal:

1. Retrieve episode-level source pages and parse candidate-relevant facts for broadcasting programs that have a `fernsehserien_de_id`.

Secondary goals:

1. Avoid repeated network requests for already-seen pages.
2. Keep all persistent writes replayable from append-only events.
3. Keep notebook orchestration thin and process modules authoritative.

## 2. Governing Inputs And Constraints

This specification is derived from:

1. `documentation/fernsehserien_de/00_immutable_input.md` (source-specific retrieval requirements and examples)
2. `documentation/coding-principles.md` (notebook/process/event-sourcing/file-write rules)
3. `documentation/workflow.md` (phase ownership and notebook order)
4. `documentation/contracts.md` (existing Stage-2 contract surface)
5. `documentation/notebook-observability.md` (append-only notebook runtime logging)

Normative constraints:

1. Phase ownership: write only under `data/20_candidate_generation/fernsehserien_de`.
2. Notebook default request pacing is `QUERY_DELAY_SECONDS=1.0`; machine-generated code/config changes must not lower this default. A human user may intentionally set a lower value manually in the notebook setup cell (for example during debugging).
3. Once a response is successfully stored, do not re-request the same URL unless an explicit manual override is provided.
4. Precision over recall for automated parsing.
5. Event log is canonical; other outputs are projections.
6. No backward compatibility is required for legacy code, legacy projections, or legacy users.
7. Cached files remain authoritative inputs and must be reused.
8. Legacy append-only events remain authoritative history and must be preserved in replay.

## 3. Inputs

Required table:

1. `data/00_setup/broadcasting_programs.csv`

Required columns:

1. `name`
2. `wikibase_id`
3. `wikidata_id`
4. `fernsehserien_de_id`

Row eligibility rule:

1. Process only rows with non-empty `fernsehserien_de_id`.

Local exploration fixtures (non-canonical, optional for parser iteration):

1. `data/01_input/fernsehserien_de/testing/` snapshots referenced in `00_immutable_input.md`

## 4. Retrieval Model

### 4.1 Program Root Discovery

For each eligible program row:

1. Build root URL: `https://www.fernsehserien.de/<fernsehserien_de_id>/`
2. Fetch once (cache-first policy).
3. Parse canonical episodenguide URL from root page links.

Rationale:

1. The episodenguide path segment with numeric id (for example `.../episodenguide/1/21920`) should be discovered from root HTML instead of guessed.

### 4.2 Episode Index Discovery

Primary path (required):

1. Use episodenguide pagination URLs discovered from root/guide pages.
2. Parse episode leaf links from each index page.
3. Continue page traversal until no unseen episode links remain or pagination end is explicit.

Secondary path (fallback, optional per run):

1. Use episode-page `weiter/zurueck` chain only when episodenguide parsing is incomplete or structurally broken.

Policy:

1. Prefer index traversal over chain traversal because it is more controllable and easier to validate for completeness.
2. Record which discovery path produced each episode URL.
3. Fallback chain traversal policy is `on_gap`: execute only when leaf parsing reveals previously unseen neighbors that index traversal did not discover.

### 4.3 Episode Leaf Retrieval

For each discovered episode URL:

1. Fetch once (cache-first).
2. Persist raw payload metadata as event(s).
3. Parse relevant fields only:
	1. Episode title/name
	2. Description/summary
	3. Publication/broadcast info
	4. Cast and crew section
	5. Sendetermine (airing schedule)

Noise-handling rule:

1. Ignore ads, footers, app prompts, and unrelated navigation unless required for deterministic traversal.

## 5. Event-Sourcing Contract (Fernsehserien)

Canonical runtime root:

1. `data/20_candidate_generation/fernsehserien_de/`

Canonical append-only event store:

1. `data/20_candidate_generation/fernsehserien_de/chunks/*.jsonl`

Checkpoint snapshot contract:

1. Checkpoint manifests and snapshots are written under `data/20_candidate_generation/fernsehserien_de/checkpoints/`.
2. Snapshot payload must include runtime projections, legacy raw query snapshot content (when present), and eventstore artifacts (`chunks/`, `chunk_catalog.csv`, `eventstore_checksums.txt`).
3. Restore/revert must work from both unzipped snapshot directories and zipped snapshot archives.
4. `checkpoint_timeline.jsonl` is append-only history of created checkpoints.
5. Retention policy: keep 3 newest unzipped snapshots; zip older ones; keep one protected daily-latest zip per day; cap additional zipped snapshots to 7 newest.

Required event envelope fields:

1. `sequence_num`
2. `event_version` (`v1_fsd` for this workflow)
3. `event_type`
4. `timestamp_utc`
5. `recorded_at`
6. `payload`

Required event types (minimum):

1. `eventstore_opened`
2. `program_root_discovered`
3. `episode_index_page_discovered`
4. `episode_url_discovered`
5. `network_request_skipped_cache_hit`
6. `network_request_performed`
7. `episode_description_discovered`
8. `episode_guest_discovered`
9. `episode_broadcast_discovered`
10. `episode_description_normalized`
11. `episode_guest_normalized`
12. `episode_broadcast_normalized`
13. `legacy_cache_page_imported` (optional; emitted when pre-existing cache pages are imported into event history)
14. `projection_checkpoint_written`
15. `eventstore_closed`

Idempotency rules:

1. URL identity is normalized absolute URL.
2. Replaying the same event sequence must recreate equivalent projection rows.
3. Duplicate discovered URLs are allowed in raw events but must collapse in projections by deterministic key.

## 6. Projection Artifacts (Initial Contract)

All projection files are derived from event replay and are replaceable.

Required projection files:

1. `data/20_candidate_generation/fernsehserien_de/projections/program_pages.csv`
2. `data/20_candidate_generation/fernsehserien_de/projections/episode_index_pages.csv`
3. `data/20_candidate_generation/fernsehserien_de/projections/episode_urls.csv`
4. `data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_discovered.csv`
5. `data/20_candidate_generation/fernsehserien_de/projections/episode_guests_discovered.csv`
6. `data/20_candidate_generation/fernsehserien_de/projections/episode_broadcasts_discovered.csv`
7. `data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv`
8. `data/20_candidate_generation/fernsehserien_de/projections/episode_guests_normalized.csv`
9. `data/20_candidate_generation/fernsehserien_de/projections/episode_broadcasts_normalized.csv`
10. `data/20_candidate_generation/fernsehserien_de/projections/summary.json`

Minimum schema expectations:

1. `program_pages.csv`: `program_name`, `fernsehserien_de_id`, `root_url`, `fetched_at_utc`, `source_event_sequence`
2. `episode_index_pages.csv`: `program_name`, `index_url`, `page_number`, `fetched_at_utc`, `source_event_sequence`
3. `episode_urls.csv`: `program_name`, `episode_url`, `discovery_path`, `discovered_at_utc`, `source_event_sequence`
4. `episode_metadata_discovered.csv`: raw metadata extraction rows
5. `episode_guests_discovered.csv`: raw guest extraction rows
6. `episode_broadcasts_discovered.csv`: raw broadcast extraction rows
7. `episode_metadata_normalized.csv`: normalized metadata rows
8. `episode_guests_normalized.csv`: normalized guest rows
9. `episode_broadcasts_normalized.csv`: normalized broadcast rows

Notes:

1. `confidence` and `parser_rule` are required for traceability where heuristic parsing is used.
2. `*_text` fields may contain raw normalized text in v0; later decomposition into structured subfields is allowed.
3. Projections are derived from discovered and normalized event families only.

## 7. Notebook Runtime Observability

Notebook `22_candidate_generation_fernsehserien_de.ipynb` must append runtime events under:

1. `data/logs/notebooks/notebook_22_candidate_generation_fernsehserien_de.events.jsonl`

It must follow the shared observability schema from `documentation/notebook-observability.md`, including:

1. `run_started` and `run_finished`
2. Network decisions and calls (including cache-hit skip)
3. Rate-limit and budget fields

This runtime log complements, but does not replace, the fernsehserien domain event store under `data/20_candidate_generation/fernsehserien_de/chunks/`.

## 8. Process Module Boundaries

Orchestrator notebook:

1. `speakermining/src/process/notebooks/22_candidate_generation_fernsehserien_de.ipynb`

Domain modules root:

1. `speakermining/src/process/candidate_generation/fernsehserien_de/`

Boundary rules:

1. Notebook handles sequencing, progress display, and checkpoint invocation.
2. Modules handle URL normalization, fetch policy, parsing, event append, and projection replay.
3. Guarded atomic writers are required for projection outputs.

## 9. Completion Criteria For First Implementation Slice

The first implementation slice is complete when all are true:

1. The notebook can process at least one program (for example `markus-lanz`) end-to-end.
2. Every network call is paced and logged.
3. Re-running without override does not repeat already successful requests.
4. Event replay reconstructs all required projection files.
5. Parsing captures the five required episode information groups for a representative sample.

## 10. Open Decisions (Track Before General Rollout)

Resolved in v1:

1. Raw HTML persistence: keep HTML in cache files and persist event metadata with cache path + content hash; do not embed full HTML bodies in domain events.
2. Request budget semantics: `max_network_calls = -1` means unlimited; `>= 0` is a hard cap.
3. Aggregate compatibility projections are not part of the canonical contract.
4. Fallback chain traversal runs `on_gap` only.

## 11. Non-Goals For This Initial Spec

1. Full entity disambiguation or deduplication logic (belongs to Phase 3).
2. Final link prediction outputs (belongs to Phase 4).
3. Frontend/reporting UX beyond notebook progress and event logs.

