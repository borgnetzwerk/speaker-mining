# guest-classification-audit

* priority: medium
* scope: pipeline
* legacy-id: TODO-040

## Summary

Elon Musk appears in `guest_catalogue.csv` but was (as far as known) never a guest — he appeared only in a topic description. This suggests systematic misclassification of topic-mentioned persons as guests. A random-sample audit is needed.

## Evidence

`data/40_analysis/guest_catalogue.csv` (Elon Musk present).

## Definition of done

1. Trace Elon Musk's entry back to its source: which Phase 1 row, which episode, which parsing rule.
2. Take a random sample of ≥20 entries from `guest_catalogue.csv` and trace each back to its Phase 1 source row to verify correct classification.
3. If systematic misclassification is found, raise a new task with the specific root cause and fix.
4. Results (sample + classification verdict) are documented in `documentation/findings.md`.
