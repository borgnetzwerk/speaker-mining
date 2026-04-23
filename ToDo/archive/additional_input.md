> **ARCHIVED 2026-04-23** — All actionable items from this file have been converted to formal TODOs in `documentation/open-tasks.md`. This file is preserved for historical context only. Do not add new tasks here — use `documentation/open-tasks.md` directly.

---

# Regarding the right time to modify/normalize values
> **Archived** — Analyzed and resolved. See **TODO-016** (`documentation/open-tasks.md`): display normalization (Phase 1, stored) vs. match-time normalization (derived at comparison time, symmetric). Write `documentation/normalization-policy.md` to satisfy the definition of done.

See:
| ~~TODO-002~~ | ~~P1→P31~~ | ~~Umlaut/ß normalization~~ — **DONE 2026-04-22** (`normalize_name_for_matching` in `person.py`) | |

I wonder if doing normalization in this early stage already is too early. This seems to be something for Phase 3 Step 3.2 Deduplication. 
Similar for abbreviation expansion.
This warrants a conversation to be had: At what point should we try to normalize, and how?
We already do it at the beginning of Step 3 so we can align the time dates, so we absolutely to need some normalization before deduplicating, at least to standardize across sources.

We need to explicitly formalize the considerations to be had and find a suitable solution.


# Wikidata bias introduction
> **Archived** — Tracked as **TODO-029** in `documentation/open-tasks.md`.

For data protection and plenty other reasons, underaged people won't be represented much on Wikidata.
Wikidata requires individuals to be notable first, and that usually requires some time - so just going by wikidata birthdates will always skew the average upwwards.
We cannot really work around this, we just have to acknowledge it. 


# Predictive analytics
> **Archived** — Tracked as **TODO-021** in `documentation/open-tasks.md`.

Identify what predicts other properties, particularly gender. Insights would be for example:
* If a woman is invited, they are mostly coming from media occupations.
* If a scientist is invited, they are mostly male.
* If a politician is invited, they are mostly male and old.
Or similar. However, we don't want to start with assumptions, but want a neutral predictive analytics and then inspect the results.

# Gender Distribution analysis
> **Archived** — Tracked as **TODO-020** in `documentation/open-tasks.md`. Also includes: age distribution violin plot (added to TODO-020 scope).

The current "Gender by occupation" is a very good start - we need to greatly extend the work we did there

1. While having this in two separate diagrams is okay, what propably really sells it is a graphic containing both bars grouped. So you can immediately see the difference between unique persons and appearences.
2. The current "by occupation" is a fine first start, but we should do much, much more:
   1. Cluster occupations by subclass dependency: Teachers (e.g. Uni and primary school), Scientists (e.g.)

Age distribution violin plot

# Compare
> **Archived** — Tracked as **TODO-022** in `documentation/open-tasks.md`.

We need to make a comparison from all prior data to our data:
* One comparison for the related work section (just high-level comparison)
* Then an extensive data comparison going through the results of all prior

## Learn from Arrrrrmin visualizations
We need all analysis and visualizations arrrrrmin had
We have his data: `data/01_input/arrrrrmin`
I need to add the website for this.

## Learn from spiegel
We have the data from them: `data/01_input/spiegel`

## adapt and improve all from Omar
His data is here: `data\01_input\omar`
His approach is here: 
and his 

# Confirm low guest numbers are accurate and not just a relic of some people not being deduplicated / disambiguated correctly
> **Archived** — Tracked as **TODO-019** in `documentation/open-tasks.md`.

Guest_catalogue.csv currently contains only 640 rows - does this mean we only have 640 guests in total?
I would have expected much more - if we have more that could not be mapped, we should have them in a list as well, maybe in a separate one, but still, we should have them
## Do a dedicated analysis on this
Look at those that could not be deduplicated and see if we still can do something for some of them. 

# Prepare for the autoritative 6-column mapping file
> **Archived** — Covered by **TODO-018** (Wikibase import, deadline 2026-04-29) in `documentation/open-tasks.md`. The six columns are: alignment_unit_id, wikibase_id, wikidata_id, fernsehserien_de_id, mention_id, canonical_label.

* alignment_unit_id
* wikibase_id
* wikidata_id
* fernsehserien_de_id
* mention_id
* canonical_label

# Identify Inter-Task relationships.
> **Archived** — Addressed by priority levels and dependency notes in `documentation/open-tasks.md`. Task principles document tracked as **TODO-026**.

This document (additional_input.md) now quickly grew to maybe ten to twenty tasks - there is likely a smart sequence in which we should work through them. For exammple, we should not rework visualizations before the visualization principles are done. We should not `Work through backlog` before we are done with all more pressing tasks here.

# We should have a dedicated dataset overview
> **Archived** — Tracked as **TODO-023** in `documentation/open-tasks.md`.

How many Instances, classes and subclasses per core class? What interesting findings? What is the percentage of instances per class (aggregated via subclasses), so we can just look up "teachers: 5" or similar.
How many entries have wikidata mapping, how many could be deduplicated? Some statistics on the entire Speaker Mining pipeline, step by step.

## Maybe also a set of dashboard-like visualizations
Create a set of visualizations (as above) and then also create an orchestrated dashboard-like visualization per core class, but also one for the total repository


# Create and always follow Visualization principles:
> **Archived** — Tracked as **TODO-024** in `documentation/open-tasks.md`. Key note: all visualization files must be available at least in PDF and PNG format (HTML is additionally fine, but PDF+PNG are the main outputs).

We have some very nice visualizations. We should formalize the principles from them. For example:
* Use colorblind friendly color palettes
* Scale visualizations
* Visualization formats: All visualizations files need to be available at least in PDF and PNG format. Additional, such as HTML, are fine, but the main outputs are PDF and PNG

Many prior visualizations are gathered here:
* `ToDo/visualization_references`
When analyzing them, we must be very careful: There are some core principles (e.g. colorblind, scaling, PDF exports, customizable font family to match paper font), but there is also a lot of noise (e.g. different ways of ingesting data, sometimes very, very messy).

As such, we must proceed as follows:
1) Set up a universally applicable core set of visualization principles.
2) Inspect our `ToDo/visualization_references` and carefully identify if we can identify potential to 
   1) refine, improving the description of the principles with what could be learned from the examples.
   2) specify, complementing general advice with explicit best practice examples
   3) extend, expanding on aspects previously not covered

The visualization principles, just as the coding principles, will grow over time. They likely also need to be nested to differentiate universal rules (e.g. color palette, spacing) from visualization type specific rules (e.g. dedicated rules for Barcharts such as bar width, height; or rules for node graphs such as configurable node number with default, configurable label requirement to only label more important nodes, etc.)

# Ingest Wikidata visualization into final visualization
> **Archived** — Tracked as **TODO-025** in `documentation/open-tasks.md`.

The old file `speakermining/src/process/notebooks/21_wikidata_vizualization.ipynb` can remain, but we need to see if there are any old visualization that we do not cover in our 5_1 visaulization notebook.
The file also still contains additional ToDos that we need to go over 
## ToDo

Improve on the following five targets:
1) There are plenty of classes labeled by their QID, not by an actual label. I saw some of this happening in Cell 12 of candidate_generation, so maybe there is already something wrong happening further upstream. Use this opportunity to thuroughly investigate this issue at the root, in the 21_candidate_generation_wikidata.ipynb. If everything there is fixed there (Check via Cell 12 output), identify if the issue still persists in the 21_wikidata_vizualization.ipynb. If so, implement additional solutions here.

2) Ensure directionality is preserved for other core classes as well in view 2 hierarchy. Currently, it looks like they are added last and thus placed at the rightmost side, despite them propably being a superclass to most of them. 

3) Then add another diagram type: Sunburst Diagram. As per usual, one per core class, but also one for all of them combined. For the combined case:
* the innermost layer should be core classes only
* starting from the second layer, everything that is less than 5% of the toal instances should just be grouped up as "other".
Core-Class specific diagrams should have no such cut-offs by default and be exhaustive (show every subclass).  

4) Then another Diagram type: Sankey diagram. Apply the rules from above: Exhaustive core-class diagrams, then one combined with 5% "other" cut-off for subclasses.

5) Finally, ensure every diagram is written as png and as pdf to data/output/visualization.

# Unify ToDo structure.
> **Archived** — Tracked as **TODO-026** in `documentation/open-tasks.md`.

We need to search the Repository for open ToDos. As we see above, some todos are hidden in places we would not expect them. We need to aggreate and unify this.

Maybe, we even need a Task Principles file:
* Tasks should be written as simple as possible, with as much detail as possible.
* Tasks should avoid organizational overhead (such as conistent numbering etc.) and focus on describing the task
* Tasks should have a scope and be written to that scope, if possible
* Rasing a task is more important than properly describing a task - if a task is found in unproper state (written to a notebook, written without documentation or simply not following any of the principles), then we should assume good faith and mend this situation: Request clarification where needed, move the task to the place and shape it should be, and apply the principles where possible. Engange in clarification requests wherever needed.
* Task progress should be documented so that other people interacting with it know what is the current status, what work and planning has been done already
* Resolved tasks should be kept in an archive, out of sight from pressing files such as "open tasks", but also not out of reach from analysis tasks such as "what changes has this repository went through?"
* Tasks should not live in notebook files, but in the task tracker file of the phase they belong to

Those and similar principles should be formalized and guide our progress.


# Titles may hinder deduplication (non-issue)
> **Archived** — Confirmed non-issue. Tracked as **TODO-028** (document the finding in `documentation/findings.md`).

Found to be a non-issue, but should be added to findings
## Consideration:
ce_221b8ed90820,pm_0d7a99f74824,pm_0d7a99f74824,Karl LAUTERBACH,Q105676,high,karl lauterbach,true
ce_762af71f2daa,person_fs_fe07a3c8b2a2,,Prof. Dr. Karl Lauterbach,,unresolved,prof. dr. karl lauterbach,false

Some also have
* Prof.
* Prof
* Prof Dr.
* Prof. Dr.
* Prof Dr
* Dr
* Dr.

Or even with Professor or Doktor / Doctor or anything like that mixed in.

ce_1f2a0ef14cdb,person_fs_10486cead9a9,,Professor Dr. Daniel Hornuff,,unresolved,professor dr. daniel hornuff,true

We may need a dedicated tier for deduplicating by dropping titles or similar.

## Finding:
This seams to be a non-issue:
ce_221b8ed90820,Q105676,56,Karl Lauterbach,Karl Lauterbach,Q6581097,male,Politiker|Arzt|Hochschullehrer|Sachbuchautor|Q12765408|Q38383816,Q82955|Q39631|Q1622272|Q15980158|Q12765408|Q38383816,Sozialdemokratische Partei Deutschlands,Q13371|Universität zu Köln,1963,2009.0,2024.0,2020.5,56.0,1963.0,46.0,58.0


# Provide an overview over the most interesting findings, the trickiest normalizations etc. going on during the pipeline.
> **Archived** — Tracked as **TODO-030** in `documentation/open-tasks.md`.

Mainly for discussing Speaker Mining during a Talk / Workshop / Paper.

e.g. Title Disambiguation

The most challenging are propably something like
* Familie LECCE (10-köpfige Familie)
* Familie EWERDWALBESLOH (Walter, Corinna und Sohn Leon, Helfer von ...)

# Keep track who's Guest, who isnt
> **Archived** — Tracked as **TODO-027** in `documentation/open-tasks.md`.

Identify if the new guest / other mention differentiation from the phase 1 is properly propagated and used throughout later stages - so our guest list accurately reflects true guests. In the end, we should have two different person files: guests, and others. 


# Once all the above is done:
## Work through backlog
| Item | Reason for deferral |
|------|---------------------|
| Einschaltquoten PDF integration | Requires separate data source work |
| Gender inference from description text | Risk of false inference — documented as inadvisable |
| Description Semantification | Experimental, noisy input |
| Forbidden Features Catalogue | Governance/legal process, not code |
| Institution extraction (TODO-005) | Intentionally deferred; needs architecture decision first |
| Gender-framing analysis methodology (TODO-006) | Depends on analysis results |
| Role/occupation merge strategy (TODO-007) | Depends on deduplication design |

Particularly Einschaltquoten would be interesting: Identify what predicts Einschaltquoten, is it specific people, topics, weekdays?
