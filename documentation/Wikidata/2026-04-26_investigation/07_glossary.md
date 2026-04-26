# Notebook 21 Redesign — Glossary
> Created: 2026-04-26  
> Status: DRAFT — terms marked ❓ require clarification before design can proceed.  
> Purpose: Establish a shared, precise vocabulary before any module or data structure is designed. Per Clarification C11: concepts that cannot be defined in one sentence need to be broken apart first.

---

## How to Use This Document

Read each term. If the definition is wrong, incomplete, or the term should be renamed — annotate with `* **Clarification:**`. If a term is marked ❓, a decision is needed before implementation begins. Terms marked ✓ are considered agreed.

---

## Core Data Concepts

### Event ✓
An immutable, append-only JSON record that describes something that happened in the system. Events are written to the event store and are never modified or deleted. They are the single source of truth from which all other state is derived.

### Event Store ✓
The set of append-only JSONL chunk files (`data/20_.../wikidata/chunks/`) that hold all events. Once written, a chunk file is never modified. New events are appended to the current chunk. The event store is the system's permanent memory.

### Event Type ✓
The `event_type` field on each event. Currently known types include:
`query_response`, `entity_discovered`, `entity_expanded`, `triple_discovered`, `class_membership_resolved`, `relevance_assigned`

❓ **Are these the complete and final set of event types? Are any of these being deprecated in the redesign? Are new types needed?**
  * **Clarification:** Very likely, these events are not the final ones. It is almost certain that future iterations will add new events. It is even possible or maybe even desirable that throughout this redesign, we add plenty of additional events. Remember: Events are persistent changes in the state of our system. There are plenty of event handlers that may want to emit such events. Also: We must align these terminologies with this glossary. It is posisble that future "entity_discovered" events will not be named such, since "discovered" is on the "maybe to vague" list. As such, I would recommend a dedicated event list, maybe here as #### event_name, or even in a dedicated file. Every event documented like this should have all the context it needs: Who fires it, who reads it, what does it represent, what is the general structure - maybe even some statistics and analysis - so many do we have so far, this is very important and must not be changed (e.g. query_response) or this is a recently implemented event with still some potential for refinement (e.g. Relevance_assigned). Overall: Just because this is the set of events that existed before the rework, it does not mean its the future set: Both because a) the old code needs to be redesigned precisely because it did not use the event store properly, and b) since many events and concepts will be broadened, maybe the events reflecting them also need to be changed.
  * **Clarification:** Keep in mind that all prior events will remain in the event log. We must be able to work with those old ones no matter what. Thus, we must never forget the old ones, and never forget how to interpret them for our new logic.

### EventHandler ✓
A class that reads events from the event store in order, reacts to relevant event types, maintains derived state, and writes a projection file. Every EventHandler persists at least its `last_processed_sequence` so it can resume from where it left off on the next run.
  * **Clarification:** Question: Who writes / creates the events?

### Projection ✓
A derived artifact (CSV, JSON, parquet) written by an EventHandler. A projection is never the source of truth — it is always rebuildable from the event store by re-running the EventHandler from sequence 0. Projections are the interface between Notebook 21 and downstream phases.

### Triple ✓
A `(subject_qid, predicate_qid, object_qid)` relationship extracted from a Wikidata entity's claims. Triples are stored as `triple_discovered` events. They represent the graph edges that the expansion engine traverses.
  * **Clarification:** In the last version of the tripple overview projection, we omitted additional context (such as "triple has reference", such as sources, or "triple has qualifier", such as start or end date). Our system must generally accomodate for those qualifiers and references; and while the overview projections should reduce this for the sake of simplicity, we should at least keep a note of "qualifiers" and "reference" so we can look those up. Instead of just storing "has_qualifier", it may be wise to store the qualifier properties PIDs here, separated with pipes, then we can get an additional glimpse of detail before we catually have to look at the subject note to find the full qualifier.

---

## Entity Classification Concepts

### Core Class ✓
One of the 7 top-level entity categories that the pipeline targets, as defined in `data/00_setup/core_classes.csv`:
- Q215627 — person
- Q214339 — role
- Q43229 — organization
- Q1983062 — episode
- Q7725310 — series
- Q11578774 — broadcasting program
- Q26256810 — topic

### Core Class Entity ❓
An entity that "belongs to" a core class. Currently unclear whether this means:
(a) An entity whose P31 chain leads to a core class (instance mode), or
  * **Clarification:** Correct, this is a "Core Class Instance"
(b) An entity whose P279 chain leads to a core class (subclass mode), or
  * **Clarification:** Correct, this is a "Core Class Subclass"
(c) Either, depending on the core class.
  * **Clarification:** No. It's always both. It's just that we sometimes are interested in one more than the other - we don't care so much about different "types" of person, but we very much care about different "instances" of person. For roles, it's the opposite: Role instances are usually barely relevant, where role subclasses are very often used. At the same time, we may care for classifying the episode instances by the episode subclasses they belong to. Thus, we always need both. It's just when it comes to downstream processing or handling relevancy propagation that we must be careful what type we use. So long as we keep both, and within those, always keep all the context - we should be fine.

**This term may need to be split or replaced.** See Clarification C3.4 and C12.1.

### Instance (of a class) ✓
A Wikidata entity that has a P31 (instance-of) claim pointing to a class. Example: Q43773 (Markus Lanz) has P31 → Q5 (human). The entity is an instance, not a class itself.

### Class Node ✓
A Wikidata entity that participates in a P279 (subclass-of) chain rather than (or in addition to) P31. Class nodes are not instances — they are types. Example: Q1930187 (journalist) has P279 → Q28640 (profession) → ... → Q214339 (role).

### Class Resolution ✓
The process of following P279 chains from a class node upward until a core class is reached. The result is stored in `class_resolution_map.csv`. A class node is "resolved" when its parent chain reaches a core class.

### Active Class ❓
Currently used in the preflight step to mean "a class QID that appears in at least one P31 or P279 claim of any known entity". Used to seed the P279 upward walk.

**Is this concept needed in the redesign? If handlers drive class resolution, what triggers the upward walk?**
  * **Clarification:** Active classes are classes that are part of the graph we care about - inactive classes are not that, yet. We maybe should try to find a new term for this. We have plenty of classes that are never used - we still need to know about them, since maybe some future discovery tries to connect to them and then we'll be happy to remember when we last used them and how they are connected to our core classes - but until then, we don't care for them. They should not be part of our analysis, not part of our visualizations, they are just in cache waiting to be useful one day. They are just classes we know to maybe be useful, but currently, they are not yet.

### Projection Mode ❓
Currently `projection_mode` in `core_classes.csv` is either `instances` (use P31-based lookup) or `subclasses` (use P279-based lookup) when writing `core_*.json`. This binary may be insufficient.

**Does each core class need a richer rule set, or is instances/subclasses the right abstraction?**
  * **Clarification:** What we do need is at least a twofold abstraction: One for instances, and one for subclasses. Then - maybe alongside them, maybe inside them - we need more nuanced separations: A person may be object of a relevant episode. Then they are a really interesting kind of person: A "guest". So maybe, we need a dedicated guest projection. It may also be the case that we differentiate such differences at a later stage when we need to - but then we need to make sure this context is clear and easy to retrieve. Both approaches seem reasonable (doing it here all at once while we have the context or doing later when needed, and then try to find the context in the projections). We need to pick the one that is most reasonable.


---

## Graph Traversal Concepts

### Seed ✓
A starting QID for graph traversal. Seeds are defined in `data/00_setup/broadcasting_programs.csv`. Traversal begins from seeds and expands outward through discovered triples.

### Expansion ❓
Currently overloaded to mean two things:
(a) **Entity fetch**: fetching a QID's Wikidata claims and storing them as events.
  * **Clarification:** Yes - we should mean this, a node is expanded from being one single node to having retrieved ALL the claims there are on this node, incoming and outgoing. If we need to find a new word for that, we should do that.
(b) **Link traversal**: following the discovered claims to find new QIDs to fetch.

**Should these be two distinct named operations? If so, what are the new names?**

Candidate names:
- **Fetch** — retrieve entity data for a QID from Wikidata (or cache), emit entity events
- **Traverse** — follow the links on a fetched entity to discover new QIDs eligible for fetching

### Hydration ❓
Currently means: fetch entity data for a QID that was first encountered as an *object* of a triple (not as a subject), when that QID has not been fetched yet. Similar to expansion, but triggered by property link rather than by graph traversal.

**Is "hydration" a distinct concept in the redesign, or is it subsumed by the general "fetch" operation under a rule?**

### Relevancy ❓
An entity is "relevant" if it should appear in the Phase 2 output. Currently determined by two conditions:
1. It is an instance/subclass of a core class.
2. It is reachable from the seed set via an approved relevancy propagation path.

**Is this definition complete? What makes a seed itself relevant? Is relevancy binary or could it have confidence levels?**

### Relevancy Propagation ✓
The process of marking an entity as relevant because it is connected to an already-relevant entity via an approved triple. Governed by `relevancy_relation_contexts.csv`. Propagation can be forward (subject → object) or backward (object → subject).

### Relevancy Rule ✓
A row in `relevancy_relation_contexts.csv` specifying `(subject_core_class, property, object_core_class, can_inherit)`. When a triple matches a rule and the subject is relevant, the object also becomes relevant (or vice versa for backward rules).

### Hydration Rule ❓
The equivalent of a relevancy rule, but for the hydration operation. Currently implemented as a hardcoded predicate whitelist (P106, P102, P108, P21, P527, P17). Per TODO-043, this should become a config file with parallel structure to `relevancy_relation_contexts.csv`.

**What is the correct structure for hydration rules? What columns are needed?**

---

## Operational Concepts

### Relevant ❓
See "Relevancy" above. Used as an adjective: a "relevant entity" is one that has been marked as relevant.

### Fully Expanded ❓
A QID is "fully expanded" if all of its Wikidata links have been fetched and stored as events. Currently this is tracked as a `seed_fully_expanded` event (or similar). But "fully expanded" is ambiguous if the expansion rules change — an entity expanded under old rules may not be fully expanded under new rules.

**How does the redesign define "fully expanded" in a way that is sensitive to rule changes?**

### Resume ✓
On re-run, the system continues from where each EventHandler last left off. There is no separate checkpoint mechanism — EventHandler progress is the resume state.

### Cache ✓
The local storage of Wikidata API responses (`data/20_.../wikidata/`), keyed by endpoint + query. Cache-first means: if a response exists in cache, it is used without a network call. Per `Wikidata.md`, cache entries are valid for 365 days.

### Budget ✓
A configurable limit on the number of network calls a run may make. `max_queries_per_run = 0` means cache-only mode. Budget is decremented per network call across all steps in a run.

---

## Output Concepts

### Core Output File ✓
A `core_<class>.json` file in the projections directory. One file per core class. Contains all entities belonging to that core class that are both discovered and relevant. Written by an EventHandler at the end of the run (output-only, not read back by Phase 2).

### Handover Projection ❓
A projection that is written for downstream consumption (Phase 31). These include the `core_*.json` files and the `projections/*.csv` files that Phase 31 reads.

**What is the complete list of files that Phase 31 reads from Phase 2? This defines the minimal output contract.**

### Entity Lookup Index ✓
A CSV/parquet file mapping QIDs to labels, used by downstream notebooks to resolve QID strings to human-readable labels. Currently `entity_lookup_index.csv`. Must be comprehensive enough that no QID in any output file is label-less.

---

## Terms to Consider Renaming or Retiring

| Current Term | Issue | Candidate Replacement |
|---|---|---|
| `materializer` / `_materialize` | Deprecated per C1.6; implies a monolithic rebuild | (no replacement — this concept is removed) |
| `node store` | Conflates "entity document cache" with "projection" | `entity cache`, `entity document store` |
| `hydration` | Overloaded; unclear how it differs from expansion | `property-link fetch`? Needs decision. |
| `expansion` | Overloaded (fetch + traverse) | `fetch` + `traverse`? Needs decision. |
| `active class` | Unclear in context of handler-driven resolution | Possibly replaced by handler-driven concept |
| `checkpoint` | Deprecated per C2; was overloaded with "backup" | (no replacement — concept is removed; backup is the correct term for event store copies) |
| `core class entity` | Unstable per C3.4 | May need to be split into `core instance`, `core class node`, `core output entity` |
| `preflight` | Steps 2.4–2.5 collectively | Needs a name in the redesigned step sequence |

---

## Open Questions Requiring Decisions

The following questions must be answered before the design document can be written:

| # | Question | Section |
|---|----------|---------|
| Q1 | What are the final event types? Are new types needed? | Event Type |
| Q2 | Is "expansion" split into "fetch" + "traverse"? If so, what are the final names? | Expansion |
| Q3 | Is "hydration" a distinct concept or subsumed by the general fetch-under-rule operation? | Hydration |
| Q4 | Is relevancy binary, or does it have confidence levels? | Relevancy |
| Q5 | What triggers the P279 upward class resolution walk in a handler-driven system? | Active Class |
| Q6 | What is the column structure for `hydration_rules.csv`? | Hydration Rule |
| Q7 | How does the redesign define "fully expanded" in a way sensitive to rule changes? | Fully Expanded |
| Q8 | What is the complete list of files that Phase 31 reads from Phase 2? | Handover Projection |
| Q9 | Does `projection_mode` (instances vs subclasses) survive, or is it replaced by per-class rules? | Projection Mode |
