# seed-removal-propagation

* priority: medium
* scope: architecture
* legacy-id: TODO-050

## Summary

When a user removes a seed, core class, or relevancy rule from the configuration, previously produced outputs retain the removed entity/class until a full re-run. There is no mechanism to propagate config removals to downstream outputs incrementally.

## Definition of done

1. A "removal propagation" mechanism is designed and documented: which events are emitted, which handlers react, and which output files are updated.
2. Removing a seed or core class triggers re-computation of affected projections without requiring a full pipeline restart.
3. An integration test verifies that a removed seed disappears from `core_*.json` after the next notebook run.

## Notes

Requires Phase 21 re-run. Depends on `wikidata-v4-rework` for the event-driven architecture that would make removal propagation feasible.
