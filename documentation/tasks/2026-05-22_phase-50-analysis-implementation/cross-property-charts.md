# cross-property-charts

* priority: medium
* scope: pipeline
* legacy-id: TODO-061

## Summary

Universal visualizations need full ColorRegistry integration (currently uses palette cycling); cross-property `% A over B` stacked bar families need the per-show scope; and cross-property charts need `guest_label`/`canonical_label` column availability verified.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F06 remaining work.

## Definition of done

1. All universal charts load colors exclusively from `ColorRegistry`; no local palette definitions remain in any `viz_*.py` module.
2. Cross-property stacked bar charts run per show as well as combined.
3. `guest_label` / `canonical_label` inconsistency is resolved; frames always carry the expected column name.
