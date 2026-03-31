# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed

## Priority Items

### WDT-001: Re-evaluate prior eligibility decisions when class lineage improves

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  Nodes previously marked as not eligible may become eligible once new subclass paths to core classes are discovered.
- Requirements:
  1. Recompute eligibility on all persisted known nodes each integrity pass.
  2. Detect state transitions from ineligible -> eligible.
  3. Trigger expansion for newly eligible, not-yet-expanded nodes.
  4. Persist audit evidence for each transition.
- Acceptance criteria:
  1. A node that becomes connected via `P279` to a core class is reclassified within the next integrity pass.
  2. The node is expanded in that same pass if not already expanded.
  3. A persistent diagnostics record captures old/new status and evidence path.

### WDT-002: Persist reclassification diagnostics for longitudinal analysis

- Status: [ ]
- Priority: P0
- Owner: unassigned
- Problem:
  We need durable evidence to identify recurring integrity failures and code hotspots.
- Requirements:
  1. Write per-run diagnostics artifacts that include all eligibility transitions.
  2. Include node id, previous reason, new reason, path-to-core-class, run id, and timestamp.
  3. Keep output append-only at run granularity.
- Acceptance criteria:
  1. Each run produces a transition artifact when transitions occur.
  2. Artifacts are stored in a stable path under `data/20_candidate_generation/wikidata/node_integrity`.
  3. Documentation artifacts are mirrored under `documentation/context/node_integrity`.

### WDT-003: Add regression tests for reclassification edge cases

- Status: [ ]
- Priority: P1
- Owner: unassigned
- Problem:
  Reclassification behavior can silently regress if not covered by tests.
- Requirements:
  1. Add tests for delayed class discovery (`Q5` style path discovered later).
  2. Add tests for no-op integrity pass when no transition occurs.
  3. Add tests that prevent duplicate expansion of already expanded nodes.
- Acceptance criteria:
  1. Tests fail when reclassification logic is disabled.
  2. Tests pass when integrity pass reclassifies and expands correctly.

## Notes

- This tracker is dedicated to Wikidata workflow internals and avoids overlap with OpenRefine/Wikidata Reconciliation Service terminology.
