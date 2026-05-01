# Requirements

**Source:** `archive/additional_input.md` (verbatim input); clarifications from `archive/additional_input.md` §Clarifications (2026-05-01).  
**Downstream:** `01_design.md` (architecture), `open-tasks.md` (implementation tasks).  
**Phase 2 additions** are marked inline where they fill clear gaps found by internal inspection.

Where requirements were initially blocked, resolutions from `open_additional_input.md` clarifications are noted inline.

---

## Global Scope

---

### REQ-G01 — Scope: Per-show and combined output

Every analysis and every visualization must be produced twice: once per individual show, and once as a combined all-shows aggregate.

**Verbatim basis:**
> Per show each and once total:

---

### REQ-G02 — Baseline output: Person-Episode Occurrence Matrix

A Person-Episode Occurrence Matrix must be produced per scope (per show + combined). Two variants: one covering all individuals, one restricted to the top-X most frequently occurring individuals. Both variants must be output as CSV and as a visualization.

**Verbatim basis:**
> Per show each and once total:
> * Person-Episode occurence Matrix
>   * One for all
>   * One for the most X occuring individuals
>   * as CSV as well as visualized.

---

### REQ-G04 — Guest appearance frequency distribution and Pareto visualization *(LanzMining gap)*

For each scope: produce a frequency distribution of unique guests by appearance count — how many guests appeared exactly once, twice, three times, etc. Complement with a Pareto-style visualization showing cumulative contribution: what percentage of all appearances is accounted for by the top X% of most frequent guests.

**Verbatim basis:**
> #Talkender vs. #Auftritte (1) — Die Mehrheit der Talkenden wird seltener in Talkshows eingeladen.
> #Talkender vs. #Auftritte (2) — Die Mehrheit der Auftritte wird von der Minderheit der Talkenden absolviert.

**Source:** LanzMining comparison (2026-05-01). Not in original requirements; identified as a meaningful structural analysis absent from our catalogue.

---

### REQ-G05 — Cross-show comparison visualization *(Phase 4 addition)*

For selected properties (at minimum: occupation, gender, political party), produce a cross-show comparison visualization that places the per-show distributions side-by-side, making structural differences between shows visible at a glance.

Acceptable chart forms: grouped bar chart (one group per property value, one bar per show); or a heatmap where rows = property values and columns = shows with cell intensity = percentage.

The combined-scope ("all") variant remains the primary output per REQ-G01; this cross-show comparison is an additional output in the combined scope only.

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` M-05). The per-show + combined scope rule (REQ-G01) produces individual outputs for each show but does not make inter-show differences visible without side-by-side comparison.

---

### REQ-G03 — Default analysis population: guest role *(Phase 2 addition)*

All analyses default to the `guest` population (persons whose role in an episode is classified as guest). Any analysis that intentionally targets a different population (moderator, staff, incidental) must declare this explicitly. Role classification follows the `guest_role` field in the episode data.

**Gap correction (Phase 2):** No population default was stated in the source. Every analysis must target a defined population; `guest` is the default.

---

## Cross-Cutting: Configuration

---

### REQ-C01 — Config-file-driven human specification

For any aspect of the analysis that requires human judgment or domain specification (e.g. loop resolution, mid-level class designation, party colors), provide an easy-to-modify and easy-to-append configuration file following the `data/00_setup/` CSV pattern. Human-specified values must not be hardcoded in notebook cells.

**Verbatim basis:**
> For everything that may need human specification, relevant properties, etc: provide easy to config / append files. see `data/00_setup` for reference.

**Known applications (non-exhaustive):**
- P279 loop resolution → `data/00_setup/loop_resolution.csv` (REQ-H04)
- Designated mid-level classes → `data/00_setup/midlevel_classes.csv` (REQ-H06)
- Party colors → `data/00_setup/party_colors.csv` (REQ-V03)

---

### REQ-C02 — Property list: configurable extension *(Phase 2 addition)*

The property lists in REQ-P01–P04 are the minimum required set. A configuration file must allow additional properties to be activated without code changes: by entering a marker (e.g. `1`) in an opt-in column of the property configuration file, that property is included and processed alongside the minimum set on the next run.

**Verbatim basis:**
> The property list in 00_requirements.md is the minimum list. There needs to be a configurable file where these are stored as an initial set, and where simply by entering a "1" in an by-default empty column, this property should be loaded as well.

**Known application:** The existing `data/00_setup/properties.csv` is the natural location for this opt-in column.

---

### REQ-A01 — Architecture: notebook-module-config separation *(Implementation input)*

Implementation must follow the established coding architecture: Jupyter notebooks orchestrate the pipeline (entry points, sequencing, high-level outputs); Python modules under `speakermining/src/` contain the reusable analysis and visualization logic; CSV/JSON files under `data/00_setup/` contain user-specified configuration. No significant logic belongs in notebook cells.

**Verbatim basis:**
> Remember our coding-principles: Notebooks orchestrate, python modules contain most of the code, and config files contain user-specified input.

---

### REQ-A02 — Visualization caching via checksum *(Implementation input)*

Before generating each visualization, check three conditions:
1. Input data checksum is unchanged since last generation
2. Output file exists at the expected path
3. Output file checksum matches the checksum recorded after the last generation

If all three conditions hold, skip regeneration and proceed to the next visualization. Record checksums after each successful generation. The default behavior is always to regenerate; caching is a time-saving optimization, not a permanent bypass. For non-visualization computation steps, always regenerate unless prohibitively expensive — never risk analysis based on stale assumptions.

**Verbatim basis:**
> Visualization created (with checksum of the input data and output file path and output file checksum) so that when we run the notebook again, we can check: did something change about the input data? No? Does the file exist? Yes? Does it have the output checksm? Yes? Then we don't need to redo that visualization and can move on to the next visualization.
> But Generally: for most things, it will be best if we just always regenerate them (unless they are very time expensive), so that we never run the issue of reusing old assumptions.

---

### REQ-A03 — GDPR: raw individual-level data in designated directory *(Phase 4 addition)*

Raw tabular data that maps named individuals to their property values or appearance counts (e.g., a CSV with one row per person listing occupation, party, appearances) must be written exclusively to the `data/50_analysis/persons/` subdirectory. This directory must:
- Be excluded from any public release or repository commit (add to `.gitignore`)
- Not be referenced from any output intended for external sharing without review

**What is NOT restricted:** visualizations showing named public figures are generally fine for public release. Talk show guests are overwhelmingly public figures; a "Top 20 guests" bar chart naming them does not trigger GDPR concerns. The restriction targets raw data dump files (tabular CSVs enumerating individuals), not aggregated visualizations.

**In practice:** the `persons/` directory holds CSV data tables; visualization files that happen to label individual people by name may live in the standard output tree.

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` P-07). The output directory tree already reserves a `persons/` path; this requirement formalizes the separation as a mandatory constraint rather than a convention.

---

## Property Classification

---

### REQ-P01 — Property type: Item

The following properties are classified as type **Item**. Item properties hold Wikidata entity references (QIDs) as values.

| Property | PID | Notes |
|---|---|---|
| occupation | P106 | Primary hierarchical property; basis for all class hierarchy analyses |
| country of citizenship | P27 | |
| sex or gender | P21 | |
| place of birth | P19 | |
| position held | P39 | |
| academic degree | P512 | |
| member of political party | P102 | |
| religion or worldview | P140 | |
| award received | P166 | |
| employer | P108 | |

**Verbatim basis:**
> * Item
>   * country of citizenship (P27)
>   * sex or gender (P21)
>   * place of birth (P19)
>   * position held (P39)
>   * academic degree (P512)
>   * member of political party (P102)
>   * religion or worldview (P140)
>   * award received (P166)

**Gap correction (Phase 2):** occupation (P106) was absent from the source but is the primary property for all class hierarchy analyses (REQ-H01–H07 use occupation as their primary example). Added as first entry.

**Gap addition (Phase 4):** employer (P108) identified from prior initiative inspection (`02_design_review.md` G-02) as a meaningful Item property absent from the original list. It is seeded with `temporal_variable=1` in `properties.csv` alongside P39 and P102 (see REQ-P07).

---

### REQ-P02 — Property type: Point in time

The following properties are classified as type **Point in time**.

| Property | PID |
|---|---|
| date of birth | P569 |

**Verbatim basis:**
> * Point in time
>   * date of birth (P569)

---

### REQ-P03 — Property type: Quantity

The following properties are classified as type **Quantity**.

| Property | PID |
|---|---|
| number of viewers/listeners | P5436 |
| social media followers | P8687 |

**Verbatim basis:**
> * Quanitiy
>   * number of viewers/listeners (P5436)
>   * social media followers (P8687)

---

### REQ-P04 — Property type: String

The following properties are classified as type **String**.

| Property | PID |
|---|---|
| Commons category | P373 |

**Verbatim basis:**
> * Sting
>   * Commons category (P373)

*Note: "Sting" in source is a typo for "String".*

---

### REQ-P05 — Derived property: Age

Age is a derived property, not a direct Wikidata claim. It is computed per appearance: `age = episode publication date (P577) year − guest date of birth (P569) year`.

**Verbatim basis:**
> There are also derived properties:
> * Age
>   * Calculated by subtracting the Point in time "date of birth (P569)" of a given guest from the "publication date (P577)" of the respective episode

---

### REQ-P06 — Derived property classification: Age → Quantity

Age, despite being derived, is classified as type **Quantity**.

**Verbatim basis:**
> Yet, even those can be classified as
> * Quanitiy
>   * Age (derived)

---

### REQ-P07 — Temporal properties: snapshot mode with documented caveat *(Phase 4 addition)*

Any Item property whose value may change over a person's lifetime is a temporally variable property. In principle, any property could be temporally variable — this must be declared per-property in the configuration file, not hardcoded in the analysis logic.

**Default behavior:** snapshot mode — use the current Wikidata value without regard to when the value was held. This is the simplest and most reproducible approach.

**Required caveats:** for any property marked as temporally variable, every visualization and table for that property must display a clearly visible note: *"Snapshot: reflects current Wikidata value, not necessarily the value at time of appearance."*

**Config flag:** `properties.csv` must include a `temporal_variable` column (0/1). When set to 1, the extraction layer (Layer 1b) may optionally use start/end date qualifiers to restrict values to those valid at episode date (`start ≤ episode_date ≤ end`, or end absent). Snapshot remains the default regardless; the flag enables the caveat display and unlocks temporal filtering as an opt-in.

**Seed values:** member of political party (P102), position held (P39), employer (P108) are the initial known temporally variable properties and must be seeded with `temporal_variable=1` in `properties.csv`. They are examples, not an exhaustive list.

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` G-05). The prior initiative did not resolve this; this requirement formalizes snapshot as the safe default with an upgrade path.

---

## Universal Analysis — All Property Types

---

### REQ-U01 — Universal carrier-based: average value count

For every property: compute the average number of values per carrier entity.

**Verbatim basis:**
> * average numbers of value,

---

### REQ-U02 — Universal carrier-based: empty count

For every property: count how many carrier entities had no value present (empty/missing).

**Verbatim basis:**
> * the times they were not present / empty

---

### REQ-U03 — Universal carrier-based: reference analysis

For every property: count how many entities have references on their values. Report the most common reference properties and their most common values. Report unique reference properties and their unique values.

**Verbatim basis:**
> * How many have references,
>   * Most common references properties
>     * Most common reference value
>   * Unique references properties
>     * Unique reference value

---

### REQ-U04 — Universal carrier-based: qualifier analysis

For every property: count how many entities have qualifiers on their values. Report the most common qualifier properties and their most common values.

**Verbatim basis:**
> * how many qualifiers
>   * Most common qualifer properties
>     * Most common qualifier value

---

### REQ-U05 — Universal carrier-based: top-X values

For every property: report the most common top-X values.

**Verbatim basis:**
> * most common top X,

---

### REQ-U06 — Universal episode appearance statistics table

For every property value: produce a statistics table with the following columns, computed over all episodes.

| Property value | min/episode | max/episode | mean over episodes | std dev | median | episode % without | total appearances | unique persons |
|---|---|---|---|---|---|---|---|---|

**Verbatim basis:**
> ##### Episode Appearance Based
> | Property value | min/episode | max/episode | mean over episodes | std dev | median | episode % without | total appearances | unique persons |
> |---|---|---|---|---|---|---|---|---|

---

### REQ-U07 — Universal visualizations: total appearances and unique individuals

For every property: produce a visualization of total appearances and a visualization of unique individuals.

**Verbatim basis:**
> ##### Visualizations needed
> * total appearances
> * unique individuals

---

### REQ-U08 — Universal: explicit "Unknown / no data" entry in every distribution *(Phase 2 addition)*

Every distribution table and its corresponding visualization must include an explicit entry for entities that had no value for the property being analyzed ("Unknown / no data"). This entry must:
- Always be present, regardless of count
- Use the gray color in all visualizations
- Be positioned after any "Other" grouping, always at the bottom of sorted charts — never sorted by count

**Gap correction (Phase 2):** REQ-V10 requires showing the empty count in context statistics, but without a mandatory Unknown row in the data, empty values become invisible in distributions. The Unknown entry makes the coverage of each property explicit.

---

### REQ-U09 — Universal: person_count and appearance_count are always paired *(Phase 2 addition)*

Every distribution table must include both:
- `person_count` — the number of unique individuals with this property value
- `appearance_count` — the total number of episode appearances by individuals with this value
- `pct_by_person` — `person_count` as a percentage of all persons in scope
- `pct_by_appearance` — `appearance_count` as a percentage of all appearances in scope

Visualizations derived from a distribution must clearly state which count they use.

**Gap correction (Phase 2):** The source specifies both "unique individuals" and "total appearances" as required outputs (REQ-U07), but the distribution table format (REQ-U05, U06) did not enforce the duality. This requirement makes the pairing systematic and mandatory.

---

### REQ-U10 — Universal: multi-value counting rule *(Phase 4 addition)*

When a property is multi-valued for a person (e.g. a guest holds multiple occupations simultaneously), each value is counted independently. A person with three occupations contributes 3 counts to the total appearance count for each of those occupations — they are not deduplicated to 1.

**The sole exception** is REQ-H05 (mid-level class aggregation): when aggregating sub-types under a designated mid-level class, each person is counted at most once per mid-level class regardless of how many matching sub-type values they hold. This exception applies only to mid-level aggregation and must not propagate to any other counting context.

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` G-03). The multi-value rule was implicit in the design but not stated, which risks inconsistent implementation.

---

## Classification-Specific Analysis — Item Properties

---

### REQ-I01 — Item: timeline visualizations

For every Item property: produce timeline visualizations in two variants — cumulative (how many appearances of each value over time) and unique (how many unique carriers of each value over time).

**Verbatim basis:**
> * Timelines
>   * Cumulative (how many X have had appearance)
>   * Unique (how many unique carriers have had appearance)

**Resolution (2026-05-01):**
- **X-axis granularity:** Adaptive. Fix a maximum number of data points (default: 50). Starting at per-episode granularity, progressively coarsen the time axis (monthly → bi-monthly → quarterly → ...) until the number of buckets is at or below the maximum.
- **Both timeline variants are required:**
  1. **Running total** — the value at time T = all appearances from the beginning of the dataset through T (monotonically non-decreasing)
  2. **Count per bucket** — the value at time T = appearances within the time bucket only (can increase or decrease)
- A combined visualization merging both variants is encouraged: filled area in the background for the running total, line+dot series in the foreground for the count per bucket. Beware of crowding.

---

### REQ-I02 — Item: sunburst visualizations

For every Item property: produce sunburst diagrams in two variants — cumulative and unique. Applied unconditionally to all Item properties; whether the P279 hierarchy for a given property yields a meaningful visualization is determined empirically by reviewing outputs, not by pre-filtering.

**Verbatim basis:**
> * Sunburst
>   * Cumulative (how many X have had appearance)
>   * Unique (how many unique carriers have had appearance)

**Resolution (2026-05-01):** All Item properties receive sunburst and Sankey visualizations unconditionally. Non-meaningful outputs are identified by flipping through a few images after generation, not by theorizing in advance.

---

### REQ-I03 — Item: Sankey diagram

For every Item property: produce two Sankey diagrams showing the class hierarchy flow. Applied unconditionally to all Item properties (see REQ-I02 resolution). Left nodes = top-level classes. Middle nodes = mid-level classes. Right nodes = first-level classes. Two variants, one per flow-width metric.

**Verbatim basis:**
> * Sankey

**Clarification (2026-05-01):** Flow direction confirmed: top-level class (left) → mid-level class (middle) → first-level class (right). Two variants: flow width = total appearances; flow width = unique persons.

---

### REQ-I04 — Item: within-property co-occurrence matrix

For every Item property: produce a co-occurrence matrix of the property's values with itself.

Two independent co-occurrence types are required:
- **Same-person (intra-person):** both values are held by the same person simultaneously (e.g. a person is both scientist and journalist)
- **Same-episode (inter-person, intra-episode):** both values appear among different guests of the same episode (e.g. a scientist and a journalist appear together)

For each type, produce three matrix variants:
1. **Full matrix** — all value combinations present in the data
2. **Top-10 × Top-10 by occurrence** — top-10 values by individual occurrence frequency
3. **Top-10 × Top-10 by co-occurrence** — top-10 value pairs by total co-occurrence count

**Verbatim basis:**
> Generally: create a Property x Property Co-occurence matrix for all item values
> * once for WITHIN the property (e.g. which occupation co-occurs with which other occupation)
>   * Top 10 x Top 10

**Resolution (2026-05-01):** Both same-person and same-episode co-occurrence types are required. The Top 10 × Top 10 from the source is one of three matrix variants; the full-matrix variant is also required.

---

### REQ-I05 — Item: cross-property co-occurrence matrix

For every Item property: produce a co-occurrence matrix against each other Item property.

Two independent co-occurrence types are required (see REQ-I04 for definitions):
- **Same-person (intra-person):** the same person holds both values simultaneously
- **Same-episode (inter-person, intra-episode):** both values appear among guests of the same episode

For each type, produce three matrix variants (same structure as REQ-I04):
1. **Full matrix** — all cross-property combinations present in the data
2. **Top-10 × Top-10 by occurrence** — top-10 values per property by occurrence frequency
3. **Top-10 × Top-10 by co-occurrence** — top-10 value pairs by total cross-property co-occurrence count

**Verbatim basis:**
> * once with each other item property (e.g. which occupation co-occurs with which gender)
>   * Top 10 x Top 10

---

### REQ-I06 — Item: most common value combinations within property

For every Item property: report the most common value combinations within that property and the total number of unique combinations.

**Verbatim basis:**
> * most common combinations,
>   * Number of Unique combinations

---

### REQ-I07 — Item: most common value combinations between properties

For every Item property: report the most common value combinations with each other Item property, one column per other property, and the total number of unique combinations per pairing.

**Verbatim basis:**
> * most common combinations between this property and a different other properties (one column for each such property)
>   * Number of Unique combinations

---

### REQ-I08 — Item: % Property A over Property B stacked bar chart

For every pair of Item properties (A, B): produce a stacked bar chart showing the distribution of Property B values within each top-10 value of Property A. Produced in two variants — cumulative (total appearances) and unique (unique persons).

**Verbatim basis:**
> * % Property A over Property B Stacked bar chart Of the top 10 from each
>   * Example: How many are
>   * Cumulative (how many X have had appearance)
>   * Unique (how many unique carriers have had appearance)

**Resolution (2026-05-01):**
- Always percentage-normalized (0–100%); REQ-V06 applies directly.
- Absolute count shown as a label inside each bar segment.
- The category axis label (e.g. each party or occupation bar) must include the total occurrence count for that category in parentheses, so the absolute scale is visible without hover.
- Sort categories descending by total occurrence (REQ-V05).

---

### REQ-I09 — Item: party colors

When a party affiliation property (P102, member of political party) is displayed in any visualization, use the party's well-known color.

**Verbatim basis:**
> Fundamentally:
> * Use party colours when party properties are displayed

---

## Classification-Specific Analysis — Point in Time Properties

---

### REQ-T01 — Point in time: birth year guest appearance distribution

For birth year (P569): produce a distribution showing guest appearance counts by birth year.

**Verbatim basis:**
> * Per Birth year:
>   * distribution of guest appereances of this birth year

---

### REQ-T02 — Point in time: per-birth-year age stacked bar chart

For birth year (P569): produce a stacked bar chart where each bar represents one birth year and its stacked segments show how often guests of that birth year appeared at each age. Bars sorted chronologically.

**Verbatim basis:**
> * per birth year, a stacked bar chart of how often they appeared on an episode at what age (so the 1950 bars could have age 1 (0) + age 2 (0) + .... + age 76 (13) as their total bars stacked on top of each other)
>   * sorted chronologically

---

## Classification-Specific Analysis — Quantity Properties

---

### REQ-Q01 — Quantity/Age: violin plot

For age (derived, REQ-P05/P06): produce a violin plot of the age distribution.

**Verbatim basis:**
> Particularly for age:
> * Violin plot

---

### REQ-Q02 — Quantity (non-age): binary presence

For all Quantity properties other than age: report only binary presence — whether or not a person had this property.

**Verbatim basis:**
> But other than age, generally just the binary presence "had this property"

---

## Classification-Specific Analysis — String Properties

---

### REQ-S01 — String: binary presence

For all String properties: report only binary presence — whether or not a person had this property.

**Verbatim basis:**
> Generally just the binary presence "had this property"

---

## Instance Analysis — Person Level

---

### REQ-PER01 — Person: top guests stacked bar chart by show

Produce a stacked bar chart of the most frequently appearing guests overall. Each bar represents one guest; bar segments show which broadcasting programs that guest appeared on, colored by show.

**Verbatim basis:**
> Most frequent guest stacked bar chart with segments per broadcasting program

---

### REQ-PER02 — Person: top guests per show

For each individual talk show: a visualization of the guests with the most appearances on that show specifically.

**Verbatim basis:**
> For each talk show, most frequent guest.

---

### REQ-PER03 — Person: individuals within category stacked bar chart

For the most frequent values of each Item property (e.g. top occupations, top parties): produce a stacked bar chart where each bar represents a category value and its segments are the individual persons contributing to that category. Top-N persons shown as named segments; remaining persons aggregated into "other".

**Verbatim basis:**
> Most frequent occupations stacked bar chart with the individuals that have them (e.g. politician bar chart with segments from Obama, Merz, Scholz, ... and "other")

**LanzMining equivalent:** "Gruppesprecher:innen — Wer sind die am häufigsten geladenen Personen, pro Gruppe?"

---

### REQ-PER04 — Person: individuals within occupation-combination stacked bar chart

For the most common multi-value occupation combinations: produce a stacked bar chart where each bar represents a combination and its segments are the individual persons holding that combination.

**Verbatim basis:**
> Most common occupation combinations and a stacked bar chart with the individuals that have them

---

### REQ-PER05 — Person: individuals sorted by birth year with occurrence stacked bar chart

Stacked bar chart where the x-axis is birth year and each bar's total height is the occurrence count for all persons born in that year. Bar segments are individual persons (top-N per year + "other").

**Verbatim basis:**
> Individuals sorted by birth year and their ocurences (stacked bar chart)

---

### REQ-PER06 — Person: encounter matrix (person × person co-occurrence)

For each scope: produce a person × person co-occurrence matrix showing how often each pair of persons appeared in the same episode. Apply to top-N guests by appearance count; N is configurable (default: persons with ≥10 appearances, or top-50, whichever is smaller).

**Verbatim basis:** *(not in original input — identified from LanzMining comparison 2026-05-01)*

**LanzMining equivalent:** "ÖRR-Talkshow Begegnungsmatrix — Wer begegnet wem in Talkshowformaten wie häufig?"

---

## Instance Analysis — Episode Level

---

### REQ-EPS01 — Episode: statistics and visualizations

For each scope: collect and visualize episode-level statistics. Required at minimum:
- Episode count per show (summary statistic + bar chart)
- Guest count per episode (distribution chart)
- Weekday distribution of episodes (bar chart)
- Episode broadcast frequency calendar — a calendar heatmap of which days/weeks had episodes, making the broadcast rhythm and breaks (summer holidays, etc.) visible

Additional statistics (episode duration, ...) if data is available in the pipeline.

**Verbatim basis:**
> Statistics (duration, weekday, number of guests, ...) and visualization thereof

**LanzMining equivalents:** "Sendefrequenz von ÖRR-Talkshows", "Sendungen im Datenzeitraum", "Sendefrequenz pro Format"

**Resolution (2026-05-01):** Episode duration is available for virtually every episode mined from ZDF Archiv / Fernsehserien.de / Wikidata. Treat duration as optional in the same way as any other property: include an "unknown" entry when absent, do not skip the visualization.

---

### REQ-EPS02 — Episode: per-show dashboard overview

For each individual talk show: produce a concise dashboard page combining the most meaningful statistics and visualizations for that show. Required components at minimum: party sunburst, guest gender distribution over time, occupation sunburst, episode broadcast frequency. Design constraint: not crowded; visually enhanced presentation of the most impactful statistics combined on one page.

**Verbatim basis:**
> Generally a dashboard overview of the most meaningful statistics and visualisations for this particular talk show (party sunburst with how often which political party occurred and if so, which politician; guest gender distribution over time; occupation sunburst for this particular show; etc.)
> Don't make it to crowded, combine visually enhanced presentation of meaningful and important statistics.

---

## Meta-Level Analysis

---

### REQ-META01 — Source coverage and data completeness visualization *(high priority)*

Produce a dedicated set of visualizations comparing what data was retrieved from each pipeline source (ZDF Archiv, Fernsehserien.de, Wikidata) for each episode. Must address:
1. **Per-episode source coverage:** which source(s) provided data for each individual episode — including multi-source combinations (e.g. guest metadata from ZDF Archiv only, or from both ZDF Archiv and Fernsehserien.de)
2. **Completeness gaps:** highlight episodes where one source had missing or incomplete data and another source filled the gap
3. **Scale:** the visualization must remain legible and informative across a large number of episodes (hundreds to thousands); adaptive layout required
4. **Cross-show and per-show** variants (REQ-G01 scope rule applies)

The visualization form is not fixed — a calendar heatmap, a matrix with source columns, a stacked timeline, or a combination may all be appropriate. The goal is to make data provenance and quality visible at a glance.

**Verbatim basis:**
> We should have a dedicated segment of visualizations just comparing what we were able to retrieve from those sources. Examples include, but are not limited to: Which Episodes were on which platforms? We need a clever visualization to show what individual episode was retrieved from which (combination of) source(s), and for a large number of episodes. We also need to be able to highlight where some episodes had missing data, e.g. we know that a segment of Fernsehserien.de was missing the guest metadata of some episodes which only ZDF Archiv could then provide. This analysis is very vital and fits into our meta-level analysis.

---

### REQ-META02 — Property coverage dashboard *(Phase 4 addition)*

Produce a property coverage dashboard showing, for each active property:
1. **% of guests with at least one value** — how complete is the Wikidata data for this property across all guests in scope
2. **Pipeline match rate** — what % of guest QIDs were successfully resolved during property extraction (i.e. entity was found in Wikidata and the property was queried)
3. **% with references** — data quality signal (from REQ-U03)

Present as a sortable summary table and a horizontal bar chart (one bar per property, sorted by coverage % descending). Apply scope rule (per show + combined).

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` M-03). The existing carrier stats (REQ-U01–U03) compute per-property coverage, but no requirement consolidated this into a dashboard that gives an at-a-glance view of data quality across all properties simultaneously.

---

## Class Hierarchy System

---

### REQ-H01 — First-level class: definition and auto-assignment

A **first-level class** is every class ever explicitly mentioned in an instance property relationship (e.g. `teacher (Q37226)` when `Bob → occupation (P106) → teacher (Q37226)`). First-level class assignment must be automatic.

**Verbatim basis:**
> * First-level class
>   * Definition: Every class that is ever explicitly mentioned in an instance property relationship.
>   * Example: Bob -> occupation (P106) -> teacher (Q37226)
>   * Requirement: Must be automatically assigned.

---

### REQ-H02 — Mid-level class: definition

A **mid-level class** is any class that has at least one first-level class as a direct or transitive subclass (via P279).

**Verbatim basis:**
> * Mid-level class
>   * Definition: A class that has at least one first-level subclass.
>   * Example: educator (Q974144), since
>     * Bob -> occupation (P106) -> teacher (Q37226)
>     * teacher (Q37226) ->  subclass of (P279) -> educator (Q974144)

---

### REQ-H03 — Top-level class: definition and auto-assignment

A **top-level class relative to class X** is any class in the hierarchy of X that has no superclass which is also a subclass of X (i.e. it is a root within that subtree). Top-level class assignment must be automatic for any given reference class X.

**Verbatim basis:**
> * Top-level class (relative to class X)
>   * Definition: A class that has no superclass which is also a subclass of X.
>   * Example: teacher (Q37226) relative to class educator (Q974144)
>   * Requirement: Must be automatically assigned in relation to class X.

**Resolution (2026-05-01):** Class X is always a designated mid-level class from REQ-H06 (e.g. scientist Q901, teacher Q37226, occupation Q12737077). Top-level computation is triggered on-demand for each mid-level class, and results are cached; once computed they are not recomputed on subsequent runs.

---

### REQ-H04 — Class hierarchy: loop detection and resolution

The P279 hierarchy may contain loops (cyclic subclass chains). The system must detect loops and designate one node in each loop as the effective top-level class for that cycle. The resolution must be rule-based, not case-by-case.

**Verbatim basis:**
> These hierarchies may contain loops:
> * scientist (Q901)
>    * subclass of (P279) -> researcher (Q1650915)
>      * subclass of (P279) -> academic professional (Q66666685)
>        * subclass of (P279) -> academic (Q3400985)
>          * subclass of (P279) -> scientist (Q901) (which is where we begun)
>
> We need to be able to handle these loops and simply define some point that shall now serve as the top-level class of this loop. For this particular example, I'd say its academic (Q3400985), but we need a rule-based approach to handle this.

**Resolution rule (clarified 2026-05-01):**
1. **Primary — manual designation:** consult `data/00_setup/loop_resolution.csv` for explicitly configured loop-to-top-level mappings (REQ-C01).
2. **Fallback — lowest QID number:** for loops not covered by the config file, designate the node with the numerically lowest Wikidata QID (Q-number) as top-level.

---

### REQ-H05 — Mid-level class aggregation with deduplication

Visualizations may aggregate sub-types into a named mid-level class (e.g. "teacher" aggregates biology teacher, physics teacher, etc.). When aggregating, each person must be counted at most once per mid-level class, regardless of how many sub-type values they hold.

**Verbatim basis:**
> These could also be within a general visualization: Aggregate all types of teachers into "teacher" so that we don't have 15 bars of size 10, but one of size 150.
> * Be wary of aggregating each human only once: If a person is both physics and biology teacher, the "teachers" count should still only increase by one.

---

### REQ-H06 — Designated mid-level class seed set

The following mid-level classes are designated for dedicated analysis and visualization:

| Class | QID |
|---|---|
| scientist | Q901 |
| teacher | Q37226 |
| musical occupation | Q135106813 |
| media profession | Q58635633 |
| occupation | Q12737077 |

**Verbatim basis:**
> * Example set of specified mid-level classes:
>   * scientist (Q901)
>   * teacher (Q37226)
>   * musical occupation (Q135106813)
>   * media profession (Q58635633)
>   * occupation (Q12737077)

---

### REQ-H07 — Dedicated mid-level class analyses and visualizations

For each designated mid-level class: produce dedicated analyses and visualizations. At minimum: a sunburst of sub-types (unique individuals by type variant + cumulative appearances variant) and a stacked bar chart of sub-types.

**Verbatim basis:**
> it is very vital to have a dedicated "occupation (Q12737077)", "teacher (Q37226)" or "researcher (Q1650915)" analysis and visualization. For example:
> * researcher Sunburst: What types of researchers were there?
>   * Once unique individuals by type
>   * Once once individuals
> * Researcher stacked barchart:

**Resolution (2026-05-01):** The incomplete "Researcher stacked barchart:" in the verbatim basis is covered by this requirement itself. The dedicated mid-level class analysis (sunburst + stacked bar) specified here is the intended output. No separate specification is needed.

---

## Visualization Principles

---

### REQ-V01 — Unique color per element within a visualization

Every distinct element (bar, line, segment, etc.) within a single visualization must have its own unique color. No two distinct elements may share a color if it can be avoided.

**Verbatim basis:**
> * Expected: Every bar/line/... that are on one visualization should have it's own unique color, where possible.

---

### REQ-V02 — Color consistency across diagrams

If an entity (e.g. "scientist (Q901)") appears in multiple diagrams, it must have the same color in all of them.

**Verbatim basis:**
> * These Colors should be consistent throughout diagrams. if "scientist (Q901)" is purple in one diagram, "scientist (Q901)" should be purple in another one as well

---

### REQ-V03 — Party colors: use well-known assignments

Political parties with established visual identities must use their canonical colors in all visualizations. Examples: CDU → Black, SPD → Red, Greens → Green, FDP → Yellow.

**Verbatim basis:**
> * For something like political parties, which have well-known colors (CDU Black, SPD red, Greens Green, FDP Yellow), we should always use this color.

---

### REQ-V04 — HTML/PDF: embed Wikidata links in labels (lowest priority)

In HTML and PDF outputs: embed hyperlinks to Wikidata in every label that refers to a Wikidata entity (rows, columns, persons, properties, occupations/roles, etc.).

**Priority:** Explicitly the lowest-priority requirement. Do not work on this until all other requirements are met.

**Verbatim basis:**
> We have the advantage that every Row/Column, every person, every Property, every Occupation / Role / ... - is further described on wikidata. To leverage this, we can embed the Links into the labels. This way, when someone has a question what "Sprecher" refers to, for example, they can click on it and go to the wikidata item on wikidata.
>
> This is excplicitly the lowest prio feature we work focus on.

---

### REQ-V05 — Bar charts: sort descending top to bottom

All bar charts must be sorted in descending order from top to bottom (largest bar at top).

**Verbatim basis:**
> * Always sort descending top to bottom

---

### REQ-V06 — Stacked bar charts: always start from 0%

Stacked bar charts must always begin at 0% on the left axis and extend to 100% on the right. Starting from any other anchor point (e.g. from the middle) is not permitted.

**Verbatim basis:**
> * stacked bar charts must always be starting from 0% leftmost and go to 100% rightmost. there is no binary assumption, no starting from the middle or anything. Stacked barchart always starts from x = 0, not from the middle or any other place.

---

### REQ-V07 — Always show show scope

Every visualization must indicate which shows contributed to it. If a single show: name it in the caption. If all shows combined: provide a clearly visible "all shows" label.

**Verbatim basis:**
> * Always show what shows were counted - either list the name in the caption, or for "all", provide a small label

---

### REQ-V08 — Post-generation quality check

After every visualization is generated, the output must be reviewed and improved. Mandatory checks: resolution, text overlap (rescale or reposition), unreadable text, requirement compliance.

**Verbatim basis:**
> * Once a visualization is done, check the output. There will often be plenty of room for improvement:
>   * Increase resolution
>   * Text overlapping, requiring rescaling or better positioning
>   * unreadable text
>   * requirements not met

---

### REQ-V09 — Bar label placement rules

Labels on bars must follow these placement rules:
- **Regular bar charts:** if the bar is ≥ 50% of the chart width, place label inside the bar; if < 50%, place label to the side.
- **Stacked bar charts:** prefer shortened labels or a legend. If a segment is too small for a label, omit the label from that segment entirely.

**Verbatim basis:**
> * On bars: When the bar is large enough, enter the label inside. When the bar is too small, add the label to the side
>   * For regular bar charts: simple, if its smaller than 50 %, add the label to the side. otherwise inside
>   * For stacked bar-charts: try to shorten the label or move it to a legend. if it's too small, just don't add the label to the bar itself anymore.

---

### REQ-V10 — Contextual statistics in every visualization

Every visualization must display: the count of total appearances and unique guests it covers, and the count of "empty" values (entities with no value for the visualized property). This context should appear in the title and/or as a short subtitle. Brief and informative.

**Verbatim basis:**
> * Every graphic should always show how many appearances or unique guests are counted for the respective graphic, and how many had "empty" as the value for said property. Generally, if possible: Every visualization should provide some statistics to contextualize what is currently shown, in the title and as a short subtitle / description. Few words, most important info.

---

### REQ-V11 — Crowding: group tail into "other"

When a visualization becomes too crowded, group all values that did not make the top-X cut into a single "other" category.

**Verbatim basis:**
> * When a visualization becomes to crowded, group the smaller percentages to "other". Everything that didn't make it to the Top X gets aggregated there.

---

### REQ-V12 — Export format: PDF and PNG mandatory *(Phase 2 addition)*

Every chart must be exported as both PDF (vector) and PNG (raster, minimum 300 DPI). HTML export is optional and not a substitute for PDF/PNG. Output paths follow the directory structure in `01_design.md`.

**Gap correction (Phase 2):** REQ-V08 referenced "resolution" without specifying a format or target. The existing `documentation/visualizations/visualization-principles.md` already mandates PDF + PNG at scale=3 (≈300 DPI); this requirement formalizes that mandate within this design.

---

### REQ-V13 — "Other" bar: fixed styling *(Phase 4 addition)*

The "other" aggregate bar (produced when REQ-V11 grouping is applied) must:
- Always appear at the bottom of the sorted chart (after all named values, before "Unknown")
- Use **light gray** (`#CCCCCC`) — never a palette color; visually distinct from "Unknown"
- Be labeled: **"Other (N items)"** where N is the count of distinct values collapsed into this bar

The "Unknown / no data" bar (REQ-U08) appears after "Other" if both are present: order from top to bottom is `[named values descending] → [Other #CCCCCC] → [Unknown #999999]`.

**Distinction:** "Other" means data exists but was grouped for legibility; "Unknown" means no data exists for this entity. Visually indistinguishable bars for two conceptually opposite categories would be misleading. Light gray for Other / medium gray for Unknown makes the distinction clear at a glance.

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` V-08). The existing REQ-V11 specifies the grouping rule but not the visual treatment or positioning of the resulting "other" bar.

---

### REQ-V14 — Color system: scalable palette with consistent QID assignment *(Phase 4 addition)*

The color system must satisfy three simultaneous goals, in priority order:
1. **Specifiable:** for entities with well-known colors (political parties from `party_colors.csv`), their canonical color is always used — these are seeded directly and do not consume palette slots
2. **Consistent:** once a QID is assigned a color, that color is used across all diagrams in the session — the registry is the single source of truth
3. **Distinguishable within a diagram:** within a single visualization, the visible values should ideally have visually distinct colors

**Palette size:** the base palette must contain 10–20 colorblind-safe colors. The Okabe-Ito 8 colors (from `visualization-principles.md`) are the seed set; additional colorblind-safe colors may be appended to reach the target range. Palette colors are assigned to non-seeded QIDs by frequency (most frequent QID across all shows gets the first palette color).

**Wrapping:** if a diagram contains more unique QIDs than palette entries, the palette wraps — two low-frequency QIDs may share a color. This is acceptable: REQ-V11 grouping (top-X + "Other") is the primary tool for reducing crowding; the color system does not override it with pattern fills or hatching.

**Seeded colors and palette collision:** when a seeded party color matches a palette entry hex value (e.g. CDU black matches Okabe-Ito black), that palette entry is skipped during dynamic assignment to avoid visual collision with a different entity.

**Gap addition (Phase 4):** identified from prior initiative inspection. Replaces an earlier draft that incorrectly proposed pattern-fill hatching as a fallback — that approach conflicts with the REQ-V11 grouping principle and with the colorblind-safe palette mandate.

---

### REQ-V15 — Geographic map for place of birth (P19) *(Phase 4 addition)*

For the place of birth property (P19): in addition to the universal bar chart and sunburst visualizations, produce a **choropleth map** as the primary visualization. Each country is colored by the count of guest appearances whose birth place falls within that country (or region, if sub-country granularity is available). Apply scope rule (per show + combined). Two variants: total appearances and unique persons.

Implementation notes:
- Resolve each `place_of_birth` QID to its country via P17 (country) if the place is a city or region
- Use a standard world map basemap (geopandas + naturalearth data)
- Color scale: sequential (light → dark); gray for countries with zero appearances; "Unknown" summary in legend

**Gap addition (Phase 4):** identified from prior initiative inspection (`02_design_review.md` V-15). Place of birth has an inherently geographic interpretation; a bar chart is a poor substitute for a map when the data is geospatial.
