# Phase 5 Analysis — Design Specification
> Created: 2026-04-29  
> Status: Draft — ready for implementation  
> Deadline: 2026-05-03

---

## 1. Data Model

Four layers, joined in sequence.

### Layer 1 — Canonical persons (who exists)
**Source:** `data/32_entity_deduplication/dedup_persons.csv` (8,998 unique persons)  
**Key columns:** `canonical_entity_id`, `wikidata_id`, `canonical_label`, `cluster_size`, `cluster_strategy`, `cluster_confidence`  
**Role:** One row per unique person. `cluster_size` = number of individual appearances merged into this canonical entity.

### Layer 2 — Appearances (who appeared where)
**Source:** `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` (26,702 appearance rows)  
**Key columns:** `alignment_unit_id`, `wikidata_id`, `fernsehserien_de_id` (= episode URL), `canonical_label`, `match_tier`  
**Role:** Primary source of record for person×episode presence. One row per unique (person, episode) pair — multiple rows may share the same person or the same episode, but each (person, episode) combination appears at most once. Confirms: "person named X with QID Y was present in episode Z." Presence does not always mean guest role — verify role via `alignment_unit_id` trace. Join on `wikidata_id` → Layer 1. Join on `fernsehserien_de_id` → Layer 3.  
**Note:** Python utility code in `data/31_entity_disambiguation/manual/` may be needed if additional columns beyond those listed are required.

### Layer 3 — Episode metadata (when and where)
**Source:** `data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv`  
**Key columns:** `episode_url`, `premiere_date`, `program_name`, `fernsehserien_de_id` (= show ID, e.g. `markus-lanz`)  
**Role:** Date and show for each episode. Join key: `episode_url` = `reconciled_data_summary.fernsehserien_de_id`. `premiere_date` = earliest known broadcast date (field name varies across sources; normalization resolves this; IDs allow alignment across heterogeneous steps).

### Layer 4 — Properties (attributes per person)
**Primary source:** `data/20_candidate_generation/wikidata/projections/core_persons.json` → `{QID: entity_doc}`  
**Fallback:** `entity_access.get_cached_entity_doc(wikidata_id, repo_root)` for QIDs missing from file  
**Claims for Phase 5:** P21 (gender), P106 (occupation), P102 (party), P108 (employer), P569 (birth date), P19 (place of birth)  
**Note:** All available claims should be accessible for ad-hoc analysis — not only the listed ones. ZDF/Fernsehserien.de textual descriptions (role, description) are an additional property source not yet integrated into this layer (tracked under TODO-045).

### Join diagram
```
dedup_persons  ──wikidata_id──▶  core_persons.json  (Wikidata properties)
      │
  canonical_entity_id
      │
reconciled_data_summary  ──fernsehserien_de_id = episode_url──▶  episode_metadata_normalized
```

---

## 2. Classification Rules

### 2.1 Role separation
Role detection is **data-driven** via the `guest_role` field in `episode_guests_normalized.csv`. Hardcoded lists are not the primary mechanism — the data already encodes role information.

**Role mapping from `guest_role` values:**
- `"Gast"` (or equivalent) → `guest`
- `"Moderation"` → `moderator`
- `"Produktionsauftrag"`, `"Redaktion"`, and other production/editorial roles → `staff`
- No Fernsehserien guest link (`pm_*` mention only) → `incidental`

**Pre-implementation step:** Survey all distinct `guest_role` values in `episode_guests_normalized.csv` and map each to one of the four categories above before implementing the tagging logic.

**Override:** `MODERATOR_QIDS = {"Q43773"}` (Markus Lanz) — explicit override for edge cases where role data is absent or ambiguous. Not the primary detection mechanism.

**Application:** Tag rows by role before analysis. No role is dropped — each forms a separate analysis set. The same analyses run for `guest` rows can also be run for `moderator` or `staff` rows.  
**Roles:** `guest`, `moderator`, `staff`, `incidental`

All analyses in Step C default to the `guest` population. Other role sets are retained and analyzable. Role tagging is explicit in all output metadata.

### 2.2 Guest classification
A person counts as a **guest** for a given episode if their row in `reconciled_data_summary.csv` has `entity_class == "person"` and the `fernsehserien_de_id` episode URL links to a relevant broadcasting program (those in `data/00_setup/broadcasting_programs.csv` — authoritative source for in-scope shows).

Topic-mentioned persons (TODO-040 risk: Elon Musk type) are identified by tracing `alignment_unit_id` back to `episode_guests_normalized.csv` and checking `guest_role`. If `guest_role == "Gast"` (or equivalent), the person is a guest. If the only source is `pm_*` mention IDs with no Fernsehserien guest link, classify as `incidental`.  
**Note:** `incidental` mentions are retained and analyzable as a separate set.

**Before proceeding:** Verify Elon Musk and sample 20 entries (TODO-040). If systematic misclassification found, raise blocking issue.

---

## 3. Analysis Steps

### Step A — Build the person catalogue
**Output:** `data/40_analysis/guest_catalogue.csv`  
**Columns:** `canonical_entity_id`, `wikidata_id`, `canonical_label`, `cluster_size`, `cluster_strategy`, `cluster_confidence`, `role`, `appearance_count`, `gender`, `gender_qid`, `birthyear`, `birthplace`, `birthplace_qid`, `occupations`, `occupation_qids`, `party`, `party_qids`, `employer`, `employer_qids`

**Algorithm:**
1. Load `dedup_persons.csv` → base catalogue (8,998 rows)
2. Survey distinct `guest_role` values in `episode_guests_normalized.csv`; build role mapping per §2.1; tag each row accordingly; apply `MODERATOR_QIDS` override for rows with missing role data
3. Count appearances per `canonical_entity_id` from `reconciled_data_summary.csv` → `appearance_count`
4. For rows with `wikidata_id`: load claims from `core_persons.json`; for missing QIDs call `ensure_basic_fetch`
5. Extract P21 (gender), P106 (occupation), P102 (party), P108 (employer), P569 (birth date → `birthyear`), P19 (place of birth → `birthplace`/`birthplace_qid`) from claims (time-sensitive filter: deferred per TODO-041)
6. Persons without `wikidata_id`: all Wikidata-derived columns `= ""`; still present with `canonical_label` and `appearance_count`

**Also output:**
- `data/40_analysis/guest_catalogue_unmatched.csv` — same columns, restricted to rows where `wikidata_id == ""`
- `data/40_analysis/person_catalogue_unclassified.csv` — same columns, restricted to persons with `appearance_count == 0` after the episode join (no match in any source). These are persons that entered the catalogue via early Wikidata discovery but were never linked to an actual episode. This list is the expected resting place for topic-mentioned QIDs (e.g. Elon Musk) that were never physically present as guests.

---

### Step B — Build the episode-guest occurrence matrix
**Output:** `data/40_analysis/occurrence_matrix.csv`  
**Rows:** Canonical persons with `role == "guest"` (sorted by `appearance_count` descending, then alphabetically)  
**Columns:** Episodes (sorted by `premiere_date` ascending)  
**Cells:** 1 if person appeared in that episode, else empty

**Algorithm:**
1. Join `reconciled_data_summary.csv` with `episode_metadata_normalized.csv` on `fernsehserien_de_id = episode_url`; filter to shows in `data/00_setup/broadcasting_programs.csv`
2. Join with `dedup_persons.csv` on `wikidata_id` (or `canonical_label` for unmatched) → `canonical_entity_id`
3. Apply role tagging (§2.1, §2.2); use `role == "guest"` for the guest matrix
4. Pivot: `canonical_entity_id` × `episode_url`
5. **Completeness check:** Compare all (person, episode) IDs in the full join against those in `episode_guests_normalized.csv`; log rows that appear in the join but have no corresponding Fernsehserien guest entry — these are candidates for missing or mis-classified entries (TODO-027 resolution approach)

**Derivative matrices (same step, additional outputs):**
- Per-show matrices: one file per `program_name`
- Guest co-occurrence matrix: `canonical_entity_id` × `canonical_entity_id` (count of shared episodes)

---

### Step C — Core property analyses

All analyses are computed over the occurrence matrix guest set (not the full catalogue). Each analysis has two modes: all shows combined, and per show.

#### C1 — Gender distribution
**Output columns:** `gender`, `person_count`, `appearance_count`, `pct_by_person`, `pct_by_appearance`  
**Grouping:** All shows; per show (one row-group per `program_name`)  
**Note:** Include explicit "unknown" row for persons with no gender data. Document caveat (TODO-033): this describes the sample, not the population.

#### C2 — Gender distribution over time
**Output:** `data/40_analysis/gender_over_time.csv` + chart  
**Grouping:** Calendar year from `premiere_date`; one row per (year, gender); `appearance_count` and `person_count` per cell  
**Two modes:** All shows combined; per show

#### C3 — Occupation distribution
**Output:** `data/40_analysis/occupation_distribution.csv`  
**Grouping:** Occupation QID → occupation label (from `core_persons.json` label); count persons, count appearances  
**Note:** One person may have multiple occupations → count each separately; document multi-count behavior  
**Subclustering via P279 (TODO-020 scope):** Required. Use class hierarchy data from Phase 2 to group related occupations (e.g. all journalism subtypes under journalist). Flat list is the fallback only if class hierarchy data is unavailable at runtime.

#### C4 — Gender by occupation
**Output:** Cross-tabulation of (occupation, gender) → person count  
**Filter:** Top 20 occupations by person count

#### C5 — Party affiliation distribution
**Output:** `data/40_analysis/party_distribution.csv` — party QID, label, person count, appearance count  
**Note:** Time-sensitive (TODO-041 deferred) — use snapshot value with documented caveat

#### C6 — Gender by party affiliation
**Output:** Cross-tabulation of (party, gender) → person count  
**Filter:** Top 15 parties by person count

#### C7 — Party affiliation by occupation
**Output:** Cross-tabulation of (occupation, party) → person count  
**Filter:** Top 15 occupations × top 10 parties

#### C8 — Age distribution
**Derived field:** `appearance_age = premiere_year - birth_year` (approximate; only year-level precision)  
**Output:** `data/40_analysis/age_distribution.csv` — histogram buckets (10-year bins) × appearance_count  
**Note:** Documented caveat: year-of-birth only; episode recording may predate broadcast date

---

### Step D — Meta-analysis and pipeline statistics

#### D1 — Dataset overview table
**Output:** `data/40_analysis/dataset_overview.csv`  
Rows: one per phase/source  
Columns: `phase`, `source`, `entity_type`, `total_count`, `wikidata_matched_count`, `coverage_pct`

Example rows:
- Phase 1 / Fernsehserien / persons: N total, N with Wikidata match
- Phase 1 / ZDF Archiv / persons: N total, N with Wikidata match
- Phase 31 / aligned / persons: N
- Phase 32 / deduplicated / persons: 8,998
- Phase 5 / guest catalogue: N matched, N unmatched

---

## 4. Output Files Summary

| File | Description | Step |
|------|-------------|------|
| `data/40_analysis/guest_catalogue.csv` | Full catalogue, all persons, with `role` column | A |
| `data/40_analysis/guest_catalogue_unmatched.csv` | Persons without Wikidata match | A |
| `data/40_analysis/person_catalogue_unclassified.csv` | Persons with no episode match in any source | A |
| `data/40_analysis/occurrence_matrix.csv` | Episode × person (guests only) | B |
| `data/40_analysis/occurrence_matrix_<show>.csv` | Per-show matrices | B |
| `data/40_analysis/co_occurrence_matrix.csv` | Person × person co-occurrences | B |
| `data/40_analysis/gender_distribution.csv` | Gender counts + pct | C1 |
| `data/40_analysis/gender_over_time.csv` | Gender by year | C2 |
| `data/40_analysis/occupation_distribution.csv` | Occupation counts | C3 |
| `data/40_analysis/gender_by_occupation.csv` | Cross-tabulation | C4 |
| `data/40_analysis/party_distribution.csv` | Party counts | C5 |
| `data/40_analysis/gender_by_party.csv` | Cross-tabulation | C6 |
| `data/40_analysis/party_by_occupation.csv` | Cross-tabulation | C7 |
| `data/40_analysis/age_distribution.csv` | Age histogram | C8 |
| `data/40_analysis/dataset_overview.csv` | Pipeline statistics | D1 |

---

## 5. Notebook Structure

One notebook: `speakermining/src/process/notebooks/50_analysis.ipynb`

Cells in order:
1. Imports and path setup
2. **Setup:** Load `data/00_setup/broadcasting_programs.csv`; survey distinct `guest_role` values in `episode_guests_normalized.csv`; build role mapping; define `MODERATOR_QIDS` override
3. **Audit:** TODO-040 guest classification check (Elon Musk trace + sample)
4. **Step A:** Build person catalogue (with role tagging)
5. **Step B:** Build occurrence matrix + derivatives + completeness check
6. **Step C1–C2:** Gender distributions + temporal
7. **Step C3–C4:** Occupation distributions (with P279 subclustering)
8. **Step C5–C7:** Party distributions + cross-tabs
9. **Step C8:** Age distribution
10. **Step D1:** Dataset overview
11. **Summary:** `analysis_summary.json` with key statistics

Each cell prints intermediate counts so results are visible without running the full notebook.

---

## 6. Open Clarifications

1. **Guest classification audit — Elon Musk case (TODO-040):** Musk was carried forward from an early Wikidata discovery run and is not matched to any episode in any of the three sources (Wikidata episodes, ZDF PDFs, Fernsehserien.de). If role classification is correctly implemented, he must appear in `person_catalogue_unclassified.csv` — not in the guest catalogue. The audit after running Step A: verify Musk is in the unclassified list. If he is in the guest list, the classification logic has a defect. This is a correctness check for the overall system, not a Musk-specific concern.
2. **Fernsehserien person ID (TODO-045):** The `fernsehserien_de_id` column in `reconciled_data_summary.csv` contains episode URLs, not person slugs (data quality issue from Phase 3). The Step B join is correct as written. The person's fernsehserien_de_id slug can be extracted from Fernsehserien source data during Step A property fetch — the slug IS the fernsehserien_de_id; no URL construction needed. The historical column mis-assignment in aligned files is deferred post-deadline.
