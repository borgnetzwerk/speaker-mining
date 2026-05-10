# Final Visualizations — Implementation Plan

**Source spec:** [10_final_visualizations.md](10_final_visualizations.md)  
**Design reference:** [Priority_Visualizations.html](reference/Priority_Visualizations.html) · [Visualizations_Critique.html](reference/Visualizations_Critique.html)  
**Output:** `data/50_analysis/all/final_visualizations/`  
**Code:** `speakermining/src/process/analysis/viz_final.py`  
**Notebook cells:** `speakermining/src/process/notebooks/50_analysis.ipynb` — Section 20

---

## Status

| # | Visualization | Status |
|---|---|---|
| 0 | Show statistics table | ✅ Implemented |
| 1 | Age at appearance — density ridge plot | ✅ Implemented |
| 2 | Gender share over time — multi-gender line chart | ✅ Implemented |
| 3a | Party affiliation share by show | ✅ Implemented |
| 3b | Male share by property (modular) | ✅ Implemented |
| 4 | Guest co-appearance network — PageRank | ✅ Implemented |
| 5 | Property coverage table | ✅ Implemented |
| 6 | Occupation hierarchy — sunburst | ✅ Implemented |

---

## Architecture

All visualizations are produced by `viz_final.py` — a standalone module that follows the existing `viz_*.py` pattern:

- Functions accept pre-prepared DataFrames (no raw I/O inside functions)
- Output: PNG (scale=3) + HTML via `save_fig()`
- Consistent **show color palette** (`SHOW_COLORS`) used across all 7 charts
- Consistent **gender color palette** (`GENDER_COLORS`) — non-binary aware, never binary-only

Data is prepared inside the Section 20 notebook cells and passed to the module functions.

---

## Data flows

### Viz 0: Show statistics table
- `per_show_stats` (computed in Section 15)
- `episode_appearances` → span (min/max premiere year per show)
- `catalogue` → Wikidata coverage % per show
- `property_frames["P21"]` → male/female % per show (of guests with known gender)
- `property_frames["AGE"]` → median age per show

### Viz 1: Age at appearance — density ridge
- `property_frames["AGE"]` merged with `episode_appearances` for `show_id`/`program_name`
- Sorted by median age descending; IQR shaded; StarTalk highlighted

### Viz 2: Gender over time — line chart
- `property_frames["P21"]` merged with `episode_appearances` for `premiere_date` + `show_id`
- Grouped by year × show × gender → rolling 3-year mean
- One line per gender category; 50% parity reference line; dedicated legend

### Viz 3a: Party affiliation share by show
- `property_frames["P102"]` merged with `episode_appearances` for `show_id`
- Unique guests per show per party → stacked horizontal bars
- Party colors from `data/00_setup/party_colors.csv`

### Viz 3b: Male share by property (modular)
- Properties: AGE (binned), P106 (occupation top 10), P39 (position held top 10), P102 (party)
- For each property value: join with P21 to get gender breakdown → male % dot plot

### Viz 4: Co-appearance network — PageRank
- `data/50_analysis/all/co_occurrence_pairs.csv` → networkx graph
- PageRank → node size; top 80 nodes by PageRank
- Color by: (a) occupation meta-category, (b) gender, (c) party
- Edges: pairs with ≥3 shared episodes; edge weight scales with count
- Layout: spring layout (networkx) → Plotly scatter

### Viz 5: Property coverage table
- `data/50_analysis/all/property_coverage_binary_by_guest.csv` → show × property heatmap
- Properties grouped into core / mid / sparse tiers
- Shows sorted by overall mean coverage (best-covered left)

### Viz 6: Occupation hierarchy — sunburst
- `property_frames["P106"]` OR `data/50_analysis/all/occupation/carrier_stats.csv`
- `OCC_META` mapping in `viz_final.py` (hand-curated Wikidata label → meta-category)
- Inner ring: 5 meta-categories; outer ring: top occupations within each
- Sequential hue ramp within each meta-category for the outer ring

---

## Design principles (from Critique + Priority docs)

1. **Consistent show ordering** — by total appearances (Markus Lanz first)
2. **Consistent show colors** — same hex per show across all 7 charts
3. **Gender is not binary** — always 3+ segments; "unknown" always visible
4. **No overlapping labels** — dedicated legends, not inline end-labels
5. **Each chart annotates its headline finding** — not just data display
   * **Clarification:** We will do this in the caption. Explicitly NOT a task for the visualization itself.
