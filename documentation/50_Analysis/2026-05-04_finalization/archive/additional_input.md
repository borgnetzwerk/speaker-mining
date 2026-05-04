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
