# Open Tasks

Implementation tasks for the analysis and visualization redesign.  
**Requirements:** `00_requirements.md`  
**Design:** `01_design.md`  
**Dependency order:** see end of this file.

Tasks are ordered by dependency — foundation first, visualization last.

---

## TASK-B19 — Setup Config Files for Human Specification

**Priority:** Immediate — prerequisite for TASK-B01, TASK-B04, TASK-B14  
**Status:** Open  
**Requirements:** REQ-C01, REQ-H04, REQ-H06, REQ-V03

Create the following configuration files in `data/00_setup/`, following the existing CSV pattern (see `core_classes.csv`, `properties.csv` for format reference):

1. **`loop_resolution.csv`** — columns: `loop_member_qid, loop_member_label, designated_top_level_qid, designated_top_level_label, note`  
   Seed with the scientist (Q901) / researcher (Q1650915) / academic professional (Q66666685) / academic (Q3400985) loop; designated top-level = academic (Q3400985).
2. **`midlevel_classes.csv`** — columns: `wikidata_id, label, note`  
   Seed with: Q901 (scientist), Q37226 (teacher), Q135106813 (musical occupation), Q58635633 (media profession), Q12737077 (occupation).
3. **`party_colors.csv`** — columns: `wikidata_id, label, hex_color`  
   Seed with at minimum: CDU (Q49762), SPD (Q49763), Greens (Q49764), FDP (Q49802) and other major German parties present in the dataset.

All files must be human-editable without code changes. Code reads from them on every run.

---

## TASK-B01 — Color Registry

**Priority:** Immediate — prerequisite for all visualization tasks  
**Status:** Open  
**Requirements:** REQ-V01, REQ-V02, REQ-V03, REQ-I09  
**Depends on:** TASK-B19

Implement a global color registry module. Responsibilities:
1. Seed known party colors from `data/00_setup/party_colors.csv`
2. Assign colors deterministically from a palette for all other QIDs, ensuring uniqueness within a diagram
3. Maintain global consistency: once a QID is assigned a color, it retains that color across all diagrams
4. Expose a single lookup function: `get_color(qid_or_label) → hex`

---

## TASK-B02 — Person-Episode Occurrence Matrix

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-G01, REQ-G02, REQ-G03

Implement the occurrence matrix for each scope (per show + combined), filtered to the `guest` population:
1. `occurrence_matrix_all.csv` — all individuals
2. `occurrence_matrix_topX.csv` — top-X most occurring individuals (X configurable)
3. PNG visualizations of both

---

## TASK-B03 — Property Data Extraction by Type

**Priority:** Immediate — prerequisite for all property analysis  
**Status:** Open  
**Requirements:** REQ-P01–P06

Implement a property extraction layer:
- For each guest QID: extract values for all Item properties (REQ-P01, including occupation P106), Point in time (REQ-P02), Quantity (REQ-P03), String (REQ-P04)
- Compute Age per guest × episode appearance: `episode_publication_year − birth_year` (REQ-P05, P06)
- Tag each extracted value with its property type for downstream routing

---

## TASK-B04 — Class Hierarchy Computation

**Priority:** Immediate — prerequisite for Item analysis  
**Status:** Open  
**Requirements:** REQ-H01–H06  
**Depends on:** TASK-B19

1. Walk P279 chains from all first-level classes; record the hierarchy graph
2. Identify mid-level classes (REQ-H02)
3. Compute top-level class relative to each designated mid-level class (REQ-H03)
4. Detect loops; consult `data/00_setup/loop_resolution.csv` for manual designations; fall back to lowest QID number for unlisted cycles (REQ-H04, REQ-C01)
5. Apply deduplication logic for mid-level aggregation (REQ-H05)

---

## TASK-B05 — Universal Carrier-Based Statistics

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-U01–U05, REQ-U08, REQ-U09

Implement a single generic function `carrier_stats(property_id, data) → DataFrame` covering REQ-U01 through REQ-U05. All output tables must include both `person_count` and `appearance_count` columns (REQ-U09) and an explicit "Unknown / no data" row (REQ-U08). Apply to all properties.

---

## TASK-B06 — Universal Episode Appearance Statistics Table

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-U06

Implement a single generic function `episode_appearance_stats(property_id, data) → DataFrame` producing the eight-column table (min/episode, max/episode, mean, std dev, median, episode % without, total appearances, unique persons). Apply to all properties.

---

## TASK-B07 — Item: Co-occurrence Matrices and Combination Tables

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-I04–I07

1. Within-property co-occurrence matrix (Top 10 × Top 10)
2. Cross-property co-occurrence matrix per pair (Top 10 × Top 10)
3. Most common value combinations within property + unique combination count
4. Most common cross-property value combinations per pairing + unique combination count

*Note: Both same-person and same-episode co-occurrence types are required. Three matrix variants each (full, top-10×10 by occurrence, top-10×10 by co-occurrence). See REQ-I04/I05.*

---

## TASK-B08 — Visualization System Infrastructure

**Priority:** Immediate — prerequisite for all visualization tasks  
**Status:** Open  
**Requirements:** REQ-V05, REQ-V06, REQ-V07, REQ-V08, REQ-V09, REQ-V10, REQ-V11, REQ-V12, REQ-U08

Implement shared visualization helpers that enforce all cross-cutting requirements:
- `add_scope_label(ax, scope)` — REQ-V07
- `add_context_stats(ax, n_appearances, n_unique, n_empty)` — REQ-V10
- `sort_bars_descending(data)` — REQ-V05
- `stacked_bar_from_zero(...)` — REQ-V06
- `place_bar_labels(ax, bars)` — REQ-V09
- `apply_other_grouping(data, top_x)` — REQ-V11
- `add_unknown_row(data)` — REQ-U08 (gray, always last)
- `save_fig(fig, path)` — REQ-V08, REQ-V12 (save PDF + PNG at 300 DPI, then trigger quality review)

These helpers must be imported by every visualization cell; no inline re-implementation.

---

## TASK-B09 — Universal Visualizations (appearances + unique)

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-U07  
**Depends on:** TASK-B08

Implement total-appearances and unique-individuals charts for each property. Uses TASK-B08 helpers.

---

## TASK-B10 — Item: Timeline Visualizations

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-I01  
**Depends on:** TASK-B08

Cumulative and unique timeline per Item property.

*Note: Adaptive granularity (max 50 data points, coarsen progressively). Both running-total and count-per-bucket variants required. Combined visualization encouraged. See REQ-I01.*

---

## TASK-B11 — Item: Sunburst Visualizations

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-I02  
**Depends on:** TASK-B04, TASK-B08

Cumulative and unique sunburst per hierarchical Item property.

---

## TASK-B12 — Item: Sankey Diagram

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-I03  
**Depends on:** TASK-B04, TASK-B01

Per hierarchical Item property: produce two Sankey diagrams showing the class hierarchy flow (top-level classes on the left, mid-level classes in the middle, first-level classes on the right):
1. Flow width = total appearances
2. Flow width = unique persons

---

## TASK-B13 — Item: % A over B Stacked Bar Charts

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-I08  
**Depends on:** TASK-B08

Per Item property pair: stacked bar showing distribution of Property B within top-10 of Property A. Cumulative + unique variants.

*Note: Always percentage-normalized. Absolute count as label inside bar. Category axis label includes total occurrence count. See REQ-I08.*

---

## TASK-B14 — Mid-Level Class Dedicated Analyses and Visualizations

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-H05–H07  
**Depends on:** TASK-B04, TASK-B19

For each designated mid-level class (REQ-H06):
1. Sunburst of sub-types — unique individuals by type + cumulative appearances
2. Stacked bar chart of sub-types

*Note: Stacked bar content is covered by REQ-H07 itself — sunburst + stacked bar of sub-types per designated mid-level class. No separate specification needed.*

---

## TASK-B15 — Point in Time: Birth Year Visualizations

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-T01, REQ-T02  
**Depends on:** TASK-B03, TASK-B08

1. Distribution of guest appearances by birth year (REQ-T01)
2. Per-birth-year age stacked bar chart (REQ-T02), sorted chronologically

---

## TASK-B16 — Quantity: Violin Plot and Binary Presence

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-Q01, REQ-Q02  
**Depends on:** TASK-B03, TASK-B08

1. Age violin plot (REQ-Q01)
2. Binary presence bar charts for non-age quantity properties (REQ-Q02)

---

## TASK-B17 — String: Binary Presence

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-S01  
**Depends on:** TASK-B08

Binary presence visualization for String properties.

---

## TASK-B20 — Architecture: Visualization Caching

**Priority:** Immediate — prerequisite for all visualization tasks  
**Status:** Open  
**Requirements:** REQ-A02  
**Depends on:** TASK-B08

Extend the visualization infrastructure (TASK-B08) with checksum-based skip logic:
1. Before generating each visualization: compute input data checksum; check output file existence and output checksum against stored record
2. If all three match: skip generation, log "skipped (cached)"
3. After successful generation: record input checksum, output path, output checksum
4. Storage: a per-scope JSON sidecar file (e.g. `data/50_analysis/all/.viz_cache.json`)

Default behavior remains full regeneration; caching is opt-in per notebook run.

---

## TASK-B21 — Guest Appearance Frequency Distribution and Pareto

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-G04  
**Depends on:** TASK-B02, TASK-B08

1. Frequency distribution: how many guests appeared exactly 1, 2, 3, ... times
2. Pareto visualization: cumulative % of appearances accounted for by top X% of guests

---

## TASK-B22 — Person-Level Visualizations

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-PER01–REQ-PER06  
**Depends on:** TASK-B03, TASK-B08

1. REQ-PER01: Top guests stacked bar chart, segments per broadcasting program
2. REQ-PER02: Top guests per individual show
3. REQ-PER03: Individuals within category stacked bar (top-N persons + "other" per property value)
4. REQ-PER04: Individuals within occupation combination stacked bar
5. REQ-PER05: Individuals sorted by birth year with occurrence stacked bar
6. REQ-PER06: Person × person encounter matrix for top-N guests (configurable threshold)

---

## TASK-B23 — Episode-Level Visualizations and Dashboard

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-EPS01, REQ-EPS02  
**Depends on:** TASK-B08

1. REQ-EPS01: Episode statistics — count per show, guest count distribution, weekday distribution, broadcast frequency calendar heatmap
2. REQ-EPS02: Per-show dashboard — party sunburst + gender over time + occupation sunburst + episode frequency, one concise page per show

*Note: episode duration depends on data availability — see `open_additional_input.md`.*

---

## TASK-B24 — Meta-Level: Source Coverage and Data Completeness Visualization

**Priority:** High — independent of all property/person/episode analysis; can run in parallel  
**Status:** Open  
**Requirements:** REQ-META01  
**Depends on:** TASK-B08

For each scope (per show + combined):
1. Compute per-episode source attribution: which source(s) (ZDF Archiv, Fernsehserien.de, Wikidata) contributed data for each episode
2. Identify completeness gaps: episodes where one source was missing data later filled by another
3. Produce source coverage visualization(s): must remain legible at hundreds-to-thousands of episodes; adaptive layout required
4. Candidate approaches to evaluate: episode × source heatmap matrix, stacked timeline by source, calendar heatmap with source-combination color coding

---

## TASK-B25 — Define Extended Color Palette and Update Visualization Principles

**Priority:** Immediate — prerequisite for TASK-B01  
**Status:** Open  
**Requirements:** REQ-V01, REQ-V02, REQ-V03, REQ-V14  
**Depends on:** TASK-B19

Define the extended color palette used by the color registry (REQ-V14). The Okabe-Ito 8 colors are the seed set; this task extends them to 12–16 total colorblind-safe colors so that visualizations with 10+ distinct entities have a larger range before wrapping occurs.
   * **Clarification:** We must be able to do this automatically. When Okabe-Ito only has 8 colors and we need 16, then use Redundant Encoding: Don't rely solely on color. Add different filling or line types (dashed, dotted, solid), ensuring they remain clear in grayscale.

1. Confirm the two reserved colors (`#999999` for Unknown, `#CCCCCC` for Other) are not included in the palette; if any clash exists, adjust the reserved shades
2. Implement palette collision avoidance in `color_registry.py`: after seeding known party colors, remove any palette entries whose hex matches an already-seeded hex before dynamic assignment
   * **Clarification:** The parties don't have a monopoly on their colors. It is fine if an occupation shares the same color as a political party.
3. Update `documentation/visualizations/visualization-principles.md`: add the extended palette entries; document the Unknown/Other color distinction; document the collision-avoidance rule

---

## TASK-B26 — Cross-Show Comparison Visualizations

**Priority:** Immediate  
**Status:** Open  
**Requirements:** REQ-G05  
**Depends on:** TASK-B05, TASK-B08

For the combined scope, produce cross-show comparison visualizations for at minimum occupation, gender, and political party:
1. Grouped bar chart: top-N property values on X-axis, one bar per show per group, Y-axis = % share within each show's total
2. Heatmap alternative: rows = property values, columns = shows, cell = percentage

Implemented in `viz_comparison.py`. Output under `all/comparison/`.

---

## TASK-B27 — Property Coverage Dashboard

**Priority:** High — independent; can run in parallel with other tasks  
**Status:** Open  
**Requirements:** REQ-META02  
**Depends on:** TASK-B05, TASK-B08

For each scope, produce a property coverage dashboard:
1. Compute per-property: `pct_with_value`, `pipeline_match_rate`, `pct_with_references`
2. Output summary table as `property_coverage.csv`
3. Produce horizontal bar chart sorted by `pct_with_value` descending, bars colored by property type

Implemented in `viz_coverage.py`. Output under `meta/`.

---

## TASK-B18 — HTML/PDF: Wikidata Link Embedding

**Priority:** Lowest — implement last, after all other tasks are complete  
**Status:** Open  
**Requirements:** REQ-V04

Embed Wikidata hyperlinks in all entity labels in HTML and PDF outputs.

---

## Dependency Order Summary

```
TASK-B19 (config files)
  ↓
TASK-B25 (resolve CDU-black conflict)   ← prerequisite for B01
  ↓
TASK-B01 (color registry)
TASK-B08 (viz infrastructure)
  ↓
TASK-B02 (occurrence matrix)
TASK-B03 (property extraction)
  ↓
TASK-B04 (class hierarchy)
TASK-B05 (carrier stats)
TASK-B06 (episode stats)
TASK-B07 (item co-occurrence)
TASK-B20 (viz caching)          ← extends TASK-B08
  ↓
TASK-B09 (universal viz)
TASK-B10 (item timelines)
TASK-B11 (item sunburst)
TASK-B12 (item sankey)
TASK-B13 (item % A over B)
TASK-B14 (mid-level class viz)
TASK-B15 (birth year viz)
TASK-B16 (quantity viz)
TASK-B17 (string viz)
TASK-B21 (guest freq distribution + pareto)
TASK-B22 (person-level viz)
TASK-B23 (episode-level viz + dashboard)
TASK-B24 (meta: source coverage viz)    ← independent, can run in parallel
TASK-B26 (cross-show comparison viz)    ← depends on B05, B08
TASK-B27 (property coverage dashboard)  ← independent, can run in parallel
  ↓
TASK-B18 (html/pdf links)       ← lowest priority
```
