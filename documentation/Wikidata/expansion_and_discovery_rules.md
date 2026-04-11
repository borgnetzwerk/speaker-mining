# Wikidata Expansion And Discovery Rules

This document is the single source of truth for Stage A graph discovery and expansion eligibility.

Any implementation, notebook behavior, diagnostics, and tests MUST follow this contract.

## Seed Set

The broadcasting program seed set is defined by:

- `data/00_setup/broadcasting_programs.csv`

Only valid Wikidata QIDs from this file are considered seeds.

## Core Class Set

The core class set is defined by:

- `data/00_setup/core_classes.csv`

Subclasses of these classes are also considered "core classes". They are marked as "subclass_of_core_class" and have a "subclass_of" path to a "core class".

## Normative Rule: Expansion Eligibility

To allow expansion, an item MUST satisfy both conditions:

1. Core class condition:
	 - The item is an instance of a core class (or subclass thereof) from `data/00_setup/core_classes.csv`.
2. Seed-neighborhood condition:
	 - The item is a first-degree or second-degree direct neighbor of a seed from `data/00_setup/broadcasting_programs.csv`.

Formal expression:

- `eligible_for_expansion = direct_or_subclass_core_match AND seed_neighbor_degree in {1, 2} AND not is_class_node`

## Degree Definitions

For any item `A` and any seed `S`, using direct graph edges (subject->object or object->subject):

1. First-degree neighbor:
	 - There exists a direct edge between `A` and `S`.
2. Second-degree neighbor:
	 - There exists an intermediate item `B` such that:
		 - `A` has a direct edge to `B`, and
		 - `B` has a direct edge to `S`.
3. Third degree or more:
	 - Not eligible for expansion under this rule.

## Discovery vs Expansion

1. Expansion:
	 - The pipeline MUST only enqueue and expand items that satisfy the normative expansion eligibility rule above.
2. Discovery:
	 - The pipeline MAY discover additional items outside this eligibility rule during traversal and data collection.
	 - Example: first-degree neighbors of expanded nodes are discovered during expansion.
	 - For discovered items, label/description/alias and class links (`instance_of`, `subclass_of`) are fetched to evaluate expansion eligibility.
	 - If an item is not eligible for expansion, it remains in status `discovered`.

Each node MUST have one of two statuses:

- `expanded` (expanded at least once)
- `discovered` (discovered but not expanded)

## Re-evaluation

Eligibility decisions are evidence-based and MUST be re-evaluated when new class-lineage or graph-neighborhood information is discovered.

## Subclass Preflight: Active vs Inactive Classes

Subclass preflight (Notebook 21, Step 2.4) uses a two-pass model to support deeper subclass coverage while limiting unnecessary class hydration.

Definitions:

1. Inactive class:
	- A class discovered in subclass expansion that is not currently required for instance-backed discovery payload hydration.
	- It is still a valid core-class subclass for class-lineage and expansion-eligibility decisions.
2. Active class:
	- A discovered core-subclass class that is also referenced by known instance evidence from local triples (`P31`).

Pass contract:

1. Pass 1 (structure crawl):
	- Crawl incoming `P279` edges breadth-first from each core class to configured depth.
	- Materialize class-resolution structure (for example `class_resolution_map.csv`).
	- Persist inactive classes as catalogued core-subclass entries with an explicit inactive hydration guard.
	- Do not hydrate every discovered subclass payload during this pass.
2. Pass 2 (activation hydration):
	- Build active class candidates from locally stored triples where `predicate == P31` and take the triple object class QIDs.
	- Intersect this set with pass-1 discovered core-subclass set.
	- Hydrate only the intersected set cache-first and persist discovered-node payloads.
	- Activation removes the inactive hydration guard for the activated class.

Instance-driven upward branch discovery (preflight augmentation):

1. Purpose:
	- Improve connectivity between active instance-side class trees and the discovered core-subclass structure.
2. Input set:
	- Start from active class QIDs derived from local `P31` evidence in pass 2.
3. Traversal rule:
	- Traverse upward along `P279` parent links from each active class.
	- Depth is bounded by `superclass_branch_discovery_max_depth` (Notebook 21 config; environment mirror `WIKIDATA_SUPERCLASS_BRANCH_DISCOVERY_MAX_DEPTH`).
4. Connectivity outcome:
	- If a traversed upward branch reaches any class already known in the discovered core-subclass structure, the branch is considered connected.
	- Connected branch nodes are incorporated into class-resolution path analysis for improved lineage bridging.
5. Operational safety:
	- Traversal is cache-first and uses the same query budget/timeout policies as preflight.
	- Budget or timeout exhaustion MUST stop branch traversal gracefully and report stop reason/metrics, not fail the whole preflight cell.
6. Hydration boundary:
	- Upward branch discovery augments structural connectivity only.
	- It MUST NOT bypass inactive hydration guards or perform generic hydration on guarded inactive classes.

Hydration guard rule:

1. Generic discovery/repair hydration MUST skip class entries marked with the inactive hydration guard.
2. Only activation logic may override and remove this guard.
3. Later modules (including Node Integrity) MUST apply the same guard semantics and must not treat guarded classes as missing-data errors.

Implications:

1. Deep subclass tree coverage is preserved even when only a subset of branches are hydrated.
2. Service load is reduced because inactive branches are not hydrated by default.
3. Activation remains evidence-based and reproducible because it derives from stored triples and deterministic intersection logic.
4. Expansion eligibility still sees inactive classes as valid core subclasses through class-resolution artifacts, without forcing payload hydration.
5. Upward branch discovery can increase the fraction of active classes with resolvable paths into the core-subclass tree while preserving guard-based hydration safety.