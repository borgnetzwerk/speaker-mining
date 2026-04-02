# Old Baggage Backlog (v2 Legacy vs v3 Event-Sourcing)

Date: 2026-04-02  
Scope: speakermining/src/process/candidate_generation/wikidata (all .py files, excluding __pycache__)  
Coverage: 33 files

This is the strict remove / refactor / keep backlog for v3 cutover work. JSON-heavy runtime artifacts are grouped first because they are the clearest legacy smell: if a runtime artifact is plain JSON and gets rewritten wholesale, it is old baggage.

---

## Remove First

These are migration-only or no-longer-needed runtime modules. They should not remain in the v3 runtime tree once the transition is complete.

- [speakermining/src/process/candidate_generation/wikidata/migration_v3.py](speakermining/src/process/candidate_generation/wikidata/migration_v3.py)
  - Status: migration-only
  - Symbols: `count_raw_queries_files`, `iterate_raw_queries_files`, `convert_v2_to_v3_event`, `migrate_v2_to_v3`, `main`
  - Why: one-time v2->v3 migration logic; not part of runtime event-sourcing.
  - Disposition: remove or archive outside the runtime package.

- [speakermining/src/process/candidate_generation/wikidata/v2_to_v3_data_migration.py](speakermining/src/process/candidate_generation/wikidata/v2_to_v3_data_migration.py)
  - Status: migration-only
  - Symbols: `run_v2_to_v3_data_migration`, `main`
  - Why: one-time wrapper for the completed data migration path.
  - Disposition: remove or archive outside the runtime package.

- [speakermining/src/process/candidate_generation/wikidata/bootstrap.py](speakermining/src/process/candidate_generation/wikidata/bootstrap.py)
  - Status: transitional artifact contract
  - Artifacts: `entities.json`, `properties.json`, `triple_events.json`, `raw_queries`
  - Why: bootstrap still initializes legacy mutable artifacts that are not canonical v3 persistence.
  - Disposition: keep only until the projection contract is fully replaced.

- [speakermining/src/process/candidate_generation/wikidata/checkpoint.py](speakermining/src/process/candidate_generation/wikidata/checkpoint.py)
  - Status: transitional artifact contract
  - Artifacts: raw_queries snapshot handling
  - Why: checkpointing still knows about legacy raw-query snapshots.
  - Disposition: remove from runtime once handler-based checkpoints are authoritative.

- [speakermining/src/process/candidate_generation/wikidata/schemas.py](speakermining/src/process/candidate_generation/wikidata/schemas.py)
  - Status: transitional artifact contract
  - Artifacts: `raw_queries_dir`, `entities_json`, `properties_json`, `triple_events_json`
  - Why: schema still exposes old mutable artifact paths.
  - Disposition: keep for now, but treat as legacy contract surface.

---

## Refactor Sequence

These commits are ordered by impact and dependency. The first two are runtime hot-path fixes. The third finishes the cutover from mutable-store materialization to handler-driven projections.

### Commit 1 - Eliminate hot-path history scans and streaming gaps

Goal: stop scanning the entire event history just to answer cache and orchestration questions.

- [speakermining/src/process/candidate_generation/wikidata/cache.py](speakermining/src/process/candidate_generation/wikidata/cache.py)
  - Symbols: `_latest_cached_record`
  - Task: replace `reversed(list(iter_query_events(...)))` with an indexed or handler-backed latest-record lookup.
  - Category: `B1`, `B6`
  - Impact: P0

- [speakermining/src/process/candidate_generation/wikidata/event_log.py](speakermining/src/process/candidate_generation/wikidata/event_log.py)
  - Symbols: `iter_all_events`, `iter_query_events`, `write_query_event`, `write_candidate_matched_event`
  - Task: make event reads stream or batch, and stop creating a fresh writer context per append.
  - Category: `B1`, `B2`
  - Impact: P0

- [speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py](speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py)
  - Symbols: `run_handlers`
  - Task: remove `all_events = list(iter_all_events(...))`; process events in streaming batches.
  - Category: `B7`, `B1`
  - Impact: P1

- [speakermining/src/process/candidate_generation/wikidata/entity.py](speakermining/src/process/candidate_generation/wikidata/entity.py)
  - Symbols: `get_or_fetch_entity`, `get_or_fetch_property`, `get_or_fetch_inlinks`, `get_or_build_outlinks`
  - Task: inherit the cache lookup fix and ensure these callers do not trigger history scans indirectly.
  - Category: `B1`, `B2` (indirect)
  - Impact: P1

### Commit 2 - Remove mutable JSON store rewrites from the hot loop

Goal: stop rewriting plain JSON artifacts on every discovered node, triple, or integrity pass.

- [speakermining/src/process/candidate_generation/wikidata/node_store.py](speakermining/src/process/candidate_generation/wikidata/node_store.py)
  - Symbols: `upsert_discovered_item`, `upsert_expanded_item`, `upsert_discovered_property`, `get_item`, `iter_items`, `iter_properties`
  - Task: replace full-file JSON read/modify/write behavior with event-backed or buffered projection state.
  - Category: `B3`, `B8`
  - Impact: P0

- [speakermining/src/process/candidate_generation/wikidata/triple_store.py](speakermining/src/process/candidate_generation/wikidata/triple_store.py)
  - Symbols: `record_item_edges`, `iter_unique_triples`, `has_direct_link_to_any_seed`
  - Task: remove `triple_events.json` as a canonical runtime artifact and move triple accumulation to handler-managed projections.
  - Category: `B3`, `B8`
  - Impact: P0

- [speakermining/src/process/candidate_generation/wikidata/expansion_engine.py](speakermining/src/process/candidate_generation/wikidata/expansion_engine.py)
  - Symbols: `run_seed_expansion`, `run_graph_expansion_stage`, `_resolve_targets_against_discovered_items`, `_write_graph_stage_handoff`
  - Task: remove per-node JSON store writes from the BFS loop and stop using full checkpoint materialization after each seed.
  - Category: `B3`, `B4`
  - Impact: P0

- [speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py](speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py)
  - Symbols: `run_fallback_string_matching_stage`, `merge_stage_candidates`, `enqueue_eligible_fallback_qids`
  - Task: stop rebuilding fallback indexes from JSON-backed item scans and move output writes into handler-driven projections.
  - Category: `B3`, `B4`
  - Impact: P1

- [speakermining/src/process/candidate_generation/wikidata/node_integrity.py](speakermining/src/process/candidate_generation/wikidata/node_integrity.py)
  - Symbols: repeated `iter_items`, `get_item`, `materialize_final`
  - Task: stop integrity passes from walking mutable JSON stores and triggering a full final materialization.
  - Category: `B3`, `B4`, `B8`
  - Impact: P1

- [speakermining/src/process/candidate_generation/wikidata/handlers/instances_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/instances_handler.py)
  - Symbols: `InstancesHandler.materialize`
  - Task: remove the `entities.json` sidecar as part of the projection contract after the new handler path is stable.
  - Category: `B6`, `B8`
  - Impact: P2

### Commit 3 - Finish incremental projection cutover

Goal: make projections handler-driven and eliminate full rebuilds from the default runtime path.

- [speakermining/src/process/candidate_generation/wikidata/materializer.py](speakermining/src/process/candidate_generation/wikidata/materializer.py)
  - Symbols: `._latest_entity_cache_docs`, `_build_instances_df`, `_build_classes_df`, `_build_properties_df`, `_build_triples_df`, `_materialize`, `materialize_checkpoint`
  - Task: keep only final or explicit rebuild support; remove per-seed full projection rebuild from the normal runtime path.
  - Category: `B1`, `B4`, `B8`
  - Impact: P0

- [speakermining/src/process/candidate_generation/wikidata/query_inventory.py](speakermining/src/process/candidate_generation/wikidata/query_inventory.py)
  - Symbols: `rebuild_query_inventory`
  - Task: replace full-history rebuild with the incremental `QueryInventoryHandler` path.
  - Category: `B1`, `B4`, `B8`
  - Impact: P1

- [speakermining/src/process/candidate_generation/wikidata/event_writer.py](speakermining/src/process/candidate_generation/wikidata/event_writer.py)
  - Symbols: `EventStore.append_event`, chunk rotation support
  - Task: keep the writer, but expose it as a long-lived run context so append operations are O(1) instead of reconstructed per call.
  - Category: no direct baggage, but required to finish the cutover
  - Impact: P2

- [speakermining/src/process/candidate_generation/wikidata/bootstrap.py](speakermining/src/process/candidate_generation/wikidata/bootstrap.py)
  - Symbols: `ensure_output_bootstrap`, `initialize_bootstrap_files`
  - Task: remove any bootstrap dependency on plain JSON projections once the handler pipeline is authoritative.
  - Category: `B6`, `B8`
  - Impact: P2

- [speakermining/src/process/candidate_generation/wikidata/checkpoint.py](speakermining/src/process/candidate_generation/wikidata/checkpoint.py)
  - Symbols: `write_checkpoint_snapshot`, `restore_checkpoint_snapshot`
  - Task: remove snapshot semantics tied to legacy raw-query state after handler progress becomes the only resume source.
  - Category: `B6`, `B8`
  - Impact: P2

- [speakermining/src/process/candidate_generation/wikidata/schemas.py](speakermining/src/process/candidate_generation/wikidata/schemas.py)
  - Symbols: `build_artifact_paths`
  - Task: narrow the artifact contract so plain JSON projections are no longer presented as runtime defaults.
  - Category: `B6`, `B8`
  - Impact: P2

---

## Keep

These files are already aligned with the v3 direction or are useful infrastructure with no current baggage signal.

- [speakermining/src/process/candidate_generation/wikidata/candidate_targets.py](speakermining/src/process/candidate_generation/wikidata/candidate_targets.py)
  - Status: aligned
  - Symbols: `build_targets_from_phase2_lookup`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/checksums.py](speakermining/src/process/candidate_generation/wikidata/checksums.py)
  - Status: aligned
  - Symbols: checksum helpers for chunk validation
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py](speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py)
  - Status: aligned
  - Symbols: `summarize_chunk`, `rebuild_chunk_catalog`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/class_resolver.py](speakermining/src/process/candidate_generation/wikidata/class_resolver.py)
  - Status: aligned
  - Symbols: `resolve_class_path`, `compute_class_rollups`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/common.py](speakermining/src/process/candidate_generation/wikidata/common.py)
  - Status: aligned
  - Symbols: text normalization, qid helpers, language helpers
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/contact_loader.py](speakermining/src/process/candidate_generation/wikidata/contact_loader.py)
  - Status: aligned
  - Symbols: contact and user-agent helpers
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/event_handler.py](speakermining/src/process/candidate_generation/wikidata/event_handler.py)
  - Status: aligned
  - Symbols: `EventHandler`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/graceful_shutdown.py](speakermining/src/process/candidate_generation/wikidata/graceful_shutdown.py)
  - Status: aligned
  - Symbols: shutdown helpers
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handler_registry.py](speakermining/src/process/candidate_generation/wikidata/handler_registry.py)
  - Status: aligned
  - Symbols: `HandlerRegistry`, progress tracking
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/inlinks.py](speakermining/src/process/candidate_generation/wikidata/inlinks.py)
  - Status: aligned
  - Symbols: `build_inlinks_query`, `parse_inlinks_results`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/outlinks.py](speakermining/src/process/candidate_generation/wikidata/outlinks.py)
  - Status: aligned
  - Symbols: `extract_outlinks`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/candidates_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/candidates_handler.py)
  - Status: aligned
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py)
  - Status: aligned
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py)
  - Status: aligned
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py)
  - Status: aligned
  - Disposition: keep.

---

## Keep

These files are already aligned with the v3 direction or are useful infrastructure with no current baggage signal.

- [speakermining/src/process/candidate_generation/wikidata/candidate_targets.py](speakermining/src/process/candidate_generation/wikidata/candidate_targets.py)
  - Status: aligned
  - Symbols: `build_targets_from_phase2_lookup`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/checksums.py](speakermining/src/process/candidate_generation/wikidata/checksums.py)
  - Status: aligned
  - Symbols: checksum helpers for chunk validation
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py](speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py)
  - Status: aligned
  - Symbols: `summarize_chunk`, `rebuild_chunk_catalog`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/class_resolver.py](speakermining/src/process/candidate_generation/wikidata/class_resolver.py)
  - Status: aligned
  - Symbols: `resolve_class_path`, `compute_class_rollups`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/common.py](speakermining/src/process/candidate_generation/wikidata/common.py)
  - Status: aligned
  - Symbols: text normalization, qid helpers, language helpers
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/contact_loader.py](speakermining/src/process/candidate_generation/wikidata/contact_loader.py)
  - Status: aligned
  - Symbols: contact and user-agent helpers
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/event_handler.py](speakermining/src/process/candidate_generation/wikidata/event_handler.py)
  - Status: aligned
  - Symbols: `EventHandler`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/graceful_shutdown.py](speakermining/src/process/candidate_generation/wikidata/graceful_shutdown.py)
  - Status: aligned
  - Symbols: shutdown helpers
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handler_registry.py](speakermining/src/process/candidate_generation/wikidata/handler_registry.py)
  - Status: aligned
  - Symbols: `HandlerRegistry`, progress tracking
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/inlinks.py](speakermining/src/process/candidate_generation/wikidata/inlinks.py)
  - Status: aligned
  - Symbols: `build_inlinks_query`, `parse_inlinks_results`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/outlinks.py](speakermining/src/process/candidate_generation/wikidata/outlinks.py)
  - Status: aligned
  - Symbols: `extract_outlinks`
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/candidates_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/candidates_handler.py)
  - Status: aligned
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py)
  - Status: aligned
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py)
  - Status: aligned
  - Disposition: keep.

- [speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py](speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py)
  - Status: aligned
  - Disposition: keep.

---

## Runtime Hotlist Summary

The highest-impact drag items, in order, are:

1. [speakermining/src/process/candidate_generation/wikidata/node_store.py](speakermining/src/process/candidate_generation/wikidata/node_store.py)
2. [speakermining/src/process/candidate_generation/wikidata/triple_store.py](speakermining/src/process/candidate_generation/wikidata/triple_store.py)
3. [speakermining/src/process/candidate_generation/wikidata/materializer.py](speakermining/src/process/candidate_generation/wikidata/materializer.py)
4. [speakermining/src/process/candidate_generation/wikidata/cache.py](speakermining/src/process/candidate_generation/wikidata/cache.py)
5. [speakermining/src/process/candidate_generation/wikidata/event_log.py](speakermining/src/process/candidate_generation/wikidata/event_log.py)
6. [speakermining/src/process/candidate_generation/wikidata/expansion_engine.py](speakermining/src/process/candidate_generation/wikidata/expansion_engine.py)
7. [speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py](speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py)
8. [speakermining/src/process/candidate_generation/wikidata/query_inventory.py](speakermining/src/process/candidate_generation/wikidata/query_inventory.py)
9. [speakermining/src/process/candidate_generation/wikidata/node_integrity.py](speakermining/src/process/candidate_generation/wikidata/node_integrity.py)
10. [speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py](speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py)

---

## Artifact Rules for v3

- JSON files are old baggage unless they are strictly configuration, documentation examples, or transient migration inputs.
- JSON outputs in the runtime path are not acceptable as canonical persistence if they are rewritten wholesale.
- JSONL is acceptable for append-only event streams.
- CSV and pandas-derived projections are acceptable when they are incremental or handler-driven.

---

## Net Assessment

- Remove: 2 files
- Refactor: 10 files
- Keep: 13 files
- Transitional contracts still under watch: 8 files

Total files covered: 33

This backlog is now ordered by impact and is suitable as the implementation queue for the next refactor wave.
