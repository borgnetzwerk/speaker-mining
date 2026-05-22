# institution-extraction-responsibility

* priority: low
* scope: architecture
* legacy-id: TODO-005

## Summary

Institution extraction exists in deferred code and findings but not in active default outputs. The phase responsible for it is undefined and conflicting documentation remains in the codebase.

## Evidence

`speakermining/src/process/candidate_generation/INSTITUTION_EXTRACTION_DEFERRED.md`, `documentation/findings.md`.

## Definition of done

1. Architecture decision documented in `workflow.md`: which phase owns institution extraction.
2. Conflicting wording removed from docs.
3. Deferred extraction either activated with contract updates or explicitly archived.
