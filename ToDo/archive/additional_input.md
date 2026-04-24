> **ARCHIVED 2026-04-24 (batch 5)** — Processed into TODO-036 through TODO-044. See `documentation/open-tasks.md` for details.

---

## Phases 3.1 onwards does not follow the notebook orchestration guidelines.
`speakermining/src/process/entity_disambiguation/orchestrator.py` contains a function called run_phase31.
Similarly, Phase 3.2 has a similar function run_phase32 in `speakermining/src/process/entity_deduplication/orchestrator.py`.

This clearly breaks with our `documentation/coding-principles.md`. Notebooks should be the orchestrators, not single functions. Where possible, we need cells containing the step by step processes, with intermediate and regular output so the user can monitor the process and progress.  
We need to inspect the scope of this drift - it likely begins in Notebook 3.1. and then fans out to every notebook thereafter. We must both fix this, as well as formalizing an AGENT.md and CLAUDE.md, since likely this issue was introduced when Claude Code was introduced as well and assumed some coding principles which are not aligned with this repository.

### Example 1: Column trimming (all aligned files, TODO-017)
Claude Output:
  The issue is that the notebook calls the build functions directly, bypassing run_phase31. The trim must live inside each build function.

TODO-017 was fixed not in the actual notebook workflow, but in an artificial wrapping "run_phase31" function. This means work and time was invested in a side-track that now needs to be worked back into the maintrack: The notebooks and their modules.

### Example 2: Visualization notebook 51 is completely outdated and full of errors
Another example that the code written was not executed through the notebook, but through some structure created in parallel. When the Notebook was first executed, it did not even run properly.
Reworking the Visualization notebook 51 should propably wait until all the vislualization tasks are on the current task list - but when that happens, we need to make sure that these follow our notebook-first orchestration coding principles. 


## property based hydration fix may be structurally related to relevancy propagation 

There is a consideration to be bad that our # ToDo 31 related property based hydration fix should be either constructed similarly to our relevancy propagation or be merged into it.

What this means:
1. Those two are not the same, one propagates relevancy, qualifying a node for EXPANSION (meaning it is an interesting subjective), the other is an object hydration engine, mostly ensuring that the outlinks of our subjects are meaningful.
Notheles, both say "if you find a link with this this property, you are allowed to [expand/hydrate] a the object if the subject meets some criteria".
2. Since the logic is similar, it may make sense to treat them similar. Either by handling both through the same config file (currently, relevancy has a config file where relevancy propagation can be set to true for certain properties), or treat them both through similar, yet independent config files.
Likely, two similar, yet separate config files are better, since a) that stresses that they are not the same, and b) hydration properties can target non-core-class-instances, where relevancy propagation is explicitly reduced to links between core-class-instance. By the time our property hydration whitelisting is used, we sometimes don't even know yet if the object is a core class instance



## Wikidata v4 rework
Generally, the logic from wikidata likely needs could use a fundamentall rework. This is explicitly out of scope for now, but an important lesson learned:
Currently, 2.1 seems like a patchwork of of various different modules, all mending different shortcomings of the other modules. The ideal goal would be a simple, rule driven graph expansion: Find core node: Apply rules, then discover links via  hydration or expansion. For each of those newly discovered rules, same thing again:  apply rule, hydrate or expand, or do nothing and leave them as a QID.

If all the logic from all the modules were to be correctly integrated into these rules - that would be the ideal state.

This is a task for much, much later. Not a priority now.



## Ontological Findings: Classes that are subclasses of multiple core classes
On the note of interesting findings worth discussing:
The discover conflict patterns may be ontologically interesting to discuss:
 
[notebook] Step 2.4.1 start: discover conflict patterns from all rows
[notebook] Step 2.4.1 label language: en
Conflict summary:
  class_resolution_rows: 14704
  conflict_rows: 1381
  clustered_rows (patterned): 1377
  outlier_rows (unclustered): 4
  discovered_cluster_count (coarse): 10
  discovered_cluster_count (strict): 12
  largest_cluster_size: 1183
  source: data/20_candidate_generation/wikidata/projections/class_resolution_map.csv

Discovered coarse conflict clusters (labels + decision rationale):
...

There are some interesting implications, e.g. "Arabic Speaker" being both a role and a person.
And plenty other.



## age at first appearance is only a first step

Currently, we only have "age at first appearance"
We could have a secpmd visualization / overlay for "age" in general, so not only counting the first appearance, but every appearance. If the same Person of age 50, 51, 52, 53 ... appears over and over again, every appearance should be counted there.

### General principle:
We should exclude the moderator from all such analysis. The data of the moderator should not skew all the graphics. Maybe, this is already considered - a simple check would be to see if Markus Lanz himself is counted in the evaluation.



## Treatment for time sensitive claims

We have learned that some statements get outdated. Whenever we have a start or end date, we should check if the statement was true during the particular episde the guest appeared in (party afficliation, position, occupation, ...)



## The final guest list is certainly wrong right now

Elon Musk is part of the final data/40_analysis/guest_catalogue.csv

Yet, the single time I could find him was in the description of Markus Lanz 27.09.2023.

As far as I can tell, he was never a guest.

If Elon Musk got into this list by accident, then there is likely a much deeper issue of people getting misclassified as guests. There are some other open Tasks already raised to sharpen the definition of guests, so we can use this as a test if we avoided missclassification.
That being said, we should also have a closing analysis segment that takes a random sample of our output and traces their origins back and checks if these serve correct. If we find something like a mislabeled guest who actually comes from a topic description, we raise an alarm and know we have to refine our code.



## Finding / Lesson learned: Our starting assumption that we are looking for core class instances was not even correct.
We are not looking for core class instances only, in the case of "roles", what we are actually looking for is core class subclasses



## Wikidata Step took quite some time
These steps took a relatively long time. I have preserved some outputs in 
* `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context.md`
* `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context_second.md`
I also see that these are here:
`documentation/context/node_integrity/node_integrity_20260424T140800Z.md`
`documentation/context/node_integrity/node_integrity_20260424T105030Z.md`

since this took over 6726 seconds (or the first run: 1648 seconds) without completing, it may be worth investigating if everything going on there is correct

---

> **ARCHIVED 2026-04-23 (batch 4)** — TODO-031 clarification processed: root cause was wrong. Fix is NOT a one-time script but a new Phase 2.1 notebook step (Step 2.4.2 "Property-Value Basic Hydration"). Predicate whitelist: P106, P102, P108, P21, P527, P17, plus all objects of expanded core class instance subjects. Design documented in TODO-031 notes. No new TODO created — implementation proceeds directly.

---

> **ARCHIVED 2026-04-23 (batch 3)** — Visualization principles feedback processed: centered stacked bar charts section added, nested subgraphs section added, universal-rules-first restructuring applied, use-case-specific mappings section added. All items resolved in `documentation/visualization-principles.md` directly (no new TODO required — principles doc is open-ended).

---

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

---
> **ARCHIVED 2026-04-23** — Second batch of additional input processed below.

# Persistent Task archiving and structuring
> **Archived** — TODO-010 (wont-fix 2026-04-22) moved from `open-tasks.md` to `closed-tasks.md` (Wont-fix section). The `documentation/visualizations/classes.md` content was already ingested into the `open_additional_input.md` visualization section and then into task notes; the file deletion was already staged.

# Additional information for the Visualization rework
> **Archived** — Two notes added: (1) edge-overlap minimization for hierarchical/circular layouts added to TODO-024 Notes; (2) multi-parent challenge for sunburst/sankey added to TODO-025 Notes.

## Circular and hierarchical visualization
The layout principle — co-locate subclasses that share the same superclass set, place edge-non-interacting nodes at cluster perimeters — is captured in TODO-024 Notes.

## Sunburst and sankey diagram
The multi-parent challenge (subclasses with multiple superclasses break tree-like hierarchy) is captured in TODO-025 Notes.

# Many QIDs still not labeled
> **Archived** — Tracked as **TODO-031** in `documentation/open-tasks.md`. Evidence: Q1238570 (political scientist / Politikwissenschaftler) and Q40348 (lawyer / Rechtsanwalt) appearing as bare QIDs in `top_occupations` output despite both having German and English Wikidata labels.

# Ensure we have all analysis and visualization LanzMining had
> **Archived** — Covered by **TODO-022** in `documentation/open-tasks.md` (Compare to prior work, includes ingesting arrrrrmin/Website/LanzMining.html). The "Not less data for humans / very good as is: Tons of columns, tons of data" note is an affirmation of current analysis output quality — no new task required.

# Current Page rank visualization is flawed
> **Archived** — Tracked as **TODO-032** in `documentation/open-tasks.md`. Page rank should be a node graph, not a bar chart.

# Differentiate gender bias in entire population from gender bias in sample set
> **Archived** — Tracked as **TODO-033** in `documentation/open-tasks.md`. The analysis can only report sample-set bias; population-level claims require external reference data. This is a methodological caveat to document, not a data quality issue to fix.

# Some not task-relevant findings
> **Archived** — All three findings added to `documentation/findings.md`.

## Data sources differ in time scope
> Tracked as **F-014** in `documentation/findings.md`. ZDF archive covers 2008–2024; fernsehserien.de includes more recent post-2024 episodes.

## Our Language encodes data
> Tracked as **F-015** in `documentation/findings.md`. German grammatical gender, Japanese seniority encoding, etc. are data-privacy relevant attributes encoded in everyday language.

## Some signals may be reliable positive indicator, but their absence does not mean negative
> Tracked as **F-016** in `documentation/findings.md`. All-caps surname is a strong positive indicator for a guest but title-case does not reliably mean incidental. Current implementation correctly uses relation-cue words (ehemann, ihr, etc.) as the clean incidental signal.

# Learnings
## PDF Extraction is equal to other source retrieval
> **Archived** — Tracked as **F-017** in `documentation/findings.md` and **TODO-034** in `documentation/open-tasks.md`. PDF archive, Wikidata graph discovery, and fernsehserien.de are peer candidate discovery steps. Wikidata string-based generation is a substep of reconciliation (Phase 3.1), not a standalone major phase.

# Some context is helpful for manual Reconciliation
> **Archived** — Incorporated into **TODO-017** (`documentation/open-tasks.md`): updated definition of done with ~40-column target, column selection priority (ids, label, description, aliases, links, most-common properties), and cut criteria (≥ 99% empty or not useful for human reviewers). OpenRefine usability is the driving rationale.

Current state: `aligned_persons.csv` has ~2,531 (sometimes ~5,000) columns — too many for OpenRefine to load comfortably. Target: ~40 columns (hard ceiling 50). Keep enough for a human reviewer to match or reject an entity without leaving OpenRefine.

## Clarification for TODO-031
> **Archived **
The problem has two parts, not one:

* 65 occupation QIDs: in entity store but inactive_guarded (zero labels) — discovered via P279 subclass chain
* 157 occupation QIDs: completely absent from entity store — appeared only as P106 property values in hydrated persons but were never added to the store at all

The broader scope is large. Across all predicates, the counts of unhydrated object QIDs are: P31 missing 4,534 — P279 missing 3,630 — P1343, P17, P527, P910 each missing 1,000–4,000+. For P106 specifically: 222 unhydrated of 312 unique.

Before implementing a systematic fix, I need four answers:

1. Predicate scope. The "every referenced node should be hydrated" rule, taken literally, would require ~20,000+ network fetches across all predicates — P17 (country), P1343 (encyclopedia), P910 (topic category), etc. Are you intending the rule to apply to ALL property value QIDs, or should we scope basic hydration to a defined set of predicates (e.g. only those that produce analysis-relevant labels: P106, P102, P108, P21)?
   1. **Clarification:** This consideration seems very correct, this could escalate very quickly. Let us carefully proceed by only whitelisting certain properties for this hydration now. If we then find this to be not enough, we can continue to add more properties to that list. If we find this approach to not scale well, we can also place a flag that simply says "hydrate all properties" (obviously set to false for now), with adequate warnings and descriptions in place why this is currently set to false. For now, let us proceed with hydrating them by explicitly whitelisting the hydration via certain properties (there should be a configurable list):
      * P106 (occupation)
      * P102 (member of political party)
      * P108 (employer)
      * P21 (sex or gender)
      * P527 (has part(s))
      * P17 (Country)
    2. be sure to confirm that this still hydrates the objects of these properties properly, including their class belonging, so we discover if they themselves are core class instances. P102 (member of political party) should reveal organizations, P106 (occupation) should reveal roles, P527 (has part(s)) may reveal seasons or episodes.
    3. Beyond those specific properties, we should always at least fetch the basic information for objects that are linked to a relevant core class instance subject. Basically, the following principles apply:
      * If the subject is a core class instance (e.g. episode, person) connected to a broadcasting program, then every of it's links should be hydrated. We have a core set of broadcasting programs (e.g. Markus Lanz), their seasons (e.g. Markus Lanz Season 1), episodes (e.g. Markus Lanz Episode 1) and guests (e.g. Elmar Theveßen). Whenever any of them are subject, we need the label of their objects - and thus, the objects of their outgoing links need to be hydrated.
      * The fact that P106 (occupation) has 222 unhydrated of 312 unique is especially damning since those objects are likely themselves core class instances (roles), meaning we'd need them in our subclass tree (e.g. biologist (Q864503) -> scientist (Q901) -> researcher (Q1650915) -> academic professional (Q66666685), all of which being subclass of profession (Q28640) -> occupation (Q12737077) -> social position (Q1807498) -> position (Q4164871) -> role (Q214339), which is one of our core classes). If we don't hydrate those occupations, we're likely missing plenty of our core class instances.

2. P31/P279 gap. P31 itself has 4,534 object QIDs missing from the store. Should those also be covered by the fix, or is P31 already handled through the existing activation path (meaning the issue is something else for P31)?
   1. **Clarification:** There will be leaf nodes in our graph, meaning mostly classes from which we do not search further. For example: A person has a favorite Band X - > that band's node will be a leaf node, since it is not further relevant for us. This Band X will be instance of something, but we don't care about that and don't further hydrate this bands class belonging. So the fact that P31 has unhydrated object QIDS by itself is expected and does not raise further concern.

3. Where the fix lives architecturally. Should the new "property-value basic hydration" step be:
* Integrated into the existing subclass preflight (Notebook 21, after Pass 2), OR
* A separate post-expansion pass triggered at the end of the main expansion loop, OR
* Something else?
    1. **Clarification:** There are good reasons for either of them. I would say a new cell right after the subclass preflight. This way, we do a top-down subclass discovery first, and then ensure in a separate cell that all bottom-up links are able to properly connect to this fanned out subclass tree.

4. Retroactive vs. forward-only. The current entity store has 65 inactive_guarded + 157 completely absent occupation QIDs with no labels. Should the fix include a mechanism to hydrate these on the NEXT run of Notebook 21 (i.e. the fix takes effect after a re-run), or do we also need a separate one-time backfill step to fix the existing stored data without re-running the full Phase 2?
    1. **Clarification:** Never implement one-time backfills, or one-time actions of any kind. All features we implement should be integrated in to the run of a notebook. "Run All" should be the only thing that has to be done to complete the step of any given Notebooks - no branching patches, no one-time actions anywhere outside.

## 6.5 Run Node integrity pass very slow
This may be correct behaviour, but 6.5 Run Node integrity pass spent 1600 seconds to expand 34 QIDs. An excerpt from `ToDo/21_wikidata_6_5_run_Node_integrity_pass_context.md` (inspect for full output):

[notebook] Step 6.5 complete in 1648.80s
Node integrity summary:
  known_qids: 41153
  checked_qids: 41153
  repaired_discovery_qids: 392
  newly_discovered_qids: 349
  eligible_unexpanded_qids: 1082
  expanded_qids: 34
  network_queries_discovery: 2
  network_queries_expansion: 617
  total_network_queries: 619
  timeout_warnings: 0
  stop_reason: user_interrupted