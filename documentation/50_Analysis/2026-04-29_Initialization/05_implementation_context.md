# Phase 5 Implementation Context
> Created: 2026-04-29
> Purpose: Capture non-obvious data discoveries and design decisions made during implementation so future sessions do not rediscover the same information.

---

## 1. Data Source Decisions

### Wikidata properties — CORRECTED UNDERSTANDING
**The design spec Layer 4 says:** primary source is `core_persons.json`; fallback: `entity_access.get_cached_entity_doc()`

**Coverage reality (checked 2026-04-29):**
- `reconciled_data_summary.csv` has **5,374 unique wikidata_ids** (authoritative, OpenRefine-reconciled)
- `dedup_persons.wikidata_id` has only **673** (only for `wikidata_qid_match` strategy clusters)
- `archive/core_persons.json` has **673 entries**, covering **630** of the 5,374 reconciled QIDs
- **4,744 reconciled QIDs are NOT in archive/core_persons.json**
- **`entity_access.get_cached_entity_doc(qid, repo_root)`** checks the event log cache (full_fetch first, basic_fetch fallback) — this may cover many of the 4,744 from Phase 2 hydration
- Use `data/20_candidate_generation/wikidata/projections/archive/` for all projections; current projections dir is fractured

**Action for next session:** For each canonical entity, derive wikidata_id from reconciled_data_summary (highest match_tier row), then: (1) try archive/core_persons.json, (2) try entity_access.get_cached_entity_doc(), (3) document coverage gap.

### Wikidata properties — archive files
**Source:** `data/20_candidate_generation/wikidata/projections/archive/core_persons.json`
- **Type:** `{QID: entity_doc}` dict
- **Coverage:** 673 entries — covers 630 of the 5,374 reconciled wikidata_ids
- **Completeness:** Full entity docs with all claims (P21, P106, P102, P108, P569, P19, etc.)
- **Why archive:** The current projections `core_persons.json` is fractured (30 entries). Use archive.

**entity_access.py API (from code inspection):**
- `get_cached_entity_doc(qid, repo_root)` → checks event log cache: full_fetch ("entity") first, basic_fetch fallback. Returns full entity doc if cached, None otherwise. O(1) per call after index primed.
- `ensure_basic_fetch(qid, repo_root)` → cache hit → same as above; miss → network fetch (basic only: labels + P31/P279). NOT sufficient for P21/P106/P102/P108/P569/P19.
- Full_fetch cache likely covers many Phase 2 QIDs via the entity hydration run.

### P279 class hierarchy (occupation subclustering)
**Source:** `data/20_candidate_generation/wikidata/projections/archive/class_hierarchy.csv`
- Columns: `class_id, class_filename, path_to_core_class, distance_to_core_min, parent_qids, ...`
**Alternative:** `data/20_candidate_generation/wikidata/projections/class_resolution_map.csv`
- Columns: `class_qid, parent_qids, depth, core_class_qid`

Also useful: `data/20_candidate_generation/wikidata/projections/archive/instances.csv`
- Columns: `qid, label, labels_de, labels_en, aliases, description, ...`
- Use for QID → label lookup (German label preferred)

### Page rank / graph
**Source:** `data/20_candidate_generation/wikidata/projections/archive/triples.csv`
- This is the v3 triples file for page rank computation via networkx
- Also available as `archive/triples.parquet`

### Episode guests and metadata
**Source:** `data/31_entity_disambiguation/raw_import/episode_guests_normalized.csv`
- Columns: `fernsehserien_de_id` (show ID), `program_name`, `episode_url`, `guest_name`, `guest_role`, `guest_description`, `guest_url`, `guest_image_url`, `guest_order`, ...
- 25,452 rows

**Source:** `data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv`
- Columns: `fernsehserien_de_id` (show ID), `program_name`, `episode_url`, `episode_title`, `duration_minutes`, `description_text`, `premiere_date`, `premiere_broadcaster`, ...

### The join bridge
**Source:** `data/32_entity_deduplication/dedup_cluster_members.csv`
- Columns: `canonical_entity_id, alignment_unit_id, mention_id, canonical_label, wikidata_id, match_tier, cluster_key, is_representative`
- 31,823 rows; 8,998 unique canonical_entity_ids
- **Critical:** This is the bridge from `reconciled_data_summary.alignment_unit_id` → `canonical_entity_id`
- 97.2% match rate: 24,066 out of 24,758 reconciled alignment_unit_ids found in cluster_members
- 692 reconciled rows don't match — unresolved entries or new additions; acceptable loss

---

## 2. Guest Role Values (Complete Taxonomy)

From `episode_guests_normalized.guest_role` (all distinct values):

| Raw value | Mapped role | Semantic meaning |
|-----------|-------------|-----------------|
| `Gast` | `guest` | Invited guest |
| `Kommentar` | `guest` | Commentary — commentator/analyst present as guest |
| `Kommentator` | `guest` | Commentator — essentially the same as Kommentar |
| `Moderation` | `moderator` | Show host/moderator |
| `Produktionsauftrag` | `staff` | Production order — company commissioned to produce |
| `Produktionsfirma` | `staff` | Production company |
| `Redaktion` | `staff` | Editorial staff |
| `Regie` | `staff` | Director |
| `Drehbuch` | `staff` | Screenwriter/script |
| `''` (empty) | `guest` | Unknown role — person IS listed on episode page (has fernsehserien link), so assumed guest. This is an assumption; treat with caveat. |

**Fifth role — `incidental`:** Persons with `fernsehserien_de_id = ''` in `reconciled_data_summary` (no episode link at all). These entered the catalogue via Wikidata-only discovery and were never linked to an actual episode. They appear in `person_catalogue_unclassified.csv` for manual review.

**Override:** `MODERATOR_QIDS = {'Q43773'}` (Markus Lanz) — override for rows with missing or ambiguous role data.

---

## 3. Join Strategy

### From appearance_unit to canonical person
```
reconciled_data_summary.alignment_unit_id
  → dedup_cluster_members.alignment_unit_id
  → dedup_cluster_members.canonical_entity_id
```

### From person to episode (for occurrence matrix)
```
reconciled_data_summary.fernsehserien_de_id  (= episode URL, NOT show ID!)
  → episode_metadata_normalized.episode_url
  → episode_metadata_normalized.fernsehserien_de_id  (= show ID, e.g. "markus-lanz")
  → filter: show_id in IN_SCOPE_SHOW_IDS
```

**IMPORTANT naming confusion:**
- `reconciled_data_summary.fernsehserien_de_id` = **episode URL** (e.g. `https://www.fernsehserien.de/markus-lanz/folgen/1-folge-1-514614`)
- `episode_metadata_normalized.fernsehserien_de_id` = **show ID** (e.g. `markus-lanz`)
- `episode_guests_normalized.fernsehserien_de_id` = **show ID** (e.g. `markus-lanz`)
- The join key between reconciled and episode_metadata is: `reconciled.fernsehserien_de_id = episode_metadata.episode_url`

### Getting guest_role per appearance
```
reconciled_data_summary.fernsehserien_de_id (= episode URL)
  + reconciled_data_summary.canonical_label (case-insensitive)
  → episode_guests_normalized.episode_url
  + episode_guests_normalized.guest_name (case-insensitive)
  → episode_guests_normalized.guest_role
```
Name matching is approximate (case-insensitive lowercase). Unmatched rows → `''` role → mapped to `guest` by ROLE_MAP.

---

## 4. In-Scope Broadcasting Programs

From `data/00_setup/broadcasting_programs.csv` (non-NONE fernsehserien_de_id values):

| Show ID | Label |
|---------|-------|
| `markus-lanz` | Markus Lanz |
| `hart-aber-fair` | Hart aber fair |
| `maischberger-ard` | Maischberger |
| `maybrit-illner` | Maybrit Illner |
| `caren-miosga` | Caren Miosga |
| `scobel` | scobel |
| `phoenix-runde` | Phoenix Runde |
| `precht` | Precht |
| `internationaler-fruehschoppen` | Der Internationale Frühschoppen |
| `presseclub` | Presseclub |
| `startalk` | StarTalk |
| `couchwissen` | couchwissen |

Shows with `NONE` as fernsehserien_de_id (Unbouble, WTF talk, Lanz und Precht) are excluded from in-scope filtering.

---

## 5. Data Gaps Found During Run (2026-04-30)

### Phoenix Runde — no episode data
`phoenix-runde` is configured in `data/00_setup/broadcasting_programs.csv` as an in-scope show, but `data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv` contains **zero rows** for this show ID. No per-show occurrence matrix is produced and no guest appearances are attributed to it. This is a data gap from Phase 1 (the show was never scraped). The notebook behaves correctly — absence of data is not a bug. Future task: scrape or manually import episode data for Phoenix Runde.

### Cartesian product bug in C3/C5 — fixed 2026-04-30
`CELL_15_CODE` (occupation) and `CELL_17_CODE` (party) originally did two sequential `explode` calls on parallel pipe-joined columns (`occupation_qids` + `occupations`, `party_qids` + `party`), producing a Cartesian product instead of a zip. This created duplicate rows with scrambled labels (e.g. Q1930187 labeled both "Journalist" and "Schriftsteller"). Fixed in `gen_50_analysis.py` by zipping both columns into `_occ_pairs`/`_pty_pairs` before exploding. Confirmed: 0 duplicate QIDs after fix.

---

## 6. Key Counts (at time of implementation)

| File | Rows | Notes |
|------|------|-------|
| `dedup_persons.csv` | 8,998 | All canonical persons |
| `dedup_persons.csv` with wikidata_id | 673 | Only `wikidata_qid_match` strategy clusters |
| `reconciled_data_summary.csv` | 26,659 | 24,758 distinct alignment_unit_ids |
| `reconciled_data_summary` unique wikidata_ids | **5,374** | Authoritative source for property lookup |
| `reconciled_data_summary` matched to cluster_members | 24,066 | 97.2% match rate |
| `dedup_cluster_members.csv` | 31,823 | 8,998 unique canonical_entity_ids |
| `episode_guests_normalized.csv` | 25,452 | All show-episode-guest triples |
| `archive/core_persons.json` | 673 | Full Wikidata entity docs; covers 630 of 5,374 reconciled QIDs |
| `broadcasting_programs.csv` | 15 rows | 12 with valid fernsehserien_de_id |

---

## 6. Wikidata Property Extraction

From archive `core_persons.json` entity docs (`claims` dict):

```python
def extract_props(claims):
    """Extract Phase 5 Wikidata properties from claims dict."""
    gender_qid    = _item_qid(claims['P21'][0]) if 'P21' in claims else ''
    occ_qids      = [_item_qid(s) for s in claims.get('P106', []) if _item_qid(s)]
    party_qids    = [_item_qid(s) for s in claims.get('P102', []) if _item_qid(s)]
    employer_qids = [_item_qid(s) for s in claims.get('P108', []) if _item_qid(s)]
    birthyear     = _time_year(claims['P569'][0]) if 'P569' in claims else ''
    bp_qid        = _item_qid(claims['P19'][0]) if 'P19' in claims else ''
    return gender_qid, occ_qids, party_qids, employer_qids, birthyear, bp_qid
```

For QID → label lookup: use `archive/instances.csv` (columns: `qid, label, labels_de, labels_en`) — German label preferred, fallback to English.

---

## 7. Analysis Functions (from 04_analysis_angle_structure.md)

All Step C analyses use five generic functions: F1 (distribution), F2 (over-time), F3 (cross-tab), F4 (continuous), F5 (hierarchy/Sunburst). See `04_analysis_angle_structure.md` for full signatures.

Key implementation note: analyses use the `catalogue` (per-person, 8,998 rows) for distribution counts, and `episode_appearances` (per person-episode pair) for temporal analyses (C2). Both are built in Steps A and B respectively.

---

## 8. Wikidata Property Fetch Strategy

**Implemented (2026-04-29):** Step A derives `wikidata_id` per canonical entity from `reconciled_data_summary.wikidata_id` (highest match_tier row per entity — up to 5,374 unique QIDs). Property lookup chain:
1. `archive/core_persons.json` (673 full entity docs, covers 630 reconciled QIDs)
2. `entity_access.get_cached_entity_doc(qid, repo_root)` — checks full_fetch event log cache; may cover many Phase 2 hydrated QIDs
3. No data → properties left empty; counted in coverage summary printed by Step A

**Known gap:** After notebook run on 2026-04-30: 910 of 5,738 guests have property data — 84% unknown. The remaining ~4,464 QIDs need to be fetched. See TASK-A06.

**Confirmed API chain (checked 2026-04-30):**
- `entity_access.all_outlink_fetch(qid, repo_root)` is the correct Phase 2 public interface for full property retrieval. Cache-first: returns immediately if entity doc exists in cache. On miss: calls `full_fetch.full_fetch(depth=0)` internally, writing to the event log as `source_step="entity_fetch"`.
- `entity_access.get_cached_entity_doc()` reads via `_latest_cached_record(repo_root, "entity", qid)` which maps `"entity"` → `"entity_fetch"` in `cache.py`. The chain is fully wired.
- `ensure_basic_fetch()` only retrieves labels + P31/P279 — insufficient for P21/P102/P106/P108/P569/P19. **Do NOT use it as a property source.**
- Phase 5 code must never import from `full_fetch` directly. Use `entity_access.all_outlink_fetch`.

**CRITICAL — Network guardrail (discovered 2026-04-30):**  
`_http_get_json` in `cache.py` will **always raise `RuntimeError`** if `begin_request_context` has not been called first. This is Phase 2's explicit network budget guardrail. `full_fetch.full_fetch()` catches the exception and returns `None`, so failures are silent — every fetch returns `None` without any error output. The notebook cell `nb50_c05c` now correctly calls `entity_access.begin_request_context(budget_remaining=-1, query_delay_seconds=0.1, ...)` before the fetch loop and `entity_access.end_request_context()` in a `finally` block after it.

**⚠ WARNING FOR FUTURE SESSIONS: Before implementing ANY new Phase 5 → Phase 2 interaction, thoroughly read the Phase 2 Wikidata source code in `speakermining/src/process/candidate_generation/wikidata/`. The system has multiple interconnected guardrails (network budget, event sourcing, cache indexing, source_step naming) that are not obvious from the public API alone. Discovering them only at runtime (as we did here) wastes a full fetch run. Read `cache.py`, `event_log.py`, `event_writer.py`, and the relevant fetch module completely before writing any new code that touches this layer.**

**Action:** TASK-A06 in `open-tasks.md` tracks the dedicated fetch cell in `50_analysis.ipynb` (cell `nb50_c05c`). The cell is now correctly implemented: context initialized → fetch loop → context teardown → cache index reset.

---

## 9. Wikidata ID Source Fix (Applied 2026-04-29)

**Fixed in:** `gen_50_analysis.py` Cell 9 / `50_analysis.ipynb` Cell 9.

**What was wrong:** Step A used `dedup_persons.wikidata_id` (673 entries) for property lookup.

**Fix applied:**
- Derives best `wikidata_id` per canonical entity from `reconciled_ceid['wikidata_id']` (the reconciled, authoritative source), picking the highest `match_tier` row per entity
- Overrides `dedup_persons.wikidata_id` with this reconciled value
- Property lookup: archive first → entity_access cache → empty with count

**entity_store.jsonl note:** `archive/entity_store.jsonl` has 28M lines but is NOT line-delimited JSON. Do not parse directly; use `entity_access.get_cached_entity_doc()` which handles the format correctly.
