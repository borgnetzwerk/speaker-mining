## Clarifications (2026-05-01)

**QUESTION: REQ-I03 / TASK-B12 — Sankey diagram semantics**

The input specifies "Sankey" as a required visualization for Item properties, but does not define what the Sankey should represent. Specifically: what are the source nodes, target nodes, and flow quantity? For occupation/role data, a plausible interpretation is a flow from top-level class → mid-level class → first-level class (with flow width = person count or appearance count), but this is an assumption.
* Clarification: Correct.

Before TASK-B12 can be implemented, please clarify:
1. What do the left-side nodes represent?
* Clarification: top level classes
2. What do the right-side nodes represent?
3. What does the flow width represent (appearances or unique persons)?
* Clarification: both, one visualization for each
1. Should the Sankey show the class hierarchy, or something else entirely (e.g. flow between shows, flow between properties)?
* Clarification: Class hierarchy

---

**QUESTION: REQ-H04 / TASK-B04 — Loop resolution rule for P279 cycles**

The input acknowledges that P279 class hierarchies may contain loops and states that a rule-based approach is needed to designate one node in each cycle as the top-level class. The example "academic (Q3400985)" is given as the intended top-level for the scientist→researcher→academic→scientist cycle, but no governing rule is stated.

Candidate rules (non-exhaustive):
1. **Highest in-dataset prevalence:** the node in the loop that appears most often as a first-level class value in the data becomes top-level.
2. **Manual designation:** a configuration file maps known loop QIDs to their designated top-level node; the algorithm falls back to a default rule for unknown loops.
3. **Longest label / most generic:** a heuristic based on label breadth (e.g. "academic" is broader than "scientist").
4. **Lowest Wikidata QID number:** a stable, arbitrary tiebreaker.
* Clarification: this. manual designation possible: provide easy to modify CSV (or similar) config
  * Generally: For everything that may need human specification, relevant properties, etc: provide easy to config / append files. see `data/00_setup` for reference.

Which rule should be used? Can we adopt a manual designation for the known cases (scientist loop) and a fallback for unknowns?

---

## Fundamental rework 

The data aggregation and of the current implementation works fine, but we must fundamentally structure how we do analysis and visualization. 
1. All of the below must be converted into clear requirements. The verbatim basis for these Requirements must be preserved in the requirement description.
2. All of these Requirements must be used to structure an adequate redesign.

Use this to grasp a definition of "bare minimum" - what we seek to have on visualizations is extensive:
Baseline assumption:

Per show each and once total:
* Person-Episode occurence Matrix
  * One for all
  * One for the most X occuring individuals
  * as CSV as well as visualized. 

### Property classification
The currently known classifications of relevant properties are:
* Item
  * country of citizenship (P27)
  * sex or gender (P21)
  * place of birth (P19)
  * position held (P39)
  * academic degree (P512)
  * member of political party (P102)
  * religion or worldview (P140)
  * award received (P166)
* Point in time
  * date of birth (P569)
* Quanitiy
  * number of viewers/listeners (P5436)
  * social media followers (P8687)
* Sting
  * Commons category (P373)

These are First-level properties: They are explicitly mentioned as an instance property.

There are also derived properties:
* Age
  * Calculated by subtracting the Point in time "date of birth (P569)" of a given guest from the "publication date (P577)" of the respective episode 

Yet, even those can be classified as
* Quanitiy
  * Age (derived)

For every property, there are universal and classification specific rules 

#### Universal

##### Carrier based
* average numbers of value,
* the times they were not present / empty
* How many have references,
  * Most common references properties
    * Most common reference value
  * Unique references properties
    * Unique reference value
* how many qualifiers
  * Most common qualifer properties
    * Most common qualifier value
* most common top X,


##### Episode Appearance Based
| Property value | min/episode | max/episode | mean over episodes | std dev | median | episode % without | total appearances | unique persons |
|---|---|---|---|---|---|---|---|---|

##### Visualizations needed
* total appearances
* unique individuals

#### classification Specific Rules

##### Item

Examples include:
Occupation, Gender, Party affiliation 

* Timelines 
  * Cumulative (how many X have had appearance)
  * Unique (how many unique carriers have had appearance)
* Sunburst 
  * Cumulative (how many X have had appearance)
  * Unique (how many unique carriers have had appearance)
* Sankey 

Generally: create a Property x Property Co-occurence matrix for all item values
* once for WITHIN the property (e.g. which occupation co-occurs with which other occupation)
  * Top 10 x Top 10
* once with each other item property (e.g. which occupation co-occurs with which gender)
  * Top 10 x Top 10
* most common combinations,
  * Number of Unique combinations
* most common combinations between this property and a different other properties (one column for each such property)
  * Number of Unique combinations

* % Property A over Property B Stacked bar chart Of the top 10 from each
  * Example: How many are 
  * Cumulative (how many X have had appearance)
  * Unique (how many unique carriers have had appearance)


Fundamentally:
* Use party colours when party properties are displayed

##### Point in time
* Per Birth year:
  * distribution of guest appereances of this birth year
  * per birth year, a stacked bar chart of how often they appeared on an episode at what age (so the 1950 bars could have age 1 (0) + age 2 (0) + .... + age 76 (13) as their total bars stacked on top of each other)
    * sorted chronologically


##### Quanitiy
Particularly for age:
* Violin plot

But other than age, generally just the binary presence "had this property"

##### Sting

Generally just the binary presence "had this property"



### Class Hierarchy Terminology
* First-level class
  * Definition: Every class that is ever explicitly mentioned in an instance property relationship.
  * Example: Bob -> occupation (P106) -> teacher (Q37226)
  * Requirement: Must be automatically assigned.
* Mid-level class 
  * Definition: A class that has at least one first-level subclass.
  * Example: educator (Q974144), since 
    * Bob -> occupation (P106) -> teacher (Q37226)
    * teacher (Q37226) ->  subclass of (P279) -> educator (Q974144)
* Top-level class (relative to class X)
  * Definition: A class that has no superclass which is also a subclass of X. 
  * Example: teacher (Q37226) relative to class educator (Q974144)
  * Requirement: Must be automatically assigned in relation to class X.

For a class to be relevant for our analysis, it must be one of the above. A class can fulfill multiple levels: teacher (Q37226) is certainly first-level, may be specified as mid-level and can be top-level relative to some other class X (e.g. educator (Q974144)).

These hierarchies may contain loops:
* scientist (Q901)
   * subclass of (P279) -> researcher (Q1650915)
     * subclass of (P279) -> academic professional (Q66666685)
       * subclass of (P279) -> academic (Q3400985)
         * subclass of (P279) -> scientist (Q901) (which is where we begun)

We need to be able to handle these loops and simply define some point that shall now serve as the top-level class of this loop. For this particular example, I'd say its academic (Q3400985), but we need a rule-based approach to handle this.

All of the above are subclasses of the core class "role (Q214339)". Yet, it is very vital to have a dedicated "occupation (Q12737077)", "teacher (Q37226)" or "researcher (Q1650915)" analysis and visualization. For example:
* researcher Sunburst: What types of researchers were there?
  * Once unique individuals by type
  * Once once individuals
* Researcher stacked barchart:

These could also be within a general visualization: Aggregate all types of teachers into "teacher" so that we don't have 15 bars of size 10, but one of size 150. 
* Be wary of aggregating each human only once: If a person is both physics and biology teacher, the "teachers" count should still only increase by one.

* Example set of specified mid-level classes:
  * scientist (Q901)
  * teacher (Q37226)
  * musical occupation (Q135106813)
  * media profession (Q58635633)
  * occupation (Q12737077)

## Visualization principles
We do already have an early version of `documentation/visualizations/visualization-principles.md`. However, it seems incomplete and sometimes confusing.

All the below is authoritative:

### Colors
* Current Issue: Sometimes, there were 5 entries, 2 of them had distinct colors and 3 others were just "grey"
* Expected: Every bar/line/... that are on one visualization should have it's own unique color, where possible.
* These Colors should be consistent throughout diagrams. if "scientist (Q901)" is purple in one diagram, "scientist (Q901)" should be purple in another one as well
  * For something like political parties, which have well-known colors (CDU Black, SPD red, Greens Green, FDP Yellow), we should always use this color.


### HTML / PDF
We have the advantage that every Row/Column, every person, every Property, every Occupation / Role / ... - is further described on wikidata. To leverage this, we can embed the Links into the labels. This way, when someone has a question what "Sprecher" refers to, for example, they can click on it and go to the wikidata item on wikidata.

This is excplicitly the lowest prio feature we work focus on.

### Bar Charts
* Always sort descending top to bottom


## Stray notes
* stacked bar charts must always be starting from 0% leftmost and go to 100% rightmost. there is no binary assumption, no starting from the middle or anything. Stacked barchart always starts from x = 0, not from the middle or any other place.
* Always show what shows were counted - either list the name in the caption, or for "all", provide a small label
* Once a visualization is done, check the output. There will often be plenty of room for improvement:
  * Increase resolution
  * Text overlapping, requiring rescaling or better positioning
  * unreadable text
  * requirements not met
* On bars: When the bar is large enough, enter the label inside. When the bar is too small, add the label to the side 
  * For regular bar charts: simple, if its smaller than 50 %, add the label to the side. otherwise inside
  * For stacked bar-charts: try to shorten the label or move it to a legend. if it's too small, just don't add the label to the bar itself anymore.
* Every graphic should always show how many appearances or unique guests are counted for the respective graphic, and how many had "empty" as the value for said property. Generally, if possible: Every visualization should provide some statistics to contextualize what is currently shown, in the title and as a short subtitle / description. Few words, most important info.
* When a visualization becomes to crowded, group the smaller percentages to "other". Everything that didn't make it to the Top X gets aggregated there.

---

## Phase 2 gap analysis — Q&A (2026-05-01)

*Phase 2 gap analysis questions — raised 2026-05-01 from internal inspection of `00_requirements.md` alone.*

---

**QUESTION: REQ-I01 — Timeline x-axis granularity**

REQ-I01 requires timeline visualizations (cumulative + unique) for every Item property, but does not specify the x-axis granularity. Options:
- Per individual episode (too fine-grained for multi-year spans)
- Per month
  * **Clarification:** Possibly this.
- Per year (most likely intended)
  * **Clarification:** Generally this.
- Per decade (useful for long-running shows)

Which granularity is required? Should it be configurable, or fixed?
  * **Clarification:** What we should do is set a fixed number of maximum datapoints. For example: if this number were 50, and we have a show with 45 episodes, we can do one datapoint for every episode. If we have 2000 episodes, then we'll have to try if doing it by month brings the number down below 50. no? by two months. still no? 3 months. - and so on. 

---

**QUESTION: REQ-I01 — Definition of "cumulative" in timeline context**

REQ-I01 specifies: "Cumulative (how many X have had appearance)". The word "cumulative" is ambiguous in this context:
- **Running total:** the bar/line at year Y shows all appearances from the beginning of the dataset through year Y (ever-increasing)
- **Count per bucket:** the bar/line at year Y shows only the appearances that occurred in year Y (can go up or down)

The second interpretation is more commonly called "frequency over time", not "cumulative." The first would produce a monotonically non-decreasing line. Which is intended?
  * **Clarification:** Both types here are generally required - not sure which one was ment by "commulative" and which one by the respective other, but generally, we need both: One line that keeps increasing, and one that keeps going up and down
    * Possibly, there will also be suitable visualizations that unify both in one: A filling area in the background doing the running total (maybe even for multiple, like stacked bar charts, but as area), and lines with dots in the foreground depicting the count per bucket. 
      * Be careful, this could get crowded quickly.

---

**QUESTION: REQ-I04 / REQ-I05 — Co-occurrence definition: same person or same episode?**

REQ-I04 says "which occupation co-occurs with which other occupation" — but "co-occurs" is ambiguous:
- **Same person:** person X has both occupation A and occupation B simultaneously (intra-person co-occurrence)
- **Same episode:** occupation A and occupation B both appear among guests of the same episode (inter-person, intra-episode co-occurrence)

These are fundamentally different computations and answer different questions:
- Same-person tells us about combined roles (scientist-journalist, politician-author)
  * **Clarification:** Yes, we are very interested in this!
- Same-episode tells us about booking patterns (which types of guests appear together)
  * **Clarification:** I had not thought about this, but yes, this is also very much interesting - this is exactly what we were looking for with Phase 2, great spotting! This will be very interesting also for party affiliations (when party X is invited, what other person is invited), or even for combinations (if a young female actor is invited, what other combination is also often invited) or similar

Which is intended? Or should both be computed?
  * **Clarification:** Was not intended - good clarification - both should be computed and visualized. Great work!

---

**QUESTION: REQ-I08 — Stacked bar chart: percentage-normalized or absolute count?**

REQ-I08 is titled "% Property A over Property B" which implies percentage-normalized output (each bar sums to 100%). But the requirement also specifies "Cumulative (how many X have had appearance)" and "Unique (how many unique carriers)" which sound like absolute counts.

- If percentage-normalized: REQ-V06 (0% to 100%) applies directly. Each bar shows the relative composition.
  * **Clarification:** This. We can still show the absolute as a label within this bar.
- If absolute count: bars have different heights, REQ-V06 does not apply. The chart shows volume, not proportion.
  * **Clarification:** No, this rarely has any useful application. Unless we find a good usecase, non-normalized stacked bar charts are usually not that interesting. Maybe for "given occurences of a party, which individual person having the guest appereance contributes the most to the appearance count", but even then, we could still have it as normalized. The only difference it would make is comparing between parties, and there we can just keep the total as a label.
  * **Clarification:** Also as a general rule: We already established that we sort descending by total occurences. Also add this information to the respective axis label so one can see how many occurences a given party/occupation/gender/... had in total as well.

Both are useful but serve different purposes. Which is required? Or both?

---

**QUESTION: REQ-H03 — What is class X in "top-level class relative to X"?**

REQ-H03 defines top-level class as "relative to class X" — but X is never specified in the requirements. The requirement says this must be automatically computed "in relation to class X", but which class(es) serve as X?

Options:
- X is always one of the designated mid-level classes from REQ-H06 (scientist, teacher, occupation, etc.)
  * **Clarification:** yes.
- X can be any class, and top-level is computed on-demand for any given X
  * **Clarification:** Technically yes, but two issues: one, if it is computed on demand, we should store it, so we don't recompute it ever again. Second, We only have the demand when we need it, and we only need it for specified classes (currently labeled "mid-level classes", renaming to a more suitable name pending)
- X is always a fixed root class (e.g. role Q214339)
  * **Clarification:** no.

This affects how the hierarchy computation in TASK-B04 is structured.

---

**QUESTION: REQ-I02 / REQ-I03 — Which Item properties have meaningful P279 class hierarchies?**

REQ-I02 (sunburst) and REQ-I03 (Sankey) apply to Item properties with a meaningful P279 class hierarchy. But not all Item properties in REQ-P01 have P279 hierarchies in the way occupation (P106) does:

| Property | Has P279 hierarchy? |
|---|---|
| occupation (P106) | Yes — rich hierarchy (teacher → educator → ...) |
  * **Clarification:** Exactly, this is the one we're most interested in
| country of citizenship (P27) | Possibly — countries are subclasses of geographic entities, but not meaningful for analysis |
  * **Clarification:** could be - grouping by geography could be interesting, seing who comes from europe, from within that - could be
| sex or gender (P21) | Unlikely — gender values are not organized in a P279 hierarchy |
  * **Clarification:** if that's the case, that's fine. We assume a standardized shape, and if that happens to not be the case and the analysis / visualization we conducted was not meaningful, that is fine. What we want is to reduce the overall amount of analysis / visualizations specified, if we over-procude some non-meaningful ones along the way, that is fine.
    * We should also begin to specifiy design principles such as this. They are not requirements, but they are principles / philosophies that may give context to what we want and don't want to do
| place of birth (P19) | Possibly — geographic hierarchy (city → region → country), but may not be in Wikidata P279 |
  * **Clarification:** exactly, see above.
| position held (P39) | Possibly — some positions have P279 relationships |
  * **Clarification:** yes, important
| academic degree (P512) | Possibly — degree levels may have P279 relationships |
  * **Clarification:** yes.
| member of political party (P102) | Unlikely for party values, but party families exist |
  * **Clarification:** unlikely meaningful, but maybe - we'll see
| religion or worldview (P140) | Possibly — religious denominations may have P279 hierarchies |
  * **Clarification:** we'll see
| award received (P166) | Possibly — award categories may have P279 relationships |
  * **Clarification:** yes, will be interesting

Which properties should have sunburst/Sankey applied? Only occupation, or others as well? Or should the system try all and only produce the visualization when a meaningful hierarchy is found?
  * **Clarification:** All. We don't filter first, we just do and see then. That's the point of this restructuring. Adding a new property means all visualization that can be created for its type will be created. If they carry meaning can then be decided by flipping through a few images, not by theorizing.

---

**QUESTION: REQ-H07 — "Researcher stacked barchart:" — what does it show?**

The verbatim basis for REQ-H07 includes:

> * Researcher stacked barchart:

The sentence ends with a colon and no further content. The specification for what this stacked bar chart should show is incomplete.

Possible interpretations:
1. Sub-types of researcher stacked over time (how the mix of researcher types changed year by year)
2. Sub-types of researcher stacked as a single bar (a single bar showing composition by sub-type)
3. Researchers stacked by another property (e.g. gender breakdown of researcher sub-types)

What should the stacked bar chart of a mid-level class show?
  * **Clarification:** This is currently captured by our "mid-level class visualizations" and can be ignored. Intended was propably a stacked barchart / sunburst / hierarchy / ... similar visualization of researchers. We have that covered via mid-level classes.



##  Properties
 * **Clarification:** The property list in 00_requirements.md is the minimum list. There needs to be a configurable file where these are stored as an initial set, and where simply by entering a "1" in an by-default empty column, this property should be loaded as well. It should 

---

## New Input (2026-05-01)

*Processed 2026-05-01 — see requirements for resolved forms.*

## Implementation Specification
Remember our coding-principles: Notebooks orchestrate, python modules contain most of the code, and config files contain user-specified input.

For this phase, we don't need a very deep Event-sourced infrastructure, but we can still make some use of it:
Events we can use:
* Visualization created (with checksum of the input data and output file path and output file checksum) so that when we run the notebook again, we can check: did something change about the input data? No? Does the file exist? Yes? Does it have the output checksm? Yes? Then we don't need to redo that visualization and can move on to the next visualization.

Additional events may make sense, currently unclear which. Some options:
* Loop identified with all members of a loop
* Loop resolved with a top-level qid specified
* Config changed, when the input config changed
* Input data changed (with checksum of input data), so we know when we got new episodes/persons/... 

But Generally: for most things, it will be best if we just always regenerate them (unless they are very time expensive), so that we never run the issue of reusing old assumptions.
Aside from visualization checksum timesaving, it is unlikely that we will have deep use for eventsourcing in this phase


## Don't forget Instance Analysis and Visualizations
Currently, we largely focus on properties and their visualizations. What we should also focus on is the individuals:
* A set of plenty different visualizations for persons,
* A set for episodes of a specific talk show 

Person examples (please extend)
* Most frequent guest stacked bar chart with segments per broadcasting program
* For each talk show, most frequent guest.
* Most frequent occupations stacked bar chart with the individuals that have them (e.g. politician bar chart with segments from Obama, Merz, Scholz, ... and "other")
* Most common occupation combinations and a stacked bar chart with the individuals that have them
* Individuals sorted by birth year and their ocurences (stacked bar chart)
* (To be extended)

Episode
* Statistics (duration, weekday, number of guests, ...) and visualization thereof
* Generally a dashboard overview of the most meaningful statistics and visualisations for this particular talk show (party sunburst with how often which political party occurred and if so, which politician; guest gender distribution over time; occupation sunburst for this particular show; etc.)
Don't make it to crowded, combine visually enhanced presentation of meaningful and important statistics.

## Learn from existing analysis / visualization and ensure we have at least all visualizations that prior work had
Compare arrrrrmins set of visualizations `data/01_input/arrrrrmin/Website/LanzMining.html` against the currently known set of analysis visualizations. Inspect which ones we have and insert the ones we are missing into our required catalogue of visualizations

---

## Episode duration Q&A (2026-05-01)

**QUESTION: REQ-EPS01 — Episode duration data availability**

REQ-EPS01 lists "duration" as one of the episode statistics to visualize (verbatim: "Statistics (duration, weekday, number of guests, ...)"). Weekday and guest count can be derived from the existing episode data. However, episode duration (runtime in minutes) is not obviously present in the current data structures.

Is episode duration (runtime) available in the current pipeline data? If so, which field/source provides it? If not, should it be:
- Deferred until a scraping source is added
- Dropped from REQ-EPS01 entirely
- Or marked as optional (included if data present, skipped if absent)?
  * **Clarification:** We have all this data on virtually every episode, it should be available. This can remain optional (and then keep an "unknown" just as with everything else), but generally, for every episode we mined from ZDF Archiv / Fernsehserien.de / Wikidata, we should have this information.
    * **Clarification:** On that note: Very good point on ZDF Archiv / Fernsehserien.de / Wikidata: We should have a dedicated segment of visualizations just comparing what we were able to retrieve from those sources. Examples include, but are not limited to: Which Episodes were on which platforms? We need a clever visualization to show what individual episode was retrieved from which (combination of) source(s), and for a large number of episodes. We also need to be able to highlight where some episodes had missing data, e.g. we know that a segment of Fernsehserien.de was missing the guest metadata of some episodes which only ZDF Archiv could then provide. This analysis is very vital and fits into our meta-level analysis.
