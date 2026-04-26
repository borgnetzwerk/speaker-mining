# Notebook 21 Redesign — Known Rules Catalogue
> Created: 2026-04-26  
> Status: DRAFT — rules marked ❓ are uncertain or need clarification before implementation.  
> Purpose: Express every rule that currently governs Phase 2 behavior in plain language, without implementation details. Per Clarification C12: start with granular, individually-expressible rules; cluster only after the rule space is understood.

This document is intentionally implementation-free. It describes *what* the system must do, not *how*. Rule numbers are stable identifiers for use in design discussions.

---

## Rule Groups

Rules are organized by the concern they govern. Rules within a group are individually expressible — no clustering or merging has been done yet.

---

## Group A — Seed Rules (what starts the traversal)

**A1** — Traversal begins from a configured list of seed QIDs (broadcasting programs defined in `data/00_setup/broadcasting_programs.csv`).

**A2** — A seed QID is always considered relevant by definition, regardless of whether it satisfies any other relevancy rule.

**A3** — Seeds are the only entities that are relevant without being reachable from another relevant entity.

**A4** — The seed list must be configurable without code changes.

❓ **A5** — A seed is "fully processed" when all of its links have been traversed to the configured depth. The system must be able to determine whether a seed was processed under the current config version — if the config changed, the seed may need reprocessing.

---

## Group B — Entity Fetch Rules (when to retrieve data for a QID)

**B1** — Entity data (labels, descriptions, claims) is fetched for a QID when that QID is first encountered as a traversal target or as an object of a relevant triple (per hydration rules).

**B2** — Entity data is never fetched more than once per 365 days (cache-first policy per `Wikidata.md`).

**B3** — If a cached response exists for a QID, the cache response is used without a network call, regardless of `max_queries_per_run`.

**B4** — If no cached response exists and `max_queries_per_run = 0`, the QID is skipped — no network call is made.

**B5** — Entity data fetches count against the query budget. When the budget is exhausted, no further fetches occur in the current run.

**B6** — Entity data must be stored as events in the event store, not only in a local cache file.

❓ **B7** — If an entity's claims reference QIDs that are not yet fetched, those QIDs are eligible for fetching under the hydration rules. The order of fetching is not specified — what determines priority?

---

## Group C — Graph Traversal Rules (what links are followed)

**C1** — From a relevant entity, follow outgoing P31 (instance-of) and P279 (subclass-of) links.

**C2** — From a relevant entity, follow all links (outgoing and incoming) that are configured for traversal.

❓ **C3** — Which predicates are traversed? Is this configurable (like hydration rules) or fixed? The current system follows all links from expanded entities. Is that correct?

**C4** — Traversal respects the configured depth limit. Entities beyond the depth limit are discovered but not traversed further.

**C5** — Traversal is breadth-first from seeds.

**C6** — An entity is traversed at most once per run, even if reached via multiple paths.

❓ **C7** — When a new entity is discovered via traversal, is it immediately fetched, or is it queued? If queued, what is the queue ordering?

---

## Group D — Class Resolution Rules (mapping entities to core classes)

**D1** — Every discovered entity is classified into at most one core class by following its P31 → P279 chain until a core class QID is reached.

**D2** — The set of core class QIDs is defined in `data/00_setup/core_classes.csv` and is never hardcoded.

**D3** — Root class QIDs (Q35120 = entity, Q1 = Universe) terminate the P279 walk. An entity whose P279 chain reaches a root class without passing through a core class is unclassified.

**D4** — Manual override rules in `data/00_setup/rewiring_catalogue.csv` (formerly `rewiring.csv`) take precedence over the computed P279 resolution. If a QID has an override entry, that entry determines its core class.

**D5** — An entity that resolves to multiple core classes (via multiple P31 / P279 paths) is considered in conflict. The conflict must be visible in the output, not silently resolved by picking one.

**D6** — Conflict resolution may be governed by priority rules (which core class takes precedence) defined in config. In the absence of a priority rule, the conflict is reported but the entity is not excluded.

**D7** — A class node (P279 entity) resolves to a core class by following its P279 chain upward, the same as an instance follows its P31 → P279 chain. Class nodes are not instances but participate in the same resolution logic.

---

## Group E — Relevancy Rules (what makes an entity relevant)

**E1** — A seed entity is always relevant (see A2).

**E2** — An entity is relevant if it is connected to a relevant entity via a triple that matches an approved relevancy rule in `data/00_setup/relevancy_relation_contexts.csv`.

**E3** — Relevancy propagation is directional: the approved rule specifies whether relevancy flows from subject to object, from object to subject, or both.

**E4** — A relevancy rule is expressed as `(subject_core_class, property, object_core_class)`. If a triple `(S, P, O)` matches a rule and S is relevant, then O is relevant.

**E5** — For reverse-directional rules: if a triple `(S, P, O)` matches a reverse rule and O is relevant, then S is relevant.

**E6** — Adding a new relevancy rule requires only a change to `relevancy_relation_contexts.csv` — no code change.

**E7** — Relevancy propagation is transitive: if A is relevant and A→B is approved, B is relevant; if B→C is also approved, C is relevant.

**E8** — An entity that resolves to a core class but is not reachable via any relevancy path is "not relevant" and is NOT included in the core output files.

**E9** — An entity that is relevant but resolves to no core class is "unclassified" and is NOT included in the core output files, but may be logged.

❓ **E10** — An entity can be relevant through multiple paths (e.g. a person who is both a guest and the object of a has-part triple). How is multi-path relevancy handled? Is it additive, or does any single path suffice?

❓ **E11** — The current approved context `(Q215627=person, P106=occupation, Q214339=role)` propagates from a relevant person to a role class node. But "not every instance of human is a relevant guest" (Clarification C3.4). What additional condition is required for a person to be a valid *subject* of this propagation? Just "is relevant"? Or more specific criteria?

---

## Group F — Hydration Rules (which property-links to follow for data completeness)

**F1** — When a relevant entity has a claim with a QID object, that object QID may be fetched even if it was not reached by graph traversal.

**F2** — Hydration is governed by a configurable list of predicates (currently P106, P102, P108, P21, P527, P17).

**F3** — Hydration applies to objects of relevant entities, not to random graph neighbors.

**F4** — Hydrated entities are fetched under the same cache-first and budget rules as traversal-reached entities (B1–B5).

**F5** — Hydration does NOT automatically make the hydrated entity relevant. It only ensures its data is available for classification and display.

❓ **F6** — Should hydration rules also specify subject requirements (e.g., "only hydrate P106 objects when subject is an instance of human")? See Clarification C3.4 on class expansion cost.

❓ **F7** — Should hydration also trigger class resolution for the hydrated QID (so that occupation QIDs get their P279 chains walked)? Currently this is done in step 2.4.3 as a separate pass.

---

## Group G — Output Rules (what ends up in Phase 2 output)

**G1** — For each core class, a `core_<class>.json` file is produced containing all entities that are both (a) resolved to that core class AND (b) marked as relevant.

**G2** — For each core class, a `not_relevant_core_<class>.json` file is produced containing entities resolved to that core class but NOT marked as relevant.

**G3** — The output files for roles use class nodes (P279 subclass chain), not instances (P31 chain).

❓ **G4** — What is the per-entity data structure in `core_<class>.json`? Which fields are required? Which are optional? Does it include qualifier data (per TODO-041)?

**G5** — The entity lookup index must contain a label for every QID that appears in any output file.

**G6** — Output files are written once, at the end of the run. They are not updated during intermediate expansion steps (per C8).

**G7** — All projections must be rebuildable from the event store alone. An output file that cannot be reconstructed from events must not exist.

---

## Group H — Operational Rules (how the system runs)

**H1** — The system must be runnable with `max_queries_per_run = 0` (pure cache mode) once data is cached. A full cache-only run must produce identical output to a network run on the same data.

**H2** — Every network call must go through the cache layer. No direct `requests` calls outside the cache/event system.

**H3** — User interruption (Ctrl-C, stop button) must be handled gracefully everywhere. No partial-write corruption of the event store.

**H4** — A heartbeat must be emitted at regular intervals (at least every minute) for any operation that runs for more than one minute.

**H5** — Configuration parameters are read from an external config file, not from a hardcoded notebook cell.

**H6** — The config file is auto-created with defaults if missing, then an error is raised asking the user to configure it.

**H7** — All Wikidata API requests must include a valid User-Agent with contact information per `Wikidata.md`.

**H8** — Rate-limiting backoff is applied on 429/503 responses.

---

## Group I — Integrity Rules (correctness invariants)

**I1** — Every QID referenced as the object of a stored triple must have entity data in the event store (either fetched or hydrated).

**I2** — Every QID in a core output file must have at least a label in the entity lookup index.

**I3** — Every QID in `class_resolution_map.csv` must trace to a known core class or be explicitly unresolved.

**I4** — No event may be deleted, modified, or overwritten. The event store is append-only at all times.

**I5** — If a rule in `relevancy_relation_contexts.csv` references a core class QID that is not in `core_classes.csv`, it is a configuration error that must be reported at startup.

---

## Rules That Have Been Retired

The following rules governed the old system but are explicitly retired in the redesign:

| Retired Rule | Reason |
|---|---|
| "After all seeds are processed, run `_materialize` to rebuild all projections" | Materializer concept deprecated (C1.6) |
| "After integrity pass, run `materialize_final` unconditionally" | Integrity pass deprecated (C6); materializer deprecated (C1.6) |
| "Checkpoint the full projection state after each seed completes" | Checkpoint system deprecated (C2) |
| "If checkpoint is corrupted, revert to previous snapshot" | Revert/rollback concept removed (C2.4) |
| "Run fallback string matching for unresolved mention targets" | Phase 2 scope is graph traversal only (C9) |
| "Run node integrity pass to repair entities referenced in triples but not discovered" | Integrity-by-construction replaces post-hoc repair (C6) |
