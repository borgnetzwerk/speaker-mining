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

✓ **A5** — A seed is "fully fetched" when its derived fetch queue is fully processed — every entity the seed's traversal generated has been `full_fetch`ed or deferred by budget. The system does not need to track per-seed config-version history; config changes only trigger projection rebuilds, not re-fetches.
  * **Clarification:** A seed can only be "full_fetched" that's about it. A seed being fully progressed means that every entity it was linked to (and every consequentally fetched node) is completely resolved. So the concept of "fully fetched" just means "fetching list it generated is completely resolved". If a new config changes, all that does is rules processing these fetched nodes again. Since this requires a projection updating again, we don't need to consider this further. 
  * **Resolution:** Simplified: "fully fetched" = fetch queue empty. No per-seed config-version tracking needed.

---

## Group B — Entity Fetch Rules (when to retrieve data for a QID)

**B1** — Entity data (labels, descriptions, claims) is fetched for a QID when that QID is first encountered as a traversal target or as an object of a relevant triple (per hydration rules).

**B2** — Entity data is never fetched more than once per 365 days (cache-first policy per `Wikidata.md`).

**B3** — If a cached response exists for a QID, the cache response is used without a network call, regardless of `max_queries_per_run`.

**B4** — If no cached response exists and `max_queries_per_run = 0`, the QID is skipped — no network call is made.

**B5** — Entity data fetches count against the query budget. When the budget is exhausted, no further fetches occur in the current run.

**B6** — Entity data must be stored as events in the event store, not only in a local cache file.

✓ **B7** — When a `full_fetch`ed entity's claims reference new QIDs, each is classified as `potentially_relevant` (connecting predicate appears in `relevancy_relation_contexts.csv`) or `unlikely_relevant` (predicate not in the relevancy rules). `potentially_relevant` QIDs are queued for immediate `basic_fetch`; `unlikely_relevant` QIDs are deferred per `deferred_basic_fetch_mode`. Queue ordering within either group is irrelevant — correctness does not depend on processing order.
  * **Clarification:** a) naming conventions changed, this must be applied here too. hydration is now called "basic_fetching". Regarding order: It does not matter. So long as our fetching queue is not empty, we still have work to do. It matters not in what order we progress through them.
  * **Resolution:** Classification via `potentially_relevant` / `unlikely_relevant`. Immediate vs deferred basic_fetch. Queue order irrelevant.


---

## Group C — Graph Traversal Rules (what links are followed)

**C1** — From a relevant entity, follow outgoing P31 (instance-of) and P279 (subclass-of) links.

**C2** — From a relevant entity, follow all links (outgoing and incoming) that are configured for traversal.

✓ **C3** — All predicates are traversed by default from a `full_fetch`ed entity; no whitelist is required. An optional predicate blacklist may be configured for known-irrelevant predicates. Relevancy propagation is separately governed by `relevancy_relation_contexts.csv` and does not restrict traversal coverage.
  * **Clarification:** again, naming updated. Currently, I see no reason to regulate predicate traversal. If we know for certain a property is irrelevant, we can add it to a blacklist, but generally, I currently don't see a reason why we should stop basic_fetch for any property object of a relevant subject. And for relevancy propagation, other rules apply, so this is regulated already. Unless reasons can be mentioned not to traverse all properties, this can be kept as is. 
  * **Resolution:** Traverse-all by default; optional blacklist for exclusions. No whitelist needed.

**C4** — Traversal respects the configured depth limit. Entities beyond the depth limit are discovered but not traversed further.

**C5** — Traversal is breadth-first from seeds.

**C6** — An entity is traversed at most once per run, even if reached via multiple paths.

✓ **C7** — When a new entity appears as an object in a `triple_discovered` event from a `full_fetch`ed entity, it is classified as `potentially_relevant` (connecting predicate in `relevancy_relation_contexts.csv`) or `unlikely_relevant` (predicate not in the relevancy rules). `potentially_relevant` entities are queued for immediate `basic_fetch`; `unlikely_relevant` entities are deferred per `deferred_basic_fetch_mode` config. Within the immediate queue, ordering is implementation-defined — prefer batch-capable eager drainage.
  * **Clarification:** There is little difference between "immediately fetched" and "queued". We'll get to them when we get to them. Fundamentally, it is propably wise to keep the basic_fetch queue as empty as possible, since they are needed kontext to understand the graph we have. However, if we find a good way to mass fetch them, the opposite may also be true: We accumulate X of them (e.g. 100) and then fetch 100 at a time, if there is a suitable format that bulk fetches X at a time. Basically: Whatever suits the system best. 
  * **Resolution:** Classification at discovery: `potentially_relevant` → immediate basic_fetch; `unlikely_relevant` → deferred. Prefer eager, batch-capable drainage for the immediate queue.

---

## Group D — Class Resolution Rules (mapping entities to core classes)

**D1** — Every discovered entity is classified into at most one core class by following its P31 → P279 chain until a core class QID is reached.

**D2** — The set of core class QIDs is defined in `data/00_setup/core_classes.csv` and is never hardcoded.

**D3** — Root class QIDs (Q35120 = entity, Q1 = Universe) terminate the `class_hierarchy_resolution`. An entity whose P279 chain reaches a root class without passing through a core class is unclassified.

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

✓ **E10** — An entity that is reached via multiple relevancy paths is still simply "relevant." Multi-path relevancy is non-additive (no score or weight), non-conflicting, and monotonic — any single matching path suffices; being matched by many paths changes nothing.
  * **Clarification:** relevancy is binary and can only be gained, not lost. Indivudals like show hosts will be made relevant a thousand times, once by every episode. For us, this does not matter: Relevant is relevant, now matter how frequent.
  * **Resolution:** Binary: any single path suffices. Multiple paths are a no-op beyond the first.

✓ **E11** — The only prerequisite for a person to propagate relevancy to their occupation (via P106) is that the person is relevant. No additional condition is required. The propagation chain from seeds guarantees that only reachable, actually-relevant persons trigger this rule — the seed graph itself provides the necessary filtering.
  * **Clarification:** Just "is relevant". They themselves somehow inherit this from our seed notes, who are the only ones that are relevant to begin with. This propagates, eventually reaches a person (e.g. guest of a relevant episode) and then propagates to their occupation.
  * **Resolution:** Prerequisite is "is relevant" only. The relevancy propagation chain from seeds provides the necessary guard.

---

## Group F — Discovery Classification and basic_fetch Scope

**F1** — When a `full_fetch`ed relevant entity produces a triple (S, P, O) where P appears in `relevancy_relation_contexts.csv`, O is classified as `potentially_relevant` and queued for immediate `basic_fetch`.

**F2** — The set of predicates that classify a discovered object as `potentially_relevant` is derived dynamically from `relevancy_relation_contexts.csv` — no separate rule config file is needed. When the relevancy rules change, the classification updates automatically via `rule_changed` event handling.

**F3** — `basic_fetch` (immediate or deferred) applies only to objects of `full_fetch`ed relevant entities. Objects whose subject entity has not been `full_fetch`ed are not classified or queued.

**F4** — `basic_fetch`ed entities follow the same cache-first and budget rules as traversal-reached entities (B1–B5).

**F5** — `basic_fetch` does NOT automatically make the fetched entity relevant. It only ensures the entity's basic data is available for class resolution and relevancy evaluation.

✓ **F6** — Objects of `full_fetch`ed relevant entities where the connecting predicate is NOT in `relevancy_relation_contexts.csv` are classified as `unlikely_relevant`. Their `basic_fetch` is deferred, controlled by `deferred_basic_fetch_mode`:
- `"never"` (default): skip entirely unless rules later change
- `"end_of_run"`: process after all `potentially_relevant` work is complete
No class_hierarchy_resolution fires for `unlikely_relevant` nodes regardless of deferral setting.
  * **Clarification:** naming conventions changed. basic_fetch is a basic necessity of virtually every leaf node in our graph. We always want to know at least basic information about the node, hence the name. Yet, basic_fetch also reveals new entities (via "instance of" and "subclass of" links). These must never be followed just because of that, since otherwise we may run an excessive amount of queries just to fetch some nieche superclass of a leaf node. Basically: basic_fetch leaf nodes of fully_fetched nodes. No further steps unless these leaf nodes meet full_fetch criteria (e.g. inheriting relevancy).
  * **Resolution:** `unlikely_relevant` classification governs deferred `basic_fetch`. Default: never. No class_hierarchy_resolution for deferred nodes.

✓ **F7** — The class_hierarchy_resolution fires as part of `basic_fetch` only for `potentially_relevant` nodes. It does not fire for `unlikely_relevant` nodes. The ClassHierarchyHandler governs a separate, independent class_hierarchy_resolution queue with its own logic; a non-empty ClassHierarchyHandler queue takes priority over other work.
  * **Clarification:** There are no separate steps. The "n step upwards walk" is a fundamental principle of every basic_fetch (n is currently configured to 5). It is a 100 % basic requirement of the basic_fetch.
  * **Resolution:** `class_hierarchy_resolution` fires for `potentially_relevant` nodes only. ClassHierarchyHandler's queue is separate and higher-priority.

**F8** — When `relevancy_relation_contexts.csv` changes, a `rule_changed` event is emitted. The `basic_fetch` handler tracks the rule version it last applied. On observing `rule_changed`, it re-evaluates all deferred `unlikely_relevant` QIDs: any whose connecting predicate is now in the updated rules is promoted to `potentially_relevant` and queued for immediate `basic_fetch`.

---

## Group G — Output Rules (what ends up in Phase 2 output)

**G1** — For each core class, a `core_<class>.json` file is produced containing all entities that are both (a) resolved to that core class AND (b) marked as relevant.

**G2** — For each core class, a `not_relevant_core_<class>.json` file is produced containing entities resolved to that core class but NOT marked as relevant.

**G3** — The output files for roles use class nodes (P279 subclass chain), not instances (P31 chain).

✓ **G4** — The per-entity data structure in `core_<class>.json` contains all data the system has for that entity: all claims and triples, qualifier PIDs and reference indicators, labels, descriptions, and aliases. Nothing is optional. The output must accommodate the full richness of Wikidata data including qualifiers (TODO-041).
  * **Clarification:** ALL data we have on them. Nothing is optional. These outputs contain everything we have on those core class instances and core class subclasses.
  * **Resolution:** Include all available data. No field omitted. Qualifiers (TODO-041) must be included.

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

**I1** — Every QID referenced as the object of a stored triple that is classified as `potentially_relevant` must have entity data in the event store (via `basic_fetch` or `full_fetch`). QIDs classified as `unlikely_relevant` are exempt — they may exist in stored triples without entity data; this is correct behavior under `deferred_basic_fetch_mode = "never"`.

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
