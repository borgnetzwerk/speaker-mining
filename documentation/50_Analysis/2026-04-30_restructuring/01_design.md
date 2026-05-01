# Design

**Status:** Phase 3 complete — authoritative design specification.
**Source requirements:** `00_requirements.md` (59 requirements, all resolved)
**Downstream:** `open-tasks.md` (24 implementation tasks)

---

## Design Principles

1. **Produce all applicable → evaluate empirically.** Do not theorize whether a property has a meaningful hierarchy or visualization. Produce all applicable outputs for all properties unconditionally. Evaluate meaning by reviewing the generated outputs, not by pre-filtering. A non-meaningful visualization costs one page of output; pre-filtering costs a design discussion and risks silently omitting something valuable.
2. **Configurable by humans, not hardcoded.** Any value requiring domain judgment (class designations, party colors, loop resolution) must live in a human-editable config file, not in notebook cells. See `data/00_setup/`.
3. **Keep things human-readable.** Labels and directory names use the property label (e.g. `occupation/`, "occupation (P106)"), never raw PIDs.
4. **Notebooks orchestrate; modules contain logic.** Notebook cells are entry points and sequencing only. All reusable logic lives in Python modules under `speakermining/src/`. No significant computation in notebook cells.
5. **Regenerate by default; cache only expensive visualizations.** Always regenerate unless checksum-based caching confirms both input and output are unchanged (REQ-A02). Never reuse stale results.
6. **Idempotent.** Running the full pipeline twice on the same input must produce byte-identical outputs. No random seeds, no time-dependent defaults, no non-deterministic ordering. Every output can be reproduced exactly from the same inputs.
7. **German-first label resolution.** When resolving a QID to a human-readable label, prefer the German label from `instances.csv` (which contains German preferred labels). Fall back to the English label if no German label is present. Never display raw QIDs in user-facing output.
8. **Progress reporting.** Every analysis and visualization step must log its progress to notebook output: at minimum the step name, the scope, and the property being processed. Long loops must report progress within the loop (e.g. every 10th item or every 10 seconds). Silent cells are not acceptable.

---

## Architecture Overview

### Pipeline Flow

```
data/00_setup/                     speakermining/src/analysis/
  party_colors.csv  ──────────────► color_registry.py       (Layer 0)
  midlevel_classes.csv ───────────►
  loop_resolution.csv ───────────►  class_hierarchy.py      (Layer 1c)
  properties.csv ────────────────►  property_extraction.py  (Layer 1b)

data/ (episode + guest data) ─────► occurrence_matrix.py    (Layer 1a)
                                 ├► property_extraction.py  (Layer 1b)
                                 └► class_hierarchy.py      (Layer 1c)
                                          │
                                          ▼
                               Layer 2: Analysis modules
                               (universal_stats, cooccurrence,
                                midlevel_aggregation, person_analysis,
                                episode_analysis, source_coverage)
                                          │
                                          ▼
                               Layer 3: Visualization modules
                               (viz_base, viz_universal, viz_timelines,
                                viz_sunburst, viz_sankey, viz_cooccurrence,
                                viz_stacked_pct, viz_persons, viz_episodes,
                                viz_meta, ...)
                                          │
                                          ▼
                               data/50_analysis/<scope>/<property>/...
```

### Module Structure

```
speakermining/src/analysis/
  color_registry.py        # Layer 0 — global QID→color mapping
  occurrence_matrix.py     # Layer 1a — person×episode matrix
  property_extraction.py   # Layer 1b — per-property DataFrames by type
  class_hierarchy.py       # Layer 1c — P279 walk, loop resolution, level assignments
  universal_stats.py       # Layer 2a/2b — carrier stats + episode appearance stats
  cooccurrence.py          # Layer 2c/2d — co-occurrence matrices + combination tables
  midlevel_aggregation.py  # Layer 2e — mid-level class deduplication + counts
  person_analysis.py       # Layer 2f — frequency dist, pareto, encounter matrix
  episode_analysis.py      # Layer 2g — episode statistics + calendar
  source_coverage.py       # Layer 2h — per-episode source attribution
  viz_base.py              # Layer 3 cross-cutting — shared helpers (TASK-B08)
  viz_universal.py         # Layer 3a — appearances + unique bar charts
  viz_timelines.py         # Layer 3b — running total + count per bucket
  viz_sunburst.py          # Layer 3c/3g — sunburst for properties + mid-level classes
  viz_sankey.py            # Layer 3d — Sankey class hierarchy flow
  viz_cooccurrence.py      # Layer 3e — heatmap matrices
  viz_stacked_pct.py       # Layer 3f — 100% stacked bars (A over B)
  viz_time.py              # Layer 3h — birth year charts
  viz_quantity.py          # Layer 3i — violin + binary presence
  viz_string.py            # Layer 3j — binary presence
  viz_persons.py           # Layer 3k — person-level visualizations
  viz_episodes.py          # Layer 3l — episode stats + dashboard
  viz_meta.py              # Layer 3m — source coverage visualizations
  viz_geo.py               # Layer 3n — geographic choropleth map (P19 place of birth)
  viz_comparison.py        # Layer 3o — cross-show comparison visualizations
  viz_coverage.py          # Layer 3p — property coverage dashboard
  cache.py                 # REQ-A02 — checksum-based visualization skip logic
```

### Notebook Orchestration

Following the existing pattern (`50_analysis.ipynb`, `51_visualization.ipynb`):

- **`50_analysis.ipynb`** — runs Layers 0–2: loads config, builds color registry, computes occurrence matrix, extracts properties, walks class hierarchy, runs all analysis modules. Outputs CSVs to `data/50_analysis/`.
- **`51_visualization.ipynb`** — runs Layer 3: loads analysis outputs, builds all visualizations, writes PNG+PDF to `data/50_analysis/`. Uses caching (`cache.py`) to skip unchanged visualizations.

Each scope (per-show + combined) is iterated in a loop within each notebook cell. No per-scope code duplication.

---

## Data Model

### Scope

A scope is a named filter on the episode+guest dataset. Two types:
- **Combined** (`all`): all episodes from all shows
- **Per-show** (`<show_label>`): episodes from one specific show only

Every analysis function and every visualization receives a scope parameter. The output path root changes; the logic does not.

### Primary Data Structures

| Name | Shape | Key Columns | Produced by |
|---|---|---|---|
| `guest_facts` | flat fact table | `episode_id, guest_qid, guest_label, role, show_id, show_label, date` | pipeline input |
| `occurrence_matrix` | guests × episodes | binary (0/1) | Layer 1a |
| `property_values` | per property | `guest_qid, episode_id, value_qid, value_label, type, refs, qualifiers` | Layer 1b |
| `age_values` | derived | `guest_qid, episode_id, age` | Layer 1b (derived) |
| `hierarchy_graph` | directed graph | nodes: `(qid, label, first_level, mid_level, top_level_of[])` | Layer 1c |
| `carrier_stats` | per property | see REQ-U01–U05 columns | Layer 2a |
| `episode_stats` | per property | see REQ-U06 columns | Layer 2b |
| `cooccurrence` | per property pair + type | `value_a, value_b, count` | Layer 2c |
| `combinations` | per property | `combination_tuple, count, unique_combinations` | Layer 2d |
| `midlevel_counts` | per mid-level class | `class_qid, class_label, person_count, appearance_count` | Layer 2e |
| `source_attribution` | per episode | `episode_id, sources (set), gaps (list)` | Layer 2h |

### Property Type Routing

After Layer 1b extracts all property values, each property is routed to the applicable analysis and visualization modules based on its type:

| Type | Modules | Key Visualizations |
|---|---|---|
| Item | 2a, 2b, 2c, 2d, 2e (if designated mid-level) | 3a, 3b, 3c, 3d, 3e, 3f |
| Point in time | 2a, 2b | 3a, 3h |
| Quantity | 2a, 2b | 3a, 3i |
| Derived/Age | 2a, 2b | 3i (violin only) |
| String | 2a, 2b | 3a, 3j |

All types receive universal analysis (2a, 2b) and universal visualizations (3a). Type-specific modules are additive.

---

## Configuration File Schemas

All files live in `data/00_setup/` and follow the existing CSV pattern. Code reads them on every run.

### `properties.csv`
| Column | Type | Description |
|---|---|---|
| `wikidata_id` | string | Property PID (e.g. P106) |
| `label` | string | Human-readable label (e.g. "occupation") |
| `type` | string | One of: Item, Point_in_time, Quantity, String, Derived |
| `enabled` | int (0/1) | 1 = active in current analysis run (REQ-C02 opt-in column) |
| `notes` | string | Optional notes |

### `midlevel_classes.csv`
| Column | Type | Description |
|---|---|---|
| `wikidata_id` | string | Class QID |
| `label` | string | Human-readable label |
| `note` | string | Optional notes |

### `loop_resolution.csv`
| Column | Type | Description |
|---|---|---|
| `loop_member_qid` | string | Any member of the P279 cycle |
| `loop_member_label` | string | Human-readable label |
| `designated_top_level_qid` | string | QID of the designated top-level node for this loop |
| `designated_top_level_label` | string | Human-readable label |
| `note` | string | Optional notes |

### `party_colors.csv`
| Column | Type | Description |
|---|---|---|
| `wikidata_id` | string | Party QID |
| `label` | string | Party name |
| `hex_color` | string | Canonical color (e.g. #E3000F for SPD) |

---

## Layer 0: Color Registry

**Requirements:** REQ-V01, REQ-V02, REQ-V03, REQ-I09
**Module:** `color_registry.py`
**Must be initialized before any visualization.**

### Algorithm

1. Load `party_colors.csv` → seed the registry: `{ qid: hex_color }` for all known parties; record which hex values are already used
2. Query all guest facts to compute **total occurrence count per QID across all shows combined**
3. Sort QIDs descending by occurrence count
4. Build the dynamic assignment palette: start with the extended palette (see below); remove any entries whose hex value is already seeded (to avoid collision with party colors or other seeded QIDs)
5. Assign remaining palette colors in order (index 0 = most frequent non-seeded QID); wrap if more QIDs than palette entries — wrapping is acceptable (see REQ-V14)
6. Reserved: `#999999` (medium gray) is permanently reserved for "Unknown / no data" and must never be assigned to a real QID; `#CCCCCC` (light gray) is permanently reserved for "Other" and must never be assigned to a real QID

### Interface

```python
class ColorRegistry:
    def get_color(self, qid: str) -> str:
        """Return hex color for the given QID. Raises if QID not registered."""

    def get_unknown_color(self) -> str:
        """Always returns '#999999'."""

    def get_other_color(self) -> str:
        """Always returns '#CCCCCC'."""

    @classmethod
    def build(cls, guest_facts: DataFrame, party_colors_path: str) -> "ColorRegistry":
        """Factory: builds registry from data. Call once before any visualization."""
```

### Extended Palette (REQ-V14)

Base: the 8 Okabe-Ito colorblind-safe colors from `visualization-principles.md`:
`#E69F00, #56B4E9, #009E73, #F0E442, #0072B2, #D55E00, #CC79A7, #000000`

Extended with additional colorblind-safe colors to reach 12–16 entries total. Final set to be defined in TASK-B25 and documented in `visualization-principles.md`. Reserved colors (`#999999`, `#CCCCCC`) are never included in the dynamic palette.

---

## Layer 1: Data Foundation

**Requirements:** REQ-G01–G03, REQ-P01–P06, REQ-H01–H04
**Notebooks:** `50_analysis.ipynb`

### 1a — Occurrence Matrix

**Module:** `occurrence_matrix.py`
**Requirements:** REQ-G01, REQ-G02, REQ-G03

- **Input:** `guest_facts` filtered to `role == 'guest'`
- **Algorithm:** pivot table: rows = guest_qid, columns = episode_id, values = 1 (binary)
- **Outputs per scope:**
  - `occurrence_matrix_all.csv` — full matrix
  - `occurrence_matrix_topX.csv` — subset to top-X guests by row sum; X from config (default 50)
  - `occurrence_matrix_all.png`, `occurrence_matrix_topX.png` — visualizations (heatmap)

### 1b — Property Extraction

**Module:** `property_extraction.py`
**Requirements:** REQ-P01–P06, REQ-C02

- **Input:** all unique `guest_qid` values; active properties from `properties.csv` (`enabled == 1`)
- **Wikidata access:** via existing `entity_access.py` (Phase 5 entry point; requires `begin_request_context` guard)
- **Per property:** extract all values, capturing `value_qid/value_label` (Item), `date` (Point in time), `quantity` (Quantity), `string` (String), plus `references` and `qualifiers` lists
- **Derived Age:** for each (guest_qid, episode_id) pair: `age = episode.date.year − birth_date.year`; attach to an `age_values` DataFrame
- **Output:** `Dict[property_id, DataFrame]` with type tag on each DataFrame; persisted as per-property CSVs

### 1c — Class Hierarchy Computation

**Module:** `class_hierarchy.py`
**Requirements:** REQ-H01–H04, REQ-C01
**Depends on:** `midlevel_classes.csv`, `loop_resolution.csv`

- **Input:** all `value_qid` values from Item property DataFrames (first-level classes)
- **P279 walk:** BFS from each first-level class upward along P279 links; record all reachable ancestors; cache intermediate results to avoid re-fetching
- **Loop detection:** during BFS, if a node is already in the current path, record the cycle members; consult `loop_resolution.csv` for designated top-level; if not found, select lowest QID number in the cycle
- **Level assignments:**
  - *First-level:* any class directly observed as a property value
  - *Mid-level:* any class listed in `midlevel_classes.csv`
  - *Top-level (relative to mid-level X):* any ancestor of X within X's subtree that has no further superclass within the subtree; computed for each designated mid-level class
- **Multiplicity note:** a class may simultaneously hold first-level, mid-level, and top-level roles
- **Outputs:**
  - `hierarchy_graph`: adjacency structure (node → parents, node → children)
  - `class_levels.csv`: per class QID — `(qid, label, is_first_level, is_mid_level, top_level_of)` — persisted to `data/50_analysis/reference/`
  - Cached in memory for the analysis session; persisted for reuse

---

## Layer 2: Analysis

**Notebooks:** `50_analysis.ipynb`
All analysis functions are parameterized by `(property_id, scope, data)`. Scope iteration happens in notebook orchestration, not inside functions.

### 2a — Universal Carrier-Based Statistics

**Module:** `universal_stats.py`
**Requirements:** REQ-U01–U05, REQ-U08, REQ-U09

**Input:** `property_values[property_id]`, `guest_facts`

**Algorithm:**
1. Group by `value_qid`; compute `person_count` (unique guest_qid), `appearance_count` (total rows)
2. Compute `pct_by_person = person_count / total_persons_in_scope`, `pct_by_appearance` analogously
3. Reference analysis: count rows with non-empty `references`; tabulate most common reference properties and values
4. Qualifier analysis: same for `qualifiers`
5. Top-X values: sorted by `appearance_count` descending, top-X (default 20)
6. Average value count per carrier: `total_values / unique_carriers`
7. Empty count: `total_guests_in_scope − unique_carriers_with_any_value`
8. Append "Unknown / no data" row with `value_label="Unknown / no data"`, `appearance_count=empty_count`, `person_count=empty_count`, `color=gray`

**Output:** `carrier_stats` DataFrame; persisted as `carrier_stats.csv`

### 2b — Universal Episode Appearance Statistics

**Module:** `universal_stats.py`
**Requirements:** REQ-U06

**Input:** `property_values[property_id]`, `guest_facts`

**Algorithm:** for each value, join to episode facts and compute per episode appearance counts; aggregate to min/max/mean/std_dev/median/pct_without/total/unique.

**Output:** `episode_stats` DataFrame; persisted as `episode_stats.csv`

### 2c — Item: Co-occurrence Matrices

**Module:** `cooccurrence.py`
**Requirements:** REQ-I04, REQ-I05

Two co-occurrence types, applied independently:

**Same-person (intra-person):**
- Build `guest_value_set[guest_qid] = set(value_qids)` for the property
- Within-property: for each unordered pair (A, B) in the same guest's set, increment `count[A][B]`
- Cross-property: join sets from two properties on `guest_qid`; for each (A from P1, B from P2) pair per guest, increment `count[A][B]`

**Same-episode (inter-person, intra-episode):**
- Build `episode_value_set[episode_id] = set(value_qids across all guests in episode)` for the property
- Within-property: for each episode, for each unordered pair (A, B) in its value set, increment `count[A][B]`
- Cross-property: same with values from two properties per episode

**Three matrix variants per type and scope:**
1. **Full:** all (A, B) pairs with count > 0
2. **Top-10 × Top-10 by occurrence:** top-10 values by `appearance_count` from `carrier_stats`
3. **Top-10 × Top-10 by co-occurrence:** top-10 values with highest `sum(count[A,:])` across the full matrix

**Output:** six matrices per property (or property pair for cross), persisted as CSVs

### 2d — Item: Combination Tables

**Module:** `cooccurrence.py`
**Requirements:** REQ-I06, REQ-I07

- Within-property: for each guest, sort their values and form a tuple; count tuples; report top-N + unique combination count
- Cross-property: for each guest, form `(val_from_P1, val_from_P2)` tuples; same aggregation

**Output:** combination tables as CSVs

### 2e — Mid-Level Class Aggregation

**Module:** `midlevel_aggregation.py`
**Requirements:** REQ-H05–H07

For each designated mid-level class M:
1. From `hierarchy_graph`, collect all first-level classes that are descendants of M
2. For each guest: does any of their Item values belong to those descendants? → binary flag
3. Compute `person_count` (each person counted once per mid-level class, regardless of how many matching values they hold) and `appearance_count` (total appearances, same deduplication)

**Output:** per mid-level class aggregation DataFrame

### 2f — Person-Level Analysis

**Module:** `person_analysis.py`
**Requirements:** REQ-G04, REQ-PER01–PER06

- **Frequency distribution:** histogram of `appearance_count → count_of_guests_with_that_count`
- **Pareto:** sort guests by `appearance_count` descending; compute `cumulative_appearances / total_appearances`; find 80/20 breakpoint
- **Per-category breakdown (REQ-PER03/04):** for each top-N value of each Item property, join to `guest_facts`; compute per-person `appearance_count`; sort descending; cap at top-K persons + "other" aggregate
- **Encounter matrix (REQ-PER06):** for each episode, for each guest pair (a, b): increment `encounter[a][b]`; filter matrix to guests with `appearance_count >= threshold` (configurable, default 10); symmetric matrix

### 2g — Episode-Level Analysis

**Module:** `episode_analysis.py`
**Requirements:** REQ-EPS01–EPS02

- **Episode count per show:** `groupby(show_id).count()`
- **Guest count per episode:** `groupby(episode_id).count(guest_qid)`
- **Weekday distribution:** `episode.date.weekday() → count`
- **Duration statistics:** if duration data present, `groupby(show_id)[duration].describe()`; treat missing as "Unknown"
- **Broadcast calendar:** map each `(episode_id, date)` to `(ISO year, ISO week, weekday)` for calendar heatmap rendering

### 2h — Meta-Level: Source Coverage

**Module:** `source_coverage.py`
**Requirements:** REQ-META01

- **Per episode:** collect which source fields are non-null; encode as a frozenset of source names: `{ZDF_Archiv, Fernsehserien, Wikidata}`
- **Combination encoding:** map each source combination to a label and a color (from a fixed source-palette, not the QID registry)
- **Completeness gap detection:** for each (episode, field): if the field is present in source X but absent in source Y, record as a gap
- **Output:** `source_attribution.csv` with columns `(episode_id, date, show_id, sources, gaps_count, gap_details)`

---

## Layer 3: Visualization

**Notebooks:** `51_visualization.ipynb`
**All visualizations** must apply the cross-cutting rules listed below before saving.

### Cross-Cutting Rules (applied via `viz_base.py`)

Every visualization must call these helpers before `save_fig()`:

| Helper | Purpose | Requirement |
|---|---|---|
| `add_scope_label(ax, scope)` | show name or "all shows" label | REQ-V07 |
| `add_context_stats(ax, n_app, n_uniq, n_empty)` | title/subtitle stats | REQ-V10 |
| `sort_bars_descending(data)` | sort before plotting | REQ-V05 |
| `stacked_bar_from_zero(ax, ...)` | ensure 0% baseline | REQ-V06 |
| `place_bar_labels(ax, bars)` | inside if ≥50%, outside if <50% | REQ-V09 |
| `apply_other_grouping(data, top_x)` | tail → "other" | REQ-V11 |
| `add_unknown_row(data, registry)` | gray row, always last | REQ-U08 |
| `save_fig(fig, path, registry)` | PDF + PNG at 300 DPI, then quality check | REQ-V08, V12 |

`save_fig()` also triggers the checksum-based cache update (`cache.py`).

### 3a — Universal Visualizations

**Module:** `viz_universal.py` | **Requirement:** REQ-U07

For each property and scope, produce two charts:
- **Total appearances bar chart:** horizontal bar, Y = property value label, X = `appearance_count`, sorted descending; "Unknown" gray at bottom; top-N + "other" if crowded
- **Unique individuals bar chart:** same layout, X = `person_count`
  * **Clarification:** Those two charts should be able to be merged in one. A grouped bar chart should do fine, potentially with two different scales for the x axis (since there will generaly be much more appearances than unique individuals)
    * **Clarification:** generally, we must be on the lookout for different very basic visualizations that make more sense when merged into one visualization.

Both charts draw colors from the registry. Label each bar with the count (inside if ≥50% of max bar width, outside otherwise).

### 3b — Item: Timelines

**Module:** `viz_timelines.py` | **Requirement:** REQ-I01

For each Item property and scope:
1. Compute adaptive X-axis bins: start at per-episode granularity; if bin count > 50, coarsen to monthly; if still > 50, bi-monthly; and so on
2. For each top-N value (by `appearance_count`): compute running total and count-per-bucket time series
3. **Combined visualization:** filled area in the background (running total per value, stacked or overlapping); line+dot series in the foreground (count per bucket); if crowded, split into separate running-total and count-per-bucket charts
4. Apply scope label and contextual stats

Output: `timeline_running_total.png/.pdf`, `timeline_count_per_bucket.png/.pdf`, optionally `timeline_combined.png/.pdf`

### 3c — Item: Sunburst

**Module:** `viz_sunburst.py` | **Requirement:** REQ-I02

For each Item property and scope:
- Build hierarchy tree: root → top-level classes → mid-level classes → first-level classes
- Segment size = `appearance_count` (cumulative variant) or `person_count` (unique variant)
- Colors from registry for each class QID
- Applied unconditionally; if hierarchy is flat (no P279 ancestors found), falls back to a single-level sunburst (equivalent to a pie chart)

Output: `sunburst_cumulative.png/.pdf`, `sunburst_unique.png/.pdf`

### 3d — Item: Sankey

**Module:** `viz_sankey.py` | **Requirement:** REQ-I03

For each Item property and scope:
- Left column = top-level classes; middle column = mid-level classes; right column = first-level classes
- Flow from left→middle→right along P279 ancestry paths
- Flow width = `appearance_count` (appearances variant) or `person_count` (unique variant)
- Colors: use source node color (top-level class color from registry)
- Applied unconditionally; if no hierarchy found, the chart will show a single node (degenerate case, acceptable per design principle 1)

Output: `sankey_appearances.png/.pdf`, `sankey_unique.png/.pdf`

### 3e — Item: Co-occurrence Heatmaps

**Module:** `viz_cooccurrence.py` | **Requirements:** REQ-I04, REQ-I05

For each property (within) and each property pair (cross), for each of the 6 matrix variants (2 co-occurrence types × 3 size variants):
- Chart type: heatmap matrix
- Rows and columns = property value labels (sorted by occurrence count)
- Cell color = co-occurrence count, sequential color scale (light → dark)
- Axis labels include occurrence count for each value

Output naming: `cooccurrence_{type}_{scope}_{variant}.png/.pdf` (type = person/episode, scope = within/`p2_label`, variant = full/top10occ/top10cooc)

### 3f — Item: % A over B Stacked Bar Charts

**Module:** `viz_stacked_pct.py` | **Requirement:** REQ-I08

For each pair of Item properties (A, B) and scope:
- Y-axis = top-10 values of Property A, sorted descending by total occurrence; each category label includes total count in parentheses: e.g. "politician (710)"
- Segments = Property B values, colored by registry
- Segment width = percentage of Property A total that holds this Property B value (0–100%)
- Segment labels: absolute count inside segment (omit if too small per REQ-V09)
- "Unknown" segment for guests with no Property B value, always gray, always rightmost
- Two charts per pair: cumulative appearances variant + unique persons variant

Output: `stacked_pct_{b_label}_cum.png/.pdf`, `stacked_pct_{b_label}_uniq.png/.pdf`

### 3g — Mid-Level Class: Sunburst + Stacked Bar

**Module:** `viz_sunburst.py` (sunburst), `viz_stacked_pct.py` (stacked bar) | **Requirement:** REQ-H07

For each designated mid-level class M and scope:
- **Sunburst:** rooted at M; inner ring = direct sub-types of M; outer rings = further descendants; two variants (appearances + unique)
- **Stacked bar:** horizontal stacked bar of the same data in flat layout; one bar = M total; segments = sub-types by contribution; two variants

### 3h — Point in Time: Birth Year Charts

**Module:** `viz_time.py` | **Requirements:** REQ-T01, REQ-T02

- **REQ-T01 — Distribution:** histogram (bar chart); X = birth year, Y = total guest appearances; bars colored by a single palette color or by show (if per-show scope applies)
- **REQ-T02 — Per-birth-year age stacked bar:** each bar = one birth year; segments = ages at which guests of that birth year appeared (segment height = count of appearances at that age); sorted chronologically on X-axis; "Unknown" segment for missing age, gray, always leftmost

### 3i — Quantity: Violin Plot + Binary Presence

**Module:** `viz_quantity.py` | **Requirements:** REQ-Q01, REQ-Q02

- **Age (REQ-Q01):** violin plot; X or grouping = scope; Y = age distribution; shows median line and IQR; overlay individual point jitter if N is small
- **Other quantity properties (REQ-Q02):** two-segment horizontal bar; segment 1 = "has value" (count), segment 2 = "no value" (empty count); percentage-labeled

### 3j — String: Binary Presence

**Module:** `viz_string.py` | **Requirement:** REQ-S01

Same layout as non-age quantity binary presence (3i): "has value" vs "no value" bar.

### 3k — Person-Level Visualizations

**Module:** `viz_persons.py` | **Requirements:** REQ-G04, REQ-PER01–PER06

- **REQ-G04 — Frequency distribution:** histogram, X = appearance count, Y = number of guests with that count; companion Pareto chart showing cumulative % of appearances on Y, top-X% of guests on X
- **REQ-PER01 — Top guests by show:** horizontal stacked bar; Y = top-50 guests by total appearances; segments = shows (colored by show); sorted descending by total; scope label = "all shows"
- **REQ-PER02 — Top guests per show:** horizontal bar; Y = top-20 guests for this show; X = appearance count on this show; one chart per show scope
- **REQ-PER03 — Individuals within category:** for each Item property, horizontal stacked bar; Y = top-N property values sorted descending; segments = individual persons contributing to each value (top-K persons + "other"); colored by person QID from registry
- **REQ-PER04 — Individuals within combination:** same layout as PER03 but Y = top occupation-combination tuples
- **REQ-PER05 — Birth year × individuals:** horizontal stacked bar; Y = birth year (chronological); segments = individual persons born in that year sorted by appearance count; "other" for long tails
- **REQ-PER06 — Encounter matrix:** heatmap; rows and columns = top-N guests by appearance count (configurable threshold, default ≥10); cell color = episode co-occurrence count; symmetric; diagonal excluded

### 3l — Episode-Level Visualizations and Dashboard

**Module:** `viz_episodes.py` | **Requirements:** REQ-EPS01, REQ-EPS02

**REQ-EPS01 — Episode statistics:**
- Episode count per show: horizontal bar, Y = show label, X = episode count
- Guest count per episode: histogram of guest counts; X = guest count, Y = number of episodes with that guest count
- Weekday distribution: bar chart, X = weekday (Mon–Sun), Y = episode count; one bar per day
- Duration distribution: if data present, histogram of episode runtime in minutes; "Unknown" for missing; if absent, omit chart
- **Broadcast frequency calendar heatmap:** grid layout, rows = calendar weeks (ISO), columns = weekdays (Mon–Sun); cells colored by number of episodes (0 = white, >0 = show color or episode count gradient); summer/holiday gaps visible as white blocks

**REQ-EPS02 — Per-show dashboard:**
A single output page (PDF recommended) per show combining:
1. Party sunburst (top-level) — who came from which parties
2. Guest gender distribution over time (stacked area or line)
3. Occupation sunburst (top-level)
4. Broadcast frequency calendar
Layout: 2×2 grid or vertical stack; concise titles; no individual-level labels to avoid crowding; scope = this show only

### 3m — Meta-Level: Source Coverage

**Module:** `viz_meta.py` | **Requirement:** REQ-META01

For each scope, produce at minimum one primary coverage visualization. Choose the form that remains legible at the data scale:

- **Preferred — Calendar heatmap with source combination color:** each cell = one episode date; color = source combination (e.g. ZDF-only = blue, Fernsehserien-only = orange, both = green, all-three = dark green); legend shows all source combinations present
- **Alternative — Episode × source binary matrix:** rows = episodes (sorted by date), columns = sources; cell = filled (data retrieved) or empty; viable for <300 episodes; use row density grouping for larger datasets
- **Completeness gaps:** add a secondary annotation layer marking episodes with `gaps_count > 0` with a distinct marker (e.g. red border or hatching)

### 3n — Geographic Map: Place of Birth

**Module:** `viz_geo.py` | **Requirement:** REQ-V15

For the place of birth property (P19) and each scope:
1. Resolve each `value_qid` to its country via P17 (country); cache resolutions
2. Aggregate `appearance_count` and `person_count` by country
3. Render choropleth world map: cell color = sequential scale (light → dark) proportional to count; zero-count countries = gray; Unknown region in legend
4. Two variants: total appearances + unique persons
5. If sub-country granularity is available (cities → region → country chain fully resolved), produce a secondary regional map for Germany as the primary country of origin

Output: `geo_appearances.png/.pdf`, `geo_unique.png/.pdf`

### 3o — Cross-Show Comparison

**Module:** `viz_comparison.py` | **Requirement:** REQ-G05

For selected properties (at minimum: occupation, gender, political party) in combined scope:
- **Grouped bar chart:** X-axis groups = top-N property values; within each group, one bar per show; bars colored by show; Y-axis = percentage share within each show's total
- **Alternative — Heatmap:** rows = property values, columns = shows; cell intensity = percentage; useful when there are many shows or values
- Produce both chart forms and select the most readable at the data scale

Output under `all/`: `comparison_<property_label>_grouped.png/.pdf`, `comparison_<property_label>_heatmap.png/.pdf`

### 3p — Property Coverage Dashboard

**Module:** `viz_coverage.py` | **Requirement:** REQ-META02

For each scope:
1. For each active property: compute `pct_with_value` (`1 − empty_count / total_guests`), `pipeline_match_rate` (successfully resolved QIDs / total QIDs attempted), `pct_with_references` (from REQ-U03 carrier stats)
2. Summary table: rows = properties, columns = the three metrics; sortable
3. Horizontal bar chart: one bar per property sorted by `pct_with_value` descending; colored by type (Item/Point_in_time/Quantity/String)

Output under `meta/`: `property_coverage.csv`, `property_coverage.png/.pdf`

---

## Output Directory Structure

All directories and file names use human-readable property labels. Property directories append the PID in parentheses only in chart labels, not in directory names.

```
data/50_analysis/
  all/                                      # combined all-shows scope
    occurrence_matrix_all.csv
    occurrence_matrix_topX.csv
    occurrence_matrix_all.png
    occurrence_matrix_topX.png
    <property_label>/                       # e.g. occupation/, gender/
      carrier_stats.csv
      episode_stats.csv
      cooccurrence/
        person_within_full.csv/.png/.pdf
        person_within_top10occ.csv/.png/.pdf
        person_within_top10cooc.csv/.png/.pdf
        episode_within_full.csv/.png/.pdf
        episode_within_top10occ.csv/.png/.pdf
        episode_within_top10cooc.csv/.png/.pdf
        person_<p2_label>_full.csv/.png/.pdf      # cross-property
        person_<p2_label>_top10occ.csv/.png/.pdf
        person_<p2_label>_top10cooc.csv/.png/.pdf
        episode_<p2_label>_full.csv/.png/.pdf
        episode_<p2_label>_top10occ.csv/.png/.pdf
        episode_<p2_label>_top10cooc.csv/.png/.pdf
      combinations/
        within_combinations.csv
        <p2_label>_combinations.csv
      visualizations/
        universal_appearances.png/.pdf
        universal_unique.png/.pdf
        timeline_running_total.png/.pdf         # Item only
        timeline_count_per_bucket.png/.pdf      # Item only
        timeline_combined.png/.pdf              # Item only (optional)
        sunburst_cumulative.png/.pdf            # Item only
        sunburst_unique.png/.pdf                # Item only
        sankey_appearances.png/.pdf             # Item only
        sankey_unique.png/.pdf                  # Item only
        stacked_pct_<p2_label>_cum.png/.pdf     # Item only
        stacked_pct_<p2_label>_uniq.png/.pdf    # Item only
        birth_year_dist.png/.pdf                # Point in time only
        birth_year_age_stacked.png/.pdf         # Point in time only
        violin_age.png/.pdf                     # Quantity/Age only
        binary_presence.png/.pdf                # Quantity (non-age) + String
    persons/
      frequency_distribution.png/.pdf
      pareto.png/.pdf
      top_guests_by_show.png/.pdf
      encounter_matrix.png/.pdf
      <property_label>_individuals.png/.pdf     # REQ-PER03, per property
      birth_year_individuals.png/.pdf
    episodes/
      episode_count_per_show.png/.pdf
      guest_count_distribution.png/.pdf
      weekday_distribution.png/.pdf
      duration_distribution.png/.pdf            # if data present
      broadcast_calendar.png/.pdf
    meta/
      source_attribution.csv
      source_coverage_calendar.png/.pdf
      source_coverage_matrix.png/.pdf           # alternative view
      source_gaps.png/.pdf
      property_coverage.csv                     # REQ-META02
      property_coverage.png/.pdf               # REQ-META02
    comparison/                               # REQ-G05 — combined scope only
      comparison_<property_label>_grouped.png/.pdf
      comparison_<property_label>_heatmap.png/.pdf
    geo/                                      # REQ-V15 — place of birth only
      geo_appearances.png/.pdf
      geo_unique.png/.pdf
    reference/
      class_levels.csv
      class_hierarchy.json
  <show_label>/                               # per-show scope, mirrors all/
    ...
    persons/
      top_guests.png/.pdf                     # REQ-PER02
      encounter_matrix.png/.pdf
    episodes/
      ...                                     # mirrors all/ episodes/
    meta/
      ...                                     # mirrors all/ meta/
    dashboard.png/.pdf                        # REQ-EPS02 per-show dashboard
  persons/                                    # GDPR-sensitive — exclude from public releases (REQ-A03)
  reference/                                  # Wikidata reference data
  .viz_cache.json                             # REQ-A02 checksum cache (per scope)
```

---

## Definition of Done

A Phase 5 implementation is complete when all of the following hold:

1. **All requirements implemented.** Every REQ-* in `00_requirements.md` has a corresponding implementation in a Python module under `speakermining/src/analysis/`.
2. **All outputs generated for all scopes.** Running `50_analysis.ipynb` and `51_visualization.ipynb` on the full dataset produces all CSVs and visualizations for the combined scope and each per-show scope without error.
3. **Quality check passed for every visualization.** The post-generation review (REQ-V08) has been applied: no text overlap, labels readable, scope label present, context stats present.
4. **All config files seeded.** `loop_resolution.csv`, `midlevel_classes.csv`, `party_colors.csv`, and `properties.csv` contain at minimum the seed data specified in TASK-B19.
5. **Visualization cache populated.** After a full clean run, a second run completes substantially faster due to REQ-A02 caching; no stale output is reused.
6. **GDPR separation in place.** `persons/` directory is in `.gitignore`; no individual-identified data exists outside `persons/`.
7. **All tasks in `open-tasks.md` marked complete.**
