# Root Cause Analysis and Implementation Plan

## Summary

Two independent but related bugs corrupt the episode universe throughout the pipeline:

1. **Bug A — Cross-show episode merging (Phase 31):** The episode alignment function matches ZDF episodes to fernsehserien.de episodes by date alone, without verifying that both records describe the same show. This merges episodes from completely different shows that happened to air on the same date.

2. **Bug B — Fernsehserien.de as sole episode authority (Phase 50):** The analysis phase builds its episode universe exclusively from the raw fernsehserien.de metadata file, ignoring ~400 Markus Lanz episodes that exist only in ZDF Archiv or Wikidata. This silently drops those episodes from every occurrence matrix and statistic.

Bug A is the source of the corrupted person–episode mappings described in `issue.md`. Bug B is the source of the missing episode columns described in `investigation.md`. They share the same underlying assumption: fernsehserien.de is the authoritative source of truth for episodes. That assumption is false.

---

## Bug A: Cross-Show Episode Merging

### Location

[speakermining/src/process/entity_disambiguation/episode_alignment.py](../../../../speakermining/src/process/entity_disambiguation/episode_alignment.py) — `_match_fernsehserien_episode()`, lines 42–56.

### Root Cause

`fs_episode_metadata` (loaded from `data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv`) contains episodes from **all** crawled shows — `markus-lanz`, `couchwissen`, and any others. When `build_aligned_episodes()` iterates over ZDF episodes and calls `_match_fernsehserien_episode()`, it passes the entire multi-show `fs_metadata` DataFrame. The matching function then filters only by `premiere_date`:

```python
# episode_alignment.py:47 — NO show identity check
candidates = fs_metadata[fs_metadata["premiere_date"].map(parse_date) == zdf_date]
```

Any fernsehserien.de episode across any show that aired on the same date is a candidate. When multiple candidates remain (which happens whenever two tracked shows broadcast on the same date), the function applies a weak title heuristic ("folge" in episode title) and falls back to returning the first result by URL sort order:

```python
# episode_alignment.py:55-56
if not titled.empty:
    return titled.sort_values(by=["episode_url"]).iloc[0]
return candidates.sort_values(by=["episode_url"]).iloc[0]   # arbitrary
```

The `fs_metadata` DataFrame does contain a `program_name` column (the human-readable show name, e.g. "Markus Lanz", "couchwissen"), and the ZDF episode carries a `sendungstitel` field (the ZDF show title). Neither is compared during matching.

### Concrete Failure Path

1. ZDF episode "Markus Lanz 02.10.2024" (`publikationsdatum` = 2024-10-02) enters `_match_fernsehserien_episode()`.
2. Candidates = all fernsehserien.de episodes with `premiere_date` = 2024-10-02. This includes both `markus-lanz/folgen/...1747178` (correct) **and** `couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580` (wrong).
3. Neither candidate contains "folge" in its title; fallback returns whichever URL sorts first alphabetically — the couchwissen URL wins over the markus-lanz URL (`c` < `m`).
4. The ZDF Markus Lanz episode is merged with the couchwissen episode under `alignment_unit_id = ep_c3bc46df8b7e`, with `fernsehserien_de_id = https://www.fernsehserien.de/couchwissen/folgen/3x01-alles-steht-kopf-filmgespraech-1762580`.
5. All guests resolved against `ep_c3bc46df8b7e` inherit this couchwissen `fernsehserien_de_id` in `aligned_persons.csv`.
6. In Phase 50 analysis, `cluster_members` carries `fernsehserien_de_id_fernsehserien_de = couchwissen` for these persons → they are counted as couchwissen guests.

### Confidence Score Is Misleading

The merged record is assigned `match_confidence = 0.92` and `match_tier = high` (line 112). These values are hard-coded constants applied to any date match, regardless of the actual reliability of the match. A wrong-show merge looks identical to a correct merge in the output.

---

## Bug B: Fernsehserien.de as Sole Episode Authority

### Location

[speakermining/src/process/analysis/occurrence_matrix.py](../../../../speakermining/src/process/analysis/occurrence_matrix.py) — `build_person_catalogue()`, lines 131–133; `build_occurrence_matrix()`, lines 311–337.

[speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb) — cell that loads `episode_meta`.

### Root Cause

The notebook loads the episode universe from the raw fernsehserien.de import:

```python
# 50_analysis.ipynb (notebook cell)
episode_meta = pd.read_csv(
    "data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv", dtype=str
).fillna("")
```

This file is the fernsehserien.de source file forwarded into Phase 31, not the aligned output. It contains **only** episodes that fernsehserien.de tracked. Episodes that exist exclusively in ZDF Archiv or Wikidata are absent.

`in_scope_episode_urls` is derived from this file:

```python
# occurrence_matrix.py:131-133
in_scope_episode_urls = set(
    episode_meta[episode_meta["fernsehserien_de_id"].isin(in_scope_show_ids)]["episode_url"]
    .astype(str).str.strip()
)
```

The occurrence matrix columns are then restricted to this set:

```python
# occurrence_matrix.py:311-316
ep_order = (
    episode_meta[episode_meta["episode_url"].isin(in_scope_episode_urls)]
    [["episode_url", "premiere_date", "fernsehserien_de_id", "program_name"]]
    .drop_duplicates("episode_url")
    .sort_values("premiere_date")
)
ordered_episodes = list(ep_order["episode_url"])   # line 336
```

Any episode whose URL does not appear in `episode_meta` is silently dropped from the matrix columns. This accounts for the ~400 missing Markus Lanz episodes.

### Secondary Issue: Episode Identifier

The pivot and all downstream joins use `fernsehserien_de_id` as the episode key:

```python
# occurrence_matrix.py:330-333
matrix_num = guest_pairs.pivot_table(
    index="canonical_entity_id", columns="fernsehserien_de_id", ...
)
```

But in `aligned_episodes.csv`, the stable, source-neutral episode key is `alignment_unit_id`. Using `fernsehserien_de_id` as the episode identifier means any episode that has no fernsehserien.de record has no usable key in this join, further reinforcing the silent exclusion.

---

## Propagation Chain

```
Phase 20 (crawl)
  fs_episode_metadata: all shows, all episodes
  zdf_episodes: all ZDF-tracked shows, all episodes
        │
        ▼
Phase 31 (episode_alignment.py)
  Bug A: date-only match across shows
  → aligned_episodes.csv has wrong fernsehserien_de_id on merged rows
  → aligned_persons.csv inherits wrong fernsehserien_de_id via ep_c3bc46df8b7e
        │
        ▼
Phase 32 (deduplication)
  dedup_cluster_members.csv: fernsehserien_de_id_fernsehserien_de = "couchwissen"
  for guests who were actually on Markus Lanz
        │
        ▼
Phase 50 (occurrence_matrix.py)
  Bug B: episode universe = fernsehserien.de only
  → ~400 ZDF-only episodes never appear as columns
  → persons with wrong show assignment appear in wrong show's column
  → occurrence matrix is doubly corrupted
```

---

## Implementation Plan

### Fix A: Enforce Show Identity in Episode Matching

**File**: [speakermining/src/process/entity_disambiguation/episode_alignment.py](../../../../speakermining/src/process/entity_disambiguation/episode_alignment.py)

**Change**: Add a `show_norm` parameter to `_match_fernsehserien_episode()`. Before the date filter, restrict `fs_metadata` to rows where `normalize_text(program_name)` equals `show_norm`. If `show_norm` is empty or no rows match the filter, fall back to the unfiltered set.

```python
def _match_fernsehserien_episode(
    zdf_episode: pd.Series, fs_metadata: pd.DataFrame, show_norm: str = ""
) -> pd.Series | None:
    zdf_date = parse_date(zdf_episode.get("publikationsdatum", ""))
    if pd.isna(zdf_date):
        return None

    scope = fs_metadata
    if show_norm:
        scoped = fs_metadata[fs_metadata["program_name"].map(normalize_text) == show_norm]
        if not scoped.empty:
            scope = scoped

    candidates = scope[scope["premiere_date"].map(parse_date) == zdf_date]
    if candidates.empty:
        return None

    zdf_title_norm = normalize_text(zdf_episode.get("sendungstitel", ""))
    if zdf_title_norm:
        titled = candidates[candidates["episode_title_norm"].str.contains("folge", na=False)]
        if not titled.empty:
            return titled.sort_values(by=["episode_url"]).iloc[0]
    return candidates.sort_values(by=["episode_url"]).iloc[0]
```

In `build_aligned_episodes()`, extract the ZDF show name and pass it:

```python
# episode_alignment.py — inside the for-loop over zdf_episodes
zdf_show_norm = normalize_text(ep.get("sendungstitel", ""))
fs_match = _match_fernsehserien_episode(ep, fs_metadata, show_norm=zdf_show_norm)
```

**Validation**: After re-running Phase 31, confirm that:
- No `alignment_unit_id` has a `fernsehserien_de_id` pointing to a different show than the ZDF episode's `sendungstitel`.
- `ep_c3bc46df8b7e` (or any successor) maps Markus Lanz to a `markus-lanz/folgen/...` URL, not a couchwissen URL.

**Additional safeguard — lower confidence on ambiguous matches**: When a date match had multiple candidates from the same show (i.e., same-show date collision), lower `match_confidence` from 0.92 to a lesser value (e.g., 0.75) and record the ambiguity in `evidence_summary`. This makes partially uncertain merges visible in the output.

---

### Fix B: Use `alignment_unit_id` as the Episode Key in Phase 50

This fix has two sub-steps.

#### B1: Load the episode universe from `aligned_episodes.csv`

**File**: [speakermining/src/process/notebooks/50_analysis.ipynb](../../../../speakermining/src/process/notebooks/50_analysis.ipynb) and [speakermining/src/process/analysis/occurrence_matrix.py](../../../../speakermining/src/process/analysis/occurrence_matrix.py)

Replace the `episode_meta` load with `aligned_episodes.csv`:

```python
# Replace:
episode_meta = pd.read_csv(
    "data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv", dtype=str
).fillna("")

# With:
episode_meta = pd.read_csv(
    "data/31_entity_disambiguation/aligned/aligned_episodes.csv", dtype=str
).fillna("")
```

The `aligned_episodes.csv` schema differs from the raw fernsehserien.de file. The relevant columns map as follows:

| Concept | Raw fs file column | `aligned_episodes.csv` column |
|---|---|---|
| Episode key | `episode_url` | `alignment_unit_id` |
| Show ID | `fernsehserien_de_id` | `fernsehserien_de_id_fernsehserien_de` |
| Show name | `program_name` | `program_name_fernsehserien_de` |
| Air date | `premiere_date` | `premiere_date_date_fernsehserien_de` or `publikationsdatum_zdf` |
| FS episode URL | `episode_url` | `fernsehserien_de_id` (the fs episode URL field) |

#### B2: Replace `fernsehserien_de_id` with `alignment_unit_id` as the episode pivot key

**File**: [speakermining/src/process/analysis/occurrence_matrix.py](../../../../speakermining/src/process/analysis/occurrence_matrix.py)

Everywhere that `fernsehserien_de_id` is used as an *episode* identifier (not as a show identifier), replace with `alignment_unit_id`. Specifically:

- `build_person_catalogue()` line 131–136: filter and derive `in_scope_episode_ids` using `alignment_unit_id` and the show identity column (`fernsehserien_de_id_fernsehserien_de` or `program_name_fernsehserien_de`).
- `build_person_catalogue()` line 122–125: map `episode_url` to `alignment_unit_id` in `member_df`.
- `build_occurrence_matrix()` line 308: select `alignment_unit_id` instead of `fernsehserien_de_id` in `guest_pairs`.
- `build_occurrence_matrix()` line 330–333: pivot on `alignment_unit_id`.
- `build_occurrence_matrix()` line 336: `ordered_episodes` = list of `alignment_unit_id` values.

The `cluster_members` feed into `member_df`. Ensure that Phase 32 deduplication propagates `alignment_unit_id` from `aligned_episodes.csv` into each cluster member row so the join is possible.

#### B3: Derive a canonical air date per episode from all available sources

Since `aligned_episodes.csv` merges three sources, use a priority order to fill the air date:

1. `publikationsdatum_zdf` (ZDF is authoritative on broadcast date for its own episodes)
2. `premiere_date_date_fernsehserien_de`
3. Wikidata date if available

This single canonical date field should be used for sorting episode columns in the occurrence matrix.

---

### Execution Order

1. **Fix A** (Phase 31 episode alignment) — re-run Phase 31 to produce corrected `aligned_episodes.csv` and `aligned_persons.csv`.
2. **Fix B1** (Phase 50 episode universe) — update notebook and `occurrence_matrix.py` to load from `aligned_episodes.csv`.
3. **Fix B2** (Phase 50 episode key) — replace all episode-level uses of `fernsehserien_de_id` with `alignment_unit_id` throughout `occurrence_matrix.py` and the notebook.
4. **Verify B2 precondition** — confirm that `dedup_cluster_members.csv` from Phase 32 carries `alignment_unit_id` for each person–episode row. If not, Phase 32 must be updated to propagate it.
5. Re-run Phase 32 (if needed) and then Phase 50.
6. Validate occurrence matrices: episode column count must match the full union of ZDF + Wikidata + fernsehserien.de episodes for each show.

---

## Acceptance Criteria

| Check | Expected |
|---|---|
| No `alignment_unit_id` in `aligned_episodes.csv` links a ZDF show to a fernsehserien.de episode of a different show | Zero violations |
| Markus Lanz occurrence matrix column count | ≥ 2,033 (ZDF episode count) |
| couchwissen occurrence matrix contains only guests who appeared on couchwissen | Zero cross-show contamination |
| All three sources contribute to episode universe for each show | Confirmed by per-source episode count audit |
| `alignment_unit_id` is the episode key in occurrence matrices | No `fernsehserien_de_id` used as episode column header |
