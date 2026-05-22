# color-registry-none-filter

* priority: medium
* scope: pipeline
* legacy-finding: F-07 (2026-05-11 review)

## Summary

`build_show_color_registry()` in `50_analysis.ipynb` accepts the placeholder show ID `NONE` as a real show, assigning it a color slot in the registry. This produces spurious `NONE` entries in per-show charts and legend outputs.

## Evidence

Source: `documentation/archive/50_Analysis/2026-05-11_review/code_update_plan.md` (F-07) and `findings.md`.

`NONE` is a sentinel value used when a show ID is unknown or not set. The registry builder should filter it out before assigning colors.

## Definition of done

1. `build_show_color_registry()` filters out `NONE` (and any other known sentinel values) before building the registry.
2. No `NONE` entry appears in per-show chart legends or output CSVs.
