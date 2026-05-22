# guest-speaking-time

* priority: low
* scope: pipeline
* legacy-id: TODO-054

## Summary

The existing pipeline measures guest presence (appearance count) but not participation. Given Whisper-transcribed episodes and speaker diarization, each guest's actual speaking time and word count can be measured per appearance.

## Dependencies

Requires `transcript-acquisition-pipeline` (TODO-053) first.

## Definition of done

1. A diarization strategy is chosen and documented: Whisper diarize flag vs. pyannote post-processing. Limitations (speaker count uncertainty, host vs. guest confusion) are noted.
2. A `voice_share` metric is defined: words spoken per appearance, normalized to episode total. Stored in analysis output alongside existing `appearance_count`.
3. At least one Phase 50 visualization shows voice share distribution by gender and by occupation.
4. Correlation between `voice_share` and Wikidata prominence (page rank or P18 image) is computed and documented.

## Notes

Speaker count per Lanz episode is typically 3–5 (host + guests). Diarization accuracy is sufficient for word-count estimation even without perfect speaker labelling. Manual spot-check on 5 episodes should validate before full corpus run.
