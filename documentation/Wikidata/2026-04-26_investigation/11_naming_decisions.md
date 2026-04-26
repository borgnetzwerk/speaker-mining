# Notebook 21 Redesign — Naming Decisions
> Created: 2026-04-26  
> Purpose: Settle on one final name per concept. For each concept: what the old name was, what the problem was, what the candidates are with brief reasoning, and the **decided** name.  
> Status: DRAFT — items marked ✓ are decided; items marked ❓ need a decision before design begins.

This document is the authoritative naming reference. Once a name is decided here, all other documents (glossary, rules catalogue, design document, code) use that name.

---

## How to Use This Document

For each concept: read the "problem" and "candidates" briefly, then look at the decision. If you disagree with a decision, annotate it. Decisions marked ✓ are final unless explicitly overridden.

---

## 1. "Expansion" → split into Fetch + Traverse

**Old name:** `expansion` (used in `expansion_engine.py`, `entity_expanded` event, "Step 6 expansion stage")

**Problem:** Currently conflates two distinct operations:
- (a) Retrieving all Wikidata claims for a single QID and storing them as events
- (b) Deciding which QIDs discovered in those claims should themselves be retrieved next

These have different triggers, different costs, different config, and different failure modes. Conflating them under one name makes the design opaque.

**Candidates for (a) — the retrieval operation:**

| Name | Reasoning |
|------|-----------|
| `fetch` | Short, accurate — we're fetching data. Common term. No ambiguity. |
| `expand` | Current name. Intuitive if you think of expanding a node. But overloaded. |
| `full_fetch` | Distinguishes from hydration. But "full" implies there's a "partial" fetch — redundant once hydration is named separately. |
| `entity_load` | "Load" suggests reading from disk, not from a network API. Wrong connotation. |
| `entity_retrieve` | Accurate but verbose. |

**Decision (a):** ✓ **`full_fetch`** — the operation that retrieves all claims for a single QID from Wikidata (or cache) and emits events. Named in contrast to `basic_fetch` (see §2): basic retrieves a fixed minimal payload; full retrieves everything. The corresponding event is `entity_fetched`.

  * **Clarification (original):** Since hydration may be named `minimal_fetch`, `full_fetch` would be more applicable. Noteworthy downsides are a) that "minimal" and "full" are not really opposite, but "maximal_fetch" sounds wrong as well. maybe name hydration `basic_fetch`
  * **Resolution:** Updated to `full_fetch`. The pair is `basic_fetch` / `full_fetch` — basic retrieves the fixed identity payload; full retrieves all claims. "Basic" and "full" are not strict antonyms but convey the right relationship: one is constrained and predictable, the other is unconstrained and complete.

---

**Candidates for (b) — the traversal decision:**

| Name | Reasoning |
|------|-----------|
| `traverse` | Standard graph term. "Traverse the graph" is natural and unambiguous. |
| `discovery` | Risks confusion with "entity discovered" event; overloaded. |
| `link_follow` | Accurate but mechanical-sounding. |
| `expansion` | Current name. If (a) is no longer called expansion, this could take the name. But "traverse" is clearer. |
| `graph_walk` | Accurate but verbose. |

**What operation (b) actually is — description:**

After a QID has been `full_fetch`ed, the event store holds a new set of `triple_discovered` events — each representing a claim from that entity to another QID. Operation (b) is the process of examining those newly stored triples and deciding which of the referenced QIDs should themselves be `full_fetch`ed next. This decision is governed by rules: for each triple, the system checks whether the predicate is followed, whether the source entity satisfies the subject conditions, and whether the target QID's class is eligible — and if so, the target QID is added to the pending fetch queue. The end result is a queue of QIDs to be processed in subsequent fetch cycles, extending the graph outward by one hop from the source entity.

In short: operation (b) is "inspect a fetched entity's triples; queue the eligible targets for fetching."

**Revised candidates with this description in mind:**

| Name | Reasoning |
|------|-----------|
| `expand` | "Expand the graph from a node" — intuitive, freed up now that (a) is `full_fetch`. The engine can still be called "expansion engine." Natural cycle: `full_fetch` → `expand` → `full_fetch` → ... |
| `follow` | "Follow links from a node" — plain English, clear direction. Simple. But "link follow" as a noun is slightly awkward. |
| `traverse` | Standard graph CS term. Unambiguous to developers familiar with graph algorithms. But user notes it's not self-evident for non-CS readers. |
| `queue_next` | Names the outcome (queue the next fetches) rather than the action. Accurate but imperative-style. |
| `advance` | "Advance the frontier." Algorithmically correct, but abstract. |

**Decision (b):** ✓ **`fetch_decision`** — the operation that inspects a `full_fetch`ed entity's triples, evaluates each referenced QID against traversal rules, and enqueues eligible QIDs for `full_fetch`. It is purely a *decision*: all it does is decide which QIDs should be fetched next. The cycle reads: `full_fetch` → `fetch_decision` → `full_fetch` → ... The engine that orchestrates this cycle is the **`fetch_engine`** (formerly "expansion engine" — that term is retired in v4).

  * **Clarification (original):** Traverse is also not very descriptive. Please write a full 3-4 sentence description of what action we're looking to name here.
  * **Resolution:** Description written above. `expand` proposed as interim name.
  * **Clarification:** this seems like a "fetch_decision" event. we have a few new nodes and decide to what degree we should fetch them. This also reflects that so far, this is only a decision - not really an action yet. All we do is decide what we want to do. Overall, it may be very wise to completely remove every aspect of "expand" or "expansion" to ensure every v4 concept is free of the old residual logic. No more hydration, no more expansion. We must also ensure this is consistent in the documentation, since the term (expansion, expand, expanded, ...) still appears quite a few times in the documentation/Wikidata/2026-04-26_investigation
  * **Resolution:** Updated to `fetch_decision`. "Expand"/"expansion" fully retired from v4 vocabulary. Engine is `fetch_engine`. All documentation updated accordingly.

---

## 2. "Hydration" — keep or rename

**Old name:** `hydration` (used in `run_property_value_hydration`, step 2.4.2)

**Problem:** The name "hydration" is water metaphor jargon. It has no universally agreed meaning in software. However, the concept has now been precisely defined: a minimalistic, structured, mass-capable fetch of label + description + aliases + P31 + P279 only.

**Candidates:**

| Name | Reasoning |
|------|-----------|
| `hydration` | Already used; the team has built shared understanding of what it means. Distinct from `fetch`. |
| `minimal_fetch` | Accurate but generic. Doesn't convey the mass-batch capability. |
| `shallow_fetch` | "Shallow" implies depth — but hydration isn't about graph depth, it's about claim breadth. Misleading. |
| `identity_fetch` | Captures the intent (fetching enough to identify a node) but unfamiliar. |
| `node_classification_fetch` | Accurate but verbose. |

**Revised candidates (adding `basic_fetch`):**

| Name | Reasoning |
|------|-----------|
| `basic_fetch` | Pairs naturally with `full_fetch`: basic = fixed payload, full = all claims. Honest about what it is. |
| `minimal_fetch` | Accurate but "minimal" and "full" aren't opposites — "minimal" implies the minimum possible, while "full" implies all. Slightly mismatched pair. |
| `identity_fetch` | Captures intent (fetch enough to know what a node is) but unfamiliar. Adjective: `identity-fetched` — also awkward. |
| `hydration` | **VETOED.** Legacy jargon with no agreed universal meaning. |

**On the adjective form:** `basic_fetch` produces `basic_fetched` (e.g. `entity.basic_fetched = True`) which is somewhat cumbersome compared to the clean `hydrated`. However, in code this is easily handled by naming the tracking event `entity_basic_fetched` or using a status enum (`BASIC_FETCHED`). The adjective form is a secondary concern; the primary concern is that the name is clear and consistent.

**Decision:** ✓ **`basic_fetch`** — the operation that retrieves the fixed identity payload (label, description, aliases, P31, P279) for a QID in a structured, mass-batchable call. Pairs with `full_fetch`. The adjective form in code will be `entity.basic_fetched` or tracked via a `entity_basic_fetched` event.

  * **Clarification (original — hard veto):** Hard veto, this term must go. The fact that it served a purpose in legacy code and that a dev team grew accustom to it bears exactly no meaning.
  * **Clarification (original):** `minimal_fetch` seems to be the most applicable of the given choice. To go better with `full_fetch`, maybe something like basic_fetch is more applicable. We should also consider if there is a suitable adjective form - "hydrated" was really helpful as a binary property word, while "basic-fetched" is a bit cumbersome - but that is a secondary concern. If the term works well, it works.
  * **Resolution:** `basic_fetch` adopted. `hydration` retired.

---

## 3. "Active Class" → new term for class referenced in the current graph

**Old name:** `active_class` (used throughout `subclass_expansion`, class resolution code)

**Problem:** "Active" is a relative adjective — active compared to what? The current code uses it to mean "a class QID that appears in at least one P31 or P279 claim of a currently known entity." But this description contains the semantic we want: the class has been *referenced* in our event store.

**Candidates:**

| Name | Reasoning |
|------|-----------|
| `referenced_class` | Precise: this class has been referenced in a triple we've observed. No ambiguity. |
| `observed_class` | Reasonable alternative — we've observed this class in the graph. Slightly weaker than "referenced" (you can observe without referencing). |
| `graph_class` | Short. "A class in our graph." Could include unresolved, unreachable classes though. |
| `encountered_class` | Similar to "observed". Less precise than "referenced". |
| `linked_class` | Implies the class is linked *to something* — but is the class the subject or object? Ambiguous direction. |
| `active_class` | Existing name. The concept is right; the word "active" just feels vague. |

**Contrast with:** a class that is **known** (cached or walked as part of a P279 chain) but has not yet been *referenced by any entity in our graph* — this class is cached but dormant. We need a name for this too.

**Decision:** ✓ **`referenced_class`** for a class QID that appears in at least one P31 or P279 claim of a discovered entity. ✓ **`known_class`** for any class QID we have walked P279 chains for, regardless of whether it's referenced. All referenced classes are known classes; not all known classes are referenced.
  * **Clarification:** Very much agree. `populated` may also have been an idea, but since some classes may get referenced without ever being populated, `referenced` works really well. Well done!

---

## 4. "Core Class Entity" → split cleanly

**Old name:** `core class entity` (used loosely in the old code and documentation)

**Problem:** Conflates two distinct relationships between an entity and a core class:
- (a) Entity has P31 → (chain) → core class: an *instance* relationship
- (b) Entity has P279 → (chain) → core class: a *subclass* relationship

Conflating them was the direct cause of the `core_roles.json` bug.

**Candidates for (a) — instance relationship:**

| Name | Reasoning |
|------|-----------|
| `CoreClassInstance` | Precise, mirrors Wikidata terminology. Unambiguous. |
| `CoreInstance` | Shorter. Still clear. |
| `InstanceOfCoreClass` | Verbose but explicit. |

**Decision (a):** ✓ **`CoreClassInstance`** — an entity that is (transitively via P31 chains) an instance of a core class.
  * **Clarification:** Agree.

**Candidates for (b) — subclass relationship:**

| Name | Reasoning |
|------|-----------|
| `CoreClassSubclass` | Precise, parallel to CoreClassInstance. |
| `CoreSubclass` | Shorter. Still clear. |
| `SubclassOfCoreClass` | Verbose. |

**Decision (b):** ✓ **`CoreClassSubclass`** — an entity that is (transitively via P279 chains) a subclass of a core class.
  * **Clarification:** Agree.

**Retired:** `core class entity` — this term is retired. It must not appear in new code or documentation. Use `CoreClassInstance` or `CoreClassSubclass` as appropriate.
  * **Clarification:** Not 100 % sure I agree. Speaking about both, it may still make sense. But as a general rule: agree, we can theoretically always either refer to exactly one, or explicitly name both. So final verdict: Agree.

---

## 5. "Projection Mode" → retired concept

**Old name:** `projection_mode` column in `core_classes.csv` with values `instances` or `subclasses`

**Problem:** This column forced a binary choice per core class — either collect instances (P31 chain) OR collect subclasses (P279 chain) for output. But per C3.5, we always need both. The binary was an artifact of the original implementation, not a meaningful design choice.

**Q9 explained:** The "issue" with Q9 is that this column encodes a false assumption. Asking "does projection_mode survive?" is really asking: "what replaces it?" The answer is: nothing replaces it as a binary flag. Instead:
- Every core class always produces both a `CoreClassInstance` projection and a `CoreClassSubclass` projection.
- Optional sub-projections (e.g., "guests" filtered from persons) are defined by separate rules.
- The `projection_mode` column is removed from `core_classes.csv` entirely.

**Decision:** ✓ **`projection_mode` is retired** — the column is removed. Both instance and subclass projections are always computed for every core class. Sub-projections are defined by a separate `sub_projection_rules.csv` (or equivalent) if needed.
  * **Clarification:** Agree.

---

## 6. "Preflight" → retired concept

**Old name:** "preflight" (steps 2.4–2.5 collectively)

**Problem:** In the redesign, class resolution happens continuously and incrementally via the ClassHierarchyHandler (C7.5). There is no separate "preflight" phase that runs all class resolution upfront. The concept dissolves.

**Decision:** ✓ **`preflight` is retired** — the concept is replaced by the continuous operation of the ClassHierarchyHandler. What was "preflight" becomes "the ClassHierarchyHandler processing any class QIDs it hasn't resolved yet." This is not a named phase; it's the natural operation of the handler.
  * **Clarification:** Agree.

---

## 7. Event Names — old vs new

Each event type needs a final name. The constraint: the old event types in the existing event store (56,000+ events) must remain readable. New event types are additive; old event names are never renamed in the store (backward compat per C1.8). The names below are for *new* events added in v4; old event names are kept as aliases.

| Old name | Problem | v4 name | Decision |
|----------|---------|---------|----------|
| `entity_discovered` | Good name — "discovered" is clear and consistent with `triple_discovered` | **`entity_discovered`** (keep) | ✓ |
| `entity_expanded` | "expanded" now belongs to the old conflated concept | **`entity_fetched`** | ✓ |
| `triple_discovered` | Good name — parallel to `entity_discovered`; "recorded" would demand "entity_recorded" which is worse | **`triple_discovered`** (keep) | ✓ |
| `query_response` | Clear, stable, hardcoded format | **`query_response`** (keep) | ✓ |
| `class_membership_resolved` | Verbose + semantic change in v4 (per-class, not per-entity) | **`class_resolved`** | ✓ |
| `relevance_assigned` | Slightly passive; ambiguous subject | **`entity_marked_relevant`** | ✓ |
| `expansion_decision` | "expansion" is the old conflated term; operation is now `fetch_decision` | **`fetch_decision`** | ✓ |
| `eligibility_transition` | Emitted only by node integrity pass (retired in v4) | *(retired)* | ✓ |
| `candidate_matched` | Fallback stage retired from Phase 2 scope | `candidate_matched` (kept, not emitted) | ✓ |
| *(none)* | New in v4: basic_fetch completion signal | **`entity_basic_fetched`** | ✓ |

All event names decided. Full rationale and payload specifications in `12_event_catalogue.md`. Key note: `class_resolved` has a **semantic change** from v3 — the v3 event records per-entity class membership; the v4 event records per-class-QID P279 walk completion (emitted by the ClassHierarchyHandler).

---

## 8. "Node Store" → entity document store

**Old name:** `node store` (the `entity_store.jsonl` + `property_store.jsonl` files; also the conceptual layer)

**Problem:** "Node" is a graph term that doesn't specify what kind of node — entity, class, property? "Store" is fine. The compound conflates the entity document cache (for fetched Wikidata API responses) with the projection layer.

**Candidates:**

| Name | Reasoning |
|------|-----------|
| `entity_document_store` | Precise: stores Wikidata entity documents (the JSON API response for a QID). |
| `entity_cache` | Simpler. Accurately describes the purpose: locally cached entity data. |
| `entity_store` | Already the filename (`entity_store.jsonl`). Consistent. |

**Decision:** ✓ **`entity_store`** — consistent with the existing filename. Distinguishable from the event store by context. "Entity store" = the local cache of Wikidata entity documents (labels, claims). "Event store" = the JSONL chunk files of pipeline events.
  * **Clarification:** Agree.

---

## 9. Summary: All Decided Names

| Concept | Old name | **Final name** | Status |
|---------|----------|----------------|--------|
| Fixed-payload identity fetch (label + P31 + P279) | hydration | **basic_fetch** | ✓ |
| Retrieve all claims for one QID | expansion (a) | **full_fetch** | ✓ |
| Inspect triples; queue eligible QIDs for full_fetch | expansion (b) | **fetch_decision** | ✓ |
| Class referenced by at least one entity in our graph | active class | **referenced_class** | ✓ |
| Class whose P279 chain has been walked, regardless of use | (unnamed) | **known_class** | ✓ |
| Entity with P31→core class chain | core class entity (instance) | **CoreClassInstance** | ✓ |
| Entity with P279→core class chain | core class entity (subclass) | **CoreClassSubclass** | ✓ |
| Binary per-class output flag | projection_mode | **retired** (always both) | ✓ |
| Upfront class resolution phase | preflight | **retired** (→ ClassHierarchyHandler) | ✓ |
| Local cache of Wikidata entity documents | node store | **entity_store** | ✓ |
| Incremental class resolution handler | (unnamed) | **ClassHierarchyHandler** | ✓ |
| Event: basic_fetch completed for a QID | (none) | **entity_basic_fetched** | ✓ |
| Event: full_fetch completed for a QID | entity_expanded | **entity_fetched** | ✓ |
| Event: first time a QID is seen in the graph | entity_discovered | **entity_discovered** (keep) | ✓ |
| Event: triple added to graph | triple_discovered | **triple_discovered** (keep) | ✓ |
| Event: P279 chain walk completed for a class QID | class_membership_resolved | **class_resolved** | ✓ |
| Event: entity marked relevant | relevance_assigned | **entity_marked_relevant** | ✓ |
| Event: traversal eligibility decision for a candidate | expansion_decision | **fetch_decision** | ✓ |
| Event: node integrity reclassification (retired) | eligibility_transition | *(retired with node_integrity_pass)* | ✓ |

**All naming is complete.** Event names decided in `12_event_catalogue.md`.
