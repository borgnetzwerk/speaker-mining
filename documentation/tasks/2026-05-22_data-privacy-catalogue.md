# data-privacy-catalogue

* priority: low
* scope: documentation

## Summary

Define and document which data properties in the pipeline are sensitive under GDPR, living-persons protection, and research-ethics frameworks. Publish a catalogue that governs what may appear in public releases and what requires institutional access controls.

## Evidence

Raised in `documentation/archive/speaker_mining_code.md` (Future Work section) with reference to Wikidata property concepts:
- P8274 (living people protection class): pipeline data on living persons falls under Wikidata's Living People policy
- Q44601380 (property that may violate privacy): statements about living people that are not widespread public knowledge
- Q44597997 (property likely to be challenged): statements requiring reliable public sources

Current pipeline outputs include age, gender, party affiliation, and organizational membership for living individuals. These require explicit handling before any public data release.

## Definition of done

1. A `documentation/data-privacy-catalogue.md` document is created listing each potentially sensitive property (gender, age, party, employer, etc.) with a classification: public-safe, research-only, or access-controlled.
2. The catalogue references applicable Wikidata policies (P8274, Q44601380, Q44597997) and any applicable German data protection law provisions.
3. The `data/50_analysis/persons/` subdirectory isolation (already implemented) is documented as the first access-control mechanism, with instructions for repository maintainers on what to exclude from public releases.
4. A recommendation is included for researcher access tiers: who may request the full dataset and under what conditions.
