# Implementation Status and Open Questions

_Last updated: 2026-05-05_

## What has been done

### Fix A — cross-show episode merging (DONE)
   * **Clarification:** The issue is not resolved. We have matched 2030 episodes from ZDF to fernsehserien.de, but we have lost the connection to the wikidata episodes. Example:
     * Markus Lanz (11. August 2020) with wikidata_id Q99316871
     * Markus Lanz Folge 1417 with fernsehserien_de_id markus-lanz/folgen/1417-folge-1417-1396560 and fernsehserien_de_url https://www.fernsehserien.de/markus-lanz/folgen/1417-folge-1417-1396560
     * Markus Lanz 11.08.2020 with ZDF archiv mention_id ep_b64a7da9c02e
   * Currently, all three of them exist, but Q99316871 is not aggregated to the union. Generally, not a single match seems to have been made with wikidata QID, all data retrieved from wikidata remains unresolved.
   * **Resolution**: Implemented — see Fix A3 below (date+series Wikidata matching).
   * Next actions: We must inspect `data/31_entity_disambiguation/aligned/aligned_episodes.csv` and identify what unresolved instance should still be matched - we have a concrete example above, and we should use it to refine our rules. Any number of unresolved wikidata or ZDF episodes greater than 20 is highly unlikely. Use the test examples, write tests, and iterate until we have sufficient matching. Still: Critically evaluate, we still want precision. The goal is to reduce false negatives while not loosing precision.

File: [speakermining/src/process/entity_disambiguation/episode_alignment.py](../../../../speakermining/src/process/entity_disambiguation/episode_alignment.py)

Changes applied:
1. `_match_fernsehserien_episode()` now accepts a `show_norm` parameter. Before filtering by date, it restricts `fs_metadata` to rows whose `normalize_text(program_name)` equals `show_norm`. Only falls back to the full set if no programme rows are found (handles edge cases where the programme name normalisation yields no match).
   * **Clarification:** Precision is also important: If an episode only exists in one source (e.g. ZDF Archive exclusive or fernsehserien.de exclusive), then we should just leave it unmatched: It truthfully only exists in source. We can still do a second validation pass, look at all unmatched episodes and check which of those could still be matches - but generally: An unmatched episode is not necessarily a bad thing, it may just have one single source.
     * Current status: This is currently correctly implemented.
2. In `build_aligned_episodes()`, a `fs_show_norm_to_id` mapping is pre-computed (`normalize_text(program_name)` → show ID). For each ZDF episode, the longest matching known programme name is found as a substring of `normalize_text(sendungstitel)`, and this is passed as `show_norm` to the matching function.
3. If a ZDF episode gets no FS episode match but the show can be identified, `fernsehserien_de_id_fernsehserien_de` is backfilled with the FS show ID. This ensures Phase 50 can still identify which show the episode belongs to, even without an FS episode counterpart.

**Effect**: After re-running Phase 31, the wrong merge (couchwissen episode matched to Markus Lanz ZDF episode) will no longer occur.
   * **Clarification:** Correct: the wrong merge is resolved. Sadly, we have lost other valid merges in the process. We need to fix this first before we can progress.

### Fix A3 — date-based Wikidata episode matching (DONE 2026-05-05)

File: [speakermining/src/process/entity_disambiguation/episode_alignment.py](../../../../speakermining/src/process/entity_disambiguation/episode_alignment.py)

Changes applied:
1. `_indexed_wikidata_episodes()` now returns two additional indexes: `by_date` (P577 publication date → list of QIDs) and `series_by_qid` (episode QID → P179 series QID). Both indexes are built directly from the raw Wikidata JSON claims.
2. `build_aligned_episodes()` now loads `broadcasting_programs` from `normalized["setup_broadcasting_programs"]` and builds two maps: `series_qid_to_show_id` (Wikidata series QID → FS show ID) and its inverse `fs_show_id_to_series_qids`.
3. In the ZDF episode loop, Wikidata matching now uses **date first, then series filter** as the primary strategy:
   - Extract the ZDF episode date as `"YYYY-MM-DD"`.
   - Look up all Wikidata QIDs that share that date (P577).
   - If the ZDF episode's show can be identified (via `matched_show_norm`), filter date candidates to those whose P179 series QID matches the show's Wikidata series QID.
   - If exactly one candidate survives, match with strategy `date_and_series_wikidata`.
   - If no show filter is available and exactly one date candidate exists overall, match with `date_only_wikidata`.
   - Only then fall back to label-equality matching (`label_wikidata`).

**Effect**: Wikidata episodes (e.g., Q99316871 = Markus Lanz 11. August 2020) are now matched to their ZDF counterparts via `publikationsdatum` + P179 series QID, rather than requiring exact label string equality. The three previously isolated rows for the same episode (Wikidata, FS, ZDF) are now unified under a single `alignment_unit_id`.

### Fix A4 — person alignment FS context propagation (DONE 2026-05-05)

File: [speakermining/src/process/entity_disambiguation/person_alignment.py](../../../../speakermining/src/process/entity_disambiguation/person_alignment.py)

Changes applied:
1. `build_aligned_persons()` now builds `episode_fs_context`: a dict from `alignment_unit_id` → `{fernsehserien_de_id_fernsehserien_de, episode_url_fernsehserien_de, program_name_fernsehserien_de}`, populated from `aligned_episodes`.
2. In the ZDF person loop, when `fs_match_row is None` (episode has no FS guest data), the code now checks if `episode_fs_context` has FS show/episode context for that episode and populates those three columns if so.

**Effect**: ZDF-sourced persons on episodes that exist in FS but have no FS guest data now carry `fernsehserien_de_id_fernsehserien_de` and `episode_url_fernsehserien_de` from the episode alignment, so Phase 50 can correctly assign them to the right show without filtering them out.

### Fix A5 — `episode_id_zdf` propagated to Phase 32 cluster_members (DONE 2026-05-05)

Files: [speakermining/src/process/entity_deduplication/person_deduplication.py](../../../../speakermining/src/process/entity_deduplication/person_deduplication.py), [speakermining/src/process/entity_deduplication/contracts.py](../../../../speakermining/src/process/entity_deduplication/contracts.py)

Changes applied:
- Added `"episode_id_zdf"` to `_PRESERVED_MEMBER_COLUMNS` in `person_deduplication.py`.
- Added `"episode_id_zdf"` to `DEDUP_CLUSTER_MEMBERS_COLUMNS` in `contracts.py`.

**Effect**: `episode_id_zdf` (= the `alignment_unit_id` of the aligned episode for ZDF-sourced persons) is now forwarded through Phase 32 into `dedup_cluster_members.csv`. Phase 50 can use this as a fallback episode key when `episode_url_fernsehserien_de` is unavailable.

### Good Progress, but not fully fixed yet

Still, 1025 unmatched wikidata episodes.
We are also barely propagating any information of these entries to the aligned table:
* When did they air?
* What show did they belong to?

Generally, where are the mainly important wikidata columns? Sure, we should not include all 500+ properties, but we should include information such as show, publication date, duration, etc. - anything that can be used to match it against the other sources.

Generally: It still does not seem like we are treating sources equally. 

An example on 
* Wikidata: Maischberger (March 19th, 2025) (Q133500694)
* Fernsehserien.de: https://www.fernsehserien.de/maischberger-ard/folgen/866-sendung-vom-19-03-2025-1783664

`data/31_entity_disambiguation/aligned/aligned_episodes.csv`
```
alignment_unit_id,wikidata_id,fernsehserien_de_id,mention_id,canonical_label,open_refine_name,entity_class,match_confidence,match_tier,match_strategy,evidence_summary,unresolved_reason_code,unresolved_reason_detail,inference_flag,inference_basis,notes,label_wikidata,label_fernsehserien_de,label_zdf,description_wikidata,description_fernsehserien_de,description_zdf,alias_wikidata,alias_fernsehserien_de,alias_zdf,publikationsdatum_zdf,dauer_zdf,season_zdf,fernsehserien_de_id_fernsehserien_de,program_name_fernsehserien_de,episode_url_fernsehserien_de,episode_title_fernsehserien_de,duration_minutes_fernsehserien_de,description_text_fernsehserien_de,description_source_fernsehserien_de,premiere_date_fernsehserien_de,premiere_broadcaster_fernsehserien_de,normalized_at_utc_fernsehserien_de,normalizer_rule_fernsehserien_de,source_discovered_sequence_fernsehserien_de,source_event_sequence_fernsehserien_de,premiere_date_date_fernsehserien_de,guest_1_name_fernsehserien_de,guest_1_role_fernsehserien_de,broadcast_1_date_fernsehserien_de,broadcast_1_start_time_fernsehserien_de,broadcast_1_end_date_fernsehserien_de,broadcast_1_end_time_fernsehserien_de,broadcast_1_broadcaster_fernsehserien_de,broadcast_1_is_premiere_fernsehserien_de
episode_fs_4e90e66e3d3e,,https://www.fernsehserien.de/maischberger-ard/folgen/866-sendung-vom-19-03-2025-1783664,,Sendung vom 19.03.2025,,episode,0.0,unresolved,fs_episode_only_baseline,fernsehserien_de episode carried forward without deterministic ZDF/Wikidata match,no_candidate,No deterministic ZDF episode or unique Wikidata episode candidate,false,,,,Sendung vom 19.03.2025,,,Episoden,,,,,,,,maischberger-ard,Maischberger,https://www.fernsehserien.de/maischberger-ard/folgen/866-sendung-vom-19-03-2025-1783664,Sendung vom 19.03.2025,,Episoden,,2025-03-19,Das Erste,2026-04-09T09:55:54Z,episode_description_norm_v1,94755,117242,2025-03-19 00:00:00,Sandra Maischberger,Moderation,2025-03-21,00:13,2025-03-21,01:28,3sat,False
episode_wd_da136a4ce1fc,Q133500694,,,Maischberger (19. März 2025),,episode,0.0,unresolved,wikidata_episode_only_baseline,Wikidata episode carried forward without deterministic ZDF/fernsehserien_de match,no_candidate,No deterministic ZDF episode or fernsehserien_de episode candidate,false,,,Maischberger (19. März 2025),,,Sendung der Fernsehtalkshow Maischberger von 2025 (S22E43),,,,,,,,,,,,,,,,,,,,,,,,,,,,,,
```

#### Previous status
Previous state: The last two edits to episode_alignment.py — the FS→Wikidata matching in the unmatched-FS loop and the show-context enrichment in the unmatched-Wikidata loop — were written but not yet syntax-checked because the session limit hit before the check could run.

Next session must start with:

Syntax-check episode_alignment.py (python -c "import ast; ast.parse(open(...).read())")
If clean, re-run Phase 31 and verify the Maischberger case (episode_fs_4e90e66e3d3e + episode_wd_da136a4ce1fc should merge into one row)
   * **Clarification:** Phase 31 was re-run, Maischberger case verified. See below

Next step: 
Proceed to Phase 50 fixes

#### Current state: Stable, but requires cleanup (which is deferred for now)
Phase 31 was re-run, identified issues such as the wrong matches and the missing wikidata matches, such as Maischberger case, are solved and verified.

```
episode_fs_4e90e66e3d3e,Q133500694,https://www.fernsehserien.de/maischberger-ard/folgen/866-sendung-vom-19-03-2025-1783664,,Sendung vom 19.03.2025,,episode,0.8,high,date_and_series_wikidata,fs episode matched to wikidata via date_and_series_wikidata,,,false,,,Maischberger (19. März 2025),Sendung vom 19.03.2025,,Sendung der Fernsehtalkshow Maischberger von 2025 (S22E43),Episoden,,,,,,,,maischberger-ard,Maischberger,https://www.fernsehserien.de/maischberger-ard/folgen/866-sendung-vom-19-03-2025-1783664,Sendung vom 19.03.2025,,Episoden,,2025-03-19,Das Erste,2026-04-09T09:55:54Z,episode_description_norm_v1,94755,117242,2025-03-19 00:00:00,Sandra Maischberger,Moderation,2025-03-21,00:13,2025-03-21,01:28,3sat,False
```

Total stats:
* 4176 unmatched
  * 385 from Wikidata
  * 3788 from fernsehserien.de
  * 4 from ZDF
  * (sum is 4177, no idea why these numbers don't add up to 4176. Maybe a Data Wrangler issue. generally irrelevant)

Generally looks correct.

Still some formal issues:
* mention_id is never filled with the ZDF Archive ID assigned to this episode (e.g. ep_ec3af6e34bfd). Expected result: Every row that has data from a ZDF entry also has that ZDF ID in the `mention_id` field.
* There are no wikidata property columns. In fact, It is possible that this currently writes to cells where it does not belong: entries without match to fernsehserien.de still have their "premiere_date_date_fernsehserien_de" filled with the normalized date, the same same for fernsehserien_de_id_fernsehserien_de.

If there are any questions on any of these issues, ask for clarification.

Generally, these columns require cleanup. For now, this task is deferred, but remains high priority.

#### Ensure sources are truly symmetrical
The recent analysis revealed a critical issue: "Wikidata matching only happens in the ZDF episode loop"
There should be no single-source-loop.
All sources are equal.

The approach for any alignment should look similar like this:
1. Accumulate all episodes from every source.
2. Sort them by show.
3. Within shows: Sort them by time.
4. Using a set of exclusion rules (e.g. hard exclusion rule like "must belong to the same show") and confidence rules (like "similar time", "similar name", "similar guest list", "similar moderator", "similar description" etc.): merge episode entries that describe the same unique epsiode.

Since the current behaviour currently seems to have the same results as the "clean workflow" above, we can keep this as a "future clean-up task". If the current implementation already works exactly like that, we can also mark it as solved. In any case: we should not spent current time on this, but keep it as a high priority task to clean up once all other pressing tasks are implemented.


---

## What still needs to be done (and key questions)

### Fix B — treat all three sources equally as the episode universe

This is more complex than anticipated. The following section documents what we know and where we need clarification before proceeding.

#### Current state

The occurrence matrix in Phase 50 currently uses `episode_metadata_normalized.csv` (the raw fernsehserien.de import) as its episode universe. This means only FS episodes can be columns in the matrix.
   * **Clarification:** This is completely wrong behavior. It should use `data/31_entity_disambiguation/aligned/aligned_episodes.csv`

The user has confirmed: **fernsehserien.de HAS those ~400 episodes, but just does not have guest data for them. ZDF Archive has guest data for those ~400 episodes.**
   * **Clarification:** Correct.

So the episode universe question is not about which episodes EXIST but about which episodes have USABLE GUEST DATA from which source.
   * **Clarification:** Both. Some episodes only exist in one source. Some exist in multiple, but with different data: Maybe source A has guest and description, while B has better coverage of publications, and C has some additional information on who directed and produced the episode. We are looking for the union of this information.

#### The actual data flows for guest data

There are two sources of guest data in the pipeline:

| Source | Where it enters | What it covers |
|---|---|---|
| ZDF Archive (`persons.csv`) | Phase 31 person alignment | Guest mentions extracted from ZDF metadata text (all 2,033 ZDF episodes) |
| fernsehserien.de (`episode_guests_normalized.csv`) | Phase 31 person alignment | Guest lists from FS for ~1,600–1,800 episodes that FS has guest data for |
   * **Clarification:** If that is the case, that's once again completely wrong. What we should be doing is taking `data/31_entity_disambiguation/aligned/aligned_persons.csv` and processing the data from there. For persons specifically, we also have the absolutely authoritative `data/31_entity_disambiguation/manual/reconciled_data_summary.csv`, which should contain most persons AND also be authoritatively manually matched against wikidata, so most of these persons are also matched with the Wikidata QIDs. Those two are the authoritative sources of persons. 

The ~400 fernsehserien.de episodes WITHOUT guest data in FS still have guest data in ZDF Archive (persons.csv). Currently that ZDF guest data IS fed into Phase 31 — it just isn't surfacing correctly in the occurrence matrix.
   * **Clarification:** Correct. Phase 5 Analysis should use use `data/31_entity_disambiguation/aligned/aligned_episodes.csv` to get the episode list, and then create the matrix with their guests. These guests can be deduplicated over `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` (and as a fallback, if an ID is missing from that one: check if it exists in `data/31_entity_disambiguation/aligned/aligned_persons.csv`). The result should be a list of unique episodes x a list of unique persons, a unique guest x person occurrence matrix.

#### Where the ~400 episodes' guest data is getting lost

The ZDF guest data for episodes enters the pipeline in Phase 31 via `aligned_persons.csv`. The relevant columns:
- `episode_id_zdf` — ZDF episode ID (= alignment_unit_id of the episode in aligned_episodes)
- `fernsehserien_de_id` — FS episode URL (set when the ZDF episode was matched to an FS episode in Phase 31)
   * **Clarification:** For "persons", this should be their indivudal ID as a person. For example, https://www.fernsehserien.de/markus-lanz/filmografie describes the person "Markus Lanz" on fernsehserien.de
   * **Clarification:** Technically, any fernsehserien_de_id should only be ID part, so the slug, e.g. for an episode "markus-lanz/folgen/1417-folge-1417-1396560" from "https://www.fernsehserien.de/markus-lanz/folgen/1417-folge-1417-1396560", or for a person "markus-lanz" from "https://www.fernsehserien.de/markus-lanz/filmografie"
     * **Clarification:** If this is fixed, this must also be fixed in the aligned_episodes.csv and all other such files. Currently, this issue is wrong everywere and propagated and assumed everywhere onwards. Touching this may lead to unforseen issues and maybe should be deferred for now. 
- `fernsehserien_de_id_fernsehserien_de` — FS show ID (e.g., "markus-lanz")
- `episode_url_fernsehserien_de` — FS episode URL (same as fernsehserien_de_id)
   * **Clarification:** As above: Only here should be the the full URL of the episode.

**For episodes with FS guest data**: the FS guest data fills `episode_url_fernsehserien_de`, `fernsehserien_de_id_fernsehserien_de`, etc. Phase 32 propagates these to `cluster_members`.
   * **Clarification:** We must always propagate all data to all future steps. We must never drop data. 

**For episodes without FS guest data** (the ~400): `episode_url_fernsehserien_de` and `fernsehserien_de_id_fernsehserien_de` in `aligned_persons.csv` may be **empty**, even though `fernsehserien_de_id` (the FS episode URL) is filled via the episode alignment.
   * **Clarification:** Correct. This is why we need the union of all sources:
     * Person A_X is guest of episode 1_X in source X
     * episode 1_Y is without guest data in source Y
     * Once we map episode 1_X to 1_Y, we also know that A_X was guest of episode 1_Y - since they both are reflections of the same episode: Episode 1.

If `episode_url_fernsehserien_de` is empty in cluster_members for ZDF-sourced persons on these ~400 episodes, then `build_person_catalogue()` in Phase 50 filters them out:
```python
in_scope_members = member_df[
    member_df["show_id"].isin(in_scope_show_ids) &     # show_id = fernsehserien_de_id_fernsehserien_de
    member_df["episode_url"].isin(in_scope_episode_urls)  # episode_url = episode_url_fernsehserien_de
].copy()
```
   * **Clarification:** Very wrong behaviour. Any source should suffice. We are looking for aligned unions, not some authoritative source.

#### Open question for the user

**Before implementing Fix B, we need to understand what `person_alignment.py` actually puts in `aligned_persons.csv` for ZDF-sourced persons on episodes without FS guest data.**

Specifically:
- Is `episode_url_fernsehserien_de` filled (from the episode's FS URL) or empty for these persons?
- Is `fernsehserien_de_id_fernsehserien_de` filled (from the episode's FS show ID) or empty?

* **Clarification:** Example data below. pm_65ee23ef1422 is an example a guest to an episode that exists in both sources, but only has guest data in one (ZDF). Both `episode_url_fernsehserien_de` and `fernsehserien_de_id_fernsehserien_de` seem to be empty.

```aligned_persons.csv
alignment_unit_id,wikidata_id,fernsehserien_de_id,mention_id,canonical_label,open_refine_name,entity_class,match_confidence,match_tier,match_strategy,evidence_summary,unresolved_reason_code,unresolved_reason_detail,inference_flag,inference_basis,notes,label_wikidata,label_fernsehserien_de,label_zdf,description_wikidata,description_fernsehserien_de,description_zdf,alias_wikidata,alias_fernsehserien_de,alias_zdf,episode_id_zdf,mention_id_zdf,name_zdf,mention_category_zdf,beschreibung_zdf,source_text_zdf,source_context_zdf,parsing_rule_zdf,confidence_zdf,confidence_note_zdf,fernsehserien_de_id_fernsehserien_de,program_name_fernsehserien_de,episode_url_fernsehserien_de,guest_name_fernsehserien_de,guest_role_fernsehserien_de,guest_description_fernsehserien_de,guest_url_fernsehserien_de,guest_image_url_fernsehserien_de,guest_order_fernsehserien_de,normalized_at_utc_fernsehserien_de,normalizer_rule_fernsehserien_de,source_discovered_sequence_fernsehserien_de,source_event_sequence_fernsehserien_de,entity_id_wikidata,entity_type_wikidata
pm_65ee23ef1422,,https://www.fernsehserien.de/markus-lanz/folgen/250-folge-250-sondersendung-zum-tod-von-loriot-518168,pm_65ee23ef1422,Hellmuth KARASEK,Hellmuth KARASEK,person,0.0,unresolved,episode_context_name_exact,no candidate above threshold,no_candidate,No deterministic same-episode guest or unique Wikidata person candidate,false,,,,,Hellmuth KARASEK,,,"Journalist, Buchautor und Theaterwissenschaftler",,,,ep_ee61414d1a21,pm_65ee23ef1422,Hellmuth KARASEK,guest,"Journalist, Buchautor und Theaterwissenschaftler","Hellmuth KARASEK (Journalist, Buchautor und Theaterwissenschaftler)","den Studiogästen Jürgen FLIEGE (Theologe und Talkshowmoderator), Jutta DITFURTH (Politikerin und Buchautorin ""Durch unsichtbare Mauern. Wie wird so eine links?""), Ingrid VAN BERGEN (Schauspielerin), Ingo APPELT (Comedian), Hellmuth KARASEK (Journalist, Buchautor und Theaterwissenschaftler), Katja BOGDANSKI (ehemalige Schauspielerin, Darstellerin von Dicki Hoppenstedt im Sketch ""Weihnachten bei Hoppenstedts"" von Loriot, heute Verkaufsleiterin im Außendienst), Michael SCHENK (Arzt, anthroposophische Klinik, Berlin); Themen: Tod von Vicco von Bülow (Loriot), gemeinsamer Rückblick auf das Leben und Werk des großen Humoristen, Diskussion über einige von Jürgen Fliege auf den Markt gebrachten Produkte, unter anderem die ""Fliege Essenz"" und den Profit, den er scheinbar daraus schlägt; nutzt Jürgen Fliege seine Prominenz aus, um Profit aus hilfesuchenden Menschen zu schlagen?",single_parenthetical,0.95,single name directly tied to parenthetical description,,,,,,,,,,,,,,,
```

```aligned_episodes.csv
alignment_unit_id,wikidata_id,fernsehserien_de_id,mention_id,canonical_label,open_refine_name,entity_class,match_confidence,match_tier,match_strategy,evidence_summary,unresolved_reason_code,unresolved_reason_detail,inference_flag,inference_basis,notes,label_wikidata,label_fernsehserien_de,label_zdf,description_wikidata,description_fernsehserien_de,description_zdf,alias_wikidata,alias_fernsehserien_de,alias_zdf,publikationsdatum_zdf,dauer_zdf,season_zdf,fernsehserien_de_id_fernsehserien_de,program_name_fernsehserien_de,episode_url_fernsehserien_de,episode_title_fernsehserien_de,duration_minutes_fernsehserien_de,description_text_fernsehserien_de,description_source_fernsehserien_de,premiere_date_fernsehserien_de,premiere_broadcaster_fernsehserien_de,normalized_at_utc_fernsehserien_de,normalizer_rule_fernsehserien_de,source_discovered_sequence_fernsehserien_de,source_event_sequence_fernsehserien_de,premiere_date_date_fernsehserien_de,guest_1_name_fernsehserien_de,guest_1_role_fernsehserien_de,broadcast_1_date_fernsehserien_de,broadcast_1_start_time_fernsehserien_de,broadcast_1_end_date_fernsehserien_de,broadcast_1_end_time_fernsehserien_de,broadcast_1_broadcaster_fernsehserien_de,broadcast_1_is_premiere_fernsehserien_de
ep_ee61414d1a21,,https://www.fernsehserien.de/markus-lanz/folgen/250-folge-250-sondersendung-zum-tod-von-loriot-518168,,Markus Lanz 23.08.2011,,episode,0.92,high,date_backbone_plus_title_signals,date-aligned fs episode,,,false,,,,Folge 250 (Sondersendung zum Tod von Loriot),Markus Lanz 23.08.2011,,Episoden,"22:52:51 - 00:08:58 076'07 Interview Markus LANZ mit den Studiogästen Jürgen FLIEGE (Theologe und Talkshowmoderator), Jutta DITFURTH (Politikerin und Buchautorin ""Durch unsichtbare Mauern. Wie wird so eine links?""), Ingrid VAN BERGEN (Schauspielerin), Ingo APPELT (Comedian), Hellmuth KARASEK (Journalist, Buchautor und Theaterwissenschaftler), Katja BOGDANSKI (ehemalige Schauspielerin, Darstellerin von Dicki Hoppenstedt im Sketch ""Weihnachten bei Hoppenstedts"" von Loriot, heute Verkaufsleiterin im Außendienst), Michael SCHENK (Arzt, anthroposophische Klinik, Berlin); Themen: Tod von Vicco von Bülow (Loriot), gemeinsamer Rückblick auf das Leben und Werk des großen Humoristen, Diskussion über einige von Jürgen Fliege auf den Markt gebrachten Produkte, unter anderem die ""Fliege Essenz"" und den Profit, den er scheinbar daraus schlägt; nutzt Jürgen Fliege seine Prominenz aus, um Profit aus hilfesuchenden Menschen zu schlagen? (O-Ton).",,,,23.08.2011,76'08,"Markus Lanz, Staffel 4",markus-lanz,Markus Lanz,https://www.fernsehserien.de/markus-lanz/folgen/250-folge-250-sondersendung-zum-tod-von-loriot-518168,Folge 250 (Sondersendung zum Tod von Loriot),,Episoden,,2011-08-23,ZDF,2026-04-08T13:55:53Z,episode_description_norm_v1,2688,9871,2011-08-23 00:00:00,,,,,,,,
```

This determines whether the problem is in Phase 31 person alignment, Phase 32 propagation, or Phase 50 filtering.

We have not read `person_alignment.py` yet. This file likely contains the answer.

#### Proposed investigation step

Read `person_alignment.py` and then inspect actual `aligned_persons.csv` rows for a known Markus Lanz episode that has ZDF guest data but NO FS guest data. Confirm which columns are populated.

---

### Fix B implementation plan (pending clarification)

Assuming the person alignment sets `fernsehserien_de_id` (FS episode URL) but NOT `episode_url_fernsehserien_de` / `fernsehserien_de_id_fernsehserien_de` for persons on FS-guest-empty episodes, the fix chain is:

#### B0: Read person_alignment.py to confirm the above

#### B1: Fix Phase 32 — propagate `episode_id_zdf` to cluster_members

**Files**: `entity_deduplication/person_deduplication.py`, `entity_deduplication/contracts.py`

Add `"episode_id_zdf"` to `_PRESERVED_MEMBER_COLUMNS` and `DEDUP_CLUSTER_MEMBERS_COLUMNS`. This makes `episode_id_zdf` (= the aligned_episodes `alignment_unit_id`) available in Phase 50 for all person–episode rows.

#### B2: Fix Phase 50 `build_person_catalogue()` — use `alignment_unit_id` as episode key

**File**: `speakermining/src/process/analysis/occurrence_matrix.py`

Replace the `episode_meta` parameter with `aligned_episodes` (loaded from `aligned_episodes.csv`).

Build `episode_auid` for each cluster member row:
```python
fs_url_to_ep_auid = aligned_episodes[
    aligned_episodes["fernsehserien_de_id"].str.strip() != ""
].set_index("fernsehserien_de_id")["alignment_unit_id"].to_dict()

# For each member_df row:
# 1st choice: join on FS episode URL → alignment_unit_id
# 2nd choice: episode_id_zdf IS the alignment_unit_id for ZDF-sourced rows
member_df["episode_auid"] = (
    member_df["fernsehserien_de_id"].map(lambda x: fs_url_to_ep_auid.get(x, ""))
    .where(lambda s: s != "", member_df.get("episode_id_zdf", ""))
)
```

Build `in_scope_episode_ids` (= alignment_unit_id values for in-scope shows):
```python
in_scope_episode_ids = set(
    aligned_episodes[
        aligned_episodes["fernsehserien_de_id_fernsehserien_de"].isin(in_scope_show_ids)
    ]["alignment_unit_id"]
)
```

Filter `in_scope_members` by `episode_auid.isin(in_scope_episode_ids)`.

#### B3: Fix Phase 50 occurrence matrix — use `alignment_unit_id` as column key

**Files**: `occurrence_matrix.py`, `50_analysis.ipynb`

- `guest_pairs["episode_auid"]` instead of `guest_pairs["fernsehserien_de_id"]`
- Pivot on `episode_auid`
- `ep_order["alignment_unit_id"]` as the episode column order
- Fix the notebook bug: `ordered_episodes = list(ep_order["alignment_unit_id"])` — remove the `if e in matrix_num.columns` filter that was silently dropping episodes

#### B4: Fix notebook cell bb0bb166 — join episode_appearances on `episode_auid`

After building `episode_appearances`, rename `episode_auid` → `fernsehserien_de_id` so downstream cells (per-show stats, co-occurrence, export, property analysis) remain unchanged.

#### B5: Fix `meta_analysis.py` — use correct show column

`compute_per_show_coverage` currently groups by `fernsehserien_de_id` which in the new schema is the FS episode URL (not the show ID). Change to use `fernsehserien_de_id_fernsehserien_de` from `episode_meta_df`.

---

## Notebook bug found (independent of above)

In `50_analysis.ipynb`, cell `a3362316`, the `ordered_episodes` variable is built with a filter that silently drops episodes:

```python
# BUG: filters out episodes with no guest appearances in cluster_members
ordered_episodes = [e for e in ep_order["episode_url"] if e in matrix_num.columns]
```

Should be:
```python
# CORRECT: all in-scope episodes appear as columns (zero-filled if no guests)
ordered_episodes = list(ep_order["episode_url"])
```

This filter was what caused the occurrence matrix to have 1,596 columns instead of the expected 2,242+. The `build_occurrence_matrix()` function in `occurrence_matrix.py` already has the correct version (`ordered_episodes = list(ep_order["episode_url"])`), but the notebook cell duplicates the logic with the bug.

---

## Questions for the user

1. **Person alignment for FS-guest-empty episodes**: For a Markus Lanz ZDF episode that has ZDF guest data but no fernsehserien.de guest data — does `aligned_persons.csv` have `episode_url_fernsehserien_de` and `fernsehserien_de_id_fernsehserien_de` filled for those person rows? Or are they empty?
  * **Clarification:** answered above. both empty

2. **Source equality interpretation**: When we say "all three sources are equal", do we mean:
   a. Each source's guest lists are equally valid and should be merged (union), OR
     * **Clarification:** yes.
   b. Each source's episode list is equally authoritative (so episodes from all sources appear in the occurrence matrix), AND their guest data is merged?
     * **Clarification:** yes. both are correct. We are looking for a disambiguated, deduplicated episode list, each with their disambiguated, deduplicated guest list. Data from all sources equally contributes to this. unclear matches are left for further inspection.

3. **ZDF-only person detection**: Persons detected from ZDF Archive (not via FS guest data) — are these currently flowing into `aligned_persons.csv` and `dedup_cluster_members.csv`, or is the ZDF person data being used only for entity disambiguation but not for the occurrence matrix?
  * **Clarification:** All data should be used throughout all downstream phases. ZDF archive data is vital and provides much context, we must never drop this. All sources are equal.

4. **Execution order**: After applying Fix A and re-running Phase 31, should we immediately also re-run Phase 32 and validate before implementing Fix B? Or implement all fixes first and run everything once at the end?
  * **Clarification:** First implement everything, I'll run and inspect outputs in between (as I did to document this clarification step.)
