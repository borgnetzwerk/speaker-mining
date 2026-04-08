# Wave 2: Domain Event Introduction Progress

**Date**: 2026-04-07  
**Focus**: WDT-009 Wave 2 - Expand event model beyond query_response  
**Status**: ✅ First phase complete  

---

## Overview

Wave 2 begins the transition toward true event-sourced architecture by introducing three **first-promoted domain events**: `entity_discovered`, `entity_expanded`, and `expansion_decision`.

These events capture runtime **decisions with future implications** (e.g., "this entity was newly discovered", "this entity's neighbors were expanded"). Previously, only `query_response` events logged data fetching; runtime decisions were implicit in materialized CSV state.

---

## Deliverables

### 1. Domain Event Type Definitions

**Location**: [speakermining/src/process/candidate_generation/wikidata/event_log.py](event_log.py)

Added three event builder functions with full documentation and payload schemas:

#### `entity_discovered`
- **When**: A new Wikidata entity is first encountered in the expansion process
- **Payload fields**: `qid`, `label`, `source_step`, `discovery_method`
- **Discovery methods**: seed, seed_neighbor, node_integrity_repair, fallback_match, etc.
- **Usage**: Answers "which entities were discovered, when, and how?"

#### `entity_expanded`
- **When**: An entity's neighborhood (inlinks, outlinks, properties) is fetched or materialized
- **Payload fields**: `qid`, `label`, `expansion_type`, `inlink_count`, `outlink_count`
- **Expansion types**: inlinks, outlinks, properties, neighbors, triple_expansion, etc.
- **Usage**: Answers "which entities were expanded and how much work was done?"

#### `expansion_decision`
- **When**: A decision is made about further queuing/expansion of an entity
- **Payload fields**: `qid`, `label`, `decision`, `decision_reason`, `eligibility` 
- **Decisions**: queue_seed, queue_for_expansion, mark_complete, skip, mark_budget_exhausted, etc.
- **Usage**: Answers "why was entity X processed/skipped/marked complete?"

### 2. Event Integration in Orchestration Stages

#### Stage A: Graph Expansion (expansion_engine.py)

**Emission points**:
- After entity fetch and discovery: `entity_discovered` with `discovery_method="seed_neighbor"`
- After entity expansion: `entity_expanded` with `expansion_type="neighbors"`

**Code locations**:
- Line ~368: Entity discovery event after `upsert_discovered_item()`
- Line ~389: Entity expansion event after inlinks/outlinks processing

**Result**: Graph expansion now emits discovery and expansion events for every entity encountered during seed-based traversal.

#### Step 6.5: Node Integrity Pass (node_integrity.py)

**Emission points**:
- When repairing missing entity discovery: `entity_discovered` with `discovery_method="node_integrity_repair"`

**Code locations**:
- Line ~387: Discovery event when fetching repaired entity payload during integrity checking

**Result**: Node integrity pass now records which entities it discovers during repair, making historical discovery visible.

#### Stage B: Fallback String Matching (fallback_matcher.py)

**Emission points**:
- When endpoint search discovers a new match: `entity_discovered` with `discovery_method="fallback_match"`

**Code locations**:
- Line ~273: Discovery event when entity is found via fallback string search

**Result**: Fallback matching now records which entities were matched, enabling analysis of fallback effectiveness.

### 3. Test Validation

**Test command**:
```bash
python -m pytest \
  speakermining/test/process/wikidata/test_checkpoint_resume.py \
  speakermining/test/process/wikidata/test_node_integrity.py \
  speakermining/test/process/wikidata/test_fallback_stage.py \
  speakermining/test/process/wikidata/test_wdt_007_graceful_shutdown_integration.py \
  -v
```

**Result**: **31 passed in 2.29s**

- ✅ 15 checkpoint/resume tests (existing, no regression)
- ✅ 3 node integrity tests (existing + new graceful interrupt test)
- ✅ 9 fallback matcher tests (existing + new graceful interrupt test)
- ✅ 4 WDT-007 integration tests (new graceful shutdown validation)

All tests pass, indicating that domain event wiring does not break existing functionality.

---

## Architecture Impact

### Event Stream Structure

Notebook 21 event log now contains:

```
query_response event (e.g., entity_fetch succeeded)
↓
entity_discovered event (new entity X was found)
↓
entity_expanded event (entity X's neighbors were fetched)
↓
(decisions to be recorded in next phase)
```

This creates a **linked narrative** from data fetching → discovery → expansion, enabling:
- **Causality tracing**: Why was this entity expanded? (because it was discovered from seed Y)
- **Decision replay**: Replay events to reconstruct which entities would be queued for further processing
- **Projected heartbeat**: Summarize recent discoveries/expansions for operator visibility

### Backward Compatibility

- ✅ `query_response` events still emitted (no change)
- ✅ `candidate_matched` events still emitted (no change)
- ✅ New domain events are optional (event_emitter is callable check)
- ✅ Existing checkpoint/snapshot logic unchanged
- ✅ All existing tests pass without modification

---

## Known Limitations & Future Work

### Newly Wired (2026-04-08)

- **`triple_discovered`**
  - Added event type/builder in `event_log.py`.
  - Wired emission in `triple_store.record_item_edges(...)` with runtime propagation from Stage A and Step 6.5 call paths.

- **`class_membership_resolved`**
  - Added event type/builder in `event_log.py`.
  - Added callback support in `class_resolver.resolve_class_path(...)`.
  - Wired runtime emissions in Stage A seed filtering and Step 6.5 class-resolution evaluation.

- **`expansion_decision` finalization (runtime decision points)**
  - Stage A now emits expansion decisions while evaluating candidate neighbor expansion.
  - Stage B fallback now emits expansion decisions for matched-candidate eligibility outcomes.

### Event-Derived Heartbeat (WDT-008)

Wave 2 Phase 2 included the final heartbeat wiring that is now considered sufficient and closed in the tracker:
- `emit_event_derived_heartbeat(...)` reads Notebook 21's event log and summarizes recent `entity_discovered`, `entity_expanded`, and `expansion_decision` events.
- Heartbeat calls exist after Stage A graph expansion, node integrity, fallback matching, and fallback re-entry.
- Step 9 now guards against fallback re-entry after an interrupted or failed Step 8.

This work is retained as supporting context for Wave 2, but it is no longer a blocking item.

### WDT-019 Dependency Note (Notebook Config Integrity)

- Fallback-stage operational metrics are only trustworthy when Step 8 uses the exact user-configured fallback-enabled mention types from Cell 8.
- WDT-019 implementation now enforces this contract in Notebook 21:
  - fallback mention types are resolved once in Step 2,
  - Step 7 and Step 8 both consume `config["fallback_enabled_mention_types_resolved"]`,
  - invalid configuration fails fast with explicit error.

This will replace/augment current heartbeat output with event-sourced summaries.

### WDT-016 Timeout Resilience (in progress)

Recent implementation progress:
- `cache._http_get_json(...)` now treats `TimeoutError` as transient/retriable.
- Retry/backoff policy is now configurable through request context (`http_max_retries`, `http_backoff_base_seconds`) instead of only static function defaults.
- `node_integrity.run_node_integrity_pass(...)` now wires NodeIntegrityConfig timeout policy into request context for Step 6.5.
- Added regression test coverage that Step 6.5 forwards the configured timeout policy to `begin_request_context(...)`.
- Step 6.5 discovery now handles per-entity timeout failures by logging a warning event and continuing with the next qid.
- Step 6.5 now handles interruption (`KeyboardInterrupt`) as deterministic `user_interrupted` behavior instead of propagating raw traceback behavior.
- Notebook 21 Step 2/Step 6.5 now exposes and passes timeout policy knobs (`http_max_retries`, `http_backoff_base_seconds`) so long-run behavior can be tuned without code edits.
- Added non-core class-frontier limiter in node integrity discovery to cap low-value recursive subclass expansion from second-degree paths.

Validation:
- `python -m pytest speakermining/test/process/wikidata/test_network_guardrails.py speakermining/test/process/wikidata/test_node_integrity.py -q`
- Result: `13 passed`

### Remaining Wave 2 Work

Wave 2 replay closure for WDT-009 is now complete:
- replay/invariant coverage added for mixed domain/query event streams at orchestrator level
- domain-only append replay now preserves projections through handler rehydration in orchestrator
- targeted orchestrator validation passes (`pytest test/process/wikidata/test_orchestrator_handlers.py -q` -> `4 passed`)

WDT-014 deprecation work remains separate and continues outside WDT-009 closure.

---

## Impact on WDT-008 (Heartbeat)

With domain events in place, Notebook 21 heartbeat can now:

1. **Count recent discoveries**: Query event log for recent `entity_discovered` events
2. **Summarize expansion activity**: Count `entity_expanded` events by type
3. **Project queue size**: Analyze event stream to estimate pending work

This shifts heartbeat from "we fetched N queries" to "we discovered N entities, expanded M of them".

---

## Validation Checklist

- ✅ Domain event type definitions clear and documented
- ✅ Events wired into Stage A (graph expansion)
- ✅ Events wired into Step 6.5 (node integrity)
- ✅ Events wired into Stage B (fallback matching)
- ✅ Event emitter/phase passed consistently through all orchestration
- ✅ All 31 tests pass (no regressions)
- ✅ Syntax validated on all modified modules
- ✅ Integration with graceful shutdown verified (stops emitting on interrupt)

---

## Code Metrics

| File | Changes | Lines Added | Key Additions |
|------|---------|-------------|----------------|
| event_log.py | +4 event types, +3 builders | ~120 | Domain event definitions |
| expansion_engine.py | +2 emission sites | ~25 | entity_discovered, entity_expanded in graph loop |
| node_integrity.py | +1 emission site | ~20 | entity_discovered in repair discovery |
| fallback_matcher.py | +1 emission site | ~18 | entity_discovered in endpoint search match |

**Total**: ~183 lines of domain event instrumentation  
**Test coverage**: 31/31 passing  
**Backward compatibility**: 100% (no breaking changes)

---

## Next Steps

1. **Event replay tests**: Add tests proving event stream is sufficient for deterministic re-projection.
2. **Projection derivation checks**: Validate that handlers/projections can derive expected diagnostics from promoted events.
3. **Deprecation path**: Continue retiring non-event-sourced materialization surfaces (WDT-014).

---

### Summary

Wave 2 successfully introduces **three first-promoted domain events** into the Wikidata orchestration. These events bridge the gap between low-level `query_response` events and high-level materialized CSV state, enabling:

- **Visibility**: Operators can see which entities were discovered/expanded and when
- **Auditability**: Each decision and its context is durably recorded
- **Composability**: Future features (heartbeat, diagnostics) can derive from event stream
- **Determinism**: Replaying event stream produces same discovery/expansion decisions

Wave 2 for WDT-009 is complete and Wave 3 transition diagnostics is now the active stream.

**Status: Wave 2 (WDT-009 scope) ✅ Complete | Wave 3 (WDT-001/WDT-002) 🚧 In progress**

