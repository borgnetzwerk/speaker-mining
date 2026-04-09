# Wikidata Step 5: `triple_events.json` Decision

Status: Transferred to great_rework (2026-04-09)
Owner: Candidate generation / Wikidata pipeline
Depends on: `05_legacy_json_cutover.md`

## Goal

Transfer note:

1. Remaining scope is tracked in `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md` as `GRW-008`.

Decide whether `triple_events.json` remains necessary after lookup and legacy JSON cutover work is complete.

## What this step delivers

1. A concrete retain-or-deprecate decision for `triple_events.json`.
2. If retained, a narrow replay/debug-only contract.
3. If deprecated, a documented and implemented removal path.

## Scope

In scope:

1. inventory remaining consumers of `triple_events.json`
2. verify whether replay is still needed
3. separate replay requirements from entity/property lookup concerns
4. document and implement the final lifecycle decision

Out of scope:

1. changing chunk/index architecture
2. reworking core-class outputs
3. revisiting entity/property cutover choices

## Implementation checklist

1. Build consumer inventory for `triple_events.json`.
2. Validate each consumer against a concrete replay requirement.
3. Decide retain or deprecate based on observed requirements.
4. If retaining, document replay-only schema and retention limits.
5. If deprecating, remove writer/readers and update schemas/checkpoints.

## Completion criteria

This step is complete when all of the following are true:

1. The repository has a documented decision for `triple_events.json`.
2. The decision is backed by a concrete consumer inventory.
3. Any remaining use is explicitly replay-only.
4. If deprecated, the removal path is implemented and verified.

## Required completion evidence

1. Consumer inventory with keep/remove disposition.
2. Decision record citing replay requirements.
3. Verification output showing either replay-only retention or complete deprecation.

## Notes

`triple_events.json` has different operational semantics than entity/property lookup and should not be forced into the same lifecycle without evidence.

When complete, mark this file complete. If no new task appears, the implementation plan is finished.
