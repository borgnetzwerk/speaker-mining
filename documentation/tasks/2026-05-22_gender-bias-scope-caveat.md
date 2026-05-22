# gender-bias-scope-caveat

* priority: low
* scope: documentation
* legacy-id: TODO-033

## Summary

The current analysis computes gender distribution over the guest sample only and cannot make claims about the total population. This methodological caveat must be documented clearly so results are not misinterpreted.

## Evidence

`data/40_analysis/guest_catalogue.csv`, `speakermining/src/process/notebooks/51_visualization.ipynb`.

## Definition of done

1. A caveat section is added to the gender analysis output (notebook or documentation) explaining that bias metrics describe the sample set only, not the total population.
2. Example framing is provided: "X% of teachers in our sample are male" — not "X% of all teachers are male".
3. The caveat is referenced from `documentation/findings.md` as a known limitation.
