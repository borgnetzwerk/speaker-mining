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

Every discovered class QID MUST be persisted with basic class payload fields at discovery time:

- `id`
- `label_en`, `label_de`
- `description_en`, `description_de`
- `alias_en`, `alias_de`
- `instance_of` (`P31` item targets)
- `subclass_of` (`P279` item targets)

Operational rule:

1. Whenever a discovered entity references class QIDs in `P31` or `P279`, those class QIDs MUST be fetched cache-first and stored immediately.
2. Class payload hydration MUST happen before class rollups are materialized, so class labels and lineage are available in `classes.csv` and related artifacts.

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
