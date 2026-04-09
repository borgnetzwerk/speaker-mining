# Wikidata Design Improvements (2026-04-09)

Status: Revised proposal (aligned to immutable constraints)
Owner: Candidate generation / Wikidata pipeline
Scope: Notebook 21 Stage A + Node Integrity + projections

## 1. Immutable Constraints (Normative)

This design MUST follow the constraints in `00_immutable_input.md`.

1. Intermediate outputs must scale and therefore must not rely on monolithic pretty-printed JSON files.
2. Lookup for a QID must be constant-time via a deterministic locator/index artifact.
3. Runtime projections and publishable output projections can be different shapes.
4. Wikidata is the central knowledge node; later phases must have direct access to structured Wikidata-backed entities/properties/classes.
5. Core class instances are the main output contract.
6. Human readability is not a requirement for Phase 2 intermediate artifacts.

## 2. Problem Statement

Current state has two practical gaps:

1. There is no single scalable lookup surface for "everything we know about QID X".
2. Stage A expansion can miss important neighbors due to direct-P31-only eligibility and lossy neighbor capping.

Observed example: Q130638552 was discovered and later expanded, but not reliably in Stage A.

## 3. Design Summary

This revision replaces the prior single-file dossier idea with deterministic chunked projections and a constant-time locator table.

This document is intentionally foundational. The artifact deprecations and code removals that depend on these new projections are follow-on steps and should be implemented only after the contracts in this document are in place and validated.

Design pillars:

1. chunked storage for per-QID records (appendable, bounded file size).
2. Stable QID-to-chunk mapping table for constant-time resolution.
3. Separate runtime and output projection layers.
4. Core-class-first output files as the durable handoff to later phases.
5. Stage A reliability fixes (subclass-aware eligibility + deterministic neighbor prioritization).

## 4. Projection Architecture

## 4.1 Runtime Projections (optimized for pipeline execution)

Paths (existing + new):

- `data/20_candidate_generation/wikidata/projections/entities.json`
- `data/20_candidate_generation/wikidata/projections/properties.json`
- `data/20_candidate_generation/wikidata/projections/triples.csv`
- `data/20_candidate_generation/wikidata/projections/query_inventory.csv`
- `data/20_candidate_generation/wikidata/projections/class_hierarchy.csv`
- `data/20_candidate_generation/wikidata/projections/entity_lookup_index.csv` (new)
- `data/20_candidate_generation/wikidata/projections/entity_chunks/` (new)

Notes:

1. Runtime projections remain compact and machine-oriented.
2. No indentation or human-format overhead in new chunk payloads.
3. Event-store replay is optional for diagnostics, not required for regular lookup.

Follow-on deprecation targets once equivalent chunk/index-backed lookups exist:

1. `entities.json` can be deprecated once every runtime consumer reads via `entity_lookup_index.csv` + `entity_chunks/`.
2. `properties.json` can be deprecated on the same schedule, using the same lookup/index pattern for property-backed records.
3. `triple_events.json` is a special case and should be treated as a later replacement step because event-style replay and graph reconstruction have different operational constraints than entity/property lookup.

## 4.2 Output Projections (optimized for Phase 3+ consumption)

One dedicated output projection family per core class, based on `data/00_setup/core_classes.csv`:

1. `instances_core_broadcasting_programs.*`
2. `instances_core_series.*`
3. `instances_core_episodes.*`
4. `instances_core_persons.*`
5. `instances_core_topics.*`
6. `instances_core_roles.*`
7. `instances_core_organizations.*`

Rule:

- Include only instances within the intended discovery boundary:
  - direct neighbor to configured broadcasting program seeds, or
  - direct neighbor of such direct neighbors.

Implementation note:

- Keep current CSV/Parquet dual-writing for interoperability.

## 5. New Scalable QID Lookup Contract

## 5.1 Locator Table

Path:

- `data/20_candidate_generation/wikidata/projections/entity_lookup_index.csv`

Columns:

- `qid`
- `chunk_file`
- `record_key`
- `resolved_core_class_id`
- `subclass_of_core_class`
- `discovered_at_utc`
- `expanded_at_utc`

Constraints:

1. `qid` unique.
2. Lookup is O(1): `qid -> chunk_file, record_key`.
3. `chunk_file` is deterministic and stable for same QID.

## 5.2 chunked Entity Records

Directory:

- `data/20_candidate_generation/wikidata/projections/entity_chunks/`

chunk strategy:

1. Deterministic partition by hash/QID prefix (configurable).
2. File rotation by max records or max bytes.
3. New chunks created without rewriting old chunks.

Record shape (compact JSON line, no pretty-print):

- `qid`
- `labels`/`descriptions`/`aliases`
- `class_info`:
  - `direct_p31`
  - `direct_p279`
  - `resolved_core_class_id`
  - `path_to_core_class`
  - `subclass_of_core_class`
  - `is_class_node`
- `graph_edges`:
  - `outgoing` (pid, to_qid, discovered_at_utc, source_query_file)
  - `incoming` (from_qid, pid, discovered_at_utc, source_query_file)
- `graph_summary`
- `provenance_summary`
- `eligibility_summary`

Rationale:

- This delivers "everything we know" for one QID without scanning large global files.

## 6. Stage A Reliability Improvements

## 6.1 Subclass-Aware Eligibility

Current issue:

- Stage A expansion gate checks direct P31 core match only.

Canonical rule reference:

- Expansion/discovery eligibility is defined in `documentation/Wikidata/expansion_and_discovery_rules.md`.
- This design step must implement that contract and must not redefine it here.

Fallback:

- If class projection lacks the class node, resolve cache-first in-run and update class projection.

## 6.2 Deterministic Neighbor Prioritization Before Cap

Current issue:

- Capping by sorted QID can drop important neighbors.

Revised behavior:

1. Score neighbors deterministically.
2. Sort by `(score desc, qid asc)`.
3. Apply cap after ranking.

Proposed scoring:

- +100 direct seed link
- +80 direct P31 core match
- +60 subclass-of-core match
- +30 mention-target lexical hit
- +10 discovered but unexpanded

## 7. Runtime vs Output Split (Explicit)

Runtime responsibilities:

1. Fast graph mutation and checkpoint safety.
2. Compact storage and deterministic chunks.
3. Minimal replay requirements.

Output responsibilities:

1. Core-class structured instance artifacts for downstream phases.
2. Stable schemas for Phase 3+ consumers.
3. Deterministic regeneration from runtime state.

## 8. Implementation Plan

## Phase 1: Add scalable lookup artifacts

Code touchpoints:

- `speakermining/src/process/candidate_generation/wikidata/schemas.py`
  - add `entity_lookup_index_csv`, `entity_chunks_dir`
- `speakermining/src/process/candidate_generation/wikidata/bootstrap.py`
  - initialize index + chunk dir
- `speakermining/src/process/candidate_generation/wikidata/materializer.py`
  - build/update index and chunk records from compact projections

Acceptance:

1. Q130638552 resolves via one index lookup and one chunk-file read.
2. No full eventstore scan required.

## Phase 2: Stage A eligibility and ranking fixes

Code touchpoints:

- `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py`
  - subclass-aware core match
  - deterministic score+cap neighbor selection
- `speakermining/src/process/candidate_generation/wikidata/class_resolver.py`
  - reuse existing class path logic

Acceptance:

1. Subclass-of-core episodes with direct seed link become eligible in Stage A.
2. Deterministic runs keep identical ordering and counts under same inputs.

Rule source:

- Expansion/discovery rule semantics for acceptance item 1 are defined in `documentation/Wikidata/expansion_and_discovery_rules.md`.

## Phase 3: Harden core-class outputs

Code touchpoints:

- `speakermining/src/process/candidate_generation/wikidata/materializer.py`
  - ensure boundary filter is explicit and test-covered

Acceptance:

1. Core-class instance outputs satisfy two-hop neighbor boundary contract.
2. Output schemas remain stable across reruns.

## 9. Data Contracts

## `entity_lookup_index.csv`

Uniqueness:

- unique `qid`

Determinism:

- same QID maps to same chunk strategy for same config.

## `entity_chunks/*.jsonl`

Determinism:

1. records sorted by qid per chunk during compaction/materialization.
2. arrays sorted by deterministic keys.

Scalability:

1. no indentation.
2. bounded file sizes via rotation policy.

## 10. Risks and Mitigations

Risk: chunk count explosion.

- Mitigation: configurable partition + max-open-file writer policy + periodic compaction.

Risk: subclass-aware gate increases expansion volume.

- Mitigation: keep budgets, add per-core-class expansion metrics, expose stop reasons.

Risk: output/runtime divergence confusion.

- Mitigation: document explicit contracts and add validation checks in materializer.

## 11. Test Plan

Unit tests:

1. `qid -> chunk_file` mapping determinism.
2. index lookup returns valid record key.
3. subclass-aware eligibility for indirect core class paths.
4. deterministic neighbor ranking.

Integration tests:

1. cache-first run: Q130638552 retrieval via index + chunk.
2. two-hop boundary enforcement in all `instances_core_*` projections.

Regression tests:

1. existing checkpoint/restore still works.
2. existing output schemas remain backward-compatible unless explicitly versioned.

## 12. Rollout

Feature flags:

1. `enable_entity_lookup_chunks`
2. `stage_a_subclass_aware_eligibility`
3. `stage_a_neighbor_priority_ranking`

Order:

1. enable lookup chunks first
2. validate retrieval + size behavior
3. enable subclass-aware eligibility
4. enable neighbor prioritization

Rollback:

- disable flags, keep existing projections unchanged.

## 13. Operator UX

Notebook 21 summary should print:

1. lookup index path
2. chunk dir path
3. one-line lookup recipe: `qid -> chunk_file -> record`

Primary expected answer to "where is everything we know about Q130638552":

- `entity_lookup_index.csv` row for Q130638552 + corresponding chunk record.

## 14. Open Questions

1. Should chunk records include full claims for expanded nodes, or compact claim summary only?
   1. **Answer:** Full claims. We want to build the core pillar of our lookup infrastructure here.
2. What chunk rotation thresholds (records/bytes) are optimal for this repository growth profile.
   1. **Answer:** Experiment a bit. I assume around 50 MB would be a reasonable decision.
3. Do we need a second output profile for human-facing exploratory notebooks, separate from machine-optimized chunks?
   1. **Answer:** No. Outside of the dedicated output projection family per core class, nothing will ever be inspected by humans. Even those will propably get digested by machines first before being presented to humans.
   2. **Side-Note:** What we can do, however, is a small sidecar which contains three representative example instances of each class. This allows both humans and machines to quickly look inside and see what they can expect for the larger files.

## 15. Follow-On Documentation Structure

The remaining work is split into separate step files instead of being appended here.

Each step file should describe one implementation increment, one completion criterion, and one clear next action. When a step is complete, mark that file complete; if a new task appears, create a new file rather than extending this document.

Sequential order for implementation:

1. `02_entity_lookup_and_chunk_infrastructure.md`
2. `03_stage_a_reliability.md`
3. `04_core_class_output_hardening.md`
4. `05_legacy_json_cutover.md`
5. `06_triple_events_decision.md`