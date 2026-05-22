# wikidata-v4-rework

* priority: medium
* scope: architecture
* status: in-progress
* legacy-id: TODO-044

## Summary

Phase 2.1 is currently a patchwork of modules mending each other's shortcomings. The ideal is a single rule-driven graph expansion engine: find core node → apply rules → hydrate or expand linked objects → repeat. Active investigation and redesign underway.

## Evidence

Investigation folder: `documentation/Wikidata/archive/2026-04-26_investigation/` (full investigation, clarifications, and related task wiring). Architecture principles: `documentation/Wikidata/archive/2026-04-26_investigation/13_architecture_design.md`.

## Definition of done

1. Conceptual design for the rule-driven graph expansion engine is documented in a living `documentation/Wikidata/` doc (see `v4-architecture-documentation` task).
2. Clarification.md and 05_related_tasks.md in the investigation folder establish the agreed baseline.
3. Redesigned Notebook 21 implements the event-sourced, handler-driven, single-pass architecture with generic rule-driven relevancy propagation and no post-hoc repair step.

## Status

Investigation complete (2026-04-26). Clarifications aggregated. Related tasks wired: `roles-projection-fix` (TODO-042), `instances-csv-dual-write` (TODO-034), `node-integrity-pass-performance` (TODO-038), `property-hydration-config-alignment` (TODO-043), `time-sensitive-wikidata-claims` (TODO-041). Implementation phase next.

## Dependencies

- `v4-architecture-documentation` — design principles must be in a living doc before implementation
- `roles-projection-fix` — in-progress; blocking Phase 2 re-run verification

## Sub-tasks

The following medium tasks in `documentation/tasks/` are satellite sub-tasks of this rework. They can be executed independently but are tracked here as part of the v4 effort:

- [roles-projection-fix](../2026-05-22_roles-projection-fix.md) *(in-progress, high priority)*
- [instances-csv-dual-write](../2026-05-22_instances-csv-dual-write.md)
- [node-integrity-pass-performance](../2026-05-22_node-integrity-pass-performance.md)
- [property-hydration-config-alignment](../2026-05-22_property-hydration-config-alignment.md)
- [seed-removal-propagation](../2026-05-22_seed-removal-propagation.md)
- [time-sensitive-wikidata-claims](../2026-05-22_time-sensitive-wikidata-claims.md)

Full related-task inventory: `documentation/Wikidata/archive/2026-04-26_investigation/05_related_tasks.md`.
