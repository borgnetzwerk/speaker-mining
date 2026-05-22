# validation-pass-protocol

* priority: medium
* scope: workflow
* legacy-id: TODO-049

## Summary

Larger reworks (e.g. Wikidata v4 redesign, Phase 31 refactor) have no formal validation pass requirement. Without one, regressions in output files, runtimes, or design intent can go undetected.

## Definition of done

1. A validation pass checklist is documented in `documentation/workflow.md` or a dedicated `documentation/validation-protocol.md`.
2. The checklist covers: old vs. new output diff, runtime comparison, event log comparison, code review, design-vs-implementation consistency check.
3. At least one completed rework (retrospectively) documents its validation pass results.
