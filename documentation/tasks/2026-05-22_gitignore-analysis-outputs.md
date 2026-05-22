# gitignore-analysis-outputs

* priority: medium
* scope: workflow
* legacy-id: TODO-070

## Summary

The root `.gitignore` has initial analysis output rules but they need verification and fine-tuning once the full Phase 50 output set is known.

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F18 remaining work.

## Definition of done

1. `git check-ignore` confirms all raw occurrence matrices and per-person CSV files are excluded.
2. All aggregate/summary CSVs (carrier_stats, episode_stats, per_show_statistics, top_guests) are tracked.
3. PNG visualizations are tracked; PDF and HTML are not.
4. `data/50_analysis/.gitignore` created with rules specific to the analysis output tree if root rules are insufficient.
