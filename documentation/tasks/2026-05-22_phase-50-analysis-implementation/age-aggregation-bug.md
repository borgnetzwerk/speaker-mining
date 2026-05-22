# age-aggregation-bug

* priority: high
* scope: pipeline
* legacy-finding: F-04 (2026-05-11 review)

## Summary

`compute_carrier_stats` is called with `appearance_column="appearance_age"` in `50_analysis.ipynb`. This causes the function to sum age values rather than count appearances, producing incorrect carrier statistics — total guest counts appear as implausibly large age sums.

## Evidence

Source: `documentation/archive/50_Analysis/2026-05-11_review/code_update_plan.md` (F-04) and `findings.md`.

`compute_carrier_stats(df, appearance_column)` aggregates by summing the appearance_column. When passed `appearance_age`, it sums birth-year-derived ages instead of counting appearances. The correct column is `appearance_count` or equivalent.

## Definition of done

1. `compute_carrier_stats` call site in `50_analysis.ipynb` uses the correct appearance count column, not `appearance_age`.
2. Carrier stats output values match plausible guest-count ranges.
3. Existing test plan in `documentation/archive/50_Analysis/2026-05-11_review/test_plan.md` passes for this finding.
