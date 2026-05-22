# cross-source-validation

**Identified by:** Scientific Peer Reviewer (review 03), task 8

## Problem

The pipeline draws guest attribution from two independent sources: ZDF episode PDFs (Phase 1) and fernsehserien.de scraping (Phase 2/3). For episodes covered by both sources, there is no documented check of how often the two sources agree on who appeared. Disagreements reveal either parsing errors, coverage gaps, or genuine source discrepancies — all methodologically important to document.

## Action

For a sample of episodes covered by both ZDF PDFs and fernsehserien.de:

1. Identify the overlap set — episodes where both sources provide guest attribution
2. For each episode in the overlap, compare the guest name lists: exact matches, partial matches (same person, different name form), and source-exclusive mentions
3. Compute agreement rate at the episode level (fraction of episodes where the two sources name the same set of guests) and at the mention level (fraction of individual mentions confirmed by both sources)
4. Categorise disagreement types: name form variation, data entry errors, genuine source difference (e.g., fernsehserien.de includes recurring hosts that PDFs omit)
5. Document in `documentation/evaluation.md` (or a sub-section thereof) with: overlap corpus size, agreement rates, top disagreement categories, and implications for pipeline reliability

## Definition of done

1. `documentation/evaluation.md` contains a cross-source validation section.
2. Agreement rate is reported at both episode and mention level.
3. Top disagreement categories are documented with at least 2 concrete examples.
