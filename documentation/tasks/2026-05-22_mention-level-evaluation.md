# mention-level-evaluation

**Identified by:** Scientific Peer Reviewer (review 03), task 1

## Problem

The pipeline has no published precision/recall measurement at the mention level. Phase 1 (mention detection) produces `persons.csv`, but there is no documented evaluation of how often it is correct — how many genuine guest mentions it captures (recall) and how many of its outputs are correct (precision). Without this, the pipeline's scientific reliability cannot be assessed by a reader, collaborator, or grant evaluator.

## Action

Construct a 100-row held-out sample from `persons.csv` and manually annotate it for correctness:

1. Sample 100 rows from `persons.csv` stratified by `parsing_rule` (to cover all rule types proportionally)
2. For each row, manually verify: is this a genuine guest mention? Is the `name` field correctly extracted? Is `mention_category` correct?
3. Compute precision (fraction of extracted mentions that are correct) and recall (fraction of true mentions in the sampled episodes that were captured)
4. Document results in `documentation/evaluation.md` with: sample size, stratification method, annotation criteria, numeric scores, and a confusion table by `parsing_rule`

If recall cannot be computed without a fully-annotated ground truth, document a partial evaluation: precision-only on the 100-row sample, with a note on what a full recall measurement would require.

## Definition of done

1. `documentation/evaluation.md` exists and contains a precision measurement on at least 100 rows.
2. Results are stratified by `parsing_rule` so weak rules are identifiable.
3. If recall is measured: a numeric score is reported. If not: a methodological note explains why and what would be needed.
