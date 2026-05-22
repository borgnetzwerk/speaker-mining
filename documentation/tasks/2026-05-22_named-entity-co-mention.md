# named-entity-co-mention

* priority: low
* scope: pipeline
* legacy-id: TODO-055

## Summary

Persons mentioned in episode descriptions or transcripts who never appear as guests are an invisible but significant layer of the public discourse graph. Mining this co-mention layer would reveal whose names travel through the show without their presence.

## Evidence

`analysis_advanced.ipynb` extracts named entities from NLP artifacts per episode and tracks their frequency over time. Named entity extraction can use spaCy `de_core_news_lg` or `flair/ner-german-large`.

## Definition of done

1. Named entities are extracted from at least episode description text using a German NER model; results stored per episode as a JSON artifact.
2. A co-mention table is produced: for each Wikidata-resolved guest, their mention count in episodes where they did NOT appear as a guest.
3. The "mentioned but never guest" population is characterized: count, Wikidata resolution rate, and gender/occupation distribution compared to the actual guest population.
4. Results are incorporated into Phase 50 output or documented in `documentation/analysis/`.

## Notes

This is a direct input to link prediction (Phase 4): high-prominence persons frequently mentioned but never appearing may represent a systematic invitation gap.
