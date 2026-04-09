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