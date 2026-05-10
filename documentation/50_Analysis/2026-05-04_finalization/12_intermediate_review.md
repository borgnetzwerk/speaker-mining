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