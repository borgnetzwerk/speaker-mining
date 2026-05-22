# phase50-inferential-stats

**Identified by:** Scientific Peer Reviewer (review 03), task 10

## Problem

Phase 50 currently produces descriptive statistics (counts, distributions, proportions). A scientific reviewer asks whether the analysis includes any inferential statistics: hypothesis tests, confidence intervals, or effect sizes. Without at least a minimum inferential layer, the analysis cannot support causal or comparative claims in a peer-reviewed publication — only descriptive ones.

The problem is not that inferential statistics are missing (descriptive analysis is a valid output for a pipeline paper), but that the standard has not been defined and documented. Without a stated standard, reviewers assume the absence of inferential stats is an oversight rather than a deliberate design choice.

## Action

Define and document the minimum inferential statistics standard for Phase 50 outputs:

1. **Decide the standard**: does Phase 50 claim only descriptive results, or does it include hypothesis tests? This is a design decision that must be made explicitly.
2. **If descriptive-only**: add a scope statement to `documentation/analysis/README.md` (or equivalent) stating this explicitly, with a rationale (e.g., corpus is not a sample but a near-complete population for the covered period, making classical hypothesis tests inappropriate)
3. **If inferential**: specify which comparisons warrant a test (e.g., gender distribution difference between show formats), which test family is appropriate (chi-squared, Fisher's exact, permutation), and what the correction strategy for multiple comparisons is (Bonferroni, FDR)
4. Document the decision and rationale in `documentation/analysis/README.md`

## Definition of done

1. `documentation/analysis/README.md` contains an explicit statement of the inferential statistics standard for Phase 50.
2. If descriptive-only: rationale is documented.
3. If inferential: test families, comparison targets, and correction strategy are named.
