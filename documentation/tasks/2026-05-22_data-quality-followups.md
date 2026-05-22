# data-quality-followups

* priority: medium
* scope: pipeline
* legacy-id: TODO-065

## Summary

Two data quality issues require investigation: (1) implausible age outliers (3-year-old and 117-year-old guest) in distribution outputs; (2) semantically equivalent values split across multiple QIDs (e.g. "Doktor phil" vs "Doktor Philosophiae", capitalization variants of church names).

## Evidence

`documentation/archive/50_Analysis/2026-05-04_finalization/open-tasks.md` TASK-F12; `2026-04-29_Initialization/open-tasks.md` TASK-A09.

## Definition of done

1. Age outliers investigated: specific QIDs/labels identified, birth year correctness in Wikidata verified, formula confirmed or corrected, finding documented as bug fix or data limitation.
2. Apparent QID duplicates catalogued: a list of value-pairs that appear to represent the same real-world concept is produced. For each pair: either merged in pipeline (via alias/normalization rule) or documented as a genuine Wikidata distinction.
3. Any corrections propagated through Phase 50 re-run.

## Notes

See also `guest-classification-audit` which overlaps with age outlier investigation.
