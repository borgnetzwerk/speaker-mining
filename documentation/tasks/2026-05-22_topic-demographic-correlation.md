# topic-demographic-correlation

* priority: low
* scope: pipeline
* legacy-id: TODO-056

## Summary

Adding topic labels as a new dimension to Phase 50 would reveal whether specific topics are discussed with systematically different guest demographics — a key question for diversity analysis beyond aggregate counts.

## Dependencies

Requires `episode-topic-classification` (TODO-052) for topic labels.

## Definition of done

1. Topic labels from `episode-topic-classification` are joined with the deduped persons data used in Phase 50 analysis.
2. At least two new visualizations are produced: (a) gender distribution by topic (bar chart), (b) temporal gender trend per topic (line chart).
3. Statistical significance of topic × gender differences is tested and documented using the existing Mann-Whitney U infrastructure in `statistical_tests.py`.
4. Findings are added to `documentation/analysis/README.md` as planned analysis angles.

## Notes

Can be prototyped with ZDF-provided single topic labels first (already in Phase 10 output) before multi-topic labels are available.
