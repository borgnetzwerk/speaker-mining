## Fixes
* Property Occurrences are calculated wrong. We regularly output more property occurrences than we have total guest occurrences. We cannot have 20.000 occurrences and 30.000 male + 10.000 female occurrences.
* Moderators are not strictly sorted out from guest analysis early on. Persons should be classified per episode per type, so that a guest_occurence_matrix.csv truly only counts individuals that occur as guest in that particular episode, and moderators etc. each have their own occurrences_matrix not part of the guest_analysis.
* Visualizations are not very dynamic yet:
	* We must deal with long labels, they currently distort the visualizations.
		* Certainly, the horizontal proportions of the plot should be dynamic to accommodate long labels where they occur.
		* Also, we should try to introduce line-breaks to exceedingly long labels, and dynamically allocate a bit more vertical space for the additional line of text.
	* We should also generate a second visualization in english. We already have the data fetched to do so, so we might as well show off that we can easily do this.
		* We must ensure that if we do so, every hardcoded word we use is in that language (e.g. en:"guest", de:"Gast" etc.)
	* Visualizations must be more descriptive:
		* Show the number of episodes in the Title / subtitle
		* Show the broadcasting programs used for this particular visualization.
			* Potentially combine "number of episodes" with "broadcasting programs" to show e.g. "Markus Lanz: 2200 | Caren Miosga: 400 | ... "
				* Configurable, we must experiment with both.
* Birth year analysis must be by birth YEAR, not birthday - otherwise, it is close to meaningless. barely any people will share exact birthdays, we are interested in generations, in years, not in days.
* string property analyses are primarily meaningful when done binary: What kind of people HAVE a wikipedia Commons category? it lies in the nature of these categories to be unique, so it doesn't matter much to analyse who shares the same, but what matters it: What kind of properties predict to have one at all?
* min per episode is not working, it currently always shows 1, but we know it to be 0 almost everywhere.
* data basis currently not stored to analysis folder - Any data that is used during analysis must be in the Analysis folder


## Propably already captured tasks:
* Ensure people have their correct fernsehserien.de IDs
* Generally: inspect how the distributions are of those jobs, inspect the most common groups (e.g. singer + songwriter)

### Meta Statistics
* Statistics on what types of properties we have (e.g. how many of the properties are item, how many string, ...)


Source specific analysis
Of our total episodes, how many did
* Wikidata have
* Fernsehserien.de have
* ZDF Archiv have


And how many of those were unique to only that platform? That only that one had?

How many of them were without guests? Without metadata?

How many of those were legitimate without guests? Like Markus Lanz Jahresrückblick

#### Loops
* Number of discovered loops
* Number of classes in the loops

### Visualization principles:
List of plot types and their general use cases
Violin plot (age distribution)
Centered stacked bar chart (Lilkert scala)

Have reference code for every plot type ready, with dummy data so we have one example per type. Apply all principles to these examples so they are an embodiment of "doing it right".
If there is nuance to a type, maybe two different ways to display something - just make subtypes and add principles and examples to them


### Stacked Bar charts
For property A: top values of property A ranked by occurrences (top to bottom)

Each Visualization always:
Per A two grouped bar charts
* stacked bar chart of property B unique guests
* stacked bar chart of property B appearances

The segments are always labeled


## Episode specific property visualization
Apply the same pipeline as for guest properties:
* Duration (quantity)
* publication date (point in time)
* number of guests (quantity)
* description (string)
* Einschaltquote (quantiy) (not yet implemented)
* topic (item) (not yet implemented)
* Transcript (string) (not yet implemented)


## Per property (and per property combination) analysis
* Inspect where the difference between unique and total is greatest, e.g. if there is a small group of individual carriers of an otherwise rare property that are invited over and over
* Analyse how certain subsets are dominated by individuals: inspect where some individual is over-representing their group: if one female scientist is invited 100 times, hit other female scientists are only invited 5 times, then the "105 total female occurrences" do not mean as much
* Inspect where the median of property ownership (count, how many do people usuall have) is 1, and inspect the ones that have more than one (e.g. multiple occupation's)
* Generally: try to identify "outliers"


## Look to the past
In our very first implementation, we had the issue of temporal properties not being correctly associated.
Now we do correctly identify if a claim is active during an episode.

But, because of that, we have:
* gained the ability to say "this was true during that time"

but lost the knowledge of
* what was true before
* or what was true after

We currently don't do the do "ehem." Analysis: we don't look back and say "who used to be a president", we currently just analyse the current state. This is much better than mislabeling individuals with all their prior qualities aggregated as if they were active right now.

So now that we have solved the first issue, we can do a second analysis of "analyse all the properties that they had before appearing", like an ehem. president being invited

Long-term, we should do this additional analysis. For now, it has low priority.

### Examples:
* What occupations did politicians have before becoming politicians?
* What party affiliations did people have before becoming guests of the show?
* What "ehem." properties are explicitly specified, e.g. in ZDF Archiv person descriptions.


## Investigate if applicable angle for analysis
* Poisson-distribution

## Color catalogue:
* Populate from "Wikidata color (P462)" and "official color (P6364)". Their values are always contain the color we are looking for. Particularly when "sRGB color hex triplet (P465)" is available, either directly or via qualifier: use P465.

Keep a statistic of what types of classes / instances have this specified.
We know it will be the case for many political parties and countries, but what other? And what political parties / countries don't have these specified?


## Per Person
* Also: count total number of claims per person


## Additional visualization types

### Scalar: scatter plot
Whenever we use a scalar (e.g. age, birth year, ...). Examples:
* Gender over birth year: plot birth years over X and Y axis is appereances of carriers of this gender for a given birth year.

Works for ordinal and continuous numerical variables

### Boxplot with stripplot
Works for ordinal and continuous numerical variables

### Violin plots
Works for ordinal and continuous numerical variables

### stacked area plot
Whenever a stacked bar chart is applicable, we can additionally do a stacked area plot - particularly when a temporal axis is at play.


### Sankey diagram of people that changed party affiliation / occupation
Moving from occupation .... to Party ..... to occupation ....

### Treemaps
Per show and once for all shows:
* Per Property:
	* one Treemap for their values.

### Radar chart
Per Show and once for all shows:
* per property:
	* One radar chart.
* and if possible, one radar chart that will aggregate all values of properties into on a single scale form 0% to 100%. Will be complicated for most, but maybe possible for something like "average age" or "percentage politician" or "percentage scientist" or "percentage male" or similar

Layer radar charts on top of each other. For now: always layer the show's individual radar chart over the average radar chart.

---

## For Documentation
Generally: The order we established is the universal behaviour we should expect and implement at every step of the analysis:
* List episodes (e.g. 5000)
    * create binary guests x episodes occurrence matrix (e.g. 6000 x 5000)
       * from this occurrence matrix: derive all other value x episode matrix per property. (e.g. 4x5000 for one property, 532 x 5000 for another, 28 x 5000 for a third, ...). Here, each cell reflects the number of guests with that property value were present: 0 if none, 1 if one unique person, 5 if five unique persons, up to the maximum number of guests that were present in that episode, if everyone happens to have that. This way, we can quickly calculate things like "how many episodes were without carrier of this particular value" just by looking at that value's row and count the zeors.

## Separation of roles still not clear and consistent

guest_frequency_pareto seems to still count moderators:
For example, "Frank Plasberg" is correctly captured as role "Moderation", but appears in the guest pareto analysis. 

Gert Scobel is wronglycclassified as the "top_guest" of the show scobel moderated by Gert Scobel.
ce_787877c615c1,Gert Scobel,Q1515337,372,1,scobel
ce_6cda164436e5,3sat,,83,2,scobel

Here we can also see that 3sat, the production company with role "Produktionsauftrag", is also listed here. This logic is still fundamentally broken.

We must clearly classify who is guest, and who is moderator, or anything else. Do this one time, reuse it constantly throughout analysis, never overrule it, and keep it consistent downstream. Everything must follow the same logic. Ideally completely separate them into separate files:
* guest_occurrence_matrix
* moderator_occurrence_matrix
* production_order_occurrence_matrix
or similar.

---

## General principle: Show everything we found

All analysis should end up in a visualization. If an analsis is made, a respective visualization should trigger - general rule of thumb: no csv should go without png. An example would be TASK-F04, it is currently not clear if stats such as "episode coverage, min/max/avg per episode" are ever visualized. These could either all be their own visualizations, be part of some greater dashboard of each show, or part of some per-property unfied dashboard. Generally: If we calculate a stat, we should use it. This is not a binding MUST, but a guideline: If we don't utilize a value, we risk it being forgotten about. Visualizations are  the main interface access readers have to our analysis.


## Interesting findings

### PRECISELY 19.000 appereances with gender

We seem to have PRECISELY 19.000 appereances with gender. This can be totally randomness, but also the sign of some hardcoded cutoff or similar. We should conduct a short investigation to identify if we may have accidentally hardcoded something that resulted in this, or if it is indeed just a coincidence.

Confirm if unique episodes are already only those that are part of our specified series, and if guests  are guests of those.
No other irrelevant members captured.

  all/occurrence_matrix.csv: 8294 persons × 4863 episodes

### Empty properties for highly relevant individuals.
"Die Welt" only has 110 appearances as employer, despite that one Robin Alexander being there 139 times. Robin Alexander was Deputy Editor-in-Chief for "Die Welt" from 2019 to 2025. But this was never documented on Wikidata.

For the most influential persons: which properties were empty for them

## On "unique" persons

Confirm how many had no Wikidata ID and keep them in a separate counter (outside of the visualization). Also for all statistics:
Three degrees of quality:
1: Reconciled with wiidata, so a person of whom we know the wikidata QID
2: a person that is only mentioned in wikidata and in no other source
3: a person that we could at least match between two non-wikidata sources (e.g. ZDF archive and Fernsehserien.de)
4: a person that is only stated on one source, and this source is not wikidata.

Only use stage 1 and 2 for visualizations.
In statistics: always separate the counts for all of them separately: only the category 1 guests are truly high quality, 2 and 3 are okay, but not great, and 4 is so low we can only carry it as a "we found it, but are unable to do much with it". Ideally, we end up with something like:
1: 97 % of our data
2: 1 % of our data
3: 2 % of our data
4: 0% of our data

### Interesting apparrent duplicates with different QIDs
Doktor phil und Doktor Philosophiae

Evangelisch-lutherische Kirche
Evangelisch-lutherische kirche

Evangelische Kirche

### On Visualizations
Regarding visualization texts:
We should stick to a language convention: in English, if we keep the property title as is, it will be mostly lowercase (with some exceptions). Then we should keep our words we add to this, like "distribution", lowercase as well.
In German, those properties will follow German capitalization rules, and will have plenty of capitalized words - so we should uphold this with text following German rules: "Verteilung"

Additionally to this: keep the "unknown" section separate from the main visualisation. It should not be distorted from the often times un proportionally larger bar.

Turn the Pareto bars into a stacked bar chart
Add percentage of total occurences to the bar labels of that show, as well as the total on top (so you can quicky see: robin Alexander has 40 appearances on Markus Lanz, accounting for a total of 3% of that shows appearances; and on top of the bar, Robin Alexander had 153 appearances, 1% of all recorded


## Structured Output folder documentation generation
The goal would be a set of README.md files that, when navigated, allow to quickly gain an overview over the most relevant data points.
During creation, it should be filled with the data from the analysis, and it should embed the visualizations into the markdown code, so that they are visually loaded: the result should be a folder that a reader can navigate on GitHub and inspect what we found, without ever needing to click on any file. Just folder navigation should be enough to learn and see everything important in the respective README.md files.


### GitIgnore tuning
we should also configure the .gitignore to allow those files to be gitted and discoverable via GitHub. Definition of Files to be included into the git:
* does NOT contain GDPR critical data specific to a person. This means that demographic overviews are generally fine, but by person profiles are not.
* does NOT have an unreasonably large file.
* does NOT have a direct siblingthat can do the same. E.g. we don't need to upload the HTML, PNG and PDF visualizations - pick one that is most suitable for GitHub, and only permit that one.

---

## Current state and lessons learned
* When creating stacked bar charts with labels, try to create horizontal stacked bar charts, where possible. The current Pareto visualization is barely readable as a vertical stacked bar chart with labels. Current issues: Text is rotated to the other labels, so you need to rotate your view to read whats inside. If the bars were horizontal, we would not have this issue.
  * Exceptions would be something like timelines, which we'd expect to be left to right.

* On Displaying "no data": On top, we currently display "n=... unique persons  - ... appereances - ... no data". This would be the perfect place to structure it something like this:
    ... guest appereances of ... unique persons
    no property data on ... guest appereances of ... unique persons (Tier 1 and Tier 2 entries that happen to not have claims for this particular property)
    no Wikidata entry on ... guest appereances of ... unique persons (Tier 3 and Tier 4 entries)
  * potentially, there is a more clever way to format this, but the general idea is: display what data we have

* On README generation: We also need one README per property.
  * Basic principle: Every folder in `data/50_analysis` needs its own README.

* Basic principle: 
  * Every analysis, visualization and README that is created for "ALL" should also be created per show.
  * Every analysis, visualization and README that is created per show should also be created for "ALL.
    * For example: All property analysis is currently done only for ALL, but must also be done for each show individually.

Generally: The current visualizations like Pareto or simple bar charts in general are very basic, and we should not spend much more time on this. Stacked bar charts, timelines, Sunburst, Treemap etc. are all much more interesting and still not implemented. Particularly the property x property and the property x person stacked bar charts will be very interesting. We should focus on those.

## Issue resurfaced
The wrong-episode-mapping critical issue seems to have resurfaced. We once again have a `data/50_analysis/couchwissen/occurrence_matrix.csv` filled with occurrences of guests that were never there. 
Same names, same issues as originally documented in `documentation/31_entitiy_disambiguation/2026-04-05_critical_issue/issue.md`.
