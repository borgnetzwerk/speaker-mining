# predictive-analytics

* priority: low
* scope: pipeline
* legacy-id: TODO-021

## Summary

No analysis exists to identify which guest properties predict other properties. The analysis should be assumption-free — run neutral predictions and inspect results (e.g. "if a scientist is invited, they are mostly male").

## Definition of done

1. A prediction model using deterministic calculations (frequent set mining, association rule mining) is applied over guest catalogue properties.
2. Key predictors for gender, age, and party affiliation are identified and listed.
3. Results are presented neutrally, without presuppositions, and documented in `documentation/`.

## Notes

No machine learning or black-box approaches. Deterministic calculations only. Relevant concepts: frequent set mining (frequent pattern discovery), association rule mining.
