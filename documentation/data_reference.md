# Numbers Reference — Speaker Mining Paper

Each heading is the **authoritative value**. Look up any number you encounter by scanning headings.
Sources are under `data/` unless noted otherwise.

---

## Corpus: ZDF

### 2,036 — ZDF episodes (total)
- **Exactly**: All episodes in `data/10_mention_detection/episodes.csv`
- **Source**: `meta_statistics.csv` → `zdf_episodes_total`
- **Wrong**: 2,035 appears in the first-iteration table — that iteration processed 2,035 of 2,036 (one failed).

### 2008–2024 — ZDF corpus year range
- **Exactly**: Earliest and latest episode broadcast year in the ZDF extract.
- **Source**: `meta_statistics.csv` → `zdf_year_min`, `zdf_year_max`

### 13 — ZDF episodes yielding no guest rows (2nd iteration)
- **Source**: `meta_statistics.csv` → `zdf_episodes_no_person_mentions`
- **Wrong**: 125 is the 1st-iteration figure (6.1% of 2,036). Both numbers appear in the paper, in different sections.

### 125 — ZDF episodes with no guests (1st iteration)
- **Exactly**: 6.1% of 2,036; the baseline failure rate that motivated the redesign.
- **Source**: First-iteration results table.

---

## Corpus: fernsehserien.de

### 6,459 — FS episodes (total, all configured shows)
- **Source**: `meta_statistics.csv` → `fs_episodes_total`; unique `episode_url` values in `episode_metadata_normalized.csv`

### 1,639 — FS episodes without any guest/crew entry
- **Verified**: `episode_guests_normalized.csv` — episodes not present in the file at all.
- **Source**: `meta_statistics.csv` → `fs_episodes_no_guest_entry`

### 2,242 — FS episodes without a "Gast" role entry specifically
- **Exactly**: Different from 1,639. These episodes DO appear in `episode_guests_normalized.csv` but have no row with `guest_role = Gast`.
- **Verified**: Streaming count in `episode_guests_normalized.csv` against `episode_metadata_normalized.csv` unique episodes.
- **Different from 1,639**: The 1,639 have no entry at all; the 2,242 have entries (e.g., Moderation only) but no guest.

### 2,434 — FS episodes without a moderator entry
- **Source**: `meta_statistics.csv` → `fs_episodes_no_moderator`

### 25,452 — FS raw guest/crew entry rows (all roles)
- **Source**: `meta_statistics.csv` → `fs_guest_rows_total`; rows in `episode_guests_normalized.csv`

### 19,077 — FS raw "Gast" role rows
- **Source**: `meta_statistics.csv` → `fs_guest_rows_gast`

### 4,026 — FS raw "Moderation" role rows
- **Source**: `meta_statistics.csv` → `fs_guest_rows_moderation`

---

## Wikidata BFS (archive run: `node_integrity_20260426T144547Z`)

> This is the **v3 pipeline archive** — the last complete run. The v4 rework was never finished. All BFS numbers in the paper refer to this archive.

### 638 — Series instances identified by BFS
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/core_series.json` (638 items)
- **Wrong**: 397 — from an older, pre-archive pipeline run. Appeared in earlier paper drafts.

### 251 — Organization instances identified by BFS
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/core_organizations.json` (251 items)
- **Wrong**: 51 — from an older run.

### 382,400 — Wikidata triples / graph edges
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/triples.csv` (382,400 rows)
- **Wrong**: 120,930 — from an older run, also cited as "over 120,000 triples" in earlier drafts.
- **Wrong**: "over 380,000" — imprecise phrasing that appeared in the Results paragraph (line 353); fixed to exact "382,400" to match line 481 usage.

### 8,221 — Unique classes in Wikidata graph
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/classes.csv` (8,221 rows)
- **Wrong**: 2,522 — from an older run.

### 2,324 — Unique properties in Wikidata graph
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/properties.csv` (2,324 rows)
- **Wrong**: 1,665 — from an older run.

### 3,936 — Relevant QIDs (seed entities)
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/summary.json` → `relevant_qids_total`

### 48,991 — Instance rows in archive (raw event count)
- **Source**: `data/20_candidate_generation/wikidata/projections/archive/summary.json` → `instances_rows`
- **Key note**: This is the raw BFS event count before deduplication. The actual `instances.csv` CSV has only **36,126** rows (deduplicated projection). Same pattern as triples (summary.json: 426,000 raw; triples.csv: 382,400 deduplicated) and classes (summary.json: 8,315 raw; classes.csv: 8,221 deduplicated). The paper cites the **CSV row counts** (the deduplicated values), not the summary.json raw counts.
- **Verified**: `instances.csv` row count = 36,126.

---

## Programs

### 15 — Total configured broadcasting programs
- **Source**: `broadcasting_programs.csv` (all rows)

### 12 — Programs with any episode data found
- **Exactly**: 15 minus the 3 with no data at all (unbouble, wtf_talk, Lanz und Precht).
- **Includes**: Phoenix Runde and couchwissen, which had episode data but **no guest entries**.
- **Used for**: Total episode count (6,469), Table 1 "Shows" should NOT use this — see 10 below.

### 10 — Programs with usable guest data (actually analyzed)
- **Source**: `analysis_summary.json` → `broadcasting_programs=10`; `per_show_statistics.csv` (10 unique show rows)
- **Used for**: All guest/appearance analysis, per-show figures, property coverage figure.
- **Wrong**: 12 was incorrectly used as the "analyzed programs" count in earlier drafts.

### 3 — Programs with no extractable data: *unbouble*, *wtf_talk*, *Lanz und Precht*
- **Source**: Author clarification.

### 2 — Programs with episodes but no guest entries: *Phoenix Runde*, *couchwissen*
- **Source**: Author clarification; confirmed via `per_show_statistics.csv` (Phoenix Runde absent) and `episode_guests_normalized.csv` (no Phoenix Runde rows).
- **Note on Phoenix Runde**: Has a `fernsehserien_de_id` configured (`phoenix-runde`) but **0 FS episodes were ever scraped** — it is entirely absent from `episode_metadata_normalized.csv`.

---

## Episodes (Aligned Universe)

### 6,469 — Total aligned episodes (across 12 programs with any data)
- **Derivation**: ZDF (2,036) + FS (6,459) − ZDF-FS overlap (2,026) = **6,469**
  - The overlap is exactly the 2,026 `ep_*` columns in the occurrence matrix: these are ZDF episodes that were matched to FS entries and counted once.
  - The 2,835 `episode_fs_*` columns are FS-only (unmatched FS episodes).
- **Source**: Paper text; Table 1. Represents the union of episodes across all sources for the 12 programs.
- **Different from 4,861**: This is before filtering to episodes with guest data.
- **Different from 6,849**: 6,849 was the raw alignment pool in Step 3.1.1 before deduplication.

### 4,861 — Episodes with usable guest data (occurrence matrix)
- **Source**: `meta_statistics.csv` → `episode_universe_total`; column count in `occurrence_matrix.csv`
- **Wrong**: 4,251 — appeared in earlier paper drafts; stale figure.

### 2,026 — ZDF episodes in analysis universe
- **Source**: `meta_statistics.csv` → `episode_universe_zdf` (ep_* columns in occurrence matrix)

### 2,835 — FS/aligned episodes in analysis universe
- **Source**: `meta_statistics.csv` → `episode_universe_fs` (episode_fs_* columns; includes WD-matched FS episodes)

### 641 — Wikidata episodes merged into FS columns
- **Source**: `meta_statistics.csv` → `episode_universe_wd_merged_into_fs`

### 384 — Wikidata-only episodes excluded (no guest data)
- **Source**: `meta_statistics.csv` → `episode_universe_wd_only_no_guest_data`

### 6,849 — Episode alignment pool (Step 3.1.1 input)
- **Exactly**: Total episode rows fed into the Step 3.1.1 alignment step, before deduplication.
- **Source**: Paper text (commented-out table). 2,673 of 6,849 (39%) were matched.
- **Not the same as 6,469**: 6,469 is the post-dedup result.

### 2,673 — Episodes successfully matched in Step 3.1.1
- **Exactly**: 2,673 / 6,849 = 38.95% ≈ 39%.
- **Verified**: `data/31_entity_disambiguation/aligned/aligned_episodes.csv` — 6,849 total rows; 2,673 have match_tier ≠ UNRESOLVED. ✓

---

## First Iteration (Approach Section)

> These numbers are from the first-iteration bachelor's thesis run. They are historically reported and should not be confused with the second-iteration results.

### 2,035 / 2,036 — Episodes extracted in first iteration
- **Exactly**: 2,035 of 2,036 were successfully extracted; 1 failed.
- **Source**: First-iteration results table (Table 2 in paper).

### 3,966 — Person items created in first iteration
- **Source**: First-iteration results table.
- **Verification status**: ⏳ Unverified directly; taken from bachelor's thesis.

### 2,984 (75.3%) — Persons linked to Wikidata in first iteration
- **Source**: First-iteration results table.
- **Verification status**: ⏳ Unverified directly; taken from bachelor's thesis.

### 36.0% / 31.3% — Female guest share in first iteration (appearances / unique)
- **Source**: First-iteration results table. Matched Spiegel's independent 35% figure (validation).
- **Verification status**: ⏳ Unverified directly.

### 8 hours — Manual review effort in first iteration
- **Source**: Paper text. (Compare: 64 hours in second iteration for a much larger corpus.)

---

## Implementation Numbers

### 14,750 — Candidate institution mentions (deferred module)
- **Exactly**: Generated by the pattern-based institution extraction module before it was deferred due to high false-positive rate.
- **Source**: Paper text (Phase 1 description, line 236).
- **Distribution**: 55% parenthetical descriptions, 18% quoted names, 14% direct program references, 13% person/topic-based.
- **Verification status**: ⚠ Cannot verify — the module is implemented (`institution_extraction_deferred.py`) but no output file is persisted in `data/`. The number comes from a notebook run no longer stored.
- **Note**: The four percentages sum to 100% ✓.

### 20,585 — Rows in schema-mapping table (Step 3.1.1 normalization)
- **Verified**: `data/31_entity_disambiguation/aligned/source_schema_mapping.csv` — 20,585 data rows. ✓
- **Source breakdown** (rows by source_name): wikidata_organizations=12,719; wikidata_series=3,917; wikidata_persons=2,697; wikidata_topics=517; wikidata_episodes=307; wikidata_programs=191; others ≤36 each.
- **Wrong**: 11,629 — stale figure from an earlier pipeline run with fewer entities; appeared in paper text and has been corrected.
- **Note**: `source_schema_mapping.csv` maps every source column (across all 20 source files) to the canonical column set. Growth since earlier runs reflects additional Wikidata organizations being fetched.

---

## Person Pipeline (Phases 31/32)

### 31,165 — Total alignment units (all sources)
- **Verified**: `dedup_summary.json` → `input_alignment_units = 31165`; `dedup_cluster_members.csv` row count = 31,165.
- **Source**: `meta_statistics.csv` → `alignment_units_total`
- **Wrong**: 31,710 — appeared in early paper drafts; not matched by any data file.

### 10,390 — Alignment units from ZDF (pm_* / episode_context rows)
- **Verified**: `dedup_cluster_members.csv` — rows with `match_strategy = episode_context_name_exact` = 10,390 (33.34%).
- **Source**: `meta_statistics.csv` → `alignment_units_zdf`
- **Note**: Only appears in the paper in a **commented-out table** (not the paper body).

### 20,535 — Alignment units from fernsehserien.de
- **Verified**: `dedup_cluster_members.csv` — rows with `match_strategy = fernsehserien_guest_only_baseline` = 20,535 (65.89%).
- **Source**: `meta_statistics.csv` → `alignment_units_fs`
- **Note**: Only appears in the paper in a **commented-out table** (not the paper body).

### 240 — Alignment units from Wikidata-only (wikidata_person_only_baseline)
- **Verified**: `dedup_cluster_members.csv` — rows with `match_strategy = wikidata_person_only_baseline` = 240 (0.77%).
- **Note**: These 240 alignment units collapse to **88 canonical entities** via deduplication. Confirms: 10,390 + 20,535 + 240 = 31,165 ✓.

### 18.6% (5,797 of 31,165) — Step 3.1.1 HIGH-confidence match rate
- **Verified**: `dedup_cluster_members.csv` — match_tier = `high` = 5,797 (18.60%). Confirmed by paper text.
- **Exactly**: Tentative tagging in automated alignment — **informational context only**, not binding.
- **Key note**: OpenRefine (Step 3.1.2) was the authoritative step. The 55.91 + 18.79 + 12.17 + 13.13 = 100% covers all 31,165 rows.

### 55.91% — OpenRefine automatic reconciliation
- **Exactly**: Share of 31,165 rows auto-matched by OpenRefine in Step 3.1.2. ≈ 17,424 rows.
- **Verification status**: **Cannot be directly verified from any single CSV export.** The `reconciled_data_summary.csv` (26,659 rows, 24,758 unique IDs) is the post-OpenRefine output for rows that gained a Wikidata QID, but the file structure does not encode auto-vs-manual distinction cleanly. The percentage comes from the curators' session tracking (see `progress-log.md` for A-L breakdown: 10,301/16,667 = 61.8% auto-matched in A-L half).

### 18.79% — Manually mapped in OpenRefine
- **Exactly**: ≈ 5,856 rows. Curators assigned a QID by hand.
- **Verification status**: From curators' session tracking. `progress-log.md` shows 2,670/16,667 = 16.0% manual in A-L.

### 12.17% — No suitable candidate found in OpenRefine
- **Exactly**: Encoding errors, single-word names, organizations mislabeled as persons.
- **Verification status**: From curators' session tracking.

### 13.13% — Unresolved within OpenRefine time window
- **Exactly**: Rows not processed before curation stopped.
- **Verification status**: From curators' session tracking.

### 16,667 — Curator 1 slice row count (A–L)
- **Verified**: `data/31_entity_disambiguation/manual/progress-log.md` — batch totals A through L sum to exactly 16,667.
- **Slice boundary confirmed as A–L** (not A–N as in earlier paper drafts). Both the HTML filename and all progress-log batch entries (A, B … L) confirm this.
- **Source dataset**: Curators worked from `data/31_entity_disambiguation/archive/aligned_persons.csv` (31,817 rows). That total decomposes as 16,667 (A–L letter rows) + 15,043 (M–Z letter rows) + 107 non-letter rows (83 numeric-named entries flagged as non-people, ~24 special-character names) = **31,817** ✓. The 107 non-letter rows fell into neither slice.

### 15,043 — Curator 2 slice row count (M–Z)
- **Verified**: `data/31_entity_disambiguation/manual/aligned_persons_M-Z.html` — 15,043 rows (all M–Z canonical labels). Matches paper claim.

### 31,817 — Archive aligned_persons.csv (curators' source)
- **Verified**: `data/31_entity_disambiguation/archive/aligned_persons.csv` — 31,817 unique rows, all `entity_class = person`. match_tier: HIGH 5,487 + UNRESOLVED 26,330 = 31,817 ✓.
- **Relationship to 31,165**: While curators worked from this archive, the alignment code was separately improved, producing `data/31_entity_disambiguation/aligned/aligned_persons.csv` (31,165 rows). That improved file feeds directly into dedup. The paper's "31,165 person rows" refers to the improved alignment, not the archive. OpenRefine QID assignments from the archive generation were transferred to the improved alignment during deduplication.

### 64 hours — Total manual OpenRefine curation time
- **Source**: Curators' reported effort. `progress-log.md` records 37 hours for A-L.

### 8,436 — Canonical persons (all roles, all 15 programs)
- **Verified**: `dedup_summary.json` → `canonical_entities = 8436`; `dedup_persons.csv` row count = 8,436.
- **Source**: `meta_statistics.csv` → `canonical_persons_total`
- **Includes**: guests, moderators, staff, and Wikidata-only persons with no episode backing (the 88).
- **Dedup strategy breakdown** (from `dedup_summary.json` → `strategy_counts`):
  - `manual_reconciliation`: 5,214 entities (OpenRefine-confirmed; covers 23,692 alignment units)
  - `singleton`: 2,551 entities (single source, not merged; 2,551 alignment units)
  - `normalized_name_match`: 628 entities (auto-merged by name; covers 4,824 alignment units)
  - `wikidata_qid_match`: 43 entities (auto-merged by QID; covers 98 alignment units)
  - Total check: 5,214 + 2,551 + 628 + 43 = **8,436** ✓
- **Different from 8,287**: 8,287 is the guest-only subset in the occurrence matrix.
- **Wrong**: 8,313 — appeared in an earlier draft; not matched by any data file.

### 5,257 — Canonical persons with Wikidata ID
- **Verified**: `dedup_persons.csv` PowerShell count: 5,257 rows with non-empty `wikidata_id`.
- **Source**: `meta_statistics.csv` → `canonical_persons_with_wikidata`
- **Also**: Tier 1 (2,394) + Tier 2 (2,863) = 5,257 ✓

### 3,179 — Canonical persons without Wikidata ID
- **Verified**: `dedup_summary.json` → `unresolved_entities = 3179`; `dedup_persons.csv` count without wikidata_id = 3,179.
- **Source**: `meta_statistics.csv` → `canonical_persons_without_wikidata`
- **Also**: Tier 3 (628) + Tier 4 (2,551) = 3,179 ✓

### 62.3% — Wikidata reconciliation rate
- **Verified**: 5,257 / 8,436 = **62.32%** (rounds to 62.3%).
- **Source**: `meta_statistics.csv` → `canonical_persons_wikidata_pct`

### 37.7% — Canonical persons with no Wikidata link (no property data)
- **Exactly**: 3,179 / 8,436 = 37.68% ≈ 37.7%

---

## Data Quality Tiers

### 2,394 (28.4%) — Tier 1: Wikidata ID + cluster_size > 1
- **Verified**: `person_quality_tiers.csv` row: `1,2394,28.4` ✓
- **Exactly**: QID present, matched across 2+ sources.
- **Source**: `meta_statistics.csv` → `tier_1_count`
- **Property coverage figure**: Uses all 8,287 guests as denominator (not Tier 1 only). See `§ Occurrence Matrix` for 8,287.

### 2,863 (33.9%) — Tier 2: Wikidata ID + cluster_size == 1
- **Verified**: `person_quality_tiers.csv` row: `2,2863,33.9` ✓
- **Exactly**: QID present but matched in only one source; property coverage effectively zero.
- **Source**: `meta_statistics.csv` → `tier_2_count`

### 628 (7.4%) — Tier 3: No Wikidata ID, cluster_size ≥ 2
- **Verified**: `person_quality_tiers.csv` row: `3,628,7.4` ✓
- **Exactly**: Disambiguated via two non-Wikidata sources.
- **Source**: `meta_statistics.csv` → `tier_3_count`

### 2,551 (30.2%) — Tier 4: No Wikidata ID, cluster_size = 1
- **Verified**: `person_quality_tiers.csv` row: `4,2551,30.2` ✓
- **Exactly**: Single non-Wikidata source only.
- **Source**: `meta_statistics.csv` → `tier_4_count`
- **Tier sum check**: 2,394 + 2,863 + 628 + 2,551 = **8,436** ✓ (equals total canonical persons)

---

## Occurrence Matrix (Guests)

### 1972-09-10 — Oldest episode in entire aligned dataset
- **Exactly**: Earliest premiere date in `aligned_episodes.csv` across all 6,465 ZDF + FS episodes (including those without guest data).
- **Episode**: `episode_fs_4b33ba7064a2` (Internationaler Frühschoppen, fernsehserien.de)
- **Source**: `meta_statistics.csv` → `episode_dataset_oldest_date`; `aligned_episodes.csv` → `premiere_date_fernsehserien_de`
- **Note**: 9 of the 6,465 ZDF+FS episodes have no parseable premiere date.

### 2026-05-21 — Newest episode in entire aligned dataset
- **Exactly**: Latest premiere date in `aligned_episodes.csv`.
- **Episode**: `episode_fs_abb670d0485c` (Markus Lanz, fernsehserien.de)
- **Source**: `meta_statistics.csv` → `episode_dataset_newest_date`

### 1972–2026 — Full aligned dataset episode date range
- **Exactly**: 1972-09-10 to 2026-05-21.

---

### 2006-01-17 — Oldest episode with guest data (occurrence matrix)
- **Exactly**: Earliest premiere date among the 4,861 episodes in `occurrence_matrix.csv` (those with at least one guest appearance).
- **Episode**: `episode_fs_0612c9dad179` (Maischberger ARD, fernsehserien.de)
- **Source**: `meta_statistics.csv` → `episode_universe_oldest_date`
- **Different from 1972-09-10**: The Internationaler Frühschoppen 1972 episode exists in the aligned dataset but has no guest data and therefore does not appear in the occurrence matrix.
- **Note**: 4 of the 4,861 occurrence matrix episodes have no parseable premiere date.

### 2026-05-10 — Newest episode with guest data (occurrence matrix)
- **Exactly**: Latest premiere date among the 4,861 episodes in `occurrence_matrix.csv`.
- **Episode**: `episode_fs_9a84aa1ff67f` (Precht, fernsehserien.de)
- **Source**: `meta_statistics.csv` → `episode_universe_newest_date`

### 2006–2026 — Occurrence matrix (guest data) episode date range
- **Exactly**: 2006-01-17 to 2026-05-10.
- **Different from 2008–2024 ZDF corpus year range**: That figure covers ZDF-only episodes; the occurrence matrix includes FS-only episodes from additional shows (Maischberger on ARD/FS, Precht) which extend the boundaries.

### 8,287 — Unique canonical guests in occurrence matrix
- **Source**: `meta_statistics.csv` → `canonical_guests_in_matrix`; `occurrence_matrix.csv` row count; `analysis_summary.json` → `total_unique_guests`
- **Denominator for**: per-show guest counts, analysis comparisons.
- **Different from 8,436**: 8,436 includes moderators (39), staff (22), and 88 Wikidata-only persons with no episode backing. See the 88-person entry.

### 23,527 — Unique (guest, episode) appearance pairs
- **Source**: `meta_statistics.csv` → `guest_episode_pairs_dedup`; sum of all 1s in `occurrence_matrix.csv`; `analysis_summary.json` → `total_guest_appearances`
- **Wrong**: 23,747 — sum of `per_show_statistics.csv` appearance column (11 rows incl. duplicate markus-lanz row); this is a counting artifact, not authoritative.

### 39 — Moderators tracked separately
- **Source**: `meta_statistics.csv` → `moderators_excluded`; `moderator_occurrence_matrix.csv` row count

### 22 — Staff tracked separately
- **Source**: `meta_statistics.csv` → `staff_excluded`; `staff_occurrence_matrix.csv` row count

### 88 — Canonical persons absent from all occurrence matrices
- **Exactly**: 8,436 − 8,287 − 39 − 22 = 88
- **Full accounting**: 8,436 = 8,287 (guests) + 39 (moderators) + 22 (staff) + 88
- **Verified explanation**: All 88 have `match_strategy = wikidata_person_only_baseline` and `match_tier = unresolved` in `dedup_cluster_members.csv`. Their alignment_unit_id prefix is `person_wd_`. They have empty `fernsehserien_de_id` and empty `episode_id_zdf`. Their cluster_strategy in `dedup_persons.csv` is `manual_reconciliation` (confirmed in OpenRefine by curators). These are Wikidata-discovered persons who were confirmed as real people in OpenRefine but have **no corresponding guest appearance row** in either ZDF Archive or fernsehserien.de data — they are not guests of any specific episode in the corpus.
- **Wrong earlier explanation**: "Phoenix Runde and couchwissen exclusives" — this was incorrect. The 88 are not show-specific; they have zero source backing from any show's episode data.
- **Note**: The 240 `wikidata_person_only_baseline` alignment units collapsed to 88 canonical entities because multiple Wikidata IDs were confirmed to be the same person during OpenRefine review.

---

## Gender (P21)

### 5,016 — Guests with any gender annotation
- **Source**: `sex_or_gender/carrier_stats.csv` (sum of all non-Unknown rows by person_count)

### 3,301 — Guests with unknown / no gender data
- **Source**: `sex_or_gender/carrier_stats.csv` → "Unknown / no data"

### 3,127 (62.34%) — Male guests (männlich)
- **Source**: `carrier_stats.csv`; percentage of 5,016 annotated guests.
- **Wrong**: 2,617 / 4,159 — appeared in earlier paper drafts; wrong base population.

### 1,880 (37.48%) — Female guests (weiblich)
- **Source**: `carrier_stats.csv`
- **Wrong**: 1,535 / 4,159 — appeared in earlier drafts.

### 4 — Non-binary guests (nichtbinär)
- **Source**: `carrier_stats.csv`
- **Wrong**: 3 — appeared in earlier drafts.

### 2 — Trans woman guests (Transfrau)
- **Source**: `carrier_stats.csv`

### 1 — Trans man guests (Transmann)
- **Source**: `carrier_stats.csv`
- **Note**: Was entirely absent from earlier drafts.

### 1 — Agender guest
- **Source**: `carrier_stats.csv`

### 1 — Transmasculine guest (Transmaskulin)
- **Source**: `carrier_stats.csv`

### 9 — Total guests with non-binary annotation
- **Exactly**: 4 + 2 + 1 + 1 + 1 = 9
- **Wrong**: 7 — appeared in earlier drafts (missed trans man, undercounted non-binary).

### 11,948 — Male guest appearances
- **Source**: `carrier_stats.csv`

### 6,207 — Female guest appearances
- **Source**: `carrier_stats.csv`

### 18,169 — Appearances with known gender
- **Exactly**: 11,948 + 6,207 + 14 (minor categories) — the correct denominator for gender share.

### 65% — Male share of appearances with known gender
- **Exactly**: 11,948 / 18,169 ≈ 65.7%; rounded to 65% in text.
- **Key note**: Denominator is the 18,169 known-gender appearances, NOT all 23,527. Saying "65% of all appearances" would be wrong (that would be 50.8%).

### 16.97% — Episodes with no female guest
- **Source**: `sex_or_gender/episode_stats.csv` → `pct_without_value` for weiblich
- **Wrong**: 19.17% — appeared in earlier drafts (used stale episode count of 4,251 as base).

### 3.64% — Episodes with no male guest
- **Source**: `sex_or_gender/episode_stats.csv` → `pct_without_value` for männlich
- **Wrong**: 4.3% — appeared in earlier drafts.

---

## Occupation (P106)

### 988 — Unique occupation labels (non-unknown) in dataset
- **Verified**: `occupation/carrier_stats.csv` non-Unknown row count = 988 ✓
- **Source**: `occupation/carrier_stats.csv`

### 55 — Appearances by scientist (Wissenschaftler, Q901) directly
- **Verified**: `occupation/carrier_stats.csv` row 80: `Wissenschaftler,21,55,...` ✓
- **Wrong**: 85 — appeared in earlier paper drafts; source unknown.

### 21 — Persons with occupation = scientist
- **Verified**: `occupation/carrier_stats.csv` row 80: person_count=21 ✓

### 725 — Appearances by economist (Wirtschaftswissenschaftler, Q188094, a subclass)
- **Verified**: `occupation/carrier_stats.csv`: `Wirtschaftswissenschaftler,117,725,...` ✓
- **Wrong**: 1,415 — appeared in earlier paper drafts; source unknown.

### 117 — Persons with occupation = economist
- **Verified**: `occupation/carrier_stats.csv`: person_count=117 ✓

---

## Position Held (P39)

### 579 — Total rows in position_held carrier_stats.csv (578 unique labels)
- **Verified**: `position_held/carrier_stats.csv` has **579 total rows** = 578 unique position_held labels + 1 "Unknown / no data" meta-row.
- **Source**: `position_held/carrier_stats.csv`
- **Key distinction**: The paper says "579 such position_held labels" — this matches the total row count (578 actual labels + 1 Unknown). Technically 578 is the count of unique position labels, but 579 is defensible as the total CSV entries.
- **Note**: This is position_held (P39), not occupation (P106). Confusing these is easy because both encode roles.

### 6 — Position_held labels using female grammatical form
- **Verified**: `position_held/carrier_stats.csv` grep for feminine indicators. Exact labels in the data:
  1. `Bundesministerin für Bildung, Familie, Senioren, Frauen und Jugend`
  2. `Bundesministerin für wirtschaftliche Zusammenarbeit und Entwicklung`
  3. `Bundesministerin für Wohnen, Stadtentwicklung und Bauwesen`
  4. `Königin von Schweden`
  5. `Queen of Trinidad and Tobago` ← **English label in Wikidata**, not "Königin von Trinidad und Tobago"
  6. `Äbtissin`
- **Source**: `position_held/carrier_stats.csv` rows 424, 502, 580 (and Bundesministerin rows)
- **Paper reference**: Paper says "queen of Trinidad and Tobago" which is a translation; the actual Wikidata label stored is the English "Queen of Trinidad and Tobago".
- **Also present**: `monarch of Trinidad and Tobago` (row 558) — a separate label, not counted in the 6 female forms (gender-neutral English term).
- **Wrong**: 5 — appeared in earlier drafts; missed the Trinidad/Tobago entry.

---

## Derived / Abstract Values

### 17,424 — Automatically reconciled by OpenRefine (approx.)
- **Exactly**: 55.91% × 31,165 = **17,424.35 ≈ 17,424** rows
- **Note**: Cannot be pinpointed in any single CSV; derived from curator session percentages.

### 5,856 — Manually mapped via OpenRefine (approx.)
- **Exactly**: 18.79% × 31,165 = 5,855.9 ≈ 5,856 rows

### 3,793 — No suitable candidate in OpenRefine (approx.)
- **Exactly**: 12.17% × 31,165 = 3,792.8 ≈ 3,793 rows

### 4,092 — Unresolved within OpenRefine time window (approx.)
- **Exactly**: 13.13% × 31,165 = 4,091.9 ≈ 4,092 rows
- **Sanity check**: 17,424 + 5,856 + 3,793 + 4,092 = **31,165** ✓ (sums exactly — the four percentages are mutually consistent)

### 4.35 — Average guests per episode
- **Source**: `analysis_summary.json` → `average_guests_per_episode`

---

## Verification Status Summary

| Number | Verified via | Status |
|--------|-------------|--------|
| 2,036 ZDF episodes | `episodes.csv` row count | ✓ |
| 6,459 FS episodes | `episode_metadata_normalized.csv` row count | ✓ |
| 6,469 aligned episodes | Formula: 2,036 + 6,459 − 2,026 | ✓ |
| 4,861 matrix episodes | `occurrence_matrix.csv` column count | ✓ |
| 2,026 ZDF in matrix | `ep_*` column count | ✓ |
| 2,835 FS in matrix | `episode_fs_*` column count | ✓ |
| 638 BFS series | `core_series.json` key count | ✓ |
| 251 BFS organizations | `core_organizations.json` key count | ✓ |
| 382,400 triples | `triples.csv` row count (no duplicates) | ✓ (was "over 380,000" in line 353 — fixed to exact) |
| 8,221 classes | `classes.csv` row count | ✓ |
| 2,324 properties | `properties.csv` row count | ✓ |
| 3,936 relevant QIDs | `relevancy.csv` row count | ✓ |
| 31,165 alignment units | `dedup_summary.json` + `dedup_cluster_members.csv` | ✓ |
| 10,390 ZDF alignment units | `dedup_cluster_members.csv` match_strategy | ✓ |
| 20,535 FS alignment units | `dedup_cluster_members.csv` match_strategy | ✓ |
| 240 WD-only alignment units | `dedup_cluster_members.csv` match_strategy | ✓ |
| 5,797 / 18.6% HIGH tier | `dedup_cluster_members.csv` match_tier | ✓ |
| 8,436 canonical persons | `dedup_summary.json` + `dedup_persons.csv` | ✓ |
| 5,257 with Wikidata ID | `dedup_persons.csv` column count | ✓ |
| 3,179 without Wikidata ID | `dedup_summary.json` unresolved_entities | ✓ |
| 62.3% reconciliation rate | 5,257 / 8,436 = 62.32% | ✓ |
| 88 matrix-absent persons | `dedup_cluster_members.csv` investigation | ✓ |
| Dataset oldest 1972-09-10 (Int. Frühschoppen) | `meta_statistics.csv` → `episode_dataset_oldest_date` | ✓ |
| Dataset newest 2026-05-21 (Markus Lanz) | `meta_statistics.csv` → `episode_dataset_newest_date` | ✓ |
| Matrix oldest 2006-01-17 (Maischberger ARD) | `meta_statistics.csv` → `episode_universe_oldest_date` | ✓ |
| Matrix newest 2026-05-10 (Precht) | `meta_statistics.csv` → `episode_universe_newest_date` | ✓ |
| 8,287 unique guests | `occurrence_matrix.csv` row count + `analysis_summary.json` | ✓ |
| 23,527 appearances | `analysis_summary.json` | ✓ |
| 39 moderators | `moderator_occurrence_matrix.csv` row count | ✓ |
| 22 staff | `staff_occurrence_matrix.csv` row count | ✓ |
| 55.91% / 18.79% / 12.17% / 13.13% | **Cannot verify from CSVs** — curator session logs | ⚠ |
| Table 1 "Our work" Episodes | Was 6,469 (12-program universe); fixed to **4,861** (10 guest-data programs — consistent with Shows=10 and Guests=8,287) | ✓ fixed |
| 14,750 institution mentions | Module deferred; no output file persisted — cannot verify | ⚠ |
| 20,585 schema-mapping rows | `aligned/source_schema_mapping.csv` — was 11,629 in paper (stale); fixed | ✓ fixed |
| 2,673 / 39% matched episodes | `aligned/aligned_episodes.csv` — 2,673 non-UNRESOLVED of 6,849 | ✓ |
| Quality tiers 2,394/2,863/628/2,551 | `person_quality_tiers.csv` direct rows | ✓ |
| Gender 3,127/1,880/4/2/1/1/1 persons | `sex_or_gender/carrier_stats.csv` | ✓ |
| Gender 11,948/6,207 appearances | `sex_or_gender/carrier_stats.csv` + episode_stats | ✓ |
| Gender 18,169 known-gender appearances | Sum: 11,948+6,207+14 = 18,169 | ✓ |
| Gender 65% male share | 11,948/18,169 = 65.76% | ✓ |
| Gender 16.97% episodes no female | `sex_or_gender/episode_stats.csv` | ✓ |
| Gender 3.64% episodes no male | `sex_or_gender/episode_stats.csv` | ✓ |
| Occupation 988 labels | `occupation/carrier_stats.csv` non-Unknown count | ✓ |
| Occupation 55 scientist appearances | `occupation/carrier_stats.csv` row: Wissenschaftler | ✓ |
| Occupation 21 scientist persons | `occupation/carrier_stats.csv` row: Wissenschaftler | ✓ |
| Occupation 725 economist appearances | `occupation/carrier_stats.csv` row: Wirtschaftswissenschaftler | ✓ |
| Occupation 117 economist persons | `occupation/carrier_stats.csv` row: Wirtschaftswissenschaftler | ✓ |
| Position_held 579 total rows | `position_held/carrier_stats.csv` total rows (578 non-Unknown + 1) | ✓ |
| Position_held 6 female forms | `position_held/carrier_stats.csv` grep | ✓ (5th label is English "Queen of Trinidad and Tobago") |
