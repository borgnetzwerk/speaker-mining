# TDD Test Plan — 50_analysis Notebook

This plan defines test-first coverage for the critical behaviors orchestrated by `speakermining/src/process/notebooks/50_analysis.ipynb`.

## Scope

The notebook is orchestration-only by design, but it still owns wiring decisions that can break correctness. The test suite therefore covers:

1. Notebook wiring contracts (static checks on notebook source cells).
2. Module contracts that notebook wiring depends on.
3. Regression checks for previously verified findings.

## Test Matrix

1. Age distribution counts are true appearance counts
- Type: Notebook wiring contract test
- Failing condition: `compute_carrier_stats` uses `appearance_age` instead of `appearance_count`
- Pass condition: age cell sets `appearance_count = 1` and passes `appearance_column="appearance_count"`

1. Summary artifact schema is not overwritten
- Type: Notebook wiring contract test
- Failing condition: multiple writes to `analysis_summary.json`
- Pass condition: exactly one write path for canonical `analysis_summary.json`

1. README generation uses guest per-show stats table
- Type: Notebook wiring contract test
- Failing condition: notebook still passes ambiguous `per_show_stats`
- Pass condition: notebook uses explicit `guest_per_show_stats` and `coverage_per_show_stats` variable split

1. README generator validates required columns
- Type: Module contract test (`process.analysis.readme_generator`)
- Failing condition: accepts malformed DataFrame and silently emits wrong output
- Pass condition: raises `ValueError` when required columns are missing

1. Final visualization show registry rejects placeholder show IDs
- Type: Module contract test (`process.analysis.viz_final.build_show_color_registry`)
- Failing condition: accepts `NONE` entries as real shows
- Pass condition: excludes sentinel IDs from order and color mapping

1. Visualization cache requires complete output bundle
- Type: Module contract test (`process.analysis.viz_base.save_fig`)
- Failing condition: cache hit when only PNG exists but PDF/HTML missing
- Pass condition: regeneration occurs unless all expected artifacts exist

## Execution Order

1. Add tests and run targeted pytest selection; confirm failures.
1. Implement minimal code changes to satisfy failures.
1. Re-run targeted pytest selection; ensure pass.
1. Run broader analysis-related tests for regression confidence.

## Done Criteria

- New tests exist for all high-risk notebook wiring responsibilities listed above.
- Tests fail before implementation changes and pass afterward.
- Notebook and module code changes are limited to the minimum required to satisfy tests.