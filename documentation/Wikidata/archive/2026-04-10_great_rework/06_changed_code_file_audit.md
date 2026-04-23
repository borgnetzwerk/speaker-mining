# Changed Code File Audit (Pre-Commit)

Date: 2026-04-10
Scope: all changed code files in this commit (`.py` + notebook `.ipynb`).

## Audit Outcome

- Reviewed all changed code files line-by-line in diff context.
- Ran focused changed-file test sweep:
  - `pytest .../test_checksums.py .../test_runtime_evidence.py -q`
  - Result: `105 passed`.
- Static editor problem scan: no diagnostics reported.

## Issues Found During Audit (and fixed)

1. `ArtifactPaths` schema rename regression:
   - Symptom: changed-node-integrity tests failed due to missing `entities_json`/`properties_json`/`triples_events_json` attributes.
   - Fix: added backward-compatible alias properties in `schemas.py` mapped to new projection-backed paths.
2. Runtime evidence re-entry counter wiring mismatch:
   - Symptom: `build_runtime_evidence_inputs(...)` only read `expanded_qids` list, while re-entry summary currently returns integer `expanded`.
   - Fix: made `notebook_orchestrator.py` accept both contracts (`expanded` and `expanded_qids`).

## Per-File Change Summary

### Source Files

- `speakermining/src/process/candidate_generation/wikidata/cache.py` - Delegates local atomic writers to shared `io_guardrails` helpers.
- `speakermining/src/process/candidate_generation/wikidata/checkpoint.py` - Snapshot manifest handling fixed for pre-created checkpoint directories.
- `speakermining/src/process/candidate_generation/wikidata/checksums.py` - Checksum registry writes now use guarded atomic text writer.
- `speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py` - Catalog write path switched to shared guarded writer.
- `speakermining/src/process/candidate_generation/wikidata/class_resolver.py` - Added recovered-lineage loader, policy modes, and recovered-first resolution path.
- `speakermining/src/process/candidate_generation/wikidata/entity.py` - Added class-scoped SPARQL label search (+ ranked exact/prefix fallback).
- `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py` - Added lineage policy/evidence loading and phase-contract lifecycle payloads.
- `speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py` - Added class-scoped fallback mode/counters and phase-contract payloads.
- `speakermining/src/process/candidate_generation/wikidata/handler_benchmark.py` - New benchmark module for incremental vs full-rebuild runs (+ parity artifacts).
- `speakermining/src/process/candidate_generation/wikidata/handler_registry.py` - Registry persistence moved to guarded CSV helper; added snapshot/prune helpers.
- `speakermining/src/process/candidate_generation/wikidata/handlers/candidates_handler.py` - Added projection bootstrap hydration.
- `speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py` - Added node-store-based bootstrap helper for class handler state.
- `speakermining/src/process/candidate_generation/wikidata/handlers/instances_handler.py` - Added projection bootstrap hydration.
- `speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py` - Added materialization modes, run summaries, bootstrap path, and stale-handler pruning.
- `speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py` - Added projection bootstrap hydration.
- `speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py` - Added projection bootstrap hydration.
- `speakermining/src/process/candidate_generation/wikidata/heartbeat_monitor.py` - New reusable notebook heartbeat monitor with lifecycle event logging.
- `speakermining/src/process/candidate_generation/wikidata/legacy_artifact_inventory.py` - New retired-artifact consumer inventory generator (CSV/JSON outputs).
- `speakermining/src/process/candidate_generation/wikidata/materializer.py` - Added snapshot parity comparator and recovered-lineage aware materialization telemetry.
- `speakermining/src/process/candidate_generation/wikidata/mention_type_config.py` - New fallback mention-type normalization/snapshot guard module.
- `speakermining/src/process/candidate_generation/wikidata/node_integrity.py` - Added lineage policy support and phase-contract lifecycle payload coverage.
- `speakermining/src/process/candidate_generation/wikidata/node_store.py` - Cutover to projection-backed entity/property stores with recovery compatibility update.
- `speakermining/src/process/candidate_generation/wikidata/notebook_orchestrator.py` - New shared notebook orchestration helpers (budgets, context, runtime evidence payload).
- `speakermining/src/process/candidate_generation/wikidata/phase_contracts.py` - New shared phase contract/outcome payload helpers.
- `speakermining/src/process/candidate_generation/wikidata/runtime_evidence.py` - New runtime evidence bundle writer (JSON + CSV).
- `speakermining/src/process/candidate_generation/wikidata/schemas.py` - Artifact path schema switched to projection-backed JSONL store names (+ compatibility aliases).
- `speakermining/src/process/candidate_generation/wikidata/triple_store.py` - Triple runtime storage moved to projection-first `triples.csv` semantics.
- `speakermining/src/process/candidate_generation/wikidata/v2_to_v3_data_migration.py` - Legacy migration entrypoint disabled under clean-slate policy.
- `speakermining/src/process/io_guardrails.py` - Added no-op rewrite skips and guarded parquet atomic writer.
- `speakermining/src/process/notebook_event_log.py` - Added thread-safe recent-activity snapshot tracking for heartbeat summaries.
- `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb` - Notebook steps refactored to shared helpers + added Step 11 benchmark and Step 12 runtime evidence.

### Test Files

- `speakermining/test/process/wikidata/test_checksums.py` - Added no-op rewrite regression test for checksum registry.
- `speakermining/test/process/wikidata/test_class_path_resolution.py` - Added lineage policy and snapshot parity coverage tests.
- `speakermining/test/process/wikidata/test_entity_cache_unwrap.py` - Added class-scoped search cache/network/ranked fallback tests.
- `speakermining/test/process/wikidata/test_event_writer_v3.py` - Added chunk-catalog no-op rewrite regression test.
- `speakermining/test/process/wikidata/test_fallback_stage.py` - Added class-scoped preference and generic fallback behavior tests.
- `speakermining/test/process/wikidata/test_guarded_file_writes.py` - Extended guarded writer tests for retry/recovery and no-op rewrites.
- `speakermining/test/process/wikidata/test_handler_benchmark.py` - New benchmark artifact, replay delta, and parity report tests.
- `speakermining/test/process/wikidata/test_handler_registry.py` - Added registry snapshot ordering and stale-prune tests.
- `speakermining/test/process/wikidata/test_mention_type_config.py` - New mention-type config/snapshot guard tests.
- `speakermining/test/process/wikidata/test_network_guardrails.py` - Added cache-layer no-op rewrite behavior tests.
- `speakermining/test/process/wikidata/test_node_integrity.py` - Added timeout telemetry/stress coverage and updated integrity scenarios.
- `speakermining/test/process/wikidata/test_notebook_event_log_runtime.py` - Added recent-activity snapshot test coverage.
- `speakermining/test/process/wikidata/test_orchestrator_handlers.py` - Added run-summary, prune, mode, and bootstrap behavior tests.
- `speakermining/test/process/wikidata/test_recovered_class_hierarchy_loader.py` - New recovered-lineage CSV loader normalization tests.
- `speakermining/test/process/wikidata/test_runtime_evidence.py` - New runtime evidence JSON/CSV artifact tests.

## Risk Resolution

1. Full wikidata suite executed before commit:
    - Command: `pytest speakermining/test/process/wikidata -q`
    - Final result: `224 passed`.
    - During this run, legacy-surface regressions were fixed:
       - checkpoint snapshot copytree destination collision hardening in `checkpoint.py`
       - compatibility alias correction for retired triple-events path in `schemas.py`
       - untouched buffering tests updated for projection-backed filenames/writer API in `test_store_buffering.py`

2. End-to-end Notebook 21 closeout evidence confirmed:
    - Notebook code cells through Step 12 executed successfully in order.
    - Evidence artifacts produced and refreshed:
       - `data/20_candidate_generation/wikidata/benchmarks/handler_materialization_summary_latest.json`
       - `data/20_candidate_generation/wikidata/evidence/notebook21_runtime_evidence_latest.json`
    - Latest runtime evidence includes explicit `phase_outcomes` entries for Steps 6.5, 8, 9, and 11, confirming execution-order wiring and closeout payload assembly.
