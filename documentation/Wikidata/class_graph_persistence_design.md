# Class Graph Persistence Design (Pre-Implementation)

Date: 2026-04-11
Status: Draft design for review before implementation
Scope: Notebook 21 Step 2.4 subclass preflight and class-resolution persistence model

## 1) Problem Statement

Current subclass preflight can still perform expensive post-pass operations after the active-class intersection is computed.

Desired behavior:
1. Keep class processing queue-driven and bounded.
2. Persist class-graph structure so we do not rebuild the same lineage repeatedly.
3. Make pruning decisions early from persisted distances and exploration coverage.
4. Keep memory bounded by operating on queue entries and compact persisted indexes.

## 2) Design Goals

1. Single class graph model where each class node has stable persisted metadata.
2. Distinguish between:
   - Distance to nearest core class (can be unknown).
   - Superclass exploration depth coverage from that node.
3. Enable early pruning rule:
   - If `known_min_distance_to_core > remaining_depth_budget`, skip path expansion.
4. Preserve event-sourcing principles:
   - Append decisions/events first.
   - Rebuild projections deterministically.
5. Avoid repeated full in-memory path fanout structures.

## 3) Non-Goals

1. No immediate code implementation in this design document.
2. No change to Stage B fallback behavior.
3. No change to public notebook execution order.
4. No long-term compatibility baggage for legacy structures when a better model exists.

## 3.1) Migration Doctrine (Priority Rule)

This design is authoritative for the new implementation direction.

Policy:
1. New design quality takes priority over preserving old structure shapes.
2. Legacy artifacts are inputs for migration and validation, not constraints on the target architecture.
3. Keep only what is useful in the new model; explicitly remove what is obsolete.

Practical rule set:
1. Ingest and rework useful legacy structure where it reduces recomputation or improves determinism.
2. Deprecate legacy projections that duplicate truth already represented in the new graph state.
3. Delete deprecated artifacts after:
   - deterministic replay parity checks pass,
   - downstream consumers are migrated,
   - contracts and workflow docs are updated.

Anti-pattern to avoid:
1. Keeping dual structures indefinitely "just in case".
2. Writing new runtime logic that depends on old and new projections simultaneously without a clear ownership boundary.

## 4) Conceptual Model

We treat classes as a directed graph with edges:
- `child --P279--> parent`

Each node persists two independent state dimensions:
1. `distance_to_core_min`:
   - Minimum known edge distance from this class to any core class.
   - Null when unknown.
2. `superclass_explored_depth_max`:
   - Maximum upward depth explored from this node in superclass traversal.
   - Monotonic non-decreasing.

This separates "what we know about core reachability" from "how much of the upward neighborhood we have already explored".

## 5) Existing Projection Roles And Minimal New State

Location: `data/20_candidate_generation/wikidata/projections/`

We should avoid introducing a new, bloated class table if the existing projections already carry the needed facts.

### 5.1 Existing projections and their roles

1. `class_hierarchy.csv`
   - Primary persisted class-graph state.
   - Already contains the structural fields we should build on: `class_id`, `class_filename`, `path_to_core_class`, `subclass_of_core_class`, `is_core_class`, `is_root_class`, `parent_count`, `parent_qids`.
   - This is the best home for any small scalar coverage state needed for pruning.

2. `class_resolution_map.csv`
   - Derived resolution evidence.
   - Best suited for the full deterministic path evidence and conflict explanation.
   - Should remain a derivation artifact, not the only runtime state store.

3. `classes.csv`
   - Class metadata and rollup projection.
   - Good for labels, descriptions, aliases, and discovered/expanded counts.
   - Should not be forced to carry traversal-control state unless that state is also useful for reporting.

4. `triples.csv`
   - Active-class evidence source.
   - Used to derive the `P31` object set for pass-2 intersection.

5. `entity_lookup_index.csv`
   - Retrieval index for entity payload storage.
   - Useful for fast node access, but not the right place for class traversal semantics.

### 5.1.1 Legacy ingestion and retirement matrix

Use this matrix during implementation:

1. `class_hierarchy.csv`
   - Action: ingest and evolve.
   - Target role: primary class-state projection.

2. `class_resolution_map.csv`
   - Action: keep as derived evidence, simplify if redundant fields appear.
   - Target role: diagnostics and deterministic explanation artifact.

3. `classes.csv`
   - Action: keep for metadata/rollups, remove traversal-control duplication if introduced.
   - Target role: human-facing class metadata projection.

4. `triples.csv`
   - Action: keep.
   - Target role: active-class evidence source.

5. `entity_lookup_index.csv`
   - Action: keep.
   - Target role: payload location index.

6. Any newly introduced projection that only mirrors event provenance
   - Action: do not add, or deprecate immediately.
   - Target role: none; provenance belongs to event logs and run summaries.

### 5.1.2 Observed synergies and relics from current artifacts/code review

The following findings are implementation-relevant and are now part of this design baseline.

1. Query inventory currently has split ownership and schema drift.
   - Observation: bootstrap/materializer path still supports legacy columns (`key`, `timestamp_utc`, `source_step`) while handler materialization writes aggregated columns (`first_seen`, `last_seen`, `count`).
   - Risk: whichever writer runs last defines contract shape.
   - Action: enforce one canonical writer and one canonical schema for `query_inventory.csv`.

2. Fallback candidates currently have dual-write behavior.
   - Observation: fallback stage writes `fallback_stage_candidates.csv` directly and also emits `candidate_matched` events consumed by `CandidatesHandler`.
   - Risk: duplicate ownership of one projection path.
   - Action: deprecate direct fallback-stage CSV writes and keep handler-derived projection as the single source of truth.

3. Some class JSON projections are duplicative.
   - Observation: both `instances_core_*.json` and top-level class JSON files (`persons.json`, `episodes.json`, etc.) are present; several are byte-identical in current artifacts.
   - Risk: redundant storage and unclear consumer contract.
   - Action: keep `instances_core_*.json` as canonical contract and deprecate duplicated top-level class JSON outputs once migration is complete.

4. CSV/parquet dual-write is currently unconditional for many projections.
   - Observation: sidecar parquet files are written and also included in checkpoint snapshots.
   - Risk: avoidable storage and snapshot churn.
   - Action: make parquet emission explicit/opt-in per artifact class, or remove it where there is no active consumer.

5. Smoke/preflight runs can overwrite operational interpretation of projection state.
   - Observation: `summary.json` can represent smoke-depth runs in the same projection root used for normal operations.
   - Risk: mixed run semantics in one artifact namespace.
   - Action: isolate run profiles (smoke vs operational) by projection namespace or run-scoped output location.

### 5.1.3 Projection ownership rule (must hold after migration)

1. Every persisted projection has exactly one writer path.
2. Every projection has one schema contract owner.
3. Any compatibility write path must have a deprecation date and removal checkpoint.
4. A projection may be derived from events by handlers or by a designated materializer function, but not both simultaneously for the same artifact.

### 5.2 Minimal additional class-graph state

If we add any new persisted class-graph state, keep it to the smallest useful scalar set:
1. `distance_to_core_min` (nullable int)
   - Optional cached lower bound / exact distance to a core class.
2. `superclass_explored_depth_max` (int, default 0)
   - Coverage marker for how far upward exploration has already gone from this node.

Those two fields are the only ones that directly support pruning.
Everything else in the earlier draft is better owned elsewhere:

- `distance_confidence`: derive from whether `distance_to_core_min` is exact, unknown, or an upper bound; do not persist it unless we later prove we need it for diagnostics.
- `last_discovered_at_utc` and `last_updated_at_utc`: live in the event log and handler run summary, not the node table.
- `source_run_id`: provenance belongs in the event stream / run summary, not per-row class state.

### 5.3 Optional edge projection

If edge provenance is needed for debugging, add a compact `class_graph_edges.csv` only if `class_resolution_map.csv` plus event history is insufficient.

Suggested columns:
1. `child_class_id`
2. `parent_class_id`
3. `source_step`
4. `source_query_hash`

Unique key: `(child_class_id, parent_class_id)`

### 5.4 Optional frontier projection

`class_graph_frontier.csv` remains optional.

Use it only if restart latency becomes a real problem.
Otherwise queue state can be reconstructed from the event store plus the compact node projection.

### 5.5 Run profile isolation requirement

To avoid artifact interpretation drift:
1. Smoke runs must not overwrite operational baseline summaries without explicit operator intent.
2. Runtime evidence must include run profile (`smoke`, `cache_only`, `operational`) and configured depth/budget.
3. Migration parity checks must compare like-for-like run profiles.

## 6) Queue-Driven Algorithm (High-Level)

### 6.1 Initialization

1. Load core classes and seed queue with core class nodes.
2. Load existing `class_hierarchy.csv` and optional `class_graph_edges.csv` (if present).
3. Build compact lookup maps only for required columns.

### 6.2 Processing Rule

For each queue item `(node, remaining_depth_budget, phase)`:
1. If interrupted, stop cleanly and persist checkpoint/progress.
2. Evaluate pruning before network/cache fetch.
3. Expand one step (cache-first), persist discovered edges/nodes, update queue.

### 6.3 Pruning Rule

If `distance_to_core_min` is known for `node` and `distance_to_core_min > remaining_depth_budget`, do not expand this path.

Rationale:
- Even full expansion within remaining budget cannot reach a core class, so it cannot change active-class eligibility outcome for this run.

### 6.4 Coverage Rule

Before expanding superclass from node `n` with needed depth `d_needed`:
- If `superclass_explored_depth_max(n) >= d_needed`, skip expansion.
- Else expand only the missing depth delta and update `superclass_explored_depth_max`.

## 7) Active-Class Resolution Path

The pass-2 contract remains and should stay simple:
1. Read `triples.csv` columns `predicate,object`.
2. Filter `predicate == P31`.
3. Build set `active_instance_classes` from `object`.
4. Read `class_hierarchy.csv` or `classes.csv` for `subclass_of_core_class=true`.
5. Compute intersection to get active core-subclass classes.

This remains O(n) over compact projections and should be fast.

## 8) Event-Sourcing Alignment

Proposed domain events (names tentative):
1. `class_edge_discovered`
2. `class_node_distance_updated`
3. `class_superclass_coverage_updated`
4. `class_queue_pruned`
5. `class_queue_enqueued`

Projection handlers then derive:
1. `class_hierarchy.csv` (canonical class-node state)
2. optional `class_graph_edges.csv` (only if provenance demand justifies it)
3. `class_resolution_map.csv`

If event volume is high, batch append by page/iteration is acceptable, while preserving deterministic replay.

## 9) Memory Boundaries

1. Never store full path fanout for all intermediate nodes in memory.
2. Store only:
   - Queue entries.
   - Node scalar state.
   - Edge dedupe keys.
3. Reconstruct detailed path evidence lazily when needed for diagnostics.

## 10) Observability Requirements

For each long-running local phase emit periodic events/prints:
1. Queue size.
2. Nodes processed.
3. Pruned paths count.
4. Coverage skips count.
5. Current RSS-friendly indicators (counts, not object dumps).

Interrupt checks must exist:
1. Between queue pops.
2. Inside long per-node neighbor iteration loops.
3. Before expensive serialization loops.

## 11) Risk Review And Precautions

The main risks to watch early are not "more fields" but hidden re-computation and hidden fanout.

1. Loops that rebuild full paths repeatedly instead of using compact scalar state.
2. Branch traversals that retain every intermediate derived path instead of a queue entry plus a coverage marker.
3. Duplicated truth across `classes.csv`, `class_hierarchy.csv`, and `class_resolution_map.csv`.
4. Provenance fields that are stored in projections even though the event log already has them.
5. Growth in projection size that turns a cheap scan into a memory-heavy read.

Precautions:
1. Keep only scalar pruning state in the persistent node projection.
2. Keep provenance in append-only logs and run summaries.
3. Treat detailed resolution evidence as derived, not as the primary control plane.
4. Add tests that enforce queue processing and bounded-memory behavior.

## 12) Migration Plan (Concept)

1. Phase A: Build target graph-state projection and replay logic without adding compatibility-only fields.
2. Phase B: Ingest useful legacy artifacts into the new projection build path for bootstrap/backfill.
3. Phase C: Switch pass-2 and branch traversal decisions fully to the new projection semantics.
4. Phase D: Mark legacy-duplicative artifacts as deprecated, migrate all consumers, and remove writes.
    - Required first-wave deprecations from current review:
       - dual query inventory writer paths,
       - direct fallback-stage candidate CSV write path,
       - duplicated top-level class JSON outputs,
       - unconditional parquet sidecars where no active consumer exists.
5. Phase E: Delete deprecated artifacts and cleanup fallback read paths.

## 13) Acceptance Criteria

1. Re-running Step 2.4 on unchanged inputs should show reduced memory growth.
2. Post-pass2 phases must emit progress at bounded intervals.
3. Interrupt during any queue phase exits within one progress interval.
4. Deterministic replay reproduces the same `class_resolution_map.csv` semantics.
5. Pass-2 active-class intersection runtime remains near linear in projection size.
6. No runtime-critical decision depends on deprecated legacy projections after cutover.
7. Deprecated artifact writes are removed, not merely ignored.
8. Each retained projection has one owner (single writer + single schema contract).
9. Smoke/profile-isolated runs cannot silently redefine operational baseline interpretation.

## 14) Open Design Questions

1. Should `distance_to_core_min` be updated only on strict proof, or allow upper-bound placeholders?
2. Is `class_graph_frontier.csv` needed, or is event replay sufficient for restart latency targets?
3. Which projection remains canonical for `subclass_of_core_class`: `classes.csv` or graph-node distance derived view?
4. What is the preferred compaction strategy for high-volume class-edge events?

## 15) Proposed Next Documentation Step

After review approval, add:
1. Event schema contract updates in `documentation/contracts.md`.
2. Workflow ownership update in `documentation/workflow.md` for the new class-graph projections.
3. Implementation task breakdown in `documentation/Wikidata/wikidata_todo_tracker.md`.

## 16) Implementation Progress Notes (2026-04-11)

This section tracks concrete rollout progress for the deprecation/synergy items above.

### 16.1 Completed in first implementation slice

1. Query inventory ownership moved to handler-driven materialization in runtime flows.
   - `materializer` no longer builds/writes `query_inventory.csv` via the legacy query-inventory materializer path.
   - `checkpoint` snapshot refresh now uses handler incremental materialization before file capture.
   - Bootstrap header for `query_inventory.csv` now matches the handler contract schema.

2. Backward compatibility for existing query inventory files was added at handler bootstrap.
   - Legacy rows carrying `timestamp_utc` are mapped to handler fields (`first_seen`/`last_seen`) during hydration.
   - Missing/invalid legacy counts are normalized to safe defaults during hydration.

3. Fallback candidates projection ownership was moved to handler derivation.
   - Direct `fallback_stage_candidates.csv` writing in fallback stage was removed.
   - Fallback stage now triggers incremental handler materialization so the candidates projection is event-derived.

4. Checkpoint snapshot capture now includes dynamic `instances_core_*.csv` projections.
   - Restores preserve dynamic core-instance CSV artifacts expected by resume/recovery flows.

### 16.2 Pending follow-up after this slice

1. Continue optional optimization work for class-graph frontier persistence only if restart latency targets require it.

### 16.3 Contract alignment completion (2026-04-11)

1. Updated `documentation/contracts.md` Wikidata v3 schema headers to match canonical runtime outputs.
2. Updated `documentation/workflow.md` with explicit single-writer projection ownership guardrails.
3. Aligned schema contract tests and verified:
   - `test_docs_contract_smoke.py::test_contracts_md_wikidata_headers_match_runtime_contract`
   - `test_contract_matrix_closure.py::test_full_materialization_schema_headers_contract`

### 16.4 Duplicate class JSON deprecation completion (2026-04-11)

1. Enforced canonical per-core JSON handoff (`instances_core_*.json`) in runtime cleanup paths.
2. Added cleanup of deprecated top-level class JSON outputs (for example `persons.json`, `episodes.json`) during bootstrap/materialization.
3. Updated tests and contracts to remove deprecated-output expectations and validate canonical JSON outputs.
4. Verified focused tests:
   - `test_bootstrap_outputs.py`
   - `test_class_path_resolution.py -k "core_projections or two_hop_boundary"`

### 16.5 Parquet sidecar policy completion (2026-04-11)

1. Added explicit parquet sidecar policy toggle in runtime common utilities.
   - `WIKIDATA_WRITE_PARQUET=0|false|no|off` disables parquet sidecars.
   - Default behavior remains enabled for compatibility.
2. Gated tabular sidecar writes in bootstrap/materialization flows.
   - When disabled, stale parquet sidecars are removed instead of retained.
3. Gated checkpoint snapshot parquet inclusion by policy.
   - Snapshot runtime file set now only includes parquet files when policy is enabled.
4. Verified focused tests:
   - `test_bootstrap_outputs.py`
   - `test_checkpoint_resume.py -k snapshot`
   - `test_contract_matrix_closure.py::test_full_materialization_schema_headers_contract`

### 16.6 Broader Wikidata regression sweep completion (2026-04-11)

1. Executed the full Wikidata process test suite after ownership/deprecation/parquet slices.
   - Result: `231 passed`.
2. Identified and fixed one regression in incremental handler orchestration.
   - Symptom: `classes.csv` could remain stale/empty when `ClassesHandler` had no pending events but node-store lineage changed.
   - Fix: `ClassesHandler` now opts out of no-pending skip optimization; orchestrator honors this handler capability.
3. Verified targeted follow-up tests for the fix and reran full suite to green.

### 16.7 Smoke/profile isolation completion (2026-04-12)

1. Added profile-aware summary writing in materialization.
   - Summary payload now includes `run_profile` and `summary_primary_updated`.
   - Every run writes profile-scoped artifacts under `projections/summary_profiles/<run_profile>/`.
2. Protected operational baseline summary semantics.
   - `summary.json` is updated only for `operational` profile by default.
   - Non-operational overwrite requires explicit operator intent via `WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE=1`.
3. Added focused tests for profile isolation behavior and explicit override path.

### 16.8 Broader Wikidata regression sweep refresh (2026-04-12)

1. Re-ran full `speakermining/test/process/wikidata` suite after profile isolation.
   - Result: `233 passed`.
2. Stabilized deterministic acceptance test fixture timestamps for reproducible cross-root byte equality checks.

### 16.9 Class graph scalar-state and pruning slice (2026-04-12)

1. Extended `class_hierarchy.csv` with persisted scalar state:
   - `distance_to_core_min`
   - `superclass_explored_depth_max`
2. Derived scalar values from resolved class paths during hierarchy materialization.
   - Handles class-node paths that start at parent class by accounting for implicit class-to-parent hop.
3. Added distance-aware pruning in subclass preflight queue traversal.
   - If known `distance_to_core_min > remaining_depth_budget`, node expansion is skipped.
   - Emitted as `pruned_by_known_distance` in subclass expansion stats.
4. Validation:
   - Updated class-path integration test to assert new hierarchy scalar fields.
   - Full Wikidata suite remains green (`233 passed`).

### 16.10 Cross-notebook run-profile operationalization completion (2026-04-12)

1. Added shared notebook orchestrator helpers for run-profile behavior:
   - run profile resolution (`operational`, `smoke`, `cache_only`),
   - non-operational summary overwrite intent resolution,
   - environment binding helper for notebook execution contexts.
2. Extended benchmark/runtime evidence run context to include:
   - `run_profile`,
   - `allow_non_operational_summary_overwrite`.
3. Added focused tests for helper resolution and evidence-context propagation.
4. Validation refresh:
   - focused orchestration/evidence tests passed,
   - full Wikidata suite passed (`239 passed`).

## 17) Affected Files And Planned Change Map (Before Next Implementation Slices)

This section is the authoritative impact map for the next rollout steps.

### 17.1 Contract alignment slice (next)

1. `documentation/contracts.md`
   - Update runtime artifact schema definitions to match canonical projection owners.
   - Remove stale or legacy header definitions where ownership has changed.

2. `documentation/workflow.md`
   - Document single-writer ownership boundaries for projections.
   - Clarify handler-owned vs materializer-owned artifact responsibilities.

3. `speakermining/test/process/wikidata/test_docs_contract_smoke.py`
   - Align expected headers with current canonical projection schemas.
   - Keep this test as documentation/runtime contract parity gate.

4. `speakermining/test/process/wikidata/test_contract_matrix_closure.py`
   - Update schema-header expectations for projections touched by ownership consolidation.
   - Preserve closure checks for stage contract artifacts.

### 17.2 Duplicate class JSON deprecation slice (planned)

1. `speakermining/src/process/candidate_generation/wikidata/materializer.py`
   - Keep `instances_core_*.json` canonical outputs.
   - Retire top-level duplicate class JSON writes once consumer migration is complete.

2. `speakermining/src/process/candidate_generation/wikidata/bootstrap.py`
   - Remove bootstrap-time creation of deprecated duplicate JSON artifacts.
   - Keep only canonical JSON projection bootstrap behavior.

3. `speakermining/src/process/candidate_generation/wikidata/checkpoint.py`
   - Ensure snapshot runtime-file capture matches canonical artifact set after deprecation.

4. `speakermining/src/process/entity_disambiguation/config.py`
   - Confirm this remains pinned to canonical `instances_core_*.json` contract paths.
   - No schema rewrite expected; only contract verification unless migration reveals gaps.

5. `speakermining/test/process/wikidata/test_bootstrap_outputs.py`
   - Remove/replace assertions for deprecated duplicate JSON bootstrap outputs.
   - Keep assertions for canonical projection files.

### 17.3 Parquet policy slice (completed)

1. `speakermining/src/process/candidate_generation/wikidata/materializer.py`
   - Gate csv+parquet dual-write by explicit policy/config per artifact class.

2. `speakermining/src/process/candidate_generation/wikidata/bootstrap.py`
   - Align empty-artifact bootstrap behavior with the same parquet policy.

3. `speakermining/src/process/candidate_generation/wikidata/checkpoint.py`
   - Align snapshot inclusion rules with retained artifact policy.

4. `documentation/contracts.md`
   - Mark persisted formats as required vs optional and identify canonical persistence format.

### 17.4 Files expected to remain unchanged in these slices

1. `speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py`
   - Already switched to handler-owned candidates projection update path.

2. `speakermining/src/process/candidate_generation/wikidata/handlers/query_inventory_handler.py`
   - Ownership and legacy bootstrap compatibility already implemented.

3. `speakermining/src/process/candidate_generation/wikidata/handlers/triple_handler.py`
   - No new changes planned in these slices.
