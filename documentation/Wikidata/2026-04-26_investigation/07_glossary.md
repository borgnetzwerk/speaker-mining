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
  * **Resolution (C1.9):** Two classes of emitter exist. (a) The **traversal engine** writes primary observation events as it fetches data: `entity_discovered`, `triple_discovered`, `entity_expanded`, `query_response`. (b) **Derivation handlers** may also write computed conclusion events: `relevance_assigned`, `class_membership_resolved`. Both are valid emitters; the distinction matters for understanding which events are facts vs which are inferences.

### Projection ✓
A derived artifact (CSV, JSON, parquet) written by an EventHandler. A projection is never the source of truth — it is always rebuildable from the event store by re-running the EventHandler from sequence 0. Projections are the interface between Notebook 21 and downstream phases.

### Triple ✓
A `(subject_qid, predicate_qid, object_qid)` relationship extracted from a Wikidata entity's claims. Triples are stored as `triple_discovered` events. They represent the graph edges that the expansion engine (v4: `fetch_engine`) traverses.
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

### class_hierarchy_resolution ✓
*(formerly also documented as "Class Resolution" — merged; the two described the same operation)*

The operation performed by the ClassHierarchyHandler when a new class QID is `entity_discovered`. It walks the P279 (subclass-of) chain upward from the class QID until either a core class is reached, a root class (Q35120 = entity, Q1 = Universe) is encountered, or the configured depth limit (n, currently 5) is exceeded. On completion, a `class_resolved` event is emitted and the result is stored in `class_resolution_map.csv`. A class node is "resolved" when its parent chain reaches a core class.

`class_hierarchy_resolution` operates from the ClassHierarchyHandler's own priority queue — independent of the `basic_fetch` classification logic. When this queue is non-empty, it takes precedence over other work because a reliable class tree is foundational to relevancy propagation.

`class_hierarchy_resolution` fires for `potentially_relevant` nodes. It does not fire for `unlikely_relevant` nodes.

### Active Class ⚠ (term to be renamed — concept resolved)
Currently used in the preflight step to mean "a class QID that appears in at least one P31 or P279 claim of any known entity". Used to seed the `class_hierarchy_resolution`.

**Concept resolution (C7.5):** The ClassHierarchyHandler owns this concept. A class becomes "active" (referenced by our graph) when the handler observes it in a P31 or P279 claim on any discovered entity. The handler is responsible for maintaining the full class hierarchy, recording which classes are currently referenced vs merely cached-but-unused.

**Naming status:** The term "active class" is imprecise and needs replacement. The distinction is:
- A class that has been **referenced** in at least one triple of a discovered entity — the ClassHierarchyHandler should walk its P279 chain
- A class that is merely **known** (appeared in a cache entry or a prior walk) but not yet referenced — tracked but not part of active analysis

The replacement term has not yet been decided. See the naming decisions document.

  * **Clarification (original):** Active classes are classes that are part of the graph we care about - inactive classes are not that, yet. We maybe should try to find a new term for this.
  * **Clarification (original):** Question: Why can't a derivative Event handler trigger the upward walk? This EventHandler may be the "Class Hierarchy Handler" that then also is responsible for maintaining the memory of where this class fits in the larger tree, if it's active or not, etc. We currently have this logic already, we just need to hand it over to a (new) event handler (or multiple).
  * **Resolution:** ClassHierarchyHandler is the answer. See C7.5. Naming still pending.

### Projection Mode ✓ (retired)
The `projection_mode` field in `core_classes.csv` (binary `instances` / `subclasses`) is **retired**. In v4, both instance projections (P31-based) and subclass projections (P279-based) are always produced for every core class. Sub-projections (e.g. a dedicated "guest" projection for persons) may be added as a later enhancement but are not part of the initial v4 design. See `11_naming_decisions.md` §5.

  * **Clarification:** What we do need is at least a twofold abstraction: One for instances, and one for subclasses. Then - maybe alongside them, maybe inside them - we need more nuanced separations: A person may be object of a relevant episode. Then they are a really interesting kind of person: A "guest". So maybe, we need a dedicated guest projection. It may also be the case that we differentiate such differences at a later stage when we need to - but then we need to make sure this context is clear and easy to retrieve. Both approaches seem reasonable (doing it here all at once while we have the context or doing later when needed, and then try to find the context in the projections). We need to pick the one that is most reasonable.
  * **Resolution:** `projection_mode` retired. Both projections (instances + subclasses) always produced. Sub-projections deferred. See `11_naming_decisions.md` §5.


---

## Graph Traversal Concepts

### Seed ✓
A starting QID for graph traversal. Seeds are defined in `data/00_setup/broadcasting_programs.csv`. Traversal begins from seeds and expands outward through discovered triples.

### Expansion ✓ (retired — split into full_fetch + fetch_decision)
Was overloaded to mean two things; both have been renamed:
(a) **Entity fetch** → **`full_fetch`**: retrieve all Wikidata claims for a QID and store them as events. See `full_fetch` entry.
(b) **Traversal decision** → **`fetch_decision`**: inspect a `full_fetch`ed entity's triples and decide which referenced QIDs to queue for `full_fetch` next. See `fetch_decision` entry.

The term "expansion" and all derived forms ("expand", "expanded", "expansion engine") are **retired from v4 vocabulary**. The engine is the **`fetch_engine`**.

  * **Clarification (original):** Yes - we should mean this, a node is expanded from being one single node to having retrieved ALL the claims there are on this node, incoming and outgoing. If we need to find a new word for that, we should do that.
  * **Resolution:** Split into `full_fetch` (a) and `fetch_decision` (b). See `11_naming_decisions.md` §1.

### basic_fetch ✓
*(old name: `hydration` — retired)*

A minimalistic, structured, mass-capable fetch that retrieves only:
- label + description + aliases (all configured languages + Wikidata default language)
- P31 (instance-of) + P279 (subclass-of) claims

Enough to know *what a node is* without knowing everything it links to. Because the payload is fixed and predictable, `basic_fetch` can be issued for many nodes in a single batch call, minimizing Wikidata API burden. Distinct from `full_fetch` (which retrieves all claims for one node) and from `fetch_decision` (which is the decision layer that queues QIDs for `full_fetch`).

  * **Clarification (original):** hydrate is a very minimalistic fetch: label, description and aliases in a selected set of languages (+ the "default for all languages" always, a wikidata concept that every item has), + the "instance of" and "subclass of" claims. This is a very minimalistic fetch to understand what the node is about - it's much less than a full fetch (with an unknown number of claims), and 100 % structured. This also means it can have potential to mass hydrate any number of nodes at a time, since we know the payload structure. This advantage can be used to lower the burden on wikidata services. We should try to always find a way that is most suitable to get just exactly the data we need from wikidata with the way that puts the lowest burden on the wikidata service
  * **Resolution:** Term renamed from `hydration` to `basic_fetch`. See C14.1 and `11_naming_decisions.md` §2.

### potentially_relevant ✓
A discovered entity whose connection to a relevant entity comes through a predicate that appears in `relevancy_relation_contexts.csv`. Because the connecting predicate is approved for relevancy propagation, this entity **may** inherit relevancy once its class is known. It is queued for immediate `basic_fetch` (and class_hierarchy_resolution) so that its class can be established and the relevancy rule evaluated.

A `potentially_relevant` node is not yet relevant — it is a candidate. Once `basic_fetch` completes, the RelevancyHandler evaluates whether the matching relevancy rule applies and, if so, emits `entity_marked_relevant`.

### unlikely_relevant ✓
A discovered entity whose connection to a relevant entity comes through a predicate that does NOT appear in `relevancy_relation_contexts.csv`. Under current rules, this entity cannot inherit relevancy through this connection. Its `basic_fetch` is deferred — either processed at the end of the run, or skipped entirely (configurable via `deferred_basic_fetch_mode`; default: skip).

If the relevancy rules change and the connecting predicate is later added to `relevancy_relation_contexts.csv`, a `rule_changed` event triggers re-evaluation: `unlikely_relevant` entities connected via the newly-whitelisted predicate are promoted to `potentially_relevant` and queued for immediate `basic_fetch`.

### Relevancy ✓
An entity is relevant if it should appear in the Phase 2 output. Relevancy is determined as follows:

1. **Seeds are authoritatively relevant** — no propagation rule required.
2. **Propagation via approved triples** — an entity connected to a relevant entity via an approved relevancy rule also becomes relevant.
   1. **Example:** Guests of relevant episodes are relevant. Topic/subject mention does NOT confer relevancy — if a relevant episode lists "topic: Barack Obama", Obama is not relevant; he was referenced, not present as a speaker.
3. **Relevancy is binary and monotonically increasing** — once relevant, always relevant; relevancy cannot be lost.

  * **Clarification (original):** The seed entities are authoritatively relevant - they are the objects of interest. Then - relevancy is propagated. A concrete example: We want to learn about speakers in a talk show. So we look up the talk show on wikidata and store it in our setup file. Everything else must be done by our relevancy propagation: The talk show is relevant, so every season that is part of that talk show must be relevant, too. Also every episode belonging to that show's seasons - and also every episode that directly says it belongs to the talk-show, but is not listed in any of its seasons. Then - we look into each of those episodes, and find guests. Guests are very relevant, since ever guest is a speaker, for our purposes. Naturally, the host is also a speaker, so they are also relevant. HOWEVER: If the episode has "topic: barack obama", then barack obama is not a speaker - he was not even there, we was just talked about. He is thus not relevant. That does not mean he is never relevant - if he ever is invited as a guest, he will be relevant. Thus: Relevancy can only be gained, not lost.
  * **Resolution:** Relevancy is binary. Seeds are authoritative. See C15.1–C15.5.

### Relevancy Propagation ✓
The process of marking an entity as relevant because it is connected to an already-relevant entity via an approved triple. Governed by `relevancy_relation_contexts.csv`. Propagation can be forward (subject → object) or backward (object → subject).

### Relevancy Rule ✓
A row in `relevancy_relation_contexts.csv` specifying `(subject_core_class, property, object_core_class, can_inherit)`. When a triple matches a rule and the subject is relevant, the object also becomes relevant (or vice versa for backward rules).
  * **Clarification:** We need to closely monitor these rules. We need to be able to later amend those rules, "overruling" their verdicts, etc. For example, if we find that not "part of series" sometimes also targets "Top 1000 Talk show episodes streamed in canada", we must prevent that all those talk show episodes suddenly become relevant just because they were mistaken for a "talk show season". We must keep a close eye on the rules, what decisions they result in, and how we need to modify them.

### basic_fetch Rule ✓
*(evolved from "Hydration Rule"; standalone `basic_fetch_rules.csv` file — retired)*

There is no separate `basic_fetch` rule config file. The trigger for `basic_fetch` is determined by the **classification of discovered entities** as `potentially_relevant` or `unlikely_relevant` (see those entries). The classification is derived directly from `relevancy_relation_contexts.csv` — no independent predicate list is maintained.

**Immediate basic_fetch:** `potentially_relevant` nodes — connecting predicate is in `relevancy_relation_contexts.csv`. class_hierarchy_resolution fires for these.

**Deferred basic_fetch:** `unlikely_relevant` nodes — connecting predicate is NOT in the relevancy rules. Behavior governed by config `deferred_basic_fetch_mode`:
- `"never"` (default): skip entirely unless rules change
- `"end_of_run"`: process after all immediate work is complete
No class_hierarchy_resolution for `unlikely_relevant` nodes.

**ClassHierarchyHandler independence:** The ClassHierarchyHandler has its own P279-walk queue and its own logic governing which class QIDs it queries and when it stops. When a `potentially_relevant` entity is `entity_discovered`, the ClassHierarchyHandler acts independently — it may use the same `basic_fetch` API calls internally but governs its own scope. A non-empty ClassHierarchyHandler queue takes priority, as a reliable class tree is the foundation of relevancy propagation.

**Rule change handling:** When `relevancy_relation_contexts.csv` changes, a `rule_changed` event is emitted. The `basic_fetch` handler and ClassHierarchyHandler each track the rule version they last applied. On `rule_changed`, the `basic_fetch` handler re-evaluates all deferred `unlikely_relevant` QIDs and promotes any whose predicate is now whitelisted.

  * **Clarification:** Currently unknown. Part of our design plan to specify this. 
  * **Clarification:** There is one reason why we could keep the basic fetch logic in place: To reduce or postpone fetching of nodes that may never become relevant. Some remarks: (1) If a relevant node is linked to a node that may be able to inherit relevancy (i.e. through a whitelisted relevancy propagating triple constellation) we 100% must basic_fetch and upwards-walk this node. (2) If a relevant node is linked to a node that cannot inherit relevancy (just by virtue that the connecting property is not yet whitelisted), we don't necessarily need to basic_fetch — we already know it can't qualify for relevancy propagation. This means we can postpone those fetches to focus on more relevant nodes first. The upwards walk should also only fire for nodes that — if walk successful — could then qualify for relevancy. Rule changes must be tracked; this is likely where the original basic_fetch rule (= upwards walk rule) stems from.
  * **Clarification:** ClassHierarchyHandler does its upwards walk separately from the basic_fetch logic. When a `potentially_relevant` node is `entity_discovered`, the ClassHierarchyHandler acts independently. It may use the same `basic_fetch` API calls and functions, but governs its own logic for what to query and when to stop. A non-empty ClassHierarchyHandler queue is high priority — a reliable class tree is the basis for much of the system.
  * **Resolution (Q6, revised):** Standalone `basic_fetch_rules.csv` retired. Trigger is derived from `relevancy_relation_contexts.csv`. Classification: `potentially_relevant` (immediate `basic_fetch` + `class_hierarchy_resolution`) vs `unlikely_relevant` (deferred, no `class_hierarchy_resolution`). `deferred_basic_fetch_mode` config governs deferred behavior. Resolves TODO-043.

---

## Operational Concepts

### Relevant ✓
A "relevant entity" is one that has been marked as relevant (see Relevancy above). The binary distinction between "relevant" and "not relevant" is meaningful data: "not relevant" means the entity is known but does not currently satisfy any propagation path from any seed. Not-relevant entities appear in `not_relevant_core_<class>.json` and may become relevant in future runs.

  * **Clarification (original):** Yes. we must differentiate between "relevant" (meaning: we want to know more about this, we must be able to talk about this, we must be able to analyze this) and "not relevant" (meaning: yes, we know it's there, but it matters not for our analysis. We're doing speaker mining, we know there are 8.3 billion people on the world, but we need to narrow this down to the few that spoke in one of our 15 broadcasting programs).
  * **Resolution:** Relevancy is binary. See C15.4–C15.5.

### Fully Fetched ✓
*(old name: "fully expanded" — retired)*

A QID is "fully fetched" if a `full_fetch` has been performed for it — all of its Wikidata claims (incoming and outgoing) have been retrieved and stored as events.

**Resolution (C7.3):** Fetch rules govern *which* nodes are `full_fetch`ed; the `full_fetch` itself is always a complete link retrieval (all incoming + outgoing claims). So "fully fetched" simply means "a `full_fetch` has been performed for this QID at least once under the current config version".

**Resolution (C7.4):** Fetch rules and relevancy rules are **separate rulesets** serving different purposes:
- **Relevancy rules** (`relevancy_relation_contexts.csv`) govern which entities are *of interest* — any entity reachable via an approved propagation path from a seed.
- **Fetch rules** govern which *relevant* entities receive a `full_fetch`. The criteria are "relevant AND X": permitting conditions (e.g. "is instance of human", "is instance of core class") grant `full_fetch`; disqualifying types (e.g. "is a class node") exclude it.

Consequence: **not all relevant entities are fully fetched**. Class nodes (e.g. occupation QIDs) are relevant but are never `full_fetch`ed — their P279 chain is walked via `basic_fetch` only. The 250+ relevant occupation class nodes are a concrete example.
  * **Clarification:** There will be relevant nodes that we cannot fully fetch. For example, we should likely never full_fetch a class node, yet, we will have 250+ relevant class occupations. Fundamentally:
    * Every fully fetched node must be relevant.
    * Not every relevant node must be fully fetched.
    * The full fetch decision is always a "relevant AND X" decision, where relevant is the prerequisite, and then there are some additional rules that must be at play. Those could be automatically disqualifying types (e.g. "is a class") or, barring none of those, one of the permitting ones (e.g. "is instance of human" or "is instance of core class" or similar. There can also be combinations: "Is instance of Human AND has property country:germany".

  * **Clarification (original):** Fully expanded means "we have all links (in and out) to this node. expansion rules should only specify what nodes should be expanded - the expansion itself is always just a "fetch all links with this node as subject/object".
  * **Clarification (original):** We must think about the overlap in "Expansion rules" and "relevancy rules".

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

### Handover Projection ✓
A projection written for downstream consumption (Phase 31+). Phase 2 sets the output contract; downstream phases adapt to it, not the other way around. Phase 2 should produce the richest correctly-structured output it can. Downstream notebooks select what they need from a richer structure.

The minimal output contract is therefore defined by what Phase 2 *can* produce, not by what Phase 3 *currently* reads.

  * **Clarification (original):** We won't know because the old Phase 3 design is build on the old Phase 2 design. So generally: We make the rules here. Whatever structures we can provide, we should. Then, in a future rework, we rework Phase 3 to be able to better use our data. For now: Think about the fact that Phase 3 needs our data, but don't think about how it expects our data. We can update phase 3 later.
  * **Resolution:** See C16.1–C16.2.

### Entity Lookup Index ✓
A CSV/parquet file mapping QIDs to labels, used by downstream notebooks to resolve QID strings to human-readable labels. Currently `entity_lookup_index.csv`. Must be comprehensive enough that no QID in any output file is label-less.

---

## Terms to Consider Renaming or Retiring

| Old Term | Issue | **Final name** |
|----------|-------|----------------|
| `materializer` / `_materialize` | Deprecated per C1.6 | **(removed)** |
| `node store` | Conflates entity cache with projection layer | **entity_store** |
| `hydration` | Jargon; no universally agreed meaning | **basic_fetch** |
| `expansion` (retrieve claims) | Overloaded (conflated retrieval + traversal) | **full_fetch** |
| `expansion` (decide next QIDs) | Overloaded; "expansion" retired from v4 | **fetch_decision** |
| `active class` | "Active" is relative and imprecise | **referenced_class** (+ **known_class** for walked-but-unused) |
| `checkpoint` | Deprecated per C2; was overloaded with "backup" | **(removed)** |
| `core class entity` | Conflates instance and subclass relationships | **CoreClassInstance** / **CoreClassSubclass** |
| `preflight` | Steps 2.4–2.5 collectively; no longer a named phase | **(removed — subsumed by ClassHierarchyHandler)** |

---

## Open Questions Status

| # | Status | Question | Resolution |
|---|--------|----------|------------|
| Q1 | ✓ RESOLVED | What are the final event types? Are new types needed? | See `12_event_catalogue.md`. `entity_basic_fetched` added as new v4 event. |
| Q2 | ✓ RESOLVED | Is "expansion" split? Final names? | `full_fetch` (retrieve claims) + `fetch_decision` (queue next fetches). "Expansion" retired from v4. |
| Q3 | ✓ RESOLVED | Is "hydration" distinct from general fetch? | Yes — minimalistic, structured, mass-capable. See C14.1–C14.4. |
| Q4 | ✓ RESOLVED | Is relevancy binary or confidence-level? | Binary and monotonic. See C15.4. |
| Q5 | ✓ RESOLVED | What triggers P279 class resolution walk in a handler-driven system? | ClassHierarchyHandler: reacts to entity/triple events, walks P279 incrementally. See C7.5. |
| Q6 | ✓ RESOLVED | What governs which discovered objects get `basic_fetch`ed? | Standalone `basic_fetch_rules.csv` retired. Trigger derived from `relevancy_relation_contexts.csv`. `potentially_relevant` vs `unlikely_relevant` classification governs immediate vs deferred `basic_fetch`. See basic_fetch Rule entry. |
| Q7 | ✓ RESOLVED | How is "fully fetched" defined with rule sensitivity? | Fetch rules and relevancy rules are separate. Not all relevant nodes are full_fetched (class nodes excluded). Criteria = "relevant AND [permitting conditions]". See Fully Fetched entry. |
| Q8 | ✓ RESOLVED | Complete file list Phase 31 reads from Phase 2? | Phase 2 sets the contract; Phase 3 adapts. See C16.1–C16.2. |
| Q9 | ✓ RESOLVED | Does `projection_mode` survive or is it replaced? | `projection_mode` retired. Both instance + subclass projections always produced. Sub-projections deferred. See `11_naming_decisions.md` §5. |
