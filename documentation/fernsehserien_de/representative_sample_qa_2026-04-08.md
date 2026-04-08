# Fernsehserien.de Representative Sample QA (2026-04-08)

Scope:
- Stage-2 extraction/normalization evidence for the required five information groups.
- Cache-first replay verification (`max_network_calls=0`).

Execution reference:
- Notebook: `speakermining/src/process/notebooks/22_candidate_generation_fernsehserien_de.ipynb`
- Observed extraction result: `network_calls_used = 0` and `max_network_calls = 0`
- Observed normalization result: `normalized_events_emitted = 0` (already normalized)

## Coverage Evidence By Artifact

Row counts from current projections:

| Artifact | Rows |
|---|---:|
| `episode_metadata_discovered.csv` | 48 |
| `episode_guests_discovered.csv` | 187 |
| `episode_broadcasts_discovered.csv` | 71 |
| `episode_metadata_normalized.csv` | 48 |
| `episode_guests_normalized.csv` | 187 |
| `episode_broadcasts_normalized.csv` | 71 |

Mapping to required information groups:

1. Episode title/name: covered by `episode_metadata_*` (`episode_title_raw` / `episode_title`).
2. Description/summary: covered by `episode_metadata_*` (`description_raw_text` / `description_text`).
3. Publication/broadcast info: covered by `episode_metadata_*` (premiere fields) and `episode_broadcasts_*`.
4. Cast and crew: covered by `episode_guests_*`.
5. Sendetermine: covered by `episode_broadcasts_*`.

## Representative Sample (Normalized)

Metadata sample:
- `program_name=Markus Lanz`
- `episode_url=https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614`
- `episode_title=Folge 1`
- `premiere_date=2008-06-03`
- `premiere_broadcaster=ZDF`

Guest sample:
- `guest_name=Verona Pooth`
- `guest_role=Gast`
- `guest_url=https://www.fernsehserien.de/verona-pooth/filmografie`

Broadcast sample:
- `broadcast_date=2008-06-05`
- `broadcast_start_time=02:35`
- `broadcast_end_time=03:35`
- `broadcast_broadcaster=ZDF`

## Conclusion

The representative sample currently satisfies Stage-2 completion criterion #5 for the five required information groups, and was validated under cache-only replay conditions (no additional network requests).
