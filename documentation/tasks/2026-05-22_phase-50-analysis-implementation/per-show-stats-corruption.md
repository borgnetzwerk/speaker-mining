# per-show-stats-corruption

* priority: high
* scope: pipeline
* legacy-finding: F-02 (2026-05-11 review)

## Summary

The variable `per_show_stats` is reused for two structurally incompatible DataFrames in `50_analysis.ipynb`: first for guest statistics, then overwritten with coverage statistics. Downstream code that reads `per_show_stats` for README generation receives the coverage data instead of guest data, producing a corrupted README.

## Evidence

Source: `documentation/archive/50_Analysis/2026-05-11_review/code_update_plan.md` (F-02) and `findings.md`.

## Definition of done

1. Guest statistics and coverage statistics are stored in separate, distinctly named variables.
2. README generation code reads from the correct guest-stats variable.
3. Generated README files contain accurate guest counts, not coverage values.
