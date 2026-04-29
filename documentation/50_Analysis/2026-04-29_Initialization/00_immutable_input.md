
# Analysis

## Basic Principles
For the analysis, we will define a large set of analysis angles. These explicitly mentioned angles can be extended and  combined:
If we explicitly mention:
* Gender distribution of talk show guests in general 
* Development of the Age distribution of guests of a specific podcast

Then we can add something like
* Occupation distribution of talk show guests

But also:
* Development of the gender distribution of a specific talk show over time

Ultimately, we will have a wide variety of parameters and analysis angles. Very likely, there will be a good way to structure this. Some ideas:

A two-dimensional axis where every row is a property (or group of properties) and every column is an analysis/visualization type. The up- and Downside of this approach is simplicity, we compress a lot of information to a simple, easily extendable and modifiable table, but we will also struggle to capture information with more than two dimensions - what about a analysis that plots the age distribution of a specific talk show against the party affiliation of guests in this age range in general, as well as the party affiliation of these guests in particular. 
* All of this could be encoded in the column definition, in a formulaic schema:
"Visualize property X development of talk show A over time, while plotting Y against talk shows in general and comparing this to the Y distribution of talk show A." While this may work, this is also not very easy to digest.
* Maybe each analysis/visualization type has its own table, defining it's own columns, and when we want to add new combinations, we just add them as rows. If we need a new analysis/visualization type, we just add it and it's table.


We must sort and cluster instances and classes by category, e.g. the relevancy they were granted. For example:
For person instances, make one dedicated group for "guests". Those are the people that had the "Gast" tag in fernsehserien.de, that were object of a "guest" triple of a relevant episode in wikidata, that had the guest identification applied during PDF mining.

This way, we can truly analyse by category, not just by class association:
What we're most interested in are guests. We must be able to differentiate them from topic mentioned people, from Moderators, from relatives being mentioned in descriptions, etc.

We must also be able to classify by broadcasting program as well, so we can for example identify of the guest distribution is different for different shows

What remains very important is:
We must be able to do all of this at the same time. We do not sort by one metric once, but we must have manifold filterable catalogue of information that we can mix and match, depending on what analysis we want to make. Some examples to demonstrate, not necessarily to later include, just to understand the point:
* Gender distribution of certain occupations over certain time frame for a selected subset of broadcasting programs
* Role distribution over the years from 1950 to 2025, reduced to the overall most appearing 20 roles in that time
* Role distribution over the years from 1950 to 2025, reduced to the overall most appearing 20 top level role superclasses in that time, where a top level superclass is a class that may have other role subclasses, but must not be a subclass to another role subclasses (e.g. "scientist", aggregating all the different sub-professions of scientists)



General note: No terminology here is final. If we find better words, better structures to describe any of the above or below, we should do so. Precision and disambiguation is key.
Also: whenever possible, add the wikidata QIDs and PIDs. This will be particularly helpful for (Core) class identifiers and property identifiers.

### Building Blocks

#### Broadcasting Program
Aka "Talk Show" or "Podcast".
Fundamentally: We seek to analyze these shows, these broadcasting programs. All of our relevant core broadcasting_programs are defined in the Input folder. We are both interested in statistics across all broadcasting programs, as well as statistics for any one specific broadcasting program. Fundamentally, these are the two modes any analysis will operate under: 
* Some analysis X for all broadcasting programs
* Some analysis X for specific broadcasting program A

#### Seasons
Seasons are almost irrelevant - they are very noisy and just an intermediate to aggregate and structure episodes.

#### Episode
Episodes are our fundamental knowledge clusters. Some properties:
* They belong to a broadcasting program, meaning they are relevant whenever that specific broadcasting program or all relevant broadcasting programs are analyzed. This only applies for all episodes that actually belong to one of our setup-specified broadcasting programs. There may be episodes in our dataset that are part of some other, not relevant broadcasting program - those must be excluded from all analysis.
* They have plenty of metadata, most importantly their guests (below) and date. The date may be "outsourced" to a publication container, but generally, we can assume the earliest date of any of the episode's publication to be that episodes "release date", or similar. We will need this for plenty of temporal analysis: How was the release schedule of talk show A in Year 2021? How has the occupation distribution of Talk show B changed over time? etc.


#### Guests
Guests (or "Persons" or "Humans"). THere are probably around 5000 unique guests in our dataset, maybe more. These persons become relevant just because they were guests of an episode - we must strictly classify and differentiate based on that. Not every human in our dataset is relevant for analysis. A select set becomes relevant because they explicitly meet certain criteria: If some analysis is conducted on show A, every guest of this show becomes relevant for this particular analysis.

Due to guests being fetched from wikidata, they have a very large set of properties. For most analysis, we must narrow this down to the most important ones. A non-exhaustive list can be found in the "Properties" section.

## Properties
Remember that not every property can be treated equally:
* Guest age is derived from the respective episode release date minus the birthday of the respective guest. Technically, this may be inaccurate due to the episode being recorded (much) earlier than it aired, or due to a birthdate being recorded only as year, not as date.
* Technically, ever guest property is episode specific. A guest can have occupation X in Episode 4, and occupation X and Y in episode 5, and then only Occupation Z in episode 16. If we have temporal data where we can derive if that property is active during the episode, we should consider this. For properties like age, this is always the case, since birthdays are always temporal datapoints. For other properties, we should go looking for temporal qualifiers such as "start time" or "end time" or similar. Where these are not there, we should keep track of just that: Add a small note to the analysis/visualization, or to the log documenting 

Naturally, any property can also be empty, and we must accurately acknowledge that:
* How many of the relevant episodes could we disambiguate from which sources? For how many of them could we accurately extract the relevant metadata?
* How many of the relevant episode guests could we identify on Wikidata? How many of those had the relevant metadata? How many of those relevant metadata were in what format?

In visualization, we could experiment with explicitly showing the "unknon" as its own segment, or maybe just as a textual representation in the legend or bar / axis labels, or headlines. 

### Age
Integer between 0 and ~120.

### Gender
Not binary, but a set of possible options. Identify options as they appear as objects of this property.

### Occupation
Usually a class that may have some subclass relationships with other occupations.

#### Occupation clustered by hierarchy
Rather than seing 400 different sub-types of scientists in an endless list - or not seening any scientits at all due to their subtypes not meeitng some cut-off numbers or "top 10" status - it may make sense to cluster them. This means that we may have multiple dedicated occupation visualizations just for the different sub-clusters - this will be a constant point of experimentation and iterative improvement.  

### Role
Occupation is the most relevant subclass of role. It will be interesting to compare the two - also role without occupation tree

#### Role without occupation subtree

### Party affiliation




## Analysis and Visualization Angles

### Development over time

## Explicit minimum combinations
* Gender distribution
    * over time
        * All guests of any of our predefined broadcasting programs 
        * One analysis/visualization per predefined broadcasting_program
* Gender distribution by party affiliation
* gender distribution by occupation
* party affiliation by occupation
* Party affiliation over time alongside constellation of bundestag over time (and maybe alongside "Sonntagsfrage" (public poll every week) results)
    * May not be a minimum requirement since maybe we can't get the poll data easily 

## Structures to ease access

### Episode X Person occurence matrix
This will propably be the most important matrix:
For example: 
* All Episodes sorted ascendingly by time as columns
* All Persons sorted descendingly by total occurrences as rows.
The result will be an episode where the first Column (thus: the oldest, the earliest in our timeline) will show a "1" in every row of a guest that was present in that episode.
The first row will show our overall most present guest, and a "1" on every column that this particular guest was present in.
All cells where that guest was not present in that particular episode will be empty.
All guests that share the same number of appearances are sorted alphabetically.

This matrix will allow some derivative Matrixes:

#### Individual Per-Show Matrices
Only include episode columns that are part of a given broadcast_program

#### Guest-Co-Occurence Matrix
Just calculate Guest x Guest co-occurrences.

#### Others
This will also ease any kind of analysis: If we want to identify which episodes had which distribution of a specific age / occupation / gender, we just extract this from the respective guests and create the respective matrix:
* Episodes remain as columns,
* Rows become 
  * Age from min to max, or
  * Occupation sorted by cumulative occurrences
  * gender sorted by cumulative occurrences
* and cells can now have values greater than 1, since there may be two people aged 52 in a given episode.

By mapping most analysis over such a matrix, we can ease plenty of analysis angles.


### Person property timeline
Structure all relevant properties per person into groups:
* Universal, meaning properties that have no start or end time documented for this particular entity (e.g. instance of)
* Temporal, meaning that these properties have a temporal component documented (age, party affiliation with start and/or end date, etc.) 

To do this properly, we need an interface for Analysis Phase Code to fetch Wikidata Phase cache and possibly make additional network calls. To do this, we have added a clarificaiton to F25:
   * **Clarification:** Then we should add this to the interface documentation: When other phases want to interact with our wikdiata data, they can use the following functions:
     * One to retrieve all cached data on a PID / QID
     * One to retrieve the basic_fetch data of a PID / QID, and do a network call that fills the cache if we need to
     * One to retrieve the full_fetch data of a PID / QID, and do a network call that fills the cache if we need to.
       * It is about time that we do a version of the full_fetch without inlinks. possible names may be all_outlink_fetch or similar. Reason:
         * all QIDs from manual reconciliation are automatically relevant permitted.
           * If one such node fails the full_fetch exclude check (e.g. is a class), we still need data on it.
           * Thus, we need a "all_outlink_fetch" or similar, to ensure we populate every relevant entity beyond just the basic_fetch, but do not run into the full_fetch issue of potentially fetching thousands of inlinks we don't care about.
   * All of these Calls should still populate our cache and event store, just that they were not part of our discovery pipeline. Usually, this will be the case when manual curation will identify a relevant wikidata QID (e.g. guest) or PID in a later phase, and now the wikidata entry on this is required.



# Meta-Analysis
Do some anylsis of the data we aquired:
* How many instances were retrieved?
* How many duplicates?
  * How many people shared a name, but were found to be different wikidata individuals?
  * How many Episodes could not be deduplicated?
    * How many of those were truly unique, meaning completely unique name even after normalization and publication time thats not similar to any other 
      * How many shared similar names or publication dates with others, but were still uncertain to be fully matched?
        * Lexemical similarity analysis between remaining unmatched entities
* How many classes were retrieved?
* How many could be matched?

## Property analyiss
* Inspect what kind of properties we have (e.g. how many of the properties are IDs)


## Source specific analysis
* Of our total episodes, how many did 
  * Wikidata have
  * Fernsehserien.de have
  * ZDF Archiv have
* And how many of those were unique to only that platform? That only that one had?
* How many of them were without guests? Without metadata?
  * How many of those were legitimate without guests? Like Markus Lanz Jahresrückblick



* How many of these statements had references
  * Which kinds of statements did have references, how often?
* How many had qualifiers
  * What kinds of statements did have qualifiers, how often?

Also regarding the manual matching:
* What did the students document?
  * Omar (Bachelor Thesis)
  * Ahad (A-L)
  * Rownak (M-Z)
    * Minor lesson learned: Slicing alongside the middle of the alphabet does not mean slicing the dataset in half.
* Example:
  * Found category of person: `Editorial Staff`. Sometimes documented as "None" in the notes, but sometimes not captured. Need systematic analysis of the dataset.
    * example: Elke Maar, Claudia ______: Both Editorial Staff 

