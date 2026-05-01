# Design Review — Gaps, Improvements, and Additional Concepts

This document identifies gaps, missing structure, and additional opportunities found by reviewing `open-tasks.md` against:
- `archive/additional_input.md` (the primary source)
- `2026-04-29_Initialization/` design artifacts (prior initiative)
- `documentation/visualizations/visualization-principles.md` (existing rules)
- `data/00_setup/` (existing config patterns)
- `00_immutable_input.md` (authoritative goals)

Items are grouped by type. For each item: what is missing, where the gap manifests, and a severity rating (**Critical / Important / Nice-to-have**).

---

## 1. Critical Gaps

These are omissions or contradictions that will produce wrong or incomplete outputs if not addressed.

---

### G-01 — Occupation (P106) is absent from the property list

**Severity: Critical**

REQ-P01 lists 8 Item properties but does not include **occupation (P106)**. Occupation is the single most important property in the entire analysis — it is the primary input for the class hierarchy, sunburst, sankey, timelines, and cross-tabulations. Without P106 in the property list, none of the hierarchy-based requirements (REQ-I01–I03, REQ-H01–H07) have a data source.

The old design listed P106 as a Step A claim and dedicated three analysis steps (C3, C4, C7) to it.

**Gap:** REQ-P01 must include `occupation (P106)`.

---

### G-02 — Employer (P108) absent from property list

**Severity: Important**

Employer (P108) was included in the prior design's Step A property fetch and is relevant for cross-tabulation with occupation and party. Not mentioned anywhere in the new design.

**Gap:** Decide whether P108 is in scope. If yes, add to REQ-P01.

---

### G-03 — Multi-value counting rule is not specified

**Severity: Critical**

When a person has multiple values for an Item property (e.g. three occupations), how are they counted in distributions? Options:
- Count each value separately → one person contributes 3 to the occupation count
- Count the person once per property → one person = 1 count regardless of occupation count
- Both modes, clearly labeled

The old design said "count each separately; document multi-count behavior." REQ-H05 addresses deduplication for mid-level class aggregation specifically, but no universal rule exists for REQ-U05, REQ-I01, REQ-I04, etc.

**Gap:** A universal multi-value counting rule must be defined and applied consistently across all distribution analyses.

---

### G-04 — No "Unknown" / empty row mandate in distributions

**Severity: Important**

REQ-V10 requires showing the "empty" count in every visualization's context statistics, but the design does not mandate an explicit "Unknown" bar in distribution charts. The prior design (F1 signature, §6 visualization mapping) explicitly required an "Unknown" row in the data output and a visible gray bar in charts.

Without this mandate, empty values become invisible — a property that 40% of guests lack could appear to cover 100% of the data.

**Gap:** Every distribution must include an explicit "Unknown / no data" entry in both the output table and the visualization. The position and styling (gray, always at the bottom of sorted charts) should be specified.

---

### G-05 — Time-sensitivity of properties not captured

**Severity: Important**

`00_immutable_input.md` states: "Technically, every guest property is episode-specific. A guest can have occupation X in Episode 4, and occupation X and Y in episode 5, and then only Occupation Z in episode 16." The design must decide:

- **Option A (snapshot):** Use the current Wikidata value, with a documented caveat.
- **Option B (temporal filter):** For properties with `start time` / `end time` qualifiers (P102 party affiliation especially), filter to values that were active at the episode's publication date.

The old design deferred temporal filtering (TODO-041) for party affiliation and noted the caveat. The new design does not mention this at all.

Properties most affected: P102 (party membership), P39 (position held), P108 (employer).

**Gap:** Define the temporal filtering strategy per property, or explicitly declare snapshot mode with a documented caveat. Create a config file entry to flag which properties support temporal filtering.

---

### G-06 — Visualization principles document already exists and is not referenced

**Severity: Critical**

`documentation/visualizations/visualization-principles.md` already defines:
- The **Okabe-Ito colorblind-safe palette** (8 named colors + gray for Unknown/Other)
- Font family configuration
- Export format mandate (PDF + PNG, scale=3 / 300 DPI)
- Figure dimensions (default 1000×600, bar chart scaling, node graph sizing)
- Title and subtitle conventions with sample-size annotation (`n=...`)
- Axis label rules

The new design (REQ-V01–V11) partially overlaps with this but contradicts it in places and introduces ambiguity where the existing doc is specific. In particular:
- REQ-V01 says "unique color per element" — the existing palette has 8 colors, meaning visualizations with >8 elements need a defined overflow strategy.
- REQ-V03 says "use party colors" — the existing doc says gray is always for Unknown/Other and black is a palette color (#8). CDU's canonical color is also black. This creates a conflict.
- The existing doc does not yet define color consistency across diagrams (REQ-V02) — this is a real gap in the existing doc.

**Gap:** The new design must formally reference and extend `visualization-principles.md`, not re-specify it. The three open issues (overflow strategy, party-color/palette conflict, cross-diagram consistency) must be resolved in that document.

---

### G-07 — Export format not specified in new design

**Severity: Important**

REQ-V08 says "increase resolution" in the quality check but does not mandate:
- PDF + PNG as required export formats (already in visualization-principles.md)
- Resolution target (300 DPI / scale=3, already in visualization-principles.md)
- Figure dimensions

**Gap:** Add an explicit export format requirement (or reference the existing doc).

---

### G-08 — No default population / role separation rule

**Severity: Important**

All analyses should default to the `guest` role. Other roles (moderator, staff, incidental) are separate populations that can be analyzed independently. This is a fundamental scoping rule from the prior design (§2.1 role separation, §3 "all analyses in Step C default to the guest population"). It is not mentioned anywhere in the new design.

**Gap:** Specify the default population and role separation convention. At minimum: every analysis should state which population it runs on; `guest` is the default.

---

### G-09 — Appearance count vs. unique person count is not a systematic output column

**Severity: Important**

The old F1 function always returned both `person_count` and `appearance_count` (+ `pct_by_person` and `pct_by_appearance`). REQ-U07 requires visualizations of both, but REQ-U05 (top-X values) and the episode statistics table (REQ-U06) do not explicitly specify that all four columns must always be present.

**Gap:** Define that every distribution table must include both `person_count` / `appearance_count` columns (and their percentage variants). This is the fundamental duality of the dataset.

---

## 2. Missing Analysis Concepts

Analysis angles that were in the prior initiative or immutable input but are absent from the new design.

---

### M-01 — Guest co-occurrence matrix (person × person)

The occurrence matrix (person × episode) is REQ-G02. But the prior design also specified a **guest co-occurrence matrix**: which guests tend to appear in the same episodes? This is a symmetric person × person matrix where each cell = count of episodes they shared.

This enables:
- Identifying "circles" of frequently co-occurring guests
- Network analysis of guest relationships
- Input to page rank

**Source:** `03_design_spec.md` §Step B; `00_immutable_input.md` §Guest-Co-Occurrence Matrix.

---

### M-02 — Page rank analysis

TASK-A03 specified: node-graph visualization of page rank, one for person instances (sized/colored by rank), one for all classes, one combined. This analysis type is completely absent from the new design.

Page rank assigns influence scores to nodes in the guest co-occurrence graph. It surfaces "structurally central" guests — those who bridge different communities — not just frequently appearing ones.

---

### M-03 — Dataset overview / pipeline meta-statistics

Step D1 from the old design: a pipeline coverage table showing, per phase and source, how many entities were retrieved, matched, and covered. Examples:
- How many episodes came from Wikidata / Fernsehserien / ZDF Archiv?
- How many guests have a Wikidata match?
- Coverage rate per property (% of guests who have a value for P21, P106, etc.)

The coverage-per-property metric is especially important: a visualization for a property where only 10% of guests have data is very different from one where 95% have data.

**Source:** `00_immutable_input.md` §Meta-Analysis; `03_design_spec.md` §Step D1.

---

### M-04 — Temporal chunking and trend analysis

Analyzing how guest properties shift over time: year-by-year and decade-by-decade changes in gender ratio, occupation mix, party distribution. This was in TASK-A05 and is related to REQ-I01 (timelines), but the new design does not specify decade-level aggregation or trend comparison.

Especially useful: how has each show's guest demographics changed since its inception?

---

### M-05 — Cross-show comparison visualization

REQ-G01 specifies per-show + combined output. But there is no visualization that puts multiple shows side by side for direct comparison. For example:
- Grouped bar chart: gender distribution, one group of bars per show
- Heatmap: shows × property values, colored by person_count

This is distinct from running each analysis separately per show.

---

### M-06 — Career arc / temporal guest patterns

From TASK-A05: identify guest trajectory types:
- "Shooting star": concentrated burst of appearances then disappearance
- "Evergreen": consistently invited over a long time span

These are temporal patterns per person computed from the occurrence matrix. They are a natural output of the data but require a dedicated analysis step.

---

### M-07 — Subset dominance analysis

From TASK-A05: which value of property A "explains" the concentration of value B? Example: if removing politicians from the guest list drops the journalist share from 80% to 5%, politicians are load-bearing for the journalist statistic.

Also: identify individuals who over-represent their group (one female scientist invited 100× while others are invited 5×).

---

### M-08 — Party affiliation history / temporal party membership

A guest may have belonged to multiple parties over time (e.g. SED → PDS → Die Linke). The current design uses snapshot party membership. A richer analysis would track which party was active at the time of each appearance.

This requires the temporal filtering from G-05. A dedicated visualization: a timeline of party membership changes for guests with multiple party affiliations.

---

### M-09 — Person property timeline view

From `00_immutable_input.md`: structure all relevant properties per person into groups (universal vs. temporal). A per-person view showing when properties were active. This is a qualitative drill-down, not a population-level statistic.

---

### M-10 — "Most relevant person" metric

From TASK-A10: define and implement a "most relevant person" output. Candidate metrics: highest `appearance_count`, widest cross-show presence, highest page rank score, or a composite. This is not in the new design.

---

## 3. Missing Visualization Types and Rules

---

### V-01 — Line chart for temporal trends

REQ-I01 specifies "timelines" but does not specify the chart type. The prior design specified **line charts** (one line per property value, value × year). Line charts are fundamentally different from bar charts and need their own rules:
- Time on X-axis (Type D)
- One line per property value
- Stacked area as secondary option

**Gap:** Specify the line chart type and its formatting rules.

---

### V-02 — Grouped bar chart for cross-show comparison

No visualization type for directly comparing shows is specified. A **grouped bar chart** (or side-by-side bar chart) where each group is a property value and each bar within a group is a show is the natural chart type for this.

---

### V-03 — Histogram for continuous properties

REQ-Q01 specifies violin plot for age, but violin plots require a certain minimum sample size to be meaningful. The prior design (F4, §6) required **histograms as the primary chart** with violin/box plot alongside. Histogram bin width should be configurable (default 10 years for age).

**Gap:** Specify histogram as a required chart type for continuous properties (in addition to violin).

---

### V-04 — Box plot

Mentioned as an option in the prior taxonomy (F4) but not specified in the new design. Useful alongside histograms and violin plots for showing median, quartiles, and outliers.

---

### V-05 — Heatmap / matrix visualization

REQ-I04 and REQ-I05 specify co-occurrence matrices (Top 10 × Top 10), but do not specify the visualization type. A **heatmap** is the natural chart type: rows = values of property A, columns = values of property B (or same property), color = co-occurrence count.

**Gap:** Specify heatmap as the required chart type for co-occurrence matrices.

---

### V-06 — Node / network graph

Page rank visualization (M-02) and guest co-occurrence (M-01) require **network graphs** (node-link diagrams). The existing visualization-principles.md already specifies default dimensions for this (`width=1400, height=1000`). The new design does not mention this chart type at all.

---

### V-07 — Geographic map for place of birth (P19)

Place of birth (P19) is listed as an Item property in REQ-P01. But a place is a geographic entity — the most natural visualization is a **choropleth map** (shading by country/region count) or a **dot map** (one dot per birth location, sized by count). A bar chart of countries is a valid fallback, but a map would be far more informative for geographic data.

---

### V-08 — "Other" bar: placement and styling

REQ-V11 says "group into other when crowded" but does not specify:
- The "other" bar should always appear at the **bottom** of descending-sorted bar charts (it is a residual, not a value).
- "Other" should use the **gray color** from the Okabe-Ito palette (already designated for Unknown/Other in visualization-principles.md).
- The label should show the count of items grouped: `Other (N items)`.

---

### V-09 — "Unknown" bar: position and styling

Distinct from "other": "Unknown" means the person had no data for this property, not that their value was in the tail. It should:
- Always use **gray** color.
- Always appear **after "other"** at the bottom of sorted charts (regardless of count).
- Be explicitly labeled with its count: `Unknown (N guests, X%)`.

---

### V-10 — Color overflow strategy for >8 categories

The Okabe-Ito palette has 8 colors (excluding gray). REQ-V01 requires unique colors per element. When a visualization has >8 distinct elements, a strategy is needed:
- Option A: Apply REQ-V11 — group tail into "other" until ≤8 elements remain.
- Option B: Use a larger palette (e.g. extend with additional colorblind-safe colors).
- Option C: Use opacity/pattern variations of the 8 base colors.

This must be decided and applied consistently.

---

### V-11 — Centered/diverging stacked bar chart

The prior design (F3 §6) specified a **centered stacked bar** when one axis is binary (e.g. gender × occupation: bars split left/right from center, female left, male right). This chart type is distinct from a regular stacked bar and the new design's REQ-I08 does not mention it.

---

### V-12 — `n=X` annotation mandate

The prior visualization mapping (§6) required annotating every chart with `n=X` (sample size). REQ-V10 partially covers this ("show appearance and unique guest counts") but does not explicitly mandate the `n=` notation or where it appears (subtitle vs. axis annotation vs. legend entry).

---

## 4. Missing Principles and Conventions

---

### P-01 — Idempotency convention

Analysis runs should produce identical output on repeated runs given identical input data. This should be explicit: no timestamps in output filenames, no randomness in color assignment (must be deterministic from QID), no non-reproducible computations.

---

### P-02 — Progress reporting in notebooks

The prior design specified that "each cell prints intermediate counts so results are visible without running the full notebook." This is a development convention that prevents silent failures. Not mentioned in the new design.

---

### P-03 — Notebook vs. generated-script architecture

The prior initiative used `gen_50_analysis.py` → `50_analysis.ipynb` pattern (a Python script that generates the notebook). The new design mentions notebooks but does not specify this architecture. Should be decided before implementation begins.

---

### P-04 — Minimum count threshold for display

REQ-V11 says "group into other when crowded" but no numerical threshold is given. When does a bar qualify for display vs. grouping into "other"? Candidates:
- Absolute count threshold (e.g. fewer than N persons)
- Relative threshold (e.g. less than 1% of total)
- Rank-based (always show top X, group the rest)

All three may be useful for different chart types. A configurable threshold in `data/00_setup/` would be consistent with REQ-C01.

---

### P-05 — Data caveat / footnote convention

`00_immutable_input.md` explicitly requires documenting data limitations. These should be systematic, not ad-hoc:
- Age: year-of-birth precision only; recording date may predate broadcast
- Party affiliation: snapshot value unless temporal filtering is applied (G-05)
- Source coverage: not all guests have Wikidata matches
- Empty values: always reported (REQ-V10), but the implication for interpretation should be noted

A convention for where caveats appear (subtitle, footnote, companion text file) should be established.

---

### P-06 — Analysis-visualization separation principle

The prior design explicitly separated analysis (computing statistics) from visualization (rendering charts) into two notebooks (`50_analysis.ipynb` + `51_visualization.ipynb`). The new design uses "Layer 2: Analysis" and "Layer 3: Visualization" but does not mandate this as a notebook boundary. This separation matters because:
- Analysis outputs (CSVs) can be inspected without rendering charts
- Visualization can be re-run without recomputing analysis
- Different people or agents can own each layer

---

### P-07 — GDPR / privacy separation

The prior design designated `data/50_analysis/persons/` as GDPR-sensitive and separate from other outputs. Named individuals in a database that links them to specific TV appearances may have data protection implications. The new design does not mention this at all.

Minimum requirement: outputs containing individual-level data (person names, QIDs) must be in a designated directory that can be excluded from public releases.

---

### P-08 — Configurable global parameters

Several requirements reference configurable parameters (X for occurrence matrix, N for top-X, bin width for histograms) without consolidating them. A single configuration section (either in a config file or a notebook setup cell) should define all global parameters:

| Parameter | Default | Used by |
|---|---|---|
| occurrence_matrix_top_x | 50 | REQ-G02 |
| top_n_bars | 10 | REQ-I04, REQ-I05, REQ-I08 |
| age_bin_width_years | 10 | REQ-Q01 |
| min_display_count | 5 | REQ-V11 |
| color_overflow_strategy | "other_group" | V-10 |
| export_formats | ["png", "pdf"] | REQ-V07 |
| figure_dpi | 300 | visualization-principles.md |

---

### P-09 — Title / axis labeling convention

Every chart requires:
1. **Main title**: what is shown (e.g. "Occupation distribution — Markus Lanz")
2. **Subtitle**: `n=X appearances, Y unique guests; Z with no data`
3. **X/Y axis labels**: never the raw column name
4. **Legend** when multiple series are shown

This is partially in visualization-principles.md §5 and partially in REQ-V10, but not consistently specified.

---

### P-10 — Accessor pattern for Wikidata labels

QIDs appear throughout analysis outputs. Every output table and every visualization label must use the human-readable label (in German or English), not the raw QID. A consistent accessor pattern is needed to look up labels from cached Wikidata data. This should be defined once and reused everywhere.

---

## 5. Structural Gaps

---

### S-01 — No requirements tracing for the F1–F5 taxonomy

The prior initiative developed a clean taxonomy of analysis function types (F1: distribution, F2: over-time, F3: cross-tabulation, F4: continuous, F5: hierarchy). The new design does not reference or extend this taxonomy. The taxonomy was explicitly validated against the requirements and mapped to chart types. Discarding it means:
- Each property's visualizations are specified independently, losing the generic-function benefit
- New properties added later must each be specified from scratch rather than just identifying their type

**Decision needed:** Adopt the F-type taxonomy (possibly extended) as part of the new design, or explicitly replace it with a different organization.

---

### S-02 — Output directory structure incompletely specified

The design specifies `data/50_analysis/all/<property_id>/visualizations/` but does not specify:
- File naming conventions for individual charts (how are variants distinguished? `_cum` / `_uniq` suffix?)
- Where combination tables go (REQ-I06, REQ-I07)
- Where the episode statistics table goes (REQ-U06)
- Whether per-show files mirror the all/ structure exactly

---

### S-03 — No specification for what constitutes "analysis complete"

There is no definition of done for the overall analysis. What checkboxes must be ticked before the analysis layer is considered finished? Without this:
- Implementation may stall at 80% with no clear stopping condition
- Quality verification (REQ-V08) has no completion criterion

---

### S-04 — No mechanism to re-run after data updates

If upstream data (Wikidata cache, episode data) is updated, which analysis outputs need to be regenerated? The design assumes a single full run but does not specify an incremental update strategy.

---

## 6. Additional Puzzle Pieces

These are concepts not mentioned anywhere in the prior or current design that could add significant value.

---

### X-01 — Bundestag composition overlay for party analysis

`00_immutable_input.md` mentions: "Party affiliation over time alongside constellation of bundestag over time (and maybe alongside 'Sonntagsfrage' public poll results)." Overlaying guest party distribution over time with the actual Bundestag composition would immediately reveal whether shows over- or under-represent government parties, opposition parties, etc.

This requires an external data source (Bundestag composition by date). The Bundestag composition is publicly available and relatively easy to obtain.

---

### X-02 — Population-level benchmarks

Guest demographics can only be interpreted in context. For example:
- Is 30% female guests high or low, relative to the overall German population (50% female)?
- Relative to the share of female politicians in the Bundestag?
- Relative to the share of female scientists in Germany?

Overlaying guest distributions with population-level benchmarks would transform descriptive statistics into normative ones. Sources: Statistisches Bundesamt, academic databases.

---

### X-03 — First-appearance vs. repeat-appearance analysis

Distinguish between:
- Guests who appeared only once ("one-timers")
- Guests who returned ("repeaters")
- The repeat-invite concentration: what fraction of total appearances is concentrated in the top-10% most-invited guests?

This reveals structural patterns in booking behavior that bare distribution statistics don't show.

---

### X-04 — Episode-level diversity metrics

Beyond per-episode property distributions, compute **diversity indices** per episode:
- Gender diversity (e.g. Shannon entropy across gender values in that episode)
- Occupation diversity (how many distinct occupation categories in one episode)
- Party diversity (how politically varied was a single episode?)

This enables answering: "Was episode 412 unusually homogeneous compared to average?"

---

### X-05 — Seasonal / recurring episode-type patterns

Some episodes may be special (year-in-review, Christmas editions, election specials). These may have systematically different guest profiles. Can they be identified by title pattern or date? If so, they could be analyzed as a separate subset.

---

### X-06 — Inter-property predictive analysis

Does having property value A predict having property value B? Example: does being a scientist strongly predict appearing with other scientists (rather than with politicians)? This moves from descriptive statistics toward predictive modeling — mutual information or χ² between property values.

**Source:** Also mentioned in TASK-A05.

---

### X-07 — Accessibility: colorblind-safe palette already defined

The Okabe-Ito palette in `visualization-principles.md` is explicitly colorblind-safe. The new design's REQ-V01–V03 should explicitly reference this rather than leaving the palette open. The conflict with party colors (CDU black vs. palette black) needs a resolution rule.

---

### X-08 — Multi-language label support

Wikidata entities have labels in many languages. The dataset is about German TV, but some entity labels may only be in English or may differ between languages. A label resolution priority (German first, English fallback, QID last) should be standardized.

---

### X-09 — Version / run metadata in outputs

Each output file should include metadata: when the analysis was run, which version of the data was used (or at least the timestamp of the source files). This helps when comparing multiple analysis runs.

---

### X-10 — Interactive exploration mode

All the CSV outputs and visualizations described are static. A lightweight interactive mode (e.g. a single-file HTML dashboard using Plotly) could allow filtering by show, property, and time range without code. This is especially valuable for sharing results with non-technical stakeholders.

---

## Summary: Priority Ranking

| ID | Item | Severity | Type |
|---|---|---|---|
| G-01 | P106 (occupation) missing from property list | **Critical** | Gap |
| G-06 | Existing visualization-principles.md not referenced | **Critical** | Gap |
| G-03 | Multi-value counting rule missing | **Critical** | Gap |
| G-04 | "Unknown" row mandate missing | **Important** | Gap |
| G-05 | Time-sensitivity of properties unaddressed | **Important** | Gap |
| G-07 | Export format not specified | **Important** | Gap |
| G-08 | Default population / role separation missing | **Important** | Gap |
| G-09 | appearance_count + person_count duality not systematic | **Important** | Gap |
| G-02 | P108 (employer) not mentioned | **Important** | Gap |
| V-05 | Heatmap not specified for co-occurrence matrices | **Important** | Viz |
| V-01 | Line chart not specified for timelines | **Important** | Viz |
| V-03 | Histogram missing for continuous properties | **Important** | Viz |
| M-01 | Guest co-occurrence matrix missing | **Important** | Analysis |
| M-03 | Dataset overview / meta-statistics missing | **Important** | Analysis |
| M-02 | Page rank analysis missing | **Important** | Analysis |
| S-01 | F1–F5 taxonomy not referenced | **Important** | Structure |
| P-08 | Global parameter config missing | **Important** | Convention |
| P-07 | GDPR separation not mentioned | **Important** | Convention |
| P-04 | Minimum count threshold not defined | **Important** | Convention |
| V-08 | "Other" bar placement/styling not specified | **Important** | Viz |
| V-09 | "Unknown" bar placement/styling not specified | **Important** | Viz |
| V-10 | Color overflow strategy (>8 categories) missing | **Important** | Viz |
| P-01 | Idempotency not specified | **Nice-to-have** | Convention |
| P-02 | Progress reporting not specified | **Nice-to-have** | Convention |
| P-06 | Analysis-visualization separation principle | **Nice-to-have** | Structure |
| P-09 | Title/axis labeling convention | **Nice-to-have** | Convention |
| P-10 | QID → label accessor pattern | **Nice-to-have** | Convention |
| M-04 | Temporal chunking / trend analysis | **Nice-to-have** | Analysis |
| M-05 | Cross-show comparison visualization | **Nice-to-have** | Analysis |
| M-06 | Career arc patterns | **Nice-to-have** | Analysis |
| M-07 | Subset dominance analysis | **Nice-to-have** | Analysis |
| M-08 | Party affiliation history | **Nice-to-have** | Analysis |
| M-10 | "Most relevant person" metric | **Nice-to-have** | Analysis |
| V-07 | Geographic map for P19 (place of birth) | **Nice-to-have** | Viz |
| V-11 | Centered/diverging stacked bar chart | **Nice-to-have** | Viz |
| S-02 | Output directory / file naming incomplete | **Nice-to-have** | Structure |
| S-03 | No definition of done for analysis | **Nice-to-have** | Structure |
| X-01 | Bundestag composition overlay | **Nice-to-have** | Extra |
| X-02 | Population-level benchmarks | **Nice-to-have** | Extra |
| X-03 | First-appearance vs. repeat-appearance | **Nice-to-have** | Extra |
| X-04 | Episode-level diversity metrics | **Nice-to-have** | Extra |
| X-10 | Interactive HTML dashboard | **Nice-to-have** | Extra |
