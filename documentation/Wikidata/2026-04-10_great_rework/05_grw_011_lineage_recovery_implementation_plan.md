# GRW-011 Implementation Plan: Lineage Recovery Foundation

Date: 2026-04-09
Scope: code-level implementation plan for recovering and operationalizing subclass lineage from reverse-engineering evidence
Status: implementation-ready draft

Note:

1. This file is an implementation detail plan for GRW-011.
2. Canonical planning and execution order lives in `documentation/Wikidata/2026-04-10_great_rework/00_master_rework_map.md`.

## Objective

Recover lost subclass closure and `path_to_core_class` behavior from reverse-engineering evidence and expose it as a reusable lineage service consumed by expansion, node integrity, fallback eligibility, and materialization.

## Progress Update (2026-04-09)

Completed:

1. Slice 1 implemented in `class_resolver.py`:
   - `RecoveredLineageEvidence` model
   - `load_recovered_class_hierarchy(...)` loader with normalization and diagnostics
2. Slice 2 implemented in `class_resolver.py`:
   - policy-aware resolution (`runtime_only`, `runtime_then_recovered`, `runtime_then_recovered_then_network`)
   - recovered-lineage precedence before network branch when policy allows
3. Slice 3 implemented in `materializer.py`:
   - recovered-lineage loading in materialization path
   - recovered-lineage wiring into instances/class-hierarchy/entity-lookup resolution
   - lineage resolution diagnostics in materializer stats (`lineage_resolution_reason_counts`, source, policy)
4. Slice 4 implemented in expansion and node-integrity paths:
   - expansion engine now loads recovered lineage and propagates resolution policy through seed filtering and expansion eligibility checks
   - node integrity now consumes recovered lineage/policy in eligibility decisions and path-to-core transition resolution
5. Slice 5 implemented (guardrails/telemetry/rollback):
   - expansion and node integrity now emit explicit lineage resolution configuration telemetry (`resolution_policy`, `recovered_lineage_source`) at runtime and in notebook events
   - one-switch rollback confirmed via `WIKIDATA_LINEAGE_RESOLUTION_POLICY=runtime_only` (recovered lineage bypassed without code changes)

Validation evidence:

1. `pytest speakermining/test/process/wikidata/test_recovered_class_hierarchy_loader.py` (pass)
2. Focused resolver-policy tests in `test_class_path_resolution.py` (pass)
3. `test_materializer_uses_recovered_lineage_when_class_docs_missing` (pass)
4. Representative node-integrity compatibility test (pass):
   - `pytest speakermining/test/process/wikidata/test_node_integrity.py -k repairs_discovery_and_expands_eligible_node`
5. Additional Slice 5 validation:
   - focused loader tests: `pytest speakermining/test/process/wikidata/test_recovered_class_hierarchy_loader.py` (pass)
   - full `test_class_path_resolution.py` run still shows known unrelated checkpoint snapshot collision guard in `checkpoint.py` (pre-existing; not lineage-specific)

Remaining:

1. Broader non-focused validation sweep and GRW-011 closure note in master map.

## Authoritative Inputs

1. `data/20_candidate_generation/wikidata/reverse_engineering_potential/class_hierarchy.csv`
2. `data/20_candidate_generation/wikidata/reverse_engineering_potential/classes.csv`
3. `data/20_candidate_generation/wikidata/reverse_engineering_potential/core_classes.csv`
4. `documentation/Wikidata/expansion_and_discovery_rules.md`
5. `documentation/Wikidata/Wikidata_specification.md`

## Non-Goals

1. Do not import legacy artifacts as runtime source-of-truth.
2. Do not preserve old JSON sidecar behavior solely for compatibility.
3. Do not change expansion eligibility semantics from the authoritative rules.

## Code Touchpoints

Primary implementation files:

1. `speakermining/src/process/candidate_generation/wikidata/class_resolver.py`
2. `speakermining/src/process/candidate_generation/wikidata/materializer.py`
3. `speakermining/src/process/candidate_generation/wikidata/node_integrity.py`
4. `speakermining/src/process/candidate_generation/wikidata/expansion_engine.py`
5. `speakermining/src/process/candidate_generation/wikidata/handlers/classes_handler.py`
6. `speakermining/src/process/candidate_generation/wikidata/bootstrap.py`
7. `speakermining/src/process/candidate_generation/wikidata/schemas.py`

Primary test files:

1. `speakermining/test/process/wikidata/test_class_path_resolution.py`
2. `speakermining/test/process/wikidata/test_classes_handler.py`
3. `speakermining/test/process/wikidata/test_node_integrity.py`
4. `speakermining/test/process/wikidata/test_contract_matrix_closure.py`
5. `speakermining/test/process/wikidata/test_handler_output_contracts.py`

## Target Architecture

1. Introduce a lineage-recovery layer in `class_resolver.py` that can preload optional hierarchy evidence and answer lineage queries in cache-first mode.
2. Keep current `resolve_class_path(...)` contract stable for existing call sites.
3. Add a deterministic precedence model:
   - runtime entity evidence first (fresh local state)
   - recovered hierarchy evidence second (reverse-engineering reconstruction)
   - network hydration last, only when policy allows.
4. Keep lineage resolution side-effect-light and replay-safe.

## Data Contracts And Invariants

1. `path_to_core_class` remains a `|`-joined QID chain.
2. `subclass_of_core_class` remains boolean and contract-compatible with current projections.
3. Core class registry remains sourced from setup/bootstrap contracts.
4. No class should be marked subclass-of-core without traceable lineage evidence.
5. Recovered lineage must not bypass `is_class_node` and seed-neighborhood gates used for expansion decisions.

## Implementation Slices

### Slice 1: Evidence Loader And Canonicalization

Deliverables:

1. Add helper(s) to parse reverse-engineering hierarchy rows into normalized lineage records.
2. Canonicalize QIDs and reject malformed rows deterministically.
3. Build in-memory maps for:
   - class -> path_to_core_class
   - class -> subclass_of_core_class
   - class -> parent_qids

Acceptance:

1. Loader is deterministic and idempotent.
2. Invalid rows produce diagnostics counters, not silent acceptance.

### Slice 2: Resolver Integration (No Behavioral Regression)

Deliverables:

1. Extend resolver path evaluation with optional recovered lineage hint lookup.
2. Keep existing output schema unchanged.
3. Add policy flag(s) to choose resolution behavior:
   - `runtime_only`
   - `runtime_then_recovered`
   - `runtime_then_recovered_then_network`

Acceptance:

1. Existing tests pass under default policy.
2. Recovered lineage is used only when runtime evidence is absent/incomplete.

### Slice 3: Materializer And Class Projection Wiring

Deliverables:

1. Wire recovered lineage into class rollups and hierarchy projection generation.
2. Ensure `class_hierarchy.csv`, `classes.csv`, and core class projections preserve schema and sort determinism.
3. Emit diagnostics summary describing lineage source mix (runtime vs recovered vs network).

Acceptance:

1. Projection output contracts remain unchanged.
2. Contract tests continue to pass.

### Slice 4: Expansion And Node Integrity Consumption

Deliverables:

1. Update expansion and node integrity lineage calls to consume resolver policy explicitly.
2. Reduce unnecessary network lineage fetches in hot decision loops when recovered lineage is available.
3. Preserve current expansion/discovery semantics.

Acceptance:

1. Decision outcomes remain contract-consistent on representative fixtures.
2. Network-call count decreases or remains bounded for lineage resolution paths.

### Slice 5: Guardrails, Telemetry, And Rollback

Deliverables:

1. Add structured diagnostics for lineage resolution source and fallback reason.
2. Add feature flag to disable recovered lineage quickly.
3. Document rollback path if recovered lineage creates mismatch in contract tests.

Acceptance:

1. Operator can identify why a class was marked subclass-of-core.
2. One-switch rollback path exists without code reverts.

## Validation Plan

1. Unit tests:
   - loader normalization and malformed-row handling
   - precedence policy behavior
   - deterministic `path_to_core_class` output
2. Integration tests:
   - class resolution parity for known cases (`Q5 -> Q215627` and similar)
   - node integrity reclassification behavior with recovered lineage
3. Contract tests:
   - output schema and closure checks remain green
4. Runtime check:
   - one cache-first notebook pass confirms no regressions in eligibility semantics

## Rollout Sequence

1. Merge Slice 1 and 2 behind feature flag.
2. Run full Wikidata test subset.
3. Merge Slice 3 and 4.
4. Run notebook cache-first validation and targeted non-zero-network validation.
5. Enable recovered lineage policy by default only after parity evidence is recorded.

## Risks And Mitigations

1. Risk: recovered lineage conflicts with fresh runtime evidence.
   - Mitigation: strict precedence (runtime first), diagnostics, feature flag rollback.
2. Risk: hidden schema drift in class projections.
   - Mitigation: contract tests and explicit projection column assertions.
3. Risk: over-trust in legacy artifact quality.
   - Mitigation: validation counters, malformed-row quarantine, conservative policy defaults.

## Definition Of Done For GRW-011

1. Recovered lineage service exists and is consumed by core lineage call sites.
2. Class and hierarchy projections remain contract-compatible.
3. Expansion and integrity behavior remains rule-consistent while reducing avoidable lineage network fetches.
4. Test and notebook evidence is linked back to GRW-011 closure notes in the backlog.
