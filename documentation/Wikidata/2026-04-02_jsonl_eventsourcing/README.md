# V3 JSONL Event-Sourcing Migration — Documentation

**Date:** 2026-04-02  
**Status:** Specification Phase (Pre-Implementation)  
**Link to previous migration:** [2026-03-31 v2 Migration](../2026-03-31_transition/)

**Runtime Policy (effective immediately):** v2 will not be executed again. All ongoing and future execution is v3-only. Legacy v2 query-response data is retained only as one-time import input.

---

## Quick Links

| Document | Purpose | Audience |
|----------|---------|----------|
| [00_OVERVIEW.md](00_OVERVIEW.md) | High-level vision and key differences | Everyone; start here |
| [01_SPECIFICATION.md](01_SPECIFICATION.md) | Technical architecture and API design | Architects, implementers |
| [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) | Current v2 vs. proposed v3 detailed comparison | Architects, tech leads |
| [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) | Step-by-step implementation plan (3 phases) | Project managers, engineers |
| [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) | Resolved decision register for implementation | Decision-makers, architects |
| [05_EXECUTION_READINESS.md](05_EXECUTION_READINESS.md) | Verified code mapping, baseline status, and action-log protocol | Implementers, reviewers |
| [06_MIGRATION_VALIDATION_REPORT_TEMPLATE.md](06_MIGRATION_VALIDATION_REPORT_TEMPLATE.md) | Standard validation report with mandatory mismatch classification | Implementers, reviewers |

---

## Documentation Alignment Policy

Clarifications made during this migration stage are normative and must be propagated to all relevant migration documents in this folder.

Required behavior:
- No concept is considered clarified until [00_OVERVIEW.md](00_OVERVIEW.md), [01_SPECIFICATION.md](01_SPECIFICATION.md), [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md), [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md), and [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) reflect the same understanding.
- If documents conflict, [01_SPECIFICATION.md](01_SPECIFICATION.md) is the technical source, and other docs must be updated to match.
- Clarification updates should be done in the same change set whenever possible.
- Execution progress and implementation decisions should be tracked in [05_EXECUTION_READINESS.md](05_EXECUTION_READINESS.md) during migration delivery.

---

## What is V3?

The **v3 migration** evolves the Wikidata candidate generation pipeline from a checkpoint-based system (v2) to an **event-sourcing architecture**. Key improvements:

✅ **Single source of truth**: All state recorded in append-only chunk files under `chunks/`  
✅ **Deterministic rebuilding**: Handlers replay events to produce projections  
✅ **Data integrity**: Checksums, corruption detection, graceful shutdown  
✅ **Maintainability**: Clear handler contracts, testable components  
✅ **Preserved semantics**: All v2 graph expansion and class resolution rules remain  

---

## How is this Organized?

### 1. 00_OVERVIEW.md (Start Here!)

**Best for:** "I want to understand what's changing and why"

Content:
- v2 vs. v3 comparison table
- Architectural principles
- Migration phases at a glance
- Scope (in/out of scope)
- Success criteria

**Read time:** 10-15 minutes  
**After reading:** You'll understand the "big picture"

---

### 2. 01_SPECIFICATION.md (For Architects & Implementers)

**Best for:** "I need to know the technical details to build this"

Content:
- Event store architecture (JSONL format, schema)
- Event schema specification (v3 envelope)
- Handler pattern (how state is maintained)
- 5 core handlers (Instances, Classes, Triples, QueryInventory, Candidates)
- Checkpointing & resume mechanisms
- Graceful shutdown & signal handling
- Chunking & archival strategy
- Data corruption protection (detection, recovery)
- Determinism & idempotency guarantees
- Configuration & tuning parameters
- API/contract surface (producer, handlers, consumers)
- Success criteria for Phase 1

**Read time:** 30-45 minutes  
**After reading:** You'll know what to build and how components interact

---

### 3. 02_GAP_ANALYSIS.md (For Architects & Tech Leads)

**Best for:** "I need to understand what changes from v2 and what risks are involved"

Content:
- **8 major gaps** between v2 and v3:
  1. Event storage architecture (scattered files → JSONL)
  2. Event schema changes (new fields for sequence, dual timestamps)
  3. State management (snapshots → event replay)
  4. Projection rebuilding (embedded → handler-driven)
  5. Write-side changes (embedded writes → isolated writer)
  6. Graceful shutdown handling (new mechanism)
  7. Chunk management (new)
  8. Class resolution & eligibility (NO GAP — preserved)
- Risk assessment table
- Data migration strategy
- Mitigation approaches

**Read time:** 20-30 minutes  
**After reading:** You'll understand the migration risks and trade-offs

---

### 4. 03_MIGRATION_SEQUENCE.md (For Project Managers & Engineers)

**Best for:** "I need the step-by-step implementation plan"

Content:
- **3 Phases** with detailed breakdown:
  - **Phase 1: Event Store Scaffolding**
    - Event store writer
    - Handler base class & registry
    - 5 core handler implementations
    - Orchestrator
    - Signal handlers & graceful shutdown
    - Checksums & data integrity
    - Testing suite
  - **Phase 2: Handler Integration**
    - Extract event writer from expansion logic
    - Checkpoint/resume using handler sequences
    - Fallback matcher integration
    - Full dataset run & validation
    - Performance benchmarking
    - Integration tests & CI
  - **Phase 3: Data Migration & v3-Only Cutover**
    - Migrate v2 raw_queries → eventstore
    - Validate migrated data
    - Remove v2 code paths
    - Archive old data
    - Production cutover
    - Documentation & knowledge transfer

- Each phase includes:
  - Detailed tasks & subtasks
  - Acceptance criteria (what "done" looks like)
  - Testing strategy
  - Completion gates (must pass before next phase)

- Cross-phase concerns:
  - Testing strategy
  - Risk mitigation
  - Resource allocation (2 engineers)
  - Communication plan

**Read time:** Scan first; detailed reading takes 60+ minutes  
**After reading:** You'll have a concrete implementation roadmap

---

### 5. 04_OPEN_QUESTIONS.md (Decision Register)

**Best for:** "What has already been decided?"

Content:
- **20 resolved decisions** across categories:
  - **Architecture & Design** (5 questions)
    - Sequential vs. async handlers (CRITICAL)
    - Snapshot strategy (HIGH)
    - Event type taxonomy (HIGH)
  - **Data & Schema** (3 questions)
    - Payload format, dual timestamps, deduplication
  - **Implementation** (3 questions)
    - Batch size, checksum algorithm, etc.
  - **Testing** (3 questions)
    - Determinism level, test data size
  - **Operations** (2 questions)
    - Monitoring, logging, alerting
  - **Migration & Rollback** (2 questions)
    - Rollback plan, data validation rigor
  - **Process & Governance** (2 questions)
    - Who approves, design review process
  - **Miscellaneous** (2 questions)
    - Version compatibility, performance SLOs

 - Each decision includes:
  - Priority context
  - Final decision
  - Implementation guidance

 - Summary table for quick reference
 - Implementation-readiness guidance

**Read time:** 20-30 minutes to scan; skip non-critical areas  
**After reading:** You'll know which decisions are fixed and can be implemented immediately

---

## Reading Paths

### "I'm new to this project"
1. Read [00_OVERVIEW.md](00_OVERVIEW.md) (10 min)
2. Skim [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) (15 min)
3. Browse [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) for phases (15 min)
4. **Total: ~40 minutes** to understand the scope

### "I need to make architectural decisions"
1. Start with [00_OVERVIEW.md](00_OVERVIEW.md)
2. Deep-dive [01_SPECIFICATION.md](01_SPECIFICATION.md)
3. Review [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md)
4. Discuss [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) risks
5. **Total: ~2 hours** to make informed decisions

### "I'm implementing Phase 1"
1. Read [00_OVERVIEW.md](00_OVERVIEW.md) (context)
2. Study [01_SPECIFICATION.md](01_SPECIFICATION.md) (detailed spec)
3. Focus on [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) Phase 1 section (~1 hr)
4. Review [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) decisions that affect Phase 1
5. **Total: ~3-4 hours** to start implementation

### "I'm managing the overall migration"
1. [00_OVERVIEW.md](00_OVERVIEW.md) (vision)
2. [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) (phases, gates)
3. [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) (decision-making)
4. Reference [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) for risk planning
5. **Total: ~2 hours** to manage the program

---

## Key Concepts

### Event Store
A single, append-only chunk chain under `chunks/` containing all persistent state changes. Each line in each chunk is a JSON event with:
- `sequence_num`: Unique, monotonic sequence number
- `event_version`: "v3" (enforced)
- `event_type`, `timestamp_utc`, `recorded_at`, `source_step`, `status`, `payload`, etc.

Chunk continuity model:
- Canonical chain is encoded in boundary events (`eventstore_closed`, `eventstore_opened`) with continuous sequence numbers.
- `chunk_catalog.csv` is a derived index for fast reads and can be rebuilt from chunk files and boundary events.

### Event Handler
A component that reads events from the event store and maintains a derived projection (CSV, JSON). Examples:
- **InstancesHandler**: Reads entity query responses → produces instances.csv
- **ClassesHandler**: Reads entity responses with P31/P279 claims → produces classes.csv
- **TripleHandler**: Reads claims → produces triples.csv
- **QueryInventoryHandler**: Reads all queries → produces query_inventory.csv

### Handler Progress Tracking
`eventhandler.csv` tracks which events each handler has processed:
```
handler_name,last_processed_sequence
InstancesHandler,1247
ClassesHandler,1245
TripleHandler,1247
QueryInventoryHandler,1247
CandidatesHandler,1000
```

Handlers read events from `(last_processed_sequence + 1)` onward.

### Three Phases
1. **Phase 1: Scaffolding** — Build event store, handlers, tests on small data
2. **Phase 2: Integration** — Wire graph expansion to event store; validate on full dataset
3. **Phase 3: Migration** — Move v2 data to v3; remove v2 code; production cutover

---

## Related Documents

### Previous Migration (V2, Completed 2026-03-31)
See [documentation/Wikidata/2026-03-31_transition/](../2026-03-31_transition/) for:
- MIGRATION_FINAL_DECISION.md (what v2 achieved)
- v2_only_policy.md (how v2 was finalized)
- Design contracts and validation

### Event-Sourcing Principles
See [documentation/context/jsonl_potential_for_eventsourcing.md](../context/jsonl_potential_for_eventsourcing.md) for:
- High-level event sourcing rationale
- Chunking and archival strategies
- Backup and corruption protection

Also: [documentation/context/de_eventsourcing_notes.md](../context/de_eventsourcing_notes.md) (German notes on event sourcing patterns and shutdown mechanisms)

### Current Wikidata System (V2)
- Notebook: `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`
- Modules: `speakermining/src/process/candidate_generation/wikidata/*.py`
- Spec: `documentation/Wikidata/Wikidata_specification.md` (class resolution, eligibility rules)

---

## Status & Milestones

| Milestone | Status |
|-----------|--------|
| 00_OVERVIEW.md | ✅ Complete |
| 01_SPECIFICATION.md | ✅ Complete |
| 02_GAP_ANALYSIS.md | ✅ Complete |
| 03_MIGRATION_SEQUENCE.md | ✅ Complete |
| 04_OPEN_QUESTIONS.md | ✅ Complete |
| Design Review & Decision-Making | ✅ Complete |
| Phase 1 Implementation | ⏳ Not Started |
| Phase 1 Completion Gate | ⏳ Pending |
| Phase 2 Implementation | ⏳ Not Started |
| Phase 2 Completion Gate | ⏳ Pending |
| Phase 3 Implementation | ⏳ Not Started |
| Phase 3 Completion & Production | ⏳ Pending |

---

## How to Use This Documentation

### For Code Reviews
Reference the spec sections most relevant to the PR:
- Adding an event handler? Check [01_SPECIFICATION.md](01_SPECIFICATION.md) section 2.2
- Changing event schema? Check section 1.3
- Adding tests? Check [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) Phase 1 section 7

### For Bug Reports
If an issue surfaces during implementation:
1. Check [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) (is this covered by an existing decision?)
2. Reference [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) (risk assessment)
3. Update documentation if the issue reveals a gap

### For Project Status
- **Phase progress**: Check [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md) completion gates
- **Known decisions**: Check [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md) resolved items
- **Risk register**: Check [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md) risk assessment table
- **Validation reporting**: Use [06_MIGRATION_VALIDATION_REPORT_TEMPLATE.md](06_MIGRATION_VALIDATION_REPORT_TEMPLATE.md) for each migration validation cycle

---

## Questions?

This documentation is intentionally thorough but also intentionally question-provoking. If you have questions:

1. **Is it about architecture?** → See [01_SPECIFICATION.md](01_SPECIFICATION.md)
2. **Is it about scope or risks?** → See [00_OVERVIEW.md](00_OVERVIEW.md) and [02_GAP_ANALYSIS.md](02_GAP_ANALYSIS.md)
3. **Is it about implementation?** → See [03_MIGRATION_SEQUENCE.md](03_MIGRATION_SEQUENCE.md)
4. **Is it about decisions?** → See [04_OPEN_QUESTIONS.md](04_OPEN_QUESTIONS.md)
5. **Is it about principles?** → See [../context/jsonl_potential_for_eventsourcing.md](../context/jsonl_potential_for_eventsourcing.md)

If your question **isn't answered** by the documentation:
- Open a follow-up issue and link the relevant section(s)

---
