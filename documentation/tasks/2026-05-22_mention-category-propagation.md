# mention-category-propagation

* priority: medium
* scope: pipeline
* legacy-id: TODO-027

## Summary

The `mention_category` field (`guest` vs. `incidental`) was added in Phase 1 but its propagation through Phase 31 alignment and Phase 32 deduplication has not been verified. The final output should distinguish guests from other mentions.

## Evidence

`speakermining/src/process/config.py` (`PERSON_MENTION_COLUMNS`).

## Definition of done

1. It is verified (or made true) that `mention_category` flows from Phase 1 persons.csv into Phase 31 `aligned_persons.csv` and Phase 32 `dedup_persons.csv`.
2. Phase 32 or Analysis produces two separate person files: `guests.csv` (mention_category = guest) and `others.csv` (mention_category = incidental/other).
3. Guest counts are verified against `guest_catalogue.csv` and any discrepancy is documented.
