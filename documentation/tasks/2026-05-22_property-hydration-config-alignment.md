# property-hydration-config-alignment

* priority: low
* scope: architecture
* legacy-id: TODO-043

## Summary

Property-based hydration (whitelisting P106, P102, etc.) and relevancy propagation both use "if subject meets criteria, follow this property to hydrate/expand the object" logic but use ad-hoc code rather than parallel config structures.

## Evidence

`relevancy_relation_contexts.csv` (relevancy config); Phase 2.1 hydration whitelist (currently hardcoded).

## Definition of done

1. A dedicated config file for property hydration (e.g. `hydration_properties.csv`) mirrors the structure of the relevancy propagation config.
2. Both configs are documented side-by-side in `documentation/workflow.md` explaining the distinction: relevancy targets core-class-instance subjects; hydration can target any subject.
3. Hardcoded hydration predicate lists in Phase 2.1 are replaced by the config file.
