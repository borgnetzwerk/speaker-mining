# transcript-acquisition-pipeline

* priority: low
* scope: pipeline
* legacy-id: TODO-053

## Summary

ZDF talk show episodes are available as audio via ZDF Mediathek or mirrored on YouTube. A Whisper-based German transcription pipeline would open an entirely new class of content-level analysis (guest speaking time, named entity co-mentions).

## Evidence

`documentation/tasks/visualization_references/Lanz-und-Precht/` demonstrates the full pipeline for the Lanz & Precht podcast: episode metadata → YouTube matching → Whisper JSON → NLP artifacts (bag_of_words, named_entities) → theme detection. Markus Lanz episodes follow the same structure.

## Definition of done

1. Legal and terms-of-use position is assessed and documented: can ZDF audio be transcribed for non-commercial academic research?
2. Audio retrieval strategy is decided: ZDF Mediathek API, yt-dlp from YouTube, or both; retention policy (delete audio after transcription) is documented.
3. Whisper pipeline produces per-episode JSON with at minimum `text` (full transcript), `language`, and `segments` (timestamped). German model (`large-v3` or equivalent) is used.
4. Transcripts are stored as JSONL or individual JSON files under `data/transcripts/` following the existing `data/` naming conventions.
5. A notebook cell demonstrates loading a transcript and retrieving its segment list.

## Downstream tasks enabled

- `guest-speaking-time` (TODO-054): voice share metric from diarized transcripts
- `named-entity-co-mention` (TODO-055): NER over transcript text

## Technical notes

Whisper `large-v3` model handles German well. Segment timestamps are essential for diarization. The Lanz & Precht notebooks store NLP artifacts (bag_of_words, named_entities) separately from the raw Whisper output — that separation should be preserved.
