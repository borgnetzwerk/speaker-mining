# Wikidata Design Improvements (2026-04-09)

Status: Proposed (implementation-ready)
Owner: Candidate generation / Wikidata pipeline
Scope: Notebook 21 Stage A + Node Integrity + projections

## 1. Problem Statement

Current state has two practical gaps:

1. There is no single per-QID artifact that answers "everything we know about QID X" without replaying or scanning multiple large files.
2. Stage A expansion can miss important neighbors due to strict direct-P31 matching and neighbor truncation behavior.

Observed example: Q130638552 was discovered and later expanded, but not reliably in Stage A, despite a direct link to seed-adjacent graph context.

## 2. Goals

1. Introduce a canonical per-QID dossier projection for fast lookup and debugging.
2. Make Stage A expansion eligibility subclass-aware (not only direct P31 core match).
3. Replace lossy neighbor truncation with deterministic, policy-aware prioritization.
4. Keep event-store replay optional for diagnostics, not required for day-to-day lookup.
5. Preserve deterministic output behavior and checkpoint compatibility.

## 3. Non-Goals

1. Replacing the event-store architecture.
2. Rewriting notebook orchestration flow.
3. Full schema redesign of all existing projections.

## 4. Deliverables

## 4.1 New Projection: entity_dossiers.jsonl

Path:
- data/20_candidate_generation/wikidata/projections/entity_dossiers.jsonl

Companion index:
- data/20_candidate_generation/wikidata/projections/entity_dossiers_index.csv

Each dossier line is one QID and contains:

- qid
- label_de
- label_en
- description_de
- description_en
- aliases_de
- aliases_en
- class_info:
  - direct_p31
  - direct_p279
  - resolved_core_class_id
  - path_to_core_class
  - subclass_of_core_class
  - is_class_node
- lifecycle:
  - discovered_at_utc
  - expanded_at_utc
  - discovered_at_utc_history
  - expanded_at_utc_history
- graph_summary:
  - outgoing_edge_count
  - incoming_edge_count
  - outgoing_property_counts
  - incoming_property_counts
  - neighbors_top_k (deterministic sample for quick inspection)
- graph_edges:
  - outgoing_edges (full list of pid, to_qid, discovered_at_utc, source_query_file)
  - incoming_edges (full list of from_qid, pid, discovered_at_utc, source_query_file)
- provenance:
  - query_inventory_rows (normalized query metadata rows touching this qid)
  - sources_present (entity_fetch, inlinks_fetch, outlinks_build, etc.)
- diagnostics:
  - expansion_eligibility_current
  - expansion_eligibility_reason
  - has_direct_seed_link

Design choice:
- This is an aggregated projection, rebuilt from compact projections (entities + triples + query_inventory + class_hierarchy), not by replaying entire chunk eventstore on every run.

## 4.2 Stage A Expansion Eligibility Upgrade

Current Stage A logic requires direct P31 core match.

New logic:
- keep: direct seed link requirement
- keep: class-node exclusion as-is
- change: p31_core_match becomes subclass-aware via class_hierarchy lookup

Eligibility predicate:
- eligible = has_direct_seed_link AND (direct_or_subclass_core_match) AND (not is_class_node)

Where direct_or_subclass_core_match is true if:
- direct P31 intersects core classes, or
- any P31 class is marked subclass_of_core_class=true in class_hierarchy projection

Fallback behavior:
- if class_hierarchy lacks class row for a P31 class, resolve on-demand (cache-first) and update projection in same run.

## 4.3 Neighbor Selection Upgrade

Current behavior slices first N sorted neighbors.

New behavior:
- deterministic score-based ranking before cap:
  - +100 if neighbor has direct seed link
  - +80 if neighbor direct P31 core match
  - +60 if neighbor subclass_of_core_class
  - +30 if mention-target label overlap exists
  - +10 if discovered but unexpanded
  - tie-break: qid ascending
- apply max_neighbors_per_node after ranking

This preserves determinism while reducing accidental loss of high-value neighbors.

## 4.4 Node Store Payload Upgrade (Optional but Recommended)

Current discovered-item minimal payload keeps only P31/P279 claims.

Recommended change:
- include a compact claims_summary map in node store with selected frequently useful PIDs:
  - P31, P279, P179, P4908, P527, P155, P156, P345
- do not store full claim blobs for all PIDs in discovered-item minimal write path

Purpose:
- improve dossier quality without forcing eventstore scans.

## 5. Implementation Plan

## Phase 1: Add dossier projection

Code touchpoints:
- speakermining/src/process/candidate_generation/wikidata/schemas.py
  - add artifact paths for entity_dossiers.jsonl and entity_dossiers_index.csv
- speakermining/src/process/candidate_generation/wikidata/materializer.py
  - add _build_entity_dossiers(...) and write outputs during materialize_checkpoint/materialize_final
- speakermining/src/process/candidate_generation/wikidata/bootstrap.py
  - initialize empty dossier projection artifacts

Algorithm:
1. Load entities from node store iterator.
2. Build incoming/outgoing edge maps from triples projection.
3. Join class_hierarchy and instances rows to compute class_info.
4. Join query_inventory rows by key/qid and normalized_query references.
5. Emit one JSON line per qid (stable ordering by qid).
6. Emit index CSV: qid, byte_offset, byte_length, label_de, class_id, expanded_at_utc.

Acceptance checks:
- Q130638552 appears in entity_dossiers with full outgoing/incoming edges.
- Entity dossier can be loaded by offset lookup using index without scanning entire file.

## Phase 2: Stage A subclass-aware eligibility

Code touchpoints:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - replace _entity_p31_core_match usage in enqueue decision with subclass-aware resolver
- speakermining/src/process/candidate_generation/wikidata/class_resolver.py (reuse existing)
- speakermining/src/process/candidate_generation/wikidata/materializer.py
  - ensure class_hierarchy is materialized before Stage A decisions rely on cached projection snapshot

Acceptance checks:
- A node with P31=Q21191270 and path to Q1983062 is eligible when direct seed link exists.
- No regression for class-node exclusion.

## Phase 3: Neighbor ranking before cap

Code touchpoints:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
  - replace capped_neighbors derivation with score+sort+cap

Acceptance checks:
- Deterministic ranking for same input graph.
- High-value episode neighbors are retained when cap is hit.

## Phase 4: Optional compact claim summary

Code touchpoints:
- speakermining/src/process/candidate_generation/wikidata/node_store.py
  - enrich _entity_minimal with compact claims_summary

Acceptance checks:
- entities.json size growth remains bounded.
- dossier quality improves for common diagnostics.

## 6. Data Contracts

## entity_dossiers_index.csv
Columns:
- qid
- byte_offset
- byte_length
- label_de
- label_en
- resolved_core_class_id
- subclass_of_core_class
- discovered_at_utc
- expanded_at_utc

Uniqueness:
- qid unique

## entity_dossiers.jsonl
One JSON object per qid.

Determinism:
- lines sorted by qid
- arrays sorted deterministically:
  - edges by (pid, counterparty_qid, discovered_at_utc, source_query_file)
  - provenance rows by (timestamp_utc, source_step, normalized_query)

## 7. Runtime and Storage Considerations

1. Dossier materialization runs from projections, not full chunk replay.
2. For large repositories, query_inventory join should use filtered hash map keyed by qid/key token.
3. Provide config switch:
- enable_entity_dossiers_projection: true/false (default true)
4. If disabled, pipeline behavior remains unchanged.

## 8. Risks and Mitigations

Risk: dossier file becomes very large.
- Mitigation: keep index for direct seeks; optionally shard by qid prefix later.

Risk: subclass-aware eligibility increases expansions significantly.
- Mitigation: preserve budgets and add per-core-class expansion counters for observability.

Risk: ranking weights bias discovery.
- Mitigation: keep deterministic metrics dashboard and allow weight tuning via config.

## 9. Test Plan

Unit tests:
- dossier builder joins expected rows for synthetic QID graph
- index offsets point to valid dossier lines
- subclass-aware eligibility true for subclass-of-core P31
- ranking order stable across repeated runs

Integration tests:
- run notebook 21 on cache-first mode and verify Q130638552 dossier completeness
- compare stage_a expanded_qids before/after change for deterministic seed fixture

Regression tests:
- no change in output when feature flags disabled
- existing class_hierarchy and instances projections unchanged in schema

## 10. Migration and Rollout

1. Implement behind feature flags:
- stage_a_subclass_aware_eligibility
- stage_a_neighbor_priority_ranking
- enable_entity_dossiers_projection

2. Default rollout:
- Enable dossier projection first
- Validate for one full run
- Enable subclass-aware eligibility
- Enable neighbor ranking

3. Rollback:
- Disable flags; existing projections remain intact.

## 11. Operator UX

Notebook 21 should print explicit hints after materialization:

- entity dossier path
- index path
- example lookup command for qid

Example lookup snippet:

- Read index row for Q130638552
- Seek byte range in entity_dossiers.jsonl
- Parse single JSON object

This gives a fast answer to "everything we know about Q130638552" without scanning eventstore.

## 12. Open Questions

1. Should dossier include full claim blobs for expanded nodes, or remain graph/provenance centric?
2. Should neighbor ranking include a recency weight from discovered_at_utc?
3. Should dossier output be sharded (e.g., entity_dossiers/Q13.jsonl) once file size passes threshold?
