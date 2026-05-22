# episode-topic-classification

* priority: medium
* scope: pipeline
* legacy-id: TODO-052

## Summary

Each episode currently carries at most one ZDF-provided topic label. A keyword-weighted multi-topic taxonomy applied to episode description and title text would enable topic × demographic analysis as a new Phase 50 dimension.

## Evidence

`documentation/tasks/visualization_references/Lanz-und-Precht/theme_detection.ipynb` demonstrates a working 10-topic taxonomy with evidence-weighted scoring across title, description, bag-of-words, named entities, and transcript text. The approach requires only description text for a first version.

## Definition of done

1. A topic taxonomy (10–15 German-language topics; e.g. Politics, Economy, Climate, Technology, Society, International, Health, Science, Media, Migration) is documented in `documentation/analysis/` with its keyword lists.
2. A Phase 50 module classifies each episode with one or more topics, writing `topic_labels` as a list column in the analysis output.
3. At least one new Phase 50 visualization shows guest gender distribution broken down by topic.

## Notes

Topic taxonomy should be iteratively validated against known episodes before running on the full corpus. Weighted scoring strategy from `theme_detection.ipynb` (higher weight for title/description than bag-of-words) should be preserved. Downstream: `topic-demographic-correlation` task depends on this output.
