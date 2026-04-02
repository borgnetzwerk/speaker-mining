# V3 Migration Execution Readiness (Phase 0)

**Date:** 2026-04-02  
**Status:** Ready for Phase 1 implementation kickoff  
**Scope:** Preparation for implementing and documenting v2 -> v3 JSONL event-sourcing migration

**Runtime Policy:** v2 is decommissioned and will not be executed again. Migration execution is v3-only.

---

## 1. Current v2 Code Surface (Verified)

Primary implementation area:
- `speakermining/src/process/candidate_generation/wikidata/`

Key modules and current responsibilities:
- `expansion_engine.py`
  - Orchestrates Stage A graph expansion.
  - Handles resume modes (`append`, `restart`, `revert`) via checkpoint module.
  - Writes discovered entities/properties and triples through store modules.
  - Runs checkpoint materialization after seed processing.
- `event_log.py`
  - Emits v2 query events to `raw_queries/*.json`.
  - Uses schema with `event_version = "v2"` and no sequence number.
- `checkpoint.py`
  - Writes checkpoint manifests plus full snapshot copies.
  - Snapshot includes projection files and `raw_queries/` directory.
- `node_store.py`
  - Maintains `entities.json` and `properties.json` via upsert semantics.
- `triple_store.py`
  - Appends edge events into `triple_events.json` and deduplicates into `triples.csv` through materializer.
- `materializer.py`
  - Rebuilds projection CSVs (`instances.csv`, `classes.csv`, `triples.csv`, `query_inventory.csv`, etc.).
- `query_inventory.py`
  - Rebuilds query inventory by scanning `raw_queries/*.json`.

Current artifact path contract is centralized in:
- `schemas.py`

---

## 2. Migration Alignment: Where v3 Slots In

Direct replacement points:
- Replace `event_log.py` file-per-event writer with chunked JSONL event store writer.
- Replace checkpoint snapshot resume dependency (`checkpoint.py`) with handler sequence tracking (`eventhandler.csv`).
- Introduce handler-based projection maintenance to replace ad-hoc rebuild trigger assumptions in current materialization flow.

Compatibility constraints to preserve during migration:
- Keep graph expansion semantics unchanged (eligibility, class resolution, deterministic ordering).
- Keep single-writer model for event production.
- Preserve deterministic output guarantees (byte-identical expectation from spec).

---

## 3. Baseline Test Status Before Migration

Command run:
- `.venv/Scripts/python.exe -m pytest speakermining/test/process/wikidata -q`

Result:
- 49 passed
- 1 failed

Current known failing test (pre-migration):
- `speakermining/test/process/wikidata/test_fallback_stage.py::test_fallback_initializes_request_context_with_budget`
- Failure type: `TypeError`
- Cause: test monkeypatch stub for `begin_request_context` does not accept newly passed kwargs (`event_emitter`, `event_phase`) from `fallback_matcher.py`.

Migration implication:
- This is a baseline discrepancy and should be tracked separately from v3 migration changes to avoid mixing concerns.

## 3.1 Migration Quality Policy (2026-04-02)

Validated migration stance for execution and review:
- Preserve all behavior that is already working in v2.
- Fix low-hanging issues during migration where changes are localized and low risk.
- Do not block migration on known unsolved v2 issues.
- Evaluate v3 on its own merits (event-store integrity, deterministic replay, recovery correctness, handler correctness), not only on strict v2 CSV parity.

Practical interpretation:
- v2 projection mismatches that map to already-known v2 defects are tracked as known deltas, not automatic migration failures.
- New regressions introduced by v3 in previously working behavior are migration failures and must be fixed.
- Validation reports must classify each mismatch into:
  1. preserved behavior
  2. intentional low-hanging fix
  3. known unresolved legacy issue
  4. new regression

Release threshold guidance:
- A v3 run that improves overall correctness over v2 should be accepted when new regressions are absent, even if legacy known-issue deltas remain.

---

## 4. Execution Plan for Phase 1 (Implementation Order)

1. Build event store writer (`event_writer.py`)
- Atomic JSONL append
- sequence_num management
- startup tail recovery for incomplete final line
- envelope/schema validation (`event_version = v3`)

2. Build chunk catalog tooling (`chunk_catalog.py`)
- derive/rebuild `chunk_catalog.csv`
- enforce canonical boundary-event linkage checks

3. Build handler foundation
- `event_handler.py` base class
- `handler_registry.py` for `eventhandler.csv`

4. Implement reference handlers in deterministic order
- InstancesHandler
- ClassesHandler
- TripleHandler
- QueryInventoryHandler
- CandidatesHandler (phase-dependent)

5. Add orchestrator runner
- Reads from event sequence start (`last_processed_sequence + 1`)
- Applies explicit dependency order
- Persists progress atomically

6. Add integrity and shutdown behavior
- SHA256 checksums for closed chunks
- SIGINT/SIGTERM terminate flag
- `.shutdown` file polling

7. Validate migration outcomes
- Replay test dataset
- Compare generated projections for regression detection (not as sole quality oracle)
- Verify deterministic reruns
- Produce mismatch classification report per policy categories in section 3.1

---

## 5. Action Documentation Protocol (Use During Execution)

For every migration PR/commit, document in this file under a dated section:
- Change summary (what was implemented)
- Files changed
- Contract(s) touched (schema/handler/checkpoint/chunking)
- Validation run (tests and deterministic checks)
- Result and follow-up items

Template:

```markdown
## Action Log - YYYY-MM-DD - <short title>

- Summary:
  -
- Files changed:
  -
- Contract updates:
  -
- Validation:
  - Command:
  - Result:
- Risks / follow-up:
  -
```

---

## 6. Immediate Next Steps

- Start Phase 1.1 implementation from `03_MIGRATION_SEQUENCE.md` with event writer + chunk catalog first.
- Add dedicated tests for:
  - sequence continuity across chunk boundaries
  - catalog rebuild from boundary events
  - incomplete-line recovery
  - deterministic replay byte parity
- Use `06_MIGRATION_VALIDATION_REPORT_TEMPLATE.md` for every migration validation run; mismatch classification fields are mandatory.
