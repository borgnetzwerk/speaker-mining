# Wikidata Persistent Specification Addendum

Date: 2026-03-31
Status: Normative requirements
Scope: Persistent graph artifacts and class-resolution guarantees for candidate generation

## 1. Core Class Registry

The canonical core classes are:

- `persons` -> `Q215627`
- `organizations` -> `Q43229`
- `roles` -> `Q214339`
- `episodes` -> `Q1983062`
- `series` -> `Q7725310`
- `broadcasting_programs` -> `Q11578774`
- `topics` -> `Q26256810`
- `entities` -> `Q35120`
- `privacy_properties` -> `Q44601380`

The registry source of truth is `data/00_setup/classes.csv`.

## 2. Class Lineage Resolution Requirements

When class detection identifies a class node (entity with at least one `P279`), lineage resolution MUST satisfy:

1. `subclass_of_core_class` is `True` if any `P279` ancestry path reaches a core class.
2. `path_to_core_class` stores the shortest discovered `P279` path using `|`-joined QIDs.
3. Direct subclass links MUST be resolved correctly. Example: `Q5` (`human`) has direct `P279 -> Q215627` (`person`) and therefore MUST resolve as:
	- `subclass_of_core_class = True`
	- `path_to_core_class = Q215627` for class-node evaluation, and
	- `path_to_core_class = Q5|Q215627` for instance rows whose class is `Q5`.
4. Missing class lineage due to absent local class payload is not acceptable once a class QID is discovered in any `P31` or `P279` edge.
5. Broad semantic classes that legitimately sit under `organization` (for example countries) are not special-case failures; if the lineage is valid, they must remain eligible under the same class-resolution rules.

## 3. Discovered Class Payload Requirements

Discovered class QIDs are handled in two phases:

1. Structure discovery phase:
	- Subclass structure is collected to configured depth (incoming `P279`) to build class-resolution artifacts.
	- Inactive discovered core-subclass classes MUST be catalogued as valid core-subclass entries.
	- Catalogued inactive entries MUST carry an explicit inactive hydration guard marker.
	- Class payload hydration is not required for every discovered subclass during this phase.
2. Activation hydration phase:
	- Active classes are derived from locally known instance evidence (`P31` triple objects), then intersected with discovered core-subclass classes.
	- Only active classes MUST be hydrated and persisted as discovered items (cache-first).

For each active class that is hydrated, payload fields MUST include:

- `id`
- `label_en`, `label_de`
- `description_en`, `description_de`
- `alias_en`, `alias_de`
- `instance_of` (`P31` item targets)
- `subclass_of` (`P279` item targets)

Operational rules:

1. Activation hydration MUST be cache-first and must not bypass existing cache policy.
2. Inactive classes MAY remain unhydrated until they become active by evidence.
3. Class lineage and resolution artifacts MUST remain complete for configured depth, independent of hydration status.
4. Inactive hydration guards MUST be enforced globally: generic hydration/repair paths MUST skip guarded classes.
5. Only activation logic may remove inactive hydration guards and hydrate those classes.
6. Later modules (for example Node Integrity) MUST honor inactive hydration guards and MUST NOT rehydrate guarded classes as part of missing-payload repair.

## 3.1 Instance-Driven Upward Superclass Branch Discovery

Preflight subclass expansion MAY use an additional upward superclass discovery route derived from active instance classes.

Normative behavior:

1. Source classes:
	- Source set is active class QIDs derived from local `P31` triple objects.
2. Traversal:
	- Traverse `P279` parents upward from each source class.
	- Traversal depth MUST be bounded by configured `superclass_branch_discovery_max_depth`.
3. Connectivity semantics:
	- A source class is considered connected when its upward branch reaches a class already present in discovered core-subclass structure.
	- Connected branch nodes MAY be added to structural path analysis for class-resolution reconciliation.
4. Query policy:
	- Traversal MUST be cache-first and follow the same budget and timeout constraints as other preflight network calls.
	- If budget or timeout limits are reached, traversal MUST stop gracefully and expose stop reason/metrics rather than throwing a hard failure for the preflight run.
5. Hydration constraints:
	- Upward branch discovery is structural discovery only.
	- It MUST NOT hydrate guarded inactive classes unless activation logic explicitly removes the inactive hydration guard.

## 4. Triple Completeness Requirements

`data/20_candidate_generation/wikidata/projections/triples.csv` is a complete item-to-item edge ledger and MUST include every discovered QID->PID->QID link, regardless of whether the source node was expanded.

In scope:

1. Outlinks discovered from expanded nodes.
2. Outlinks discovered from non-expanded but fetched nodes.
3. Inlinks discovered from SPARQL inlink queries.
4. Class hierarchy links (for example `P279`) and class membership links (for example `P31`) when discovered.

Implication:

- If 271 entities are discovered with `P31 -> Q5`, those 271 triples MUST be represented in `projections/triples.csv` after materialization.

## 5. Verification Expectations

A run is compliant only if all are true:

1. Class rows that are discovered have non-empty labels where Wikidata provides them.
2. Direct known lineage cases (`Q5 -> Q215627`) resolve as subclass-of-core.
3. Triple counts include discovered instance-to-class links even for nodes that were not enqueued for expansion.

## 6. Decision Re-Evaluation and Reclassification

Canonical rule reference:

1. Expansion/discovery eligibility and re-evaluation semantics are defined in `documentation/Wikidata/expansion_and_discovery_rules.md`.
2. This addendum does not redefine those rules; it requires implementation and diagnostics to remain consistent with that contract.

Operational expectation:

- The node integrity pass detects when previously ineligible nodes become eligible under updated class knowledge and triggers required expansion work.
