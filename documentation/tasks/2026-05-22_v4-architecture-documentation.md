# v4-architecture-documentation

* priority: medium
* scope: documentation
* legacy-id: TODO-073

## Summary

The v4 Wikidata redesign is documented in `documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md` but its 6 design principles are not yet mirrored into a living `documentation/Wikidata/` doc. This blocks T02 (V3 archive removal).

## Evidence

`documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md` — 6 principles: (1) event store is sole source of truth; (2) no post-hoc repair; (3) two actor types (EventHandlers vs ExternalEventReaders); (4) queues persisted in handler projections; (5) rules are config (CSV files); (6) backward compatibility permanent.

## Definition of done

1. A new `documentation/Wikidata/v4_architecture.md` (or equivalent section in `Wikidata.md`) documents the 6 v4 design principles in pipeline-neutral terms.
2. The module layout and handler responsibilities from `13_architecture_design.md` are summarized.
3. T02 (V3 archive removal) can proceed without losing this design knowledge.

## Notes

Dependency for T02. Low urgency while V4 is ~20% complete. Recovery source: `documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md`.
