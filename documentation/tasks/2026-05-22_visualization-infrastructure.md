# visualization-infrastructure

* priority: medium
* scope: pipeline
* legacy-id: TODO-060

## Summary

Several visualization infrastructure items remain open: language variants (DE/EN), file naming convention enforcement (`{chart_type}_{pid}_{short_label}`), per-show chart runs for cross-property charts, and episode-level property pipeline (duration, guest count, description, topic).

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F05 and TASK-F09 remaining work sections.

## Definition of done

1. Every output file includes both the PID and a ≤25-char slug: `{chart_type}_{pid}_{short_label}.{ext}`.
2. Language variant support: EN and DE localization controlled by a single config constant. `visualization-principles.md` documents the DE/EN capitalization rule.
3. Cross-property charts run per show in addition to the combined "all" scope.
4. Episode-level property pipeline produces duration, guest-count, and description outputs where data is available.
5. Source coverage dashboard shows unique-to-source episode count.
