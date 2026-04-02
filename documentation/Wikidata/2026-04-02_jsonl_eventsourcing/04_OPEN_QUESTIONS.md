# Open Questions for V3 Migration

**Date:** 2026-04-02  
**Status:** Resolved - decisions finalized for Phase 1 kickoff  

---

## Overview

This document now serves as the final decision register for the former open questions. All items are resolved and can be treated as implementation guidance.

---

## Resolved Clarifications

### R1: Canonical Chunk Linkage vs. Catalog Role

**Decision:** RESOLVED

- Canonical chunk linkage is defined by chunk boundary events in the data itself:
  - old chunk terminal event: `eventstore_closed`
  - new chunk first event: `eventstore_opened`
- Sequence numbers are continuous across chunks and never reset.
- `chunk_catalog.csv` is a derived operational index for fast lookup/replay and is rebuildable.
- If `chunk_catalog.csv` disagrees with boundary-event linkage, boundary events are canonical and catalog must be rebuilt.

---

## Final Decisions (Q1-Q20)

### Q1: Handler Execution Model - Sequential vs. Async
**Decision:** Sequential execution in Phase 1; async is out of scope for this migration.

### Q2: Snapshot Checkpoints - Full State vs. Metadata
**Decision:** Snapshot once before every run.

### Q3: Event Type Taxonomy - Define All Now or Incrementally
**Decision:** Define event types as early as possible and maintain a dedicated taxonomy file mapping handlers to event types.

### Q4: Sequence Numbering - In-Memory vs. File Lock
**Decision:** In-memory counter with single-writer assumption.

### Q5: Handler Dependencies - Implicit vs. Explicit
**Decision:** Explicit dependency ordering is required.
- Class-resolution and expansion decisions must complete before dependent handler decisions.

### Q6: Event Payload Format - Full vs. Simplified
**Decision:** Keep full Wikidata payload in events.

### Q7: Dual Timestamps - Keep Both?
**Decision:** Keep both `timestamp_utc` and `recorded_at`. For example, if an event is ever migrated to a new eventstore (as we currently do with the v2 events), we must be able to differentiate our current event time from the original time when the event was first recorded.

### Q8: Event Deduplication - Query Hash Stability
**Decision:** Keep deterministic query normalization and hash stability tests.

### Q9: Handler Batch Size
**Decision:** Default batch size is 1000; configurable.

### Q10: Checksum Algorithm
**Decision:** Use SHA256.

### Q11: Determinism Strictness
**Decision:** Byte-identical output is the target.

### Q12: Test Data Size for Phase 1
**Decision:** Use ~1000 events for Phase 1; full dataset validation in later phases.

### Q13: Monitor File Mechanism
**Decision:** Keep file-based `.shutdown` mechanism.

### Q14: Monitoring & Observability Scope
**Decision:** Implement only baseline, low-effort metrics now; extend later.

### Q15: Rollback Plan
**Decision:** Keep v2 path available through transition and maintain backups for rollback.

### Q16: Migration Validation Rigor
**Decision:** Medium validation baseline:
- Rebuild projections from migrated events
- Compare against v2 projections
- Escalate to deeper audits if mismatch is detected

### Q17: Design Review & Approval Process
**Decision:** Resolved in this document; decisions are approved for implementation.

### Q18: Phased Rollout Flexibility
**Decision:** Keep gated phases; allow schedule adjustment without lowering quality gates.

### Q19: Version Compatibility Strategy
**Decision:** v3 is the active stable format; future v4 requires explicit migration.

### Q20: Performance Targets
**Decision:** Best-effort baseline now; formal SLOs deferred.

---

## Summary Table

| # | Topic | Status | Final Decision |
|---|---|---|---|
| Q1 | Handler execution model | Resolved | Sequential in Phase 1 |
| Q2 | Snapshot strategy | Resolved | One snapshot before every run |
| Q3 | Event taxonomy timing | Resolved | Define early; maintain dedicated taxonomy file |
| Q4 | Sequence assignment | Resolved | In-memory counter with single writer |
| Q5 | Handler dependencies | Resolved | Explicit dependency ordering |
| Q6 | Payload format | Resolved | Full Wikidata payload |
| Q7 | Timestamp policy | Resolved | Keep dual timestamps |
| Q8 | Query hash stability | Resolved | Deterministic normalization + tests |
| Q9 | Batch size | Resolved | 1000 default, configurable |
| Q10 | Checksum algorithm | Resolved | SHA256 |
| Q11 | Determinism level | Resolved | Byte-identical outputs |
| Q12 | Test dataset size | Resolved | ~1000 events in Phase 1 |
| Q13 | Shutdown signaling | Resolved | `.shutdown` file pattern |
| Q14 | Observability scope | Resolved | Baseline now, expand later |
| Q15 | Rollback | Resolved | Keep v2 path during transition + backups |
| Q16 | Migration validation | Resolved | Medium baseline validation |
| Q17 | Governance | Resolved | Approved for implementation |
| Q18 | Phase flexibility | Resolved | Gated phases with schedule flexibility |
| Q19 | Versioning | Resolved | v3 stable; explicit migration for v4 |
| Q20 | Performance targets | Resolved | Best-effort now; SLOs later |

---

## Implementation Readiness

- No open blockers remain in this document.
- Implementation can proceed using [01_SPECIFICATION.md](01_SPECIFICATION.md) and [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md).
- Any newly discovered ambiguity should be logged as a new item with explicit decision owner.

---

## References

- [00_OVERVIEW.md](00_OVERVIEW.md) - High-level migration approach
- [01_SPECIFICATION.md](01_SPECIFICATION.md) - Technical design
- [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) - Current v2 vs. proposed v3
- [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) - Phased implementation plan
- [../context/jsonl_potential_for_eventsourcing.md](../context/jsonl_potential_for_eventsourcing.md) - Event-sourcing principles

---

**Document Status:** ? COMPLETE (Resolved Decision Register)

**Last Updated:** 2026-04-02  
**Owner:** [TBD]
