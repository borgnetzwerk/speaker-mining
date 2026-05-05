# Open Tasks

Finalized and deduplicated backlog for implementation.

Policy for this file:
- Keep stable task IDs (`TASK-F..`) for planning and archiving.
- Track source lineage explicitly so old context remains auditable.
- Mark tasks as `Open`, `Partial`, `Blocked`, `Low priority`, or `Resolved`.

## TASK-F01 - Guest Role Separation and Appearance Accounting
**Priority:** Immediate  
**Status:** Partial

**Problem:** Guest and moderator roles are still mixed in analysis paths, and appearance totals are inconsistent (property-level appearances can exceed total guest appearances).

**Scope:**
1. Perform per-episode person role classification once (`guest`, `moderator`, other) and reuse it across all downstream steps.
2. Ensure guest-only occurrence matrices and analyses are strictly guest-filtered.
3. Fix appearance aggregation logic so per-property appearance totals cannot exceed total guest appearances.
4. Fix `min per episode` computation so zeros are preserved.

**Primary sources:**
- 2026-05-04 additional input (`Fixes`)
- 2026-05-04 starting point
- 2026-04-30 tasks: TASK-B02, TASK-B06

**Progress update (2026-05-04):**
- Notebook property extraction is now guest-only (guest catalogue + guest episode map), so moderator/staff rows no longer expand into guest property occurrence outputs.
- Birthyear projection now keeps a single stable `birthyear` column and avoids `birthyear_x`/`birthyear_y` collisions that caused `KeyError: ['birthyear'] not in index`.
- Property statistics now expand from unique guest-episode rows, not guest totals; a regression test covers the 100-person / 40-episode counting model and prevents appearance inflation.
- Property expansion for guest-level values now derives episode joins from the occurrence basis (`ri_with_role` + canonical catalogue QIDs), which restored expected `P21` carrier coverage.
- Each property now also emits a `value_episode_matrix.csv` artifact (value x episode with unique-guest counts per cell) to support zero-based diagnostics directly.

**New evidence (2026-05-05) — role filtering still broken downstream:**
- `guest_frequency_pareto` still includes moderators: Frank Plasberg (role="Moderation") appears in the Pareto chart.
- Gert Scobel is wrongly ranked as top guest of the show he moderates (scobel); his role is recorded as moderator but is not filtered from the Pareto output.
- 3sat (role="Produktionsauftrag") also appears in the Pareto ranking — production entities are not excluded.
- Root cause: `build_guest_frequency_pareto_outputs` receives `guest_catalogue` but that frame is not pre-filtered to `role == "guest"` before being passed in; the function itself does not filter by role.
- The occurrence matrix `catalogue` has correct role assignments, but the caller site does not apply `catalogue[catalogue["role"] == "guest"]` before constructing Pareto/per-show top-guest outputs.
**Progress (2026-05-05):**
- Root cause fixed: `role_priority` in `build_person_catalogue` changed from `{guest:0, moderator:1, staff:2}` to `{moderator:0, staff:1, guest:2}` so the `min()`-based dominant-role aggregation now correctly classifies anyone who ever moderated as "moderator", not "guest".
- `build_role_occurrence_matrices` added to `occurrence_matrix.py` and exported from `__init__.py`. Produces separate moderator and staff occurrence matrices matching the guest matrix format.

**Progress (2026-05-05 — confirmed 2026-05-06):**
- Role matrices wired into notebook (cell `c5f630c5`). Moderator/staff matrices now written.
- Pareto and scobel occurrence_matrix confirmed clean — Plasberg and Gert Scobel no longer appear.
- `top_guests.csv` per show does not exist — `compute_top_guests_by_show` exists in `person_analysis.py` but is never called from the notebook. Needs wiring.

**Progress (2026-05-05 session 3):**
- `compute_top_guests_by_show` wired into notebook (markdown cell `a7f2c5e8`, code cell `b3d9e1f4`) after per-show stats cell `77d0a8d8`. Writes `top_guests.csv` to each show directory and `top_guests_combined.csv` to `all/`.

**Remaining work:**
- Validate end-to-end appearance totals against expected bounds (25,902 total appearances vs per-property totals).
- Investigate PRECISELY 19,000 gender appearances (see TASK-F12) — current run shows 24,467 for P21, suggesting this was from an earlier pipeline version.

---

## TASK-F02 - Dynamic Property-Driven Analysis Pipeline
**Priority:** Immediate  
**Status:** Open

**Goal:** One unchanged notebook run should generate all suitable analyses/visualizations for every configured property and applicable property combination.

**Scope:**
1. Drive analysis routing from `data/00_setup/analysis_properties.csv`.
2. Introduce registration/catalogue-driven analysis and visualization execution (plug in once, run everywhere applicable).
3. Extend property-combination routing so cross-property analyses run automatically where meaningful.

**Primary sources:**
- 2026-05-04 starting point (target implementation)
- 2026-04-29 TASK-A01, TASK-A12

---

## TASK-F03 - Class Hierarchy and Loop Resolution Completion
**Priority:** Immediate  
**Status:** Open

**Scope:**
1. Complete P279 hierarchy walk and mid-level mapping.
2. Resolve loops via `data/00_setup/loop_resolution.csv` with deterministic fallback.
3. Publish loop diagnostics (`number_of_loops`, `classes_in_loops`).
4. Fix hierarchy quality issues that break occupation rollups and hierarchy charts.

**Primary sources:**
- 2026-04-30 TASK-B04, TASK-B14
- 2026-04-29 TASK-A02
- 2026-05-04 additional input (`Loops`)

---

## TASK-F04 - Standardized Property Statistics and Combination Tables
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Complete the universal per-value episode statistics table for every property type where applicable.
2. Complete within-property and cross-property combination tables with unique combination counts.
3. Add analysis outputs for `unique vs total` gaps, dominance checks, and outlier detection.
4. Add meta statistics for property type coverage (item/string/quantity/time).

**Primary sources:**
- 2026-04-30 TASK-B05, TASK-B06, TASK-B07
- 2026-04-29 TASK-A04, TASK-A05
- 2026-05-04 additional input (`Meta Statistics`, `Per property`)

**Progress update (2026-05-04):**
- Notebook property standardization now preserves the full guest base and no longer assumes a pre-existing `value` column after merging extracted rows.
- Property outputs run successfully for all 16 enabled properties, including `P21`, with guest-level rows retained for carrier statistics.
- Remaining work: confirm the downstream combination tables and any per-property diagnostics still aggregate from the same guest-preserving base.

---

## TASK-F05 - Visualization Infrastructure Hardening
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Finalize shared chart helpers for reusable labeling, ordering, unknown buckets, and scope/context metadata.
2. Implement visualization caching sidecar (checksum-based skip logic).
3. Ensure dual export contract (PNG + PDF).
4. Make long-label handling robust: dynamic width, wrapping, and height adaptation.
5. Add language variants (DE/EN) with fully localized chart text — language convention: EN uses lowercase labels ("distribution", "appearances"), DE uses German capitalization rules ("Verteilung", "Auftritte").
6. Include episode-count and broadcasting-program context in titles/subtitles.
7. Keep "Unknown" visually and physically separate from the main bars. It must not appear as a competing bar that distorts the proportions of meaningful values. Implement as a secondary axis panel, footnote, or visually distinct separator.

**Primary sources:**
- 2026-04-30 TASK-B08, TASK-B20
- 2026-05-04 additional input (`Visualizations are not very dynamic yet`)
- 2026-05-06 additional input (`On Visualizations`)

---

## TASK-F06 - Universal and Cross-Property Chart Completion
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Finalize universal charts (including ColorRegistry integration and export behavior).
2. Complete `% A over B` stacked bar families (unique + appearances).
3. Ensure segment labels and sorting conventions are consistently applied.

**Primary sources:**
- 2026-04-30 TASK-B09, TASK-B13
- 2026-05-04 additional input (`Stacked Bar charts`)

---

## TASK-F07 - Hierarchical Item Visualizations
**Priority:** Immediate  
**Status:** Open

**Scope:**
1. Implement timeline visualizations with adaptive granularity.
2. Implement sunburst visualizations for hierarchical item properties.
3. Implement Sankey visualizations for hierarchy flows.
4. Add dedicated mid-level-class visualizations.

**Primary sources:**
- 2026-04-30 TASK-B10, TASK-B11, TASK-B12, TASK-B14
- 2026-04-29 TASK-A02

---

## TASK-F08 - Scalar, Quantity, String, and Extended Plot Families
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Birth-year analysis must aggregate by year (not exact date).
2. Complete quantity/string binary presence analyses.
3. Complete age distribution visualizations and related scalar outputs.
4. Add approved extended plot families where suitable: scatter, box+strip, violin, stacked area, treemap, radar.

**Primary sources:**
- 2026-04-30 TASK-B15, TASK-B16, TASK-B17
- 2026-05-04 additional input (`Birth year`, `string binary`, `Additional visualization types`)

**Progress update (2026-05-04):**
- Birthyear carry-over for catalogue generation has been stabilized to prevent notebook failure in downstream age/scalar calculations.


To retrieve a person's birth-year, we must derive it from birth-date, if available.

```
---------------------------------------------------------------------------
KeyError                                  Traceback (most recent call last)
Cell In[4], line 145
    139     catalogue["birthyear"] = ""
    141 CATALOGUE_COLS = [
    142     "canonical_entity_id", "wikidata_id", "canonical_label", "cluster_size",
    143     "cluster_strategy", "cluster_confidence", "role", "appearance_count", "birthyear",
    144 ]
--> 145 catalogue = catalogue[CATALOGUE_COLS]

File c:\workspace\git\borgnetzwerk\speaker-mining\.venv\Lib\site-packages\pandas\core\frame.py:4384, in DataFrame.__getitem__(self, key)
   4382     if is_iterator(key):
   4383         key = list(key)
-> 4384     indexer = self.columns._get_indexer_strict(key, "columns")[1]
   4386 # take() does not accept boolean indexers
   4387 if getattr(indexer, "dtype", None) == bool:

File c:\workspace\git\borgnetzwerk\speaker-mining\.venv\Lib\site-packages\pandas\core\indexes\base.py:6302, in Index._get_indexer_strict(self, key, axis_name)
   6299 else:
   6300     keyarr, indexer, new_indexer = self._reindex_non_unique(keyarr)
-> 6302 self._raise_if_missing(keyarr, indexer, axis_name)
   6304 keyarr = self.take(indexer)
   6305 if isinstance(key, Index):
   6306     # GH 42790 - Preserve name from an Index

File c:\workspace\git\borgnetzwerk\speaker-mining\.venv\Lib\site-packages\pandas\core\indexes\base.py:6355, in Index._raise_if_missing(self, key, indexer, axis_name)
   6352     raise KeyError(f"None of [{key}] are in the [{axis_name}]")
   6354 not_found = list(ensure_index(key)[missing_mask.nonzero()[0]].unique())
-> 6355 raise KeyError(f"{not_found} not in index")

KeyError: "['birthyear'] not in index"
```

---

## TASK-F09 - Episode, Source, and Cross-Show Dashboards
**Priority:** Immediate  
**Status:** Partial

**Scope:**
1. Complete episode-level dashboards and frequency/coverage visuals.
2. Complete source attribution/completeness visualizations (Wikidata/Fernsehserien/ZDF, including unique-only source coverage).
3. Complete cross-show comparison visualizations.
4. Complete property coverage dashboard outputs.
5. Extend episode-specific property analysis pipeline (duration/date/guest_count/description/topic/transcript/quote when available).
6. Convert Pareto chart from simple bars to stacked bars: each bar is one guest, segments = one per show (colored by show), bar label = appearances on that show + % of that show's total, top annotation = total appearances across all shows + % of all appearances. This answers "Robin Alexander had 40 appearances on Markus Lanz (3% of that show) and 153 total (1% of all)".

**Primary sources:**
- 2026-04-30 TASK-B23, TASK-B24, TASK-B26, TASK-B27
- 2026-05-04 additional input (`Source specific analysis`, `Episode specific property visualization`)
- 2026-05-06 additional input (`On Visualizations`, `Pareto stacked bar`)

**Progress update (2026-05-04):**
- The notebook now emits a guest frequency distribution table plus a Pareto chart/output bundle for top guest appearances, using the analysis-layer aggregation helpers.
- Visualization cleanup also removed notebook-level stub imports that were no longer needed once the Pareto output became real.
- Source attribution now has an actual dashboard layer: overall coverage, stacked by-show completeness, and unique-person coverage comparison charts are written from the meta-analysis outputs.
- The chart construction for those dashboard families now lives in `speakermining/src/process/analysis/viz_dashboards.py`; the notebook only dispatches the module calls.

**Progress (2026-05-05 session 3):**
- Pareto chart converted to stacked bar chart per-show (TASK-F09 item 6). `_build_stacked_pareto` added to `viz_dashboards.py`: each bar segment represents one broadcasting show, labeled with `{n} ({pct}% of show)`; total + overall percentage annotated above each full bar. Notebook cell `229b7a80` updated to pass `episode_appearances` to trigger stacked mode. `_build_simple_pareto` retained as fallback when no episode data is available.
  * **Clarification:** We should not mix the two. The new version is overloaded and would serve better as a two separate graphics:
    * One horizontal stacked bar chart
    * And one pareto.

---

## TASK-F10 - Person-Level and Relevance Analyses
**Priority:** High  
**Status:** Partial

**Scope:**
1. Complete person-level chart set (top guests, by-show, within-category, encounter matrix).
2. Add per-person claim count outputs.
3. Define and implement a documented "most relevant person" metric.
4. Preserve and extend specialization/dominance analyses.
5. Wire `compute_top_guests_by_show` from `person_analysis.py` into the notebook; write `top_guests.csv` to each per-show output directory. This file is currently missing despite the function existing.
6. For the top-N most-appeared guests: report which configured properties were empty (no Wikidata value found). This surfaces gaps like Robin Alexander / "Die Welt" employer not being in Wikidata.

**Primary sources:**
- 2026-04-30 TASK-B22
- 2026-04-29 TASK-A10
- 2026-05-04 additional input (`Per Person`)
- 2026-05-06 additional input (`Empty properties for highly relevant individuals`)

---

## TASK-F11 - Temporal Claim Qualification and Historical Views
**Priority:** High  
**Status:** Partial

**Scope:**
1. Finish claim-level temporal qualification plumbing (`is_temporal`, optional `effective_at`).
2. Add optional "look to the past" analyses (pre-appearance roles/affiliations) as separate outputs.
3. Keep historical/counterfactual outputs explicitly separated from active-at-episode outputs.

**Primary sources:**
- 2026-04-30 TASK-B28
- 2026-05-04 additional input (`Look to the past`)

---

## TASK-F12 - Data Quality and Coverage Follow-Ups
**Priority:** High  
**Status:** Open

**Scope:**
1. Resolve age outliers/data quality checks before publication.
2. Verify fernsehserien.de ID linkage quality for unresolved persons.
3. Continue implementation-vs-spec compliance review as part of finalization.
4. Ensure all analysis basis data used at runtime is copied into analysis output space.
5. ~~Investigate "PRECISELY 19,000 appearances with gender"~~ — **Resolved (2026-05-05 session 3)**. No hardcoded 19,000 value exists anywhere in the codebase (`grep` confirms zero matches). Current pipeline produces 24,467 P21 appearance rows, which is a natural non-round number. The 19,000 figure was from an earlier pipeline version with different expansion logic. No bug present.
6. Investigate apparent duplicate QIDs for semantically-equivalent values: "Doktor phil" vs "Doktor Philosophiae", "Evangelisch-lutherische Kirche" vs "Evangelisch-lutherische kirche" (capitalization variant), "Evangelische Kirche". These split the same real-world concept across multiple QIDs, distorting property value distributions.

**Primary sources:**
- 2026-04-29 TASK-A09, TASK-A11, TASK-A13
- 2026-05-04 additional input (`Ensure correct fernsehserien IDs`, `data basis`)
- 2026-05-06 additional input (`PRECISELY 19,000 appearances`, `Interesting apparent duplicates`)

---

## TASK-F13 - Documentation and Structural Compliance
**Priority:** High  
**Status:** Open

**Scope:**
1. Enforce taxonomy/function labels across documentation and notebooks.
2. Keep finalization backlog synchronized with implementation status.
3. Keep this task file as the canonical implementation queue for finalization.

**Primary sources:**
- 2026-04-29 TASK-A12
- 2026-05-04 starting point

---

## TASK-F14 - Lower-Priority Exploratory Angles
**Priority:** Low priority  
**Status:** Open

**Scope:**
1. Poisson-distribution applicability check.
2. Party-history deep dives and trajectory analyses.
3. Additional exploratory/experimental visual variants not blocking baseline delivery.

**Primary sources:**
- 2026-04-29 TASK-A05
- 2026-05-04 additional input (`Investigate if applicable angle for analysis`)

---

## TASK-F15 - PageRank Node Visualizations
**Priority:** Low priority  
**Status:** Open

**Scope:**
1. Implement person node-graph visualization sized/colored by rank score.
2. Implement class node-graph visualization.
3. Implement combined node-graph view where useful.
4. Export using the same chart/output contract as the rest of analysis visualizations.

**Primary sources:**
- 2026-04-29 TASK-A03

---

## TASK-F16 - Person Quality Tier Classification
**Priority:** High  
**Status:** Partial

**Scope:**
Classify every person in the catalogue into one of four quality tiers based on source reconciliation depth:
1. Reconciled with Wikidata — known QID, full property coverage possible.
2. Wikidata-only mention — appeared in a Wikidata statement but no Wikidata entity doc; limited properties.
3. Cross-source non-Wikidata match — matched between ZDF Archiv and fernsehserien.de but no Wikidata link.
4. Single-source only, not Wikidata — found in exactly one crawled source that is not Wikidata.

Rules:
- Tiers 1 and 2 only are used in property statistics and visualizations.
- All four tiers appear in summary counts, each in their own row/column — never aggregated together.
- Tier 1 is the only "truly high quality" tier with reliable property data.
- Target distribution (aspirational): Tier 1 ≈ 97%, Tier 2 ≈ 1%, Tier 3 ≈ 2%, Tier 4 ≈ 0%.

**Implementation:**
- Add `data_quality_tier` column to the person catalogue during `build_person_catalogue`.
- Tier 1: `wikidata_id` is non-empty and entity doc exists in `core_persons`.
- Tier 2: `wikidata_id` is non-empty but no entity doc (Wikidata-mentioned, not resolved).
- Tier 3: `wikidata_id` is empty but person was matched across two or more non-Wikidata sources (detectable from `cluster_strategy` or source columns in `cluster_members`).
- Tier 4: `wikidata_id` is empty and single-source only.
- Write `data/50_analysis/all/person_quality_tiers.csv` with tier counts and per-show breakdowns.
- Filter all property stats and visualization input frames to `data_quality_tier.isin([1, 2])`.

> **Clarification:**
> The currently implemented definition of Tiers is wrong. 
> 
> This is not correct:
>     # Tier 1: Wikidata QID + entity doc in core_persons cache — full property coverage.
>     # Tier 2: Wikidata QID present but no entity doc — Wikidata-mentioned only.
>     # Tier 3: No Wikidata QID but cluster_size > 1 — matched across multiple sources.
>     # Tier 4: No Wikidata QID and cluster_size == 1 — single non-Wikidata source only. 
> 
> This is correct:
>     # Tier 1: Wikidata QID + any other match, e.g. in ZDF or in fernsehserien.de. Entry (e.g. "Episode 1" or "Bob Something") exists in at least two databases, at least one of them being Wikidata.
>     # Tier 2: Wikidata QID without any other match, e.g. no match in ZDF or in fernsehserien.de. Entry (e.g. "Episode 1" or "Bob Something") exists only in Wikidata.
>     # Tier 3: No Wikidata QID but cluster_size > 1 — matched across multiple sources.
>     # Tier 4: No Wikidata QID and cluster_size == 1 — single non-Wikidata source only.
> 
> Important: All of this refers ONLY to entries that are actually related to our analyzed shows: Episodes, guests, staff, etc. Any incedental captured people or shows are not even counted in this quality tier: They are incedental and can be ignored for analysis. If we have 5 or 5000 of them - it does not matter.


**Progress (2026-05-05 session 3):**
- `_quality_tier()` function and `catalogue["data_quality_tier"]` column added to `build_person_catalogue` in `occurrence_matrix.py` (lines 201–218).
- `data_quality_tier` added to `CATALOGUE_COLS` in notebook cell `5687e84e` so the column survives the trim.
- Notebook cells `d4f8a231` (markdown) and `e5c9b342` (code) inserted after dataset overview to write `person_quality_tiers.csv` and expose `wikidata_guest_ceids` set for downstream filtering.

**Remaining work:**
  * **Clarification:** First: Rework the definition and implementation of TASK-F16 to correctly reflect the intended quality tiers, just as the `> **Clarification:**` block above specifies: Wikidata + other(s), Wikidata solo, others, other solo.
- Apply `data_quality_tier.isin([1, 2])` filter to property stats expansion inputs so only Wikidata-reconciled persons enter visualization statistics.
  * Still textually document within the documentation how many Tier 3 / Tier 4 entries are not part of this visualization.
- Add per-show tier breakdown to `person_quality_tiers.csv`.

**Primary sources:**
- 2026-05-06 additional input (`On "unique" persons`)

---

## TASK-F17 - Structured Output Folder Documentation
**Priority:** High  
**Status:** Partial

**Scope:**
Generate a `README.md` in each output folder that, when navigated on GitHub, immediately shows the most relevant data and embedded visualizations — no file-clicking required.

Rules:
- Each `data/50_analysis/<scope>/README.md` (where scope = `all`, per-show directories) is auto-generated from the analysis outputs.
- Embeds PNG visualizations inline using relative Markdown image links.
- Includes top-level summary stats (episode count, guest count, show name, date range).
- Includes the top-10 rows of the most important tables (top guests, property distributions).
- Folder navigation on GitHub alone is sufficient to understand the key findings.
- README content is purely based on published/GDPR-safe data — no person-level detail beyond what appears in the top-guest lists.
- README generation is its own module: `analysis/readme_generator.py`. The notebook calls it after all outputs are written.

**Progress (2026-05-05 session 3):**
- `readme_generator.py` module created with `generate_all_readme`, `generate_show_readme`, and `generate_all_readmes`.
- Exported from `analysis/__init__.py`.
- Notebook cells `f6a3c891` (markdown) and `c9d2b745` (code) inserted after export summary. Reads `top_guests.csv` per show (written by cell `b3d9e1f4`), reconstructs per-show dict, calls `generate_all_readmes`.

**Remaining work:**
- Expand embedded visualization list in `all/README.md` as more chart types are completed.
- Add per-show visualizations once per-show charts are generated.
- Validate output visually on GitHub after first commit.

**Primary sources:**
- 2026-05-06 additional input (`Structured Output folder documentation generation`)

---

## TASK-F18 - GitIgnore Tuning for GitHub Publication
**Priority:** High  
**Status:** Partial

**Scope:**
Configure `.gitignore` so that GDPR-safe, reasonably-sized, publication-ready analysis outputs are tracked by git and visible on GitHub.

Rules for inclusion (all three must be satisfied):
1. Does NOT contain GDPR-sensitive data identifying a specific person (demographic overviews are fine; per-person profiles are not).
2. Does NOT exceed a reasonable file size (CSV files with full matrices may be too large; prefer summary/aggregate outputs).
3. Does NOT have a direct sibling that serves the same purpose (from PNG / PDF / HTML — choose one; PNG is preferred for GitHub rendering).

Specific decisions:
- Visualizations: include PNG only (not PDF, not HTML).
- CSVs: include aggregate/summary CSVs (carrier_stats, episode_stats, per_show_statistics, top_guests); exclude raw occurrence matrices (too large and contain person-level data) and per-person property profiles.
- README.md files: always include.
- The `data/50_analysis/persons/` directory: exclude entirely (GDPR-sensitive).
- Write explicit `.gitignore` rules in `data/50_analysis/.gitignore`.

**Progress (2026-05-05 session 3):**
- Root `.gitignore` updated: unignores `data/50_analysis/all/` and per-show dirs, re-ignores `persons/`, `*_occurrence_matrix.csv`, `value_episode_matrix.csv`, `*.pdf`, `*.html`.

**Remaining work:**
- Verify rules with `git check-ignore` after next notebook run populates outputs.
- Consider adding a `data/50_analysis/.gitignore` for finer-grained control inside the analysis tree.

**Primary sources:**
- 2026-05-06 additional input (`GitIgnore tuning`)

---

## Task Lineage Notes

Items explicitly recognized as already resolved in prior documentation (not queued here as implementation tasks):
- 2026-04-29 TASK-A01, TASK-A06, TASK-A07, TASK-A08

Items represented as sub-scope under `TASK-F..` IDs above rather than duplicated one-to-one:
- 2026-04-30 TASK-B18 integrated under chart/export completion scope
- 2026-04-30 TASK-B21 integrated under dashboard/statistics scope
