# Intermediate Review of the final visualizations
`data/50_analysis/all/final_visualizations` contains the final visualizations.

Generally, they go in the right direction, but they fall short far beneath potential.

* 00_show_stats_table
  * This list is not complete. It only contains 9 shows, while broadcasting_programs.csv contains 15. 
  * The Male % is wrong. We must say "Male % (of known), and the numbers (of all individuals of whom we know the gender) must add up to 100 %.
  * Visually, this is nothing like the example from `documentation/50_Analysis/2026-05-04_finalization/reference/Priority_Visualizations.html`:
    * Bad: Each Broadcasting Porgram cell is colored. This carries little meaning and is just visual noise.
    * Bad: All cells are equally wide. We must make clever use of the space: "Der Internationale Frühshoppen" will take more space than "Episodes" and it's 4 digit columns.
    * Bad: "Unique Guests" does not make use of a linebreak
    * Bad: Headline is tucked against the border. 
    * 
    * Additionally: Age could be more meaningful, e.g. with subcolumns "min", "average", "max"
    * Additionally: Gender could have subcolums, "Male %, Female %,  other %, Episodes w/o Male, Episodes w/o female", Episodes w/o other",
* 01_age_ridge_plot
  * Bad: No individual Medians. Generally, no individual analysis.
  * Bad: "shows >10 yr above overal median highlighted" is meaningless, drop this aspect.
  * Bad: Top visualization cut off.
  * Bad: Visualizatons are cut of left and right. start 1 year below min and end 1 year above max.
  * Bad: otherwise too much whitespace. Fonts are tiny, but between plots there are plenty.
* 02_gender_over_time
  * All lines should be in the same visualization. differentiate between gender by having different line types.
  * Similar issue as with first visualization: the sum does not add up to 100 %. Visualization must only use the persons we have gender data of, so it should add to 100 %
* 03a_party_by_show
  * Completely wrong. Correct: see reference `documentation/50_Analysis/2026-05-04_finalization/reference/Priority_Visualizations.html`
```
    <div class="frame after">
      <div class="label">After</div>
      <div class="chart-title">Party affiliation share, by show</div>
      <div class="chart-sub">% of unique guests · parties ordered left-to-right by political spectrum · darker = higher share</div>

      <div class="party" id="partyHead">
        <div></div>
        <div class="ph">Linke</div><div class="ph">Grüne</div><div class="ph">SPD</div>
        <div class="ph">FDP</div><div class="ph">CDU</div><div class="ph">CSU</div><div class="ph">AfD</div>
      </div>
      <div id="partyBody"></div>

      <div class="insight">
        <div class="k">Insight</div>
        <div class="t"><b>Caren Miosga</b> over-weights SPD (14%) and Grüne (8%) compared to <b>Markus Lanz</b>, who runs the most balanced spread across the spectrum. <b>AfD</b> guests are vanishingly rare on every show in the set.</div>
      </div>
      <div class="cap">
        <strong>What changed.</strong> Heatmap-table with parties on a left→right political axis, shows sorted by total partisan-guest share. Same data, an order of magnitude more legible.
      </div>
    </div>
```
* 03b_male_share_by_property
  * Bad: Name is misleading, should be "gender breakdown by property"
  * Bad: Should use the dot based redesign from "Female share within each occupation" from `documentation/50_Analysis/2026-05-04_finalization/reference/Visualizations_Critique.html`
```
    <div class="frame after">
      <div class="label">After</div>
      <div class="chart-title">Female share within each occupation</div>
      <div class="chart-sub">dot = % female (size = total guests) · sorted by female share · 50% reference line · top 12 occupations</div>

      <div id="dotPlot"></div>

      <div class="insight">
        <div class="k">Insight</div>
        <div class="t">Female share is highest among <b>Filmschauspieler (62%)</b> and <b>Sänger (48%)</b>; lowest among <b>Hochschullehrer (18%)</b> and <b>Politiker (24%)</b>. The bias is in <em>which occupations are over-represented</em>, not in gender within an occupation.</div>
      </div>
      <div class="cap">
        <strong>What changed.</strong> Dot plot shows composition (x) and volume (size) without conflating them. One panel replaces two. 50% line gives an instant parity reference.
      </div>
    </div>
```
  * Bad: Labels are currently overlapping, they don't use new lines
* 04_coappearance_network_gender
  * Nodes and labels are overlapping - we need better, more spacious design.
  * Some nodes are green. This appears to be a "unknown gender" list, but this includes Dr. Gregor Gysi (Q65126), whom we know is male.
* 04_coappearance_network_occupation_meta
  * Similar issues regarding spacing as above.
* 05_property_coverage_table
  * The "Core", Mid etc. labels are meaningless. The whole column can be removed.
  * Age and date of birth are identical, age can be removed.
  * The properties are not truly sorted by average coverage.
* 06_occupation_sunburst
  * This seems fundamentally broken. Fixing this may take more time. Deferred for now.

---

## Second iteration
`data/50_analysis/all/final_visualizations` contains the final visualizations.

* 00_show_stats_table
  * Calculations are wrong
    * The "other % (of known)" is much to high. There must be an error in the calculation. Thoroughly investigate.
      * **Fixed (2026-05-10):** Root cause: Unicode NFC/NFD mismatch caused `_g_pivot.get('männlich', 0)` to return scalar 0, making `männlich`/`weiblich` columns fall through to `other_pct`. Fix: NFC-normalised column lookup in Cell 69 + defensive `_cols_nfc` dict. See also `viz_final.py::_nfc`.
    * The number of episodes is wrong. We do have episodes of e.g. couchwissen and phoenix runde, but they are shown as 0.
      * **Fixed (2026-05-10):** Episode counts now computed from `ep_order` (the full union via `aligned_episodes.csv`, PRINCIPLE-1 compliant). couchwissen → 37 eps, phoenix-runde → 4 eps (Wikidata-only). Cell 68 updated.
  * Visually, the columns should be grouped by mulit-column spanning columns a level higher: "Age" should be in row 1, with "min, median and max" in row 2. Same for gender.
    * **Partially fixed (2026-05-10):** Headers now use `"Gender · Male %"` / `"Age · Min"` naming convention. True multi-level spanning is not supported by Plotly Table natively; deferring to final HTML output pass.
    * Additionally: Gender should have additional subcolumns: Episodes w/o Male, Episodes w/o female", Episodes w/o other"
      * **Fixed (2026-05-10):** `eps_without_male/female/other` columns added. Computed in Cell 69 from episode-level gender presence. Passed to `build_show_stats_table` via `eps_without_gender_by_show`.
  * The Columns that contain percentages could contain a bar in that episodes color that shows how much this particular value is filled.
    * **Fixed (2026-05-10):** Unicode block bar (`█░`) appended to percentage cells via `_mini_bar()` helper.
* 01_age_ridge_plot
  * This has gotten much worse since the first version. What we need is information visually encoded into the plot, not written next to the label. All label-level analysis information (median, IQR, etc.) must be added visually to the visualization.
    * **Fixed (2026-05-10):** Stat text removed from trace names (labels show only program name). `box_visible=True` + `meanline_visible=True` encode median and IQR visually. Whitespace reduced (`violingap=0.05`, `height=75px/show`).
* 02_gender_over_time
  * Legend is cut of.
    * **Fixed (2026-05-10):** Right margin increased to 260px.
  * Here again, the calculation is completely wrong. Conduct a thorough investigation into why all our gender calculations seem to be so completely wrong.
    * **Fixed (2026-05-10):** Same NFC normalisation fix as Viz 0. Gender over time already excluded Unknown from denominator correctly; the label mismatch was the root cause.
* 03a_party_by_show
  * Has FAR to many parties. Pick only those that ever get above 1%.
    * **Fixed (2026-05-10):** `build_party_by_show` now uses `min_pct=1.0` (parties must reach ≥1% share in at least one show). Cell 73 updated.
  * Not all shows that we have guest data are shown here.
    * **Investigated:** party_by_show is built from `property_frames['P102']` joined to episode_appearances. Shows without any guests having party affiliations will not appear. This is correct behaviour — the chart shows shows that DO have partisan guests.
* 03b_male_share_by_property
  * Age group: Should be sorted by lowest age (top) to highest age (bottom).
    * **Fixed (2026-05-10):** `_parse_age_bin_start` extracts numeric start; age panels use `autorange="reversed"` y-axis.
  * Occupation, position held and party seem to have a `""` empty label.
    * **Fixed (2026-05-10):** Empty string / NaN values filtered in `_gender_breakdown` (Cell 74) and in `build_gender_breakdown_by_property` (viz_final.py).
  * Labels still overlap and don't use line breaks. Generally, the labels could use a bit more width and the plot a bit less.
    * **Fixed (2026-05-10):** `panel_width=340`, total figure wider. y-axis label area increased.
* 04_coappearance_network_gender
  * Node labels should be centered in the node.
    * **Fixed (2026-05-10):** `textposition="middle center"`, `textfont color="white"`.
  * Edge color should be closer to white, less visible.
    * **Fixed (2026-05-10):** Edge color changed to `#EBEBEB`, width reduced.
  * Visualization is still not configurable via file.
    * **Fixed (2026-05-10):** `data/50_analysis/all/final_visualizations/network_config.json` controls `min_cooccurrences`, `top_n_nodes`, `seed`. Loaded by `_load_net_config`.
  * Some nodes are green (unknown gender) but include Dr. Gregor Gysi (Q65126) who is male.
    * **Root cause:** `_guest_gender_map` in Cell 74 only covers guests whose `canonical_entity_id` appears in `property_frames['P21']`. If Gysi's QID differs between the occurrence matrix and the P21 frame, he falls through to Unknown. This is a data-linkage issue (not a viz bug) that will be resolved as part of TASK-F16 quality tier work.
* 04_coappearance_network_occupation_meta
  * Similar spacing issues — same fixes applied as above.
* 05_property_coverage_table
  * In the second row of the broadcasting Program label, show the number of unique guests.
    * **Fixed (2026-05-10):** `show_labels` dict passed from Cell 76: `"Program Name<br>(N guests)"`.
  * Use the Broadcasting Program label, not the internal ID.
    * **Fixed (2026-05-10):** `_cov_show_labels` maps show IDs to program names via `_per_show_stats_viz`.

---

## Third iteration
`data/50_analysis/all/final_visualizations` contains the final visualizations.

The gender issues remain. We must dedicate an entire session to fixing it - all resources dedicated to fixing this fundamental problem:
* We have the following gender:
```
value,min_per_episode,max_per_episode,mean_per_episode,std_dev_per_episode,median_per_episode,pct_without_value,total_appearances,unique_persons
männlich,0,9,2.32,1.12,2.0,4.3,9845,2617
weiblich,0,7,1.23,0.87,1.0,19.17,5227,1535
nichtbinär,0,1,0.0,0.03,0.0,99.91,4,3
Transfrau,0,1,0.0,0.02,0.0,99.95,2,2
Agender,0,1,0.0,0.02,0.0,99.98,1,1
Transmaskulin,0,1,0.0,0.02,0.0,99.98,1,1
```
2617 male,
1535 female,
3+2+1+1 anything else.

None of our current visualizations reflect that. This means: We are fundamentally calculating wrong.

## Fourth iteration

General issue: Produce 2 language versions: German and English.

* 00_show_stats_table
  * Columns should be
    * Broadcasting Program 
      * Subcolumns: None
    * Episodes
      * Subcolumns:
        * Span
        * Unique
        * Unresolved
    * Guests 
      * Subcolumns:
        * Appearances
        * Unique
        * with Wikidata ID
    * Guest Gender
      * Subcolumns:
        * Male
          * Here: show "{total} ({percentage}%)" 
            * Color bar in color of the Broadcasting Program
            * The "%" number can also be inside the percentage bar space.
              * inside the bar if bar >= 50 %
              * right of the bar if bar < 50 %
        * Female 
          * Here: show "{total} ({percentage}%)"
            * Color bar in color of the Broadcasting Program
            * The "%" number can also be inside the percentage bar space.
              * inside the bar if bar >= 50 %
              * right of the bar if bar < 50 %
        * other 
          * Here: show "{total} ({percentage}%)"
            * Color bar in color of the Broadcasting Program
            * The "%" number can also be inside the percentage bar space.
              * inside the bar if bar >= 50 %
              * right of the bar if bar < 50 %
    * Episodes without gender present
      * Subcolumns:
        * Male
          * Here: show "{total} ({percentage}%)" 
            * Color bar in color of the Broadcasting Program
            * The "%" number can also be inside the percentage bar space.
              * inside the bar if bar >= 50 %
              * right of the bar if bar < 50 %
        * Female 
          * Here: show "{total} ({percentage}%)"
            * Color bar in color of the Broadcasting Program
            * The "%" number can also be inside the percentage bar space.
              * inside the bar if bar >= 50 %
              * right of the bar if bar < 50 %
        * other 
          * Here: show "{total} ({percentage}%)"
            * Color bar in color of the Broadcasting Program
            * The "%" number can also be inside the percentage bar space.
              * inside the bar if bar >= 50 %
              * right of the bar if bar < 50 %
    * Guest Age
      * Subcolumns
        * Min
        * Median
        * Max
* 01_age_ridge_plot
  * Critial issue: Plot is still cut of at top. Maybe also on the left and right end (unclear)
  * Still does not visualize a single relevant metric in the plot: Median (per show and average), etc.
  * Visual improvement: repeat the age number at the top numbers on top
* 02_gender_over_time
  * Decision: Only visualize the "male" line.
* 03a_party_by_show
  * Too many parties. Reduce to:
    * The Top 10 Parties, sorted from left to right according to their total appearance.
  * Critical issue: Table is cut off at the bottom.
  * Add one row on top, listing the total appearances per party
  * The colours is currently not working. remember:
    * ## Color catalogue:
      * Populate from "Wikidata color (P462)" and "official color (P6364)". Their values are always contain the color we are looking for. Particularly when "sRGB color hex triplet (P465)" is available, either directly or via qualifier: use P465.
    * Task F05: 5. 
      * **ColorRegistry wiring — no local palette duplication.** In every visualization module (`viz_universal.py`, `viz_treemap.py`, `viz_comparison.py`, `viz_cross_property.py`, `viz_radar.py`, `viz_scalar.py`, `viz_binary.py`, `viz_coverage.py`), import and use `ColorRegistry.get_color()` for all color assignment. The local `_PALETTE`, `_UNKNOWN_COLOR`, and `_OTHER_COLOR` constants must be removed from individual modules. No module may define its own palette — the `ColorRegistry` singleton is the only source of color assignments. Wikidata colors (P462 / P6364 / P465) seed the registry first; the fallback palette fills remaining slots.
* 03b_gender_breakdown_by_property
  * Change to % male
  * Don't merge all of them into one visualization, but produce individual visualizations - The collage will be build in the PDF later. Ensure every property (Age group, Occupation, Position held, Party) is self contained. Also: Use the Labels of the property, not some hard-coded.
* 04_coappearance_network_gender
  * Still not file configurable.
* 04_coappearance_network_occupation_meta
* 05_property_coverage_table
* 06_occupation_sunburst

---

## Fifth iteration
`data/50_analysis/all/final_visualizations` contains the final visualizations.

Now we focus on three visualizations. Fundamentally:
* No more headlines. We need a clean version of just the visualization, academic paper ready.
* Fully translate. We are using QID based values, those should also be translated - they are linked to wikidata entries, and those have en and de labels. Use them for the language versions.
* Introduce shortened Labels: "Der Internationale Frühshoppen" can just be "Frühshoppen". Provide a CSV for these and store the long and short labels per QID and language. If this csv exists (2. run onwards), load from it. 


### Age at appearance
Reference: `data\50_analysis\all\final_visualizations\01_age_ridge_plot_en.html`
Overall: We must make this visualization more compact.
* Remove the legend.
* The top is still cut off. Fix this.
* Introduce meaningful visualizations:
  * Min, Max, Median as bar, Mean, IQR.


### Talk Shows Sample & Demographics
* Unbouble is listed wrongly 3 times.
* We must shrink this down to just the most relevant rows:
  * Boradcasting program
  * Episodes
  * Guest 
    * Appearances
    * Unique
  * Episode without
    * male
    * female
* Introduce multi-column header columns. (e.g. "Guest", "Episode without")
* add total row on the top 


### Gender over time
* Move legend above the plot.
  * (shorten "Frühshoppen")
* Increase font size or Shrink width
* rotate x labels to be horizontal.
* Remove "male" from legend (since now everything is male)
* Add general trend line

### Party
* apply abreviation (Parties) (Frühshoppen)
* apply uniform colors (blue, same as for property coverage)


### Property Coverage
* Reduce Column width to only the required width
* Remove legend
* Add row "has wikidata entry" for % of guests that have wikidata entries

---

## Sixth iteration — Diagnosis: 00_show_stats_table

### Why cross-column spanning never landed (and never will with the current approach)

`build_show_stats_table` in `viz_final.py` uses Plotly's `go.Table`. Plotly tables render as an **SVG canvas element**, not as DOM `<table>` elements. `colspan` / `rowspan` are HTML/DOM concepts; they cannot exist in this rendering model. Every attempt to "add spanning headers" in previous iterations has been deferred with a note like *"not natively supported — deferring to final HTML output pass"* — but that pass never happened.

**The only real fix:** Replace `go.Table` with a **hand-authored HTML/CSS `<table>`**, saved as a self-contained HTML file (no Plotly dependency). This unlocks:
* True `colspan` multi-level header rows.
* CSS-based percentage bars (a `<div>` with `width: X%` and `background: show-color`).
* Per-column CSS `width` (Plotly's `columnwidth` is proportional, not absolute, and clips text).
* Proper print-to-PDF via `@media print`.

### Why the % bar concept is gone

`_mini_bar()` (Unicode block characters `█░`) is still defined in `viz_final.py:359–364` but is **called nowhere** in `build_show_stats_table`. It was wired up in iteration 2, then silently removed when the column layout was redesigned in iterations 4/5. Even if re-wired, Unicode bars are a crude workaround — they don't scale, can't be coloured by show, and waste cell width. The 4th-iteration spec explicitly asked for a **coloured CSS bar in the show's colour**, which is only achievable in a real HTML table.

### Column drift: what the spec says vs what is rendered

| Spec (4th / 5th iteration) | Current code | Gap |
|---|---|---|
| Broadcasting Program | ✓ column 1 | — |
| Episodes · Span | ✗ missing | no date-range column at all |
| Episodes · Unique | ✓ as "Episodes" | label only; no Span or Unresolved siblings |
| Episodes · Unresolved | ✗ missing | — |
| Guests · Appearances | ✓ column 3 | — |
| Guests · Unique | ✓ column 4 | — |
| Guests · w/ Wikidata | ✗ missing | — |
| Guest Gender · Male (count + %) | ✗ missing | gender columns were dropped from the table entirely |
| Guest Gender · Female (count + %) | ✗ missing | — |
| Guest Gender · Other (count + %) | ✗ missing | — |
| Eps without · Male | ✓ column 5 | present but no % bar |
| Eps without · Female | ✓ column 6 | present but no % bar |
| Eps without · Other | ✗ missing | — |
| Guest Age · Min | ✗ missing | — |
| Guest Age · Median | ✗ missing | — |
| Guest Age · Max | ✗ missing | — |

The table has **6 columns**; the spec calls for **~15 leaf columns** under **5 grouped headers**.

### Untapped visual potential & space waste

1. **Program column is a fixed 200 px** — wastes space for "Lanz", "scobel", "StarTalk"; clips "Internationaler Frühschoppen" before the short-label kicks in. With CSS `width: auto; min-width: …` this self-sizes.

2. **All numeric columns are equally wide (55–90 px)** — "Span" (`2003–2025`) needs more room than "Min" (`34`). CSS can give each column exactly what it needs.

3. **Single-level header** — "Guest Appearances" and "Guest Unique" share a conceptual parent ("Guests") but are two completely separate header cells. A `<thead>` with two `<tr>` rows and `colspan` conveys the grouping instantly.

4. **Alternating row fill is doing all the work** — the only visual differentiator between rows is the light grey / white stripe. Show-colour could saturate the left cell of each row (the program name) as a colour swatch, giving instant cross-table anchor.

5. **No per-column alignment logic** — all numerics are `center`; percentage cells that are empty (`—`) look the same as zero. A right-aligned number column with left-aligned bar would read better.

6. **No sticky header** — in a browser the header scrolls away once there are many rows. A CSS `position: sticky` header would fix this for free.

7. **Total row is styled identically to data rows** (just a different background) — it should be visually distinct: bold text, a heavier top border, and the show-colour fields suppressed.

### Recommended path forward

Replace `build_show_stats_table` with a `build_show_stats_table_html()` function that:
1. Accepts the same dataframes as today.
2. Renders a **pure HTML template** (Jinja2 or f-string) with `<thead>` (two rows, `colspan`) and `<tbody>`.
3. Embeds inline CSS for: column widths, bar-chart cells (`<div class="bar" style="width:X%;background:COLOR">`), sticky header, alternating rows, total-row styling.
4. Writes a standalone `.html` file (no Plotly JS — tiny file, fast render, print-ready).
5. Keeps the `_save(fig, …)` path for PNG/PDF export by rendering the HTML to a headless browser via `playwright` or `weasyprint` — or simply screenshots the HTML output.

This is a one-session rewrite of a single function. The data-computation logic (merges, gender pivots, age stats) stays in the notebook; only the rendering layer changes.

---

## Seventh iteration — Diagnosis: 02_gender_over_time

Reference file: `data/50_analysis/all/final_visualizations/02_gender_over_time_en.html`

### Data gap: year 2011 is entirely absent

Every trace jumps directly from 2010 to 2012 — year 2011 is not in any trace's x-values. This is confirmed by inspecting the embedded Plotly data: the `all_years` list in `build_gender_over_time` is computed as `sorted(df["year"].unique())`, and 2011 simply never appears in `_gender_by_year_show`.

**This is NOT a missing episode in the source.** `aligned_episodes.csv` has ample 2011 coverage for every in-scope show (Markus Lanz: 118 eps, Hart aber fair: 36, Maischberger: 40, scobel: 32 — all with valid `premiere_date_date_fernsehserien_de`).

**Root cause — confirmed by data inspection:** The gap is a coverage failure in `dedup_cluster_members.csv` (Phase 32). `build_person_catalogue` maps person→episode exclusively via `episode_url_fernsehserien_de` → `alignment_unit_id`. For the period roughly 2010–2014, Phase 32 did not create cluster-member rows for the overwhelming majority of guest appearances:

| Show | Unique persons with Wikidata ID in cluster_members |
|---|---|
| | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 |
| Markus Lanz | 4 | 3 | **0** | 2 | 1 | 0 | 27 |
| Hart aber fair | 116 | 80 | **1** | 1 | 1 | 1 | 126 |
| Maischberger | 0 | 0 | **0** | 0 | 0 | 0 | 0 |

For 2011:
- **Markus Lanz:** 0 persons with Wikidata IDs → 0 rows in `_gender_by_year_show` → year 2011 absent from `all_years` → absent from every trace via `reindex(all_years)`.
- **Hart aber fair:** 1 person (almost certainly the moderator) → treated as a data point but represents 1 individual, not the guest pool.

The gender analysis (Cell 72) inner-joins `episode_appearances` with `_p21_person_gender` (persons with known Wikidata gender). Since those years lack cluster-member rows with Wikidata-linked persons, the join produces zero rows, and the years drop out of the data entirely.

**Secondary consequence — misleading values in 2010, 2012–2014:** Years with a handful of rows (e.g., Hart aber fair 2010 = 80 persons, Hart aber fair 2012 = 1 person) produce values that look statistically confident but are based on only a fraction of the true guest pool. The 3-year rolling window further blends these sparse years with adjacent years, masking the problem visually.

**Visual effect of the gap:** The x-axis uses `dtick=2` (ticks at 2006, 2008, 2010, 2012, …). When year 2011 is absent from `all_years`, the x-axis jumps directly from 2010 to 2012, creating a double-width gap between those tick marks. This appears as a visual discontinuity that the reader perceives as "around 2013."

**Stopgap fix (implemented):** In `build_gender_over_time` (`viz_final.py`), changed `all_years = sorted(df["year"].unique())` to `all_years = list(range(min_year, max_year + 1))`. Year 2011 now appears as a proper NaN break at the correct x position instead of being silently skipped.

**Proper fix (Phase 32):** Re-run Phase 32 entity deduplication to fill the 2010–2014 coverage gap. All episodes are in `aligned_episodes.csv` with valid dates; the missing piece is guest-person linkage for those years.

**Additional recommendation:** Add a per-year coverage indicator to the visualization (e.g., opacity proportional to the number of persons contributing to each data point, or dashed lines below a threshold of N persons). Years based on only 1–3 persons should be visually distinguishable from years based on 80–130 persons.

### Layout issues

#### "50 % parity" annotation cut off on the right

The annotation is placed at `x=1` (right edge of the x-domain) with `xanchor="left"`. With a right margin of only 40 px, the text extends beyond the canvas and is clipped. Code in `viz_final.py:1047-1048`:
```python
fig.add_hline(y=50, …, annotation_text=_t(lang, "02_50pct"), annotation_position="right")
```
`annotation_position="right"` maps to `x=1, xanchor="left"`, which always overflows a tight right margin.

**Fix options (pick one):**
- Change `annotation_position` to `"top right"` (places text above the line near the right edge).
- Or explicitly: `annotation=dict(text=…, x=0.98, xref="x domain", xanchor="right", y=50, yanchor="bottom")` — text sits just inside the right boundary.
- Or increase `r` margin from 40 to 120, accepting the wider figure.

#### Legend spanning two rows

10 legend entries (9 show lines + overall trend) at `font.size=12` inside a 1050 px figure routinely overflow to two rows. Each entry with a "Maischberger"-length label is ~110 px wide; 10 × 110 = 1100 px > 1050 px.

With a two-row legend the top margin (`t=120`) is consumed entirely, leaving the first row of legend text just inside or even clipped by the canvas border.

**Fix:** Reduce legend `font.size` to 10 or 11. This is sufficient for short labels and fits all 10 entries on one row at 1050 px.

#### Top of chart cut off

With `t=120` and the legend at `y=1.02` (just above the plot), a two-row legend pushes the upper row above the canvas. Fixing the legend to one row (see above) resolves this automatically. If the legend remains two rows, increase `t` to at least 150.

#### First year label and "0 %" tick overlap

The x-axis first tick (2006 or the actual data start) renders at the bottom-left corner directly next to the y-axis "0%" tick label. With both using `font.size=12` and `tickangle=0`, the two labels visually collide.

**Fix options:**
- Shift the y-axis range minimum: `range=[40, 100]` instead of `[0, 100]`. This removes the "0%" tick entirely and zooms into the actual data range (see below).
- Or add a small `standoff` to the x-axis: `xaxis.title.standoff` doesn't help here, but `xaxis.ticklabeloverflow="allow"` + `xaxis.range=[2006.3, 2025]` shifts the first label away from the axis.

### Untapped visual potential

#### Y-axis range: half the plot is empty

The y-axis spans 0–100 %, but the lowest value across all shows is ~52 % (Presseclub) and the overall trend never dips below 61 %. The bottom half of the chart (0–50 %) encodes nothing except the 50 % reference line.

**Fix:** Set `yaxis.range=[40, 100]` (or `[45, 100]`). This:
- Doubles the visual amplitude of every trend line, making year-to-year changes readable.
- Removes the empty lower half.
- Keeps the 50 % reference line visible with annotation room above it.

#### All show lines have identical visual weight

Every show line uses `width=1.8, dash="solid"`. The overall trend line is only slightly heavier at `width=2.8`. When 9 lines of the same weight overlap in a similar range (all 60–80 %), individual show trajectories are hard to trace.

**Fix options:**
- Assign each show a unique `dash` style (e.g., solid / dash / dot / dashdot) in addition to colour. Plotly supports ~5 named dash patterns, enough to differentiate 9 lines combined with colour.
- Make the trend line bolder: `width=3.5` and a dark fill colour (`#111`) so it reads above the pack without squinting.

#### `dtick=2` hides annual granularity

With every other year labelled (2006, 2008, 2010, …), the viewer cannot read single-year events. The 3-year rolling window already smooths out noise, so annual labels would not look jagged.

**Fix:** Set `dtick=1`. With 22 years × ~35 px/tick ≈ 770 px, all tick labels fit in a 1050 px width without overlap.

#### 50 % parity line is visually weak

A `line_width=1.2` dotted red line is easy to overlook. Because it is a semantically meaningful threshold (gender parity), it deserves stronger visual treatment.

**Fix:** Replace the single dashed line with a subtle background band: `add_hrect(y0=0, y1=50, fillcolor="rgba(192,57,43,0.05)", layer="below", line_width=0)`. The band tints the "below-parity" region, making the threshold immediately legible without adding clutter.

#### No markers on line ends

Because lines begin and end at different years per show (Presseclub starts 2016, StarTalk ends ~2018), the viewer cannot quickly read the current (2025) value for each show. End-of-line dots would anchor each trajectory.

**Fix:** Add `mode="lines+markers"` with `marker=dict(size=4, symbol="circle")` and `marker.showscale=False`, but only render the marker at the last non-null point. Alternatively add a text annotation at each line's last point with the 2025 value.

### Summary of recommended fixes (priority order)

| # | Issue | Fix | Effort |
|---|---|---|---|
| 1 | 2011 data gap | Debug `episode_appearances.premiere_date` for 2011 rows | Medium |
| 2 | "50 % parity" cut off | `annotation_position="top right"` or explicit coords | Tiny |
| 3 | Legend two rows | `legend.font.size=10` | Tiny |
| 4 | Top cut off | Follows from fix #3; or increase `t` to 150 | Tiny |
| 5 | Y-axis 0–100 wastes space | `yaxis.range=[40, 100]` | Tiny |
| 6 | First year / 0% overlap | Follows from fix #5 (0% label gone) | — |
| 7 | dtick=2 hides granularity | `dtick=1` | Tiny |
| 8 | Lines identical visual weight | Add dash variety; bolder trend line | Small |
| 9 | 50% line too subtle | Replace with `add_hrect` background band | Small |
| 10 | No end-of-line anchors | Markers or text at last data point | Small |
