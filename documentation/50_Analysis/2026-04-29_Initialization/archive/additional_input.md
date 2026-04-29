> **ARCHIVED 2026-04-29 (batch 2)** — Processed into TASK-A02 through TASK-A05 in `open-tasks.md`; §2.1 update in `03_design_spec.md`. See below for verbatim content.

---

## Wrongfully deferred tasks
Many (or: at least one) tasks were wrongfully deferred:
* TODO-025 contained plenty of visualizations that we care about - yes, they used to be only for wikidata, but this is 99% identical what we are doing here now. 
  * The description even references the 5_1 visualization:
    * - Summary: `21_wikidata_vizualization.ipynb` contains visualizations not yet represented in `51_visualization.ipynb`. Five specific improvements are outstanding: (1) fix QID labels in Cell 12 of candidate generation, (2) preserve directionality for non-primary core classes in hierarchy view, (3) add Sunburst diagram per core class + combined with 5% cutoff, (4) add Sankey diagram with same rules, (5) export all diagrams as PNG + PDF.
    - Evidence: `ToDo/archive/additional_input.md` (Ingest Wikidata visualization section), `speakermining/src/process/notebooks/21_wikidata_vizualization.ipynb`.
    - Definition of done:
      1. QID-label bug investigated in `21_candidate_generation_wikidata.ipynb` Cell 12 and fixed upstream; verified that `21_wikidata_vizualization.ipynb` no longer shows QID-only labels.
      2. Hierarchy view correctly places all core classes at appropriate positions (not just appended rightmost).
      3. Sunburst diagrams exist: one per core class (exhaustive) and one combined (5% "other" cutoff for subclasses; innermost ring = core classes only).
      4. Sankey diagrams exist with the same scope rules as sunburst.
      5. All diagrams are written as PNG + PDF to `data/output/visualization`.
  * The `21_wikidata_vizualization.ipynb` was an intermediate visualization step that tried to get some insights BEFORE we actually get to 51 - it was our stating ground, our learning set. Everything we learned there and set out as todos are exactly for this moment, exactly for this Phase. They are an early flight test.
  * Examples:
    * We need Sunburst diagrams of occupations, one total and one per talk show.
    * We need Hierarchy views of occupations and roles
* TODO-032 | Fix page rank visualization
  * We need exactly this! We need a fixed page rank node visualization for all instances! One more for all classes, one more for both in one.

Those tasks should not be deferred - they are made exactly to test early on what we need for right now.

## Additional Analysis/Visualization types
Additional notes for analysis angles:
* Which values of property A contribute most to the over-presence of certain value from property B
  * Example: 90 % of all RANDOM_PARTY politician are journalists. 80 % of the guests are journalists. 85 % of the invited politicians are from RANDOM_PARTY. If we were to remove the RANDOM_PARTY politicians from the guest list, the journalists percentage would drop to 6%. In general, if we were to drop politicians from the guest list, journalists would drop to 5 %. Or similar: Search for subsets that result in changes if excluded: A single party affilication/occupation/person/... distorting a statistic.
    * Analyse how certain subsets are dominated by individuals: inspect where some individual is over-representing their group: if one female scientist is invited 100 times, yet other female scientists are only invited 5 times, then the "105 total female occurrences" do not mean as much
* Which guests are present in other shows, and which just in one? Which are overly present in one show, but rarely in others? Who are balanced across all shows?
* Which guests are (all terminology temporary, surely there are better terms like "popularity window" or something)
  * "Shooting start", being invited plenty of times in quick succession, but rarely before/after
  * "evergreen", being invited often over a long period of time

## Structuring
Make property value tables:

Guest appearances of certain occupation:
| Occupation | min/episode | max/episode | mean over episodes | standard deviation | median | episode % without appearance | total | unique |
|------|--------|---------|---------|---------|---------|---------|---------|
| Scientist | ... ... .....
| Journalist | ... ... .....


The pattern should be transferable to any other property:

Guest appearances of certain age:
| Occupation | min/episode | max/episode | mean over episodes | standard deviation | median | episode % without appearance | total | unique |
|------|--------|---------|---------|---------|---------|---------|---------|
| 0 | ... ... .....
| 1 | ... ... .....
| 2 | ... ... .....
| 3 | ... ... .....



I am not 100 % sure on the terminology yet, I think we should be able to formulate the headline so we don't need the "per episode" info in each cell or similar. 

### Interesitng aspects:
* Then we can Inspect where the difference between unique and total is greatest
* Inspect how many episodes exist without women, how many episodes are without men

## Additional notes
* Inspect where the median of property ownership (count, how many do people usuall have) is 1, and inspect the ones that have more than one (e.g. multiple occupations)
  * Generally: inspect how the distributions are of those occupations, inspect the most common groups (e.g. singer + songwriter)
  * Related: Predictive analysis of properties to other properties

---

> **ARCHIVED 2026-04-29 (batch 1)** — Processed into `open-tasks.md` (Analysis folder). See below for verbatim content.

---

## Missing
What currently seems to be missing is a discussion on this section:

> For the analysis, we will define a large set of analysis angles. These explicitly mentioned angles can be extended and  combined:
> If we explicitly mention:
> * Gender distribution of talk show guests in general 
> * Development of the Age distribution of guests of a specific podcast
> 
> Then we can add something like
> * Occupation distribution of talk show guests
> 
> But also:
> * Development of the gender distribution of a specific talk show over time
> 
> Ultimately, we will have a wide variety of parameters and analysis angles. Very likely, there will be a good way to structure this. Some ideas:
> 
> A two-dimensional axis where every row is a property (or group of properties) and every column is an analysis/visualization type. The up- and Downside of this approach is simplicity, we compress a lot of information to a simple, easily extendable and modifiable table, but we will also struggle to capture information with more than two dimensions - what about a analysis that plots the age distribution of a specific talk show against the party affiliation of guests in this age range in general, as well as the party affiliation of these guests in particular. 
> * All of this could be encoded in the column definition, in a formulaic schema:
> "Visualize property X development of talk show A over time, while plotting Y against talk shows in general and comparing this to the Y distribution of talk show A." While this may work, this is also not very easy to digest.
> * Maybe each analysis/visualization type has its own table, defining it's own columns, and when we want to add new combinations, we just add them as rows. If we need a new analysis/visualization type, we just add it and it's table.

The meta-level structure. We need a document discussing and finding the right solution to a) capture, b) document and c) scale this properly. Our current combinations and examples are plenty, but they are stray and incomplete.
