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


---

> **ARCHIVED 2026-04-30 (batch 3)** — Processed into `05_implementation_context.md`, notebook fixes in `gen_50_analysis.py`, and documentation cleanup across all `2026-04-29_Initialization` files. See below for verbatim content.

---

## Ensure 04_analysis_angle_structure is used to structure notebook and implementation
`documentation/50_Analysis/2026-04-29_Initialization/04_analysis_angle_structure.md`

## Ensure implemnetation, data used are properly documented.
When implementation begun, plenty of very noteworthy insight. The key findings and decisions, guiding implemntation principles, etc. - should be captured and extended / updated whenever needed. We don't want to rediscover the same information over and over again, we want to capture and formalize it here where we can use it.

For example:

### Guest role values
* Gast → guest
* Moderation → moderator
* Produktionsauftrag → staff (production order - means the company was commissioned to produce)
* Produktionsfirma → staff (production company)
* Redaktion → staff (editorial)
* Kommentar → this is interesting - "comment" - could be a commentator/commentary
* Kommentator → commentator (similar to Kommentar)
* Drehbuch → screenwriter/script
* Regie → director
* '' (empty) → unknown


### Key data findings
1. dedup_cluster_members.csv is the join bridge: alignment_unit_id → canonical_entity_id
* 31,823 rows (vs 26,659 in reconciled) — the cluster_members includes more rows than the reconciled file
* 8,998 unique canonical_entity_ids (matches dedup_persons)
* 24,066 out of 24,758 reconciled alignment_unit_ids are in cluster_members (97.2% match rate)
* 692 reconciled rows don't match — these are likely unresolved entries or new additions
2. The join chain for appearance counting:
* reconciled_data_summary.alignment_unit_id → dedup_cluster_members.alignment_unit_id → canonical_entity_id
* Then count appearances per canonical_entity_id
3. For role detection:
* reconciled_data_summary.fernsehserien_de_id contains the episode URL (or is empty for unclassified entries)
* Join to episode_guests_normalized.csv via fernsehserien_de_id = episode_url
* Then match name using reconciled.canonical_label ≈ episode_guests.guest_name to retrieve guest_role
4. For Wikidata properties:
* Pull from core_persons.json for Wikidata-matched persons, and use entity_access.ensure_basic_fetch() to fill in missing QIDs

## Ensure all person entries with are used with full outlinks fetched
One of the prvious notes statet:
* "Pull from core_persons.json for Wikidata-matched persons, and use entity_access.ensure_basic_fetch() to fill in missing QIDs"

This could imply that it is enough to `basic_fetch` the Wikidata entry to analyze it. But that would mean that we tread it as "property: unknown" for literally EVERY property:
We must full_fetch these people, or - if possible - implement the outlink fetch, since this is the data we now need, without the additional inlinks that we do not care about (right now).


## Concept drift in implementation.
The current implementation_context does not seem to adhere to our data model. Some lower level projection with 700 entities is suddenly our primary source of truth and may seek to overrule our authoritative manually matched set with 26.000 rows and some 4000+ unique wikidata IDs.
Please, once more: Inspect all of documentation/50_Analysis/2026-04-29_Initialization, and compare each file with our implementation_context. We must remain consistent on the design.


## Maintain a clean code and documentation
Information like the "Elon Musk" test case is an automatic test case used during debugging. It is explicitly temporary and should be removed before the implementation is is ready to be considered complete and ready for commit. We don't want some "Elon Musk (Q317521)" or similar explicitly anywhere in user documentation or code - if we keep something like this audit check in there, then just by class or concept: "preserve unclassified persons for manual review" or similar.

---

> **ARCHIVED 2026-04-30 (batch 4)** — Processed into TASK-A07 through TASK-A11, updates to TASK-A02/A04/A05, TASK-A06 marked resolved, and README updated. See below for verbatim content.

---

## Session-end state note (2026-04-30) — TASK-A06 implementation in progress

The `all_outlink_fetch` function is implemented and exported from `entity_access.py`. The notebook cell `nb50_c05c` is written and calls `begin_request_context` / `end_request_context` correctly. The notebook has been regenerated (25 cells). **The fetch has NOT yet been run successfully.** First run attempt produced 0 fetched / 4,725 failed — root cause identified: `begin_request_context` was missing from the first implementation. Fixed before session end.

**CRITICAL WARNING for next session — read Phase 2 Wikidata code before touching it:**
The Phase 2 Wikidata infrastructure (`speakermining/src/process/candidate_generation/wikidata/`) has multiple interconnected guardrails that are NOT obvious from the public API. Key example: `cache.py::_http_get_json` raises `RuntimeError` if `begin_request_context` has not been called. `full_fetch.full_fetch()` catches this exception silently and returns `None`. This means 100% of fetch calls fail with zero error output — extremely hard to diagnose without reading the source. Before implementing any new Phase 2 interaction, read `cache.py`, `event_log.py`, `event_writer.py`, and `entity_access.py` in full.

**Next step for next session:** Run `50_analysis.ipynb` top to bottom (cell 5b = Wikidata fetch, ~15 min). After it completes, re-run cells 15, 17, 25 (C3–C7 occupation/party distributions and summary). Then review the corrected gender/occupation/party distributions with improved Wikidata coverage.



## Output rewiring
Everything should be `50_analysis` - some old code sill says `40_analysis`.

### Folder Structure
Generally: all files in `50_analysis` unless there is a reason for not doing so.
Reasons:
* Talk-show specific analysis folders
  * One for "ALL" and
  * one each for each dedicated (e.g. Markus Lanz, Maybrit Ilner, etc.)
* Additional as needed if we identify a certain category of analysis outputs becomes meaningful to be sorted into a dedicated space.


## Prepare Dataset
Immediate next step and important throughout everything build from now:

Everything used in analysis must be copied to `50_analysis` first. It must have its own dump of all analyzed data meaningful to our analysis. This is particularly characterized by:
* Every output of the Analysis (naturally)
* All the data on non-humans, including, but not limited to:
  * All classes
  * All other core class instances
  * Class hierarchy
  * ...
* All the data on humans
  * We must be able to split of data on humans, since we may not want to publish that together with the other data above due to GDPR restrictions. Thus, we should isolate this "kind" of data into a separate file / folder

The resulting folder should contain everything that one needs to redo our analysis, without needing anything else from any other folder.


## Temporal chunking
Customs have changed over time. One important angle should be to investigate data changing across years, across decades. We should also keep track of how many episodes of how many different shows we have for this particular year / decade.



## Analysis Output analysis
Every so often, we should inspect our output, investigate the data and identify findings. This should be interesting information to further motivate refining our analysis, create new summaries and visualizations. Maybe it's also a hint at a bug or issue. Some aspects below:

### Age
We appear to have a 3 year old and a 117 year old person as a guest. Investigate if this is correct and when that happens.  

### Party affiliation
By now, we should be able to differentiate if 
Test explicit members such as SED members

### Hierarchical data
We already see that there are already two kinds of Schauspieler and two kinds of teacher in the top 10. We need hierarchical analysis and subclass analysis. on this note:
* Some QIDs are still not basic-fetched and class_hierarchy_resolved: Example: Q488205
  * Doing so is a MUST before we can proceed.
  * Very important: For both, use the Wikidata code and interfaces accordingly. Formalize this principle of "interface with wikidata only through phase 2 code provided interfaces, adhering to their principles on caching, rates, events etc." adequately.


## General summary improvement
Show textual summary statiscs with numbers always. Just top X lists are almost meaningless, lists with the number that got them there are just as easy to implement, but much more meaningful.

We also have no "Most relevant person"

## Pattern based analysis: tables
We already specified `TASK-A04 — Property value statistics table (generic pattern)`.

We really need these analysis tables. Additional thought on them:

We need statistical analysis per property, a second one independed of "per episode":

* We need to analyze every property for 
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
  * most common combinations,
    * Unique combinations
  * most common combinations between this property and a different other properties (one column for each such property)
    * Unique combinations

particularly the last two ("most common combinations") may each require their own table to be done correctly and meaningfully
* This could warrant their own analysis and may go into predictive analyis

This is a standardized analysis that should be  applicable to all properties. If this is not the case


## Intermediate documentation vs implementation evaluation
It is about time to check our implementation and outcomes against what we specificed: 
* What is correctly implemented and can get a dedicated "fully_implemented" checkmark?
* What is not_yet_implemented?
* What is wrong?
* Maybe: What now has further potential to be implemented, discussed or refined?


## Visualization
I see that there is one single visualization mixed in to the analysis step. This is wrong on two levels:
1) We are currently doing the analysis step, the visualization comes next.
2) The sunburst visualization itself is wrong.
   * Hierarchy is not working at all.
     * There is a center section called "Person" which makes no sense
     * Each top level class has only one child, which is it itself.


We should start implementing the visualizations now once all "immediate" / more pressing / critical tasks are resolved. Data is basically ready.


## A note on classifying/structuring analysis/visualizations
Technically, analysis categories are derived from the underlying data type:
Temperature, Time, weight, age, all are skalar values - their analysis and visualizations will look similar

---

> **ARCHIVED 2026-04-30 (batch 5)** — Processed into TASK-A12 (structural consistency enforcement) and TASK-A13 (unclassified persons investigation); §6 visualization mapping added to `04_analysis_angle_structure.md`; `gen_51_visualization.py` created (20-cell visualization notebook). See below for verbatim content.

---

## Inspect Persons with no episode link
Explicitly ToDo once visualizations are resolved. This is a large-scale laborous search task that can be done manually or with an Agent without budget limit. We just need to describe the issue, goal and how-to-solve it, as well as the definition of done.
Generally: We should go through individuals that have no episode links and verify if they truly appear in no episode. We already know that Marie-Agnes Strack-Zimmermann (Q15391841) appears in several episodes, so we already know that there are things wrong here.

Persons with no episode link: 215
  With wikidata_id:    215
  Without wikidata_id: 0

match_strategy breakdown:
match_strategy
wikidata_person_only_baseline    215

Random sample of 20 (verify these are genuinely unmatched — not missed guests):
wikidata_id               canonical_label                match_strategy match_tier
  Q21523850               Tomas Avenarius wikidata_person_only_baseline unresolved
 Q118142894         Wojciech Poczachowski wikidata_person_only_baseline unresolved
  Q15391841 Marie-Agnes Strack-Zimmermann wikidata_person_only_baseline unresolved
   Q2163782            Rolf Schmidt-Holtz wikidata_person_only_baseline unresolved
    Q562958                  Anna Planken wikidata_person_only_baseline unresolved
  Q50077398                 Joachim Frank wikidata_person_only_baseline unresolved
  Q18412110                Patrick Bernau wikidata_person_only_baseline unresolved
     Q76265            Franziska Brantner wikidata_person_only_baseline unresolved
  Q15852627                  Verena Kerth wikidata_person_only_baseline unresolved
   Q1897106     Marie-Christine Ostermann wikidata_person_only_baseline unresolved
  Q17353006             Moritz Schularick wikidata_person_only_baseline unresolved
   Q1039460                  Carl Linfert wikidata_person_only_baseline unresolved
  Q18341391              Sophie Sumburane wikidata_person_only_baseline unresolved
 Q134700129                   André Nemat wikidata_person_only_baseline unresolved
 Q132931403                  Eugen Brysch wikidata_person_only_baseline unresolved
   Q1251526                   Randi Crott wikidata_person_only_baseline unresolved
    Q106721                Peter von Zahn wikidata_person_only_baseline unresolved
 Q124387759          Arne Friedrich Mörig wikidata_person_only_baseline unresolved
  Q93278208                 Michael Sauga wikidata_person_only_baseline unresolved
   Q1357121     Ernst-Ludwig Freisewinkel wikidata_person_only_baseline unresolved

These persons will appear in `person_catalogue_unclassified.csv` after Step A.
Review this list after Step A to confirm no systematically misclassified entries.


## On analysis
This is currently how we do analysis of parties:
=== C5: TOP 15 PARTIES ===
                                                 party  person_count  pct_by_person
               Sozialdemokratische Partei Deutschlands           308           5.37
                        Christlich Demokratische Union           272           4.74
                                 Bündnis 90/Die Grünen           142           2.47
                            Freie Demokratische Partei           109           1.90
                    Christlich-Soziale Union in Bayern            67           1.17
                                             Die Linke            47           0.82
                           Alternative für Deutschland            37           0.64

Yet, this is how we should do it:

A generic function that produces a per-value statistics table for any property:

| Property value | min/episode | max/episode | mean over episodes | std dev | median | episode % without | total appearances | unique persons |
|---|---|---|---|---|---|---|---|---|

This is why we have defined structures like:
> ## TASK-A04 — Property value statistics table (generic pattern)
> **Priority:** Immediate — user confirmed: "We really need these analysis tables"
> **Status:** Open

and

> `documentation/50_Analysis/2026-04-29_Initialization/04_analysis_angle_structure.md`

We should not try to customly draft plenty of different approaches - we should have analysis angles and structure according to them.

Since this is also fundamental design principle for Visualizations, these are the immediate next steps:
1) Shape a uniform structure classifying and accordingly describing all currently known analysis angles, focussing on what unites them and what common structures exist to represent them.
2) Create Visualizations utilize this structure. Remember the existing context:
   1) `documentation/visualizations/visualization-principles.md` contains universal visualization principles
   2) `documentation/50_Analysis/2026-04-29_Initialization`, particularly `documentation/50_Analysis/2026-04-29_Initialization/open-tasks.md`
3) Document (only document! not implement) A task to ensure that this structure is 
   1) Consistently documented and adhered to in all documentation and descriptions
   2) Consistently followed in the analysis and visualization notebooks, which need to be structured accordingly.

Remember: Just because a type of analysis / visualization is defered for now, it does not mean it's irrelevant for this structure: Quite the opposite: We should build a structure that is designed to accomodate all currently known analysis / visualization angles and provides structure to integrate future additions.

This may or may not be related to the current task.
