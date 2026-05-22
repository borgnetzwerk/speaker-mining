# T02: Remove _v3_archive — DEFERRED

**Condition to re-open:** V4 Wikidata candidate generation is at least 80% complete and stable enough that V3 is no longer needed as a fallback. Current V4 completion: ~20%.

## What will need to happen (when the time comes)

1. Run `Select-String -Path speakermining/test/ -Pattern "_v3_archive" -Recurse` — any test importing from _v3_archive must be removed or rewritten against v4
2. Check that no active notebook imports from `_v3_archive`
3. Remove `speakermining/src/process/candidate_generation/wikidata/_v3_archive/` (18 files) and `speakermining/src/process/notebooks/archive/21_candidate_generation_wikidata_v3_archive.ipynb`
4. `git rm -r` the above, commit

**Do not attempt this until V4 is production-stable.**
