# moderator-exclusion

* priority: medium
* scope: pipeline
* legacy-id: TODO-039

## Summary

Moderators such as Markus Lanz appear in every episode and would skew all statistics (gender distribution, age, occupation frequency, page rank). They must be excluded from all analysis outputs. Currently unknown whether they are already excluded.

## Evidence

`data/40_analysis/guest_catalogue.csv`, `speakermining/src/process/notebooks/51_visualization.ipynb`.

## Definition of done

1. Check whether Markus Lanz (Q43773) currently appears in `guest_catalogue.csv`, gender distribution, and occupation counts.
2. If present: add a dedicated "moderator" classification category to the person classification step.
3. All guest-related statistics count only guests — not moderators, topics, or other related persons. See `guest-classification-audit` for related work.
4. Analysis outputs are re-run with the exclusion rules applied.
