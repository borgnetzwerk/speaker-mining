# gender-distribution-extended

* priority: medium
* scope: pipeline
* legacy-id: TODO-020

## Summary

Current gender charts are a first start. Two improvements are needed: (1) a grouped bar chart placing the "by individual" and "by occurrence" bars side-by-side for immediate visual comparison, and (2) occupation subclustering via Wikidata subclass hierarchy so related subtypes roll up to a common parent label.

## Evidence

`speakermining/src/process/notebooks/51_visualization.ipynb`.

## Definition of done

1. A grouped-bar chart is produced showing both "by individual" and "by occurrence" in the same figure per occupation category.
2. Occupations are clustered using Wikidata subclass relations (P279 traversal) so that related subtypes roll up to a common parent label.
3. An age distribution violin plot is added (age at appearance, grouped by occupation or gender).
4. All new charts are exported as PDF + PNG to `documentation/visualizations/`.
