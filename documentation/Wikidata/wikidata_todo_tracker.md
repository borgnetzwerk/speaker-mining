# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed

### [x] Fix relevant episode detection
See: `documentation/Wikidata/relevancy.md`

We must rework how core class instances are captured. Right now, simply being instance of that subclass qualifies for being handed down to future pipelines. What we need is a real analysis and classification of the wikidata entries. Something like
* desired / relevant / interesting
* undesired / not relevant / not interesting
or similar. It could also be a boolean, "relevant:True". Currently we use "listed" for broadcasting programs.
What that means:
* a broadcasting program listed in data/00_setup/broadcasting_programs.csv is "relevant:True". We may find other broadcasting programs, but only those listed there are relevant.
* Any season or episode that is "part of the series (P179)" of any of those relevant (relevant:True) broadcasting programs is also relevant (relevant:True). Thus, relevance can be passed on through a direct link. This is where we get into some issues:
  * We must make this inheritance context sensitive.
    * Can inherit: episode instance --"part of the series (P179)"--> broadcasting program instance
    * Can not inherit: person instance --"likes show"--> broadcasting program instance
  * Since we don't know yet how each of those connections are modeled in Wikidata, and if that may change from user to user or even over time, we must build a dynamic structure for this:
    * Keep track of all kinds of direct connections between core class instances.
    * Make it easy to greenlight any of those identified connections, e.g. a csv with all of them structured like 
      * "subject,property,object,can_inherit", 
    * and each row contains looks like 
      * "episode (Q1983062)","part of the series (P179)","broadcasting program (Q11578774)",
    * and then users could just inspect the csv and if they add anything to the end of that row, it'll detect as can_inherit and allow relevancy to be inherited.
    * Naturally, this means that these decisions must be persisted and not just overwritten when the detected links csv is printed next.

Relevancy can only be gained, not lost.

We begin relevancy propagation from our 15 listed broadcasting programs.
Relevancy can propagate over inlinks and outlinks.
Episode -part of series-> broadcasting program (relevant)
* Now the episode is relevant, too
 Episode (relevant) - guest -> person
*Now the person is relevant, too

Being relevant means two things:
A) relevant nodes are being allowed to be expanded. For now, this rule coexists with all other expansion rules. Eventually, it may replace them. For now: if relevant= true then expandable = true
B) Only relevant nodes are allowed in the "instance_core_*.JSON. all non-relevant core_class instances may still be written to a similar file, yet that one needs to be explicitly marked as "not_relevant_instance_core_*.JSON", or similar

To ensure these properties are properly captured, add them to the list of properties captured during hydration.



### Fix Projections
* entity_store.jsonl 
This currently seems to be a json file dumped into a jsonl file. It is probably a failed sidecar of the `entity_chunks` and `entity_lookup_index.csv` entity writing rework. Very likely, it can be deprecated. 

### Add additional projections
* classes.json
A projection of all information we have on all classes.
* properties.json 
A projection of all information we have on all properties.

