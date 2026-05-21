## Current finding

The current occurrence-matrix build was dropping episode columns whenever an episode had no guest rows in `dedup_cluster_members.csv`. That is not acceptable for this investigation, because we need the full episode universe preserved even when a row count is zero.

### What we know so far

- `data/10_mention_detection/episodes.csv` still contains the raw Markus Lanz episode set, with 2,033 unique `episode_id` rows in the current file.
- `data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv` contains 2,242 Markus Lanz episode URLs.
- `data/32_entity_deduplication/dedup_cluster_members.csv` currently yields 1,596 unique Markus Lanz episode URLs with guest rows, and the current `data/50_analysis/markus_lanz/occurrence_matrix.csv` has exactly 1,596 episode columns.
- That means the matrix was silently shrinking to the subset of episodes that had at least one guest row.
- The couchwissen issue is separate and documented in [issue.md](issue.md); it is a wrong-merge / wrong-episode-assignment problem, not the reason for the Markus Lanz episode-column loss.

### Required rule

- No occurrence matrix may drop in-scope episode columns.
- If an episode has no guest rows, it must still appear as a zero-filled column so the absence is visible and can be investigated.

### Next verification target

- Regenerate the occurrence matrices after the code change and confirm that the episode column count matches the in-scope episode set, including zero-guest episodes.
  - Update: The change was made, the notebook ran again, but it seems the per_show_statistics are still unchanged: still 1596 Markus Lanz episodes.
- Then compare the previously missing Markus Lanz episodes against the regenerated matrix to identify which ones are still structurally absent versus simply zero-filled.
  - **Clarification:** zero-filled may also be an indicator of an issue. We must systematically double-check from our sources - that might just be the cause

### Vital information:
There ARE ~400 empty markus lanz epsiodes: ONLY in fernsehserien.de
This seems to confirm a prior suspicion: 
* We also note that the Episodes in every analysis are always using the fernsehserien.de ID of that episode. Since we do have a alignment_unit_id for every episode, but not a fernsehserien_de_id for every episode, we should always use alignment_unit_id, or we risk loosing episodes.

It seems EXTREMELY likely that we are somehow percieving the fernsehserien.de source as authorative on episodes. This is 100 % false:
* All three sources are equal:
  * ZDF Archiv
  * Wikidata
  * fernsehserien.de

If we want a list of all episodes, we are looking for union of what those three sources have on episodes:
* All ZDF Archiv episodes
* All Wikidata episodes
* All fernsehserien.de episodes

combined, then deduplicated, thats it.

This should give us back our 2000 + Markus Lanz episodes.
We must fix these issues accoridngly in our phase 31_entitiy_disambiguation and then let our Analysis retrieve the correct data from there.