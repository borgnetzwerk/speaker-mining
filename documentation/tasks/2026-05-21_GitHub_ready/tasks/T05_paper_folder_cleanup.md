# T05: Clean Up Paper Draft Folders

## What was extracted (done)

Unique repository-relevant artifacts have been moved from the paper draft folders:

- `documentation/data_reference.md` — verified pipeline output numbers mapped to CSV sources
- `documentation/corpus_selection.md` — rationale for which shows were included and why
- `speakermining/src/process/analysis/` — three statistical analysis scripts added:
  - `statistical_tests.py` (Mann-Whitney U, gender-age significance)
  - `gender_trend_analysis.py` (gender ratio over time, changepoint detection)
  - `episode_date_range.py` (episode date range analysis)
  - `results.json` + `results_episode_date_range.json` (precomputed results)

## Remaining: Delete old draft folders

All three folders are gitignored — deletion has no git impact.

```powershell
Remove-Item -Recurse -Force "documentation/ToDo/2026-05-15_Speaker_Mining_Paper"
Remove-Item -Recurse -Force "documentation/ToDo/2026-05-17_Speaker_Mining_Paper"
Remove-Item -Recurse -Force "documentation/ToDo/peer_review_paper"
```

**Precondition:** Confirm that `documentation/archive/paper/main.tex`
is the canonical working paper source.

## Acceptance criteria

- Three draft folders gone
- `documentation/data_reference.md` exists
- `documentation/corpus_selection.md` exists
- `speakermining/src/process/analysis/statistical_tests.py` etc. exist
