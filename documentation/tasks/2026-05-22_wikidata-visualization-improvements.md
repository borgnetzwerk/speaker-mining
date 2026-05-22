# wikidata-visualization-improvements

* priority: medium
* scope: pipeline
* legacy-id: TODO-025

## Summary

`21_wikidata_vizualization.ipynb` contains visualizations not yet represented in `51_visualization.ipynb`. Five specific improvements are outstanding.

## Evidence

`speakermining/src/process/notebooks/21_wikidata_vizualization.ipynb`.

## Definition of done

1. QID-label bug investigated in `21_candidate_generation_wikidata.ipynb` Cell 12 and fixed upstream; `21_wikidata_vizualization.ipynb` no longer shows QID-only labels.
2. Hierarchy view correctly places all core classes at appropriate positions (not just appended rightmost).
3. Sunburst diagrams exist: one per core class (exhaustive) and one combined (5% "other" cutoff for subclasses; innermost ring = core classes only).
4. Sankey diagrams exist with the same scope rules as sunburst.
5. All diagrams are written as PNG + PDF to `data/output/visualization`.

## Notes

Sunburst and Sankey diagrams assume tree-like hierarchy; subclasses with multiple superclasses break this assumption. Implementation must define a multi-parent strategy (e.g. primary-parent assignment or proportional count split) before items 3 and 4 can be completed.
