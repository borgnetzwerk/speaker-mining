# Wikidata Relevancy Detection And Propagation

This document defines how core-class instances are classified as relevant or not relevant.

It replaces the old assumption that every core-class instance is automatically useful for downstream pipelines.

## Goal

Classify each core-class instance into a stable relevance state:

- relevant (eligible for downstream core-instance outputs and forced expandable)
- not relevant (known core-class instance, but currently outside relevant scope)

Equivalent representation options:

- boolean field: relevant=true or relevant=false
- label field: relevant/not_relevant

Implementation may store both for readability, but boolean relevance is normative.

## Initial Relevancy Seeds

Initial relevance starts from broadcasting programs listed in:

- data/00_setup/broadcasting_programs.csv

Rule:

- A broadcasting program present in this setup file is relevant=true.
- Other discovered broadcasting programs may exist, but are not automatically relevant.

This aligns with the existing listed behavior and formalizes it as relevance seeding.

## Relevance Is Monotonic

Relevance can only be gained, never lost.

Rule:

- Once an entity is relevant=true, it must remain relevant=true for the current run and persisted outputs.

No downgrade path is allowed in this model.

## Persistence Model (Event-Sourced)

Relevancy decisions and relevancy gains MUST be event-sourced.

This follows repository coding principles for event sourcing:

- append decisions/events in the event log first
- compute and persist derived state through a dedicated event handler
- treat CSV outputs as projections, not mutable source-of-truth state

Required runtime components:

- domain events for relevancy seed assignment and propagation gains
- one dedicated relevancy event handler
- one projection artifact: relevancy.csv

Rules:

- do not mutate relevancy state directly in ad hoc notebook logic
- replaying the same event stream must rebuild the same relevancy.csv projection
- handler progress tracking must be persisted for deterministic incremental resume

## Context-Sensitive Relevance Inheritance

Relevance may propagate through direct links between core-class instances, but only for approved relation contexts.

Examples:

- allowed: episode -- part of the series (P179) --> broadcasting program (relevant)
- not automatically allowed: person -- likes show --> broadcasting program (relevant)

Important:

- propagation must be context sensitive (subject class, property, object class)
- propagation may use outlinks and inlinks
- relation approvals are stored as subject, property, object without a separate direction column

## Dynamic Relation Discovery And Approval

Because Wikidata modeling can vary by user and evolve over time, relation contexts must be discovered dynamically and made operator-approvable.

### Detected Relation Context Catalog

Maintain a persisted catalog of direct connections between core-class instances in the shape:

- subject_class_qid
- subject_class_label
- property_qid
- property_label
- object_class_qid
- object_class_label
- can_inherit

Human-readable equivalent:

- subject, property, object, can_inherit

Example row:

- episode (Q1983062), part of the series (P179), broadcasting program (Q11578774), can_inherit=

Semantics:

- blank or false-like can_inherit: not approved yet
- any non-empty user value in can_inherit: approved for inheritance

### Persistence Contract

The detected relation context catalog must be append/merge safe.

Rules:

- newly detected relation contexts are added
- existing rows and their can_inherit decisions are preserved
- regeneration must not erase prior operator decisions

This requires a persisted source-of-truth artifact, not an ephemeral print-only table.

## Propagation Workflow

1. Initialize relevant=true for listed broadcasting program seeds.
2. Discover direct core-instance connections over inlinks and outlinks.
3. Match each observed edge to a relation context row.
4. If relation context is approved (can_inherit), propagate relevance between connected endpoints over both outlinks and inlinks.
5. Repeat until fixed point (no additional nodes become relevant).
6. Never unset relevance.

Operational persistence note:

- each first-time relevancy gain emits an append-only event
- projection updates are performed by the relevancy handler

## Interaction With Expansion Eligibility

For now, relevancy coexists with current expansion rules.

Normative interim rule:

- if relevant=true, then expandable=true

Other existing expansion eligibility criteria remain in place during transition.

Future direction:

- relevancy may replace parts of current expansion eligibility once validated.

## Output Segregation Rules

Relevance must control core-instance output files.

Rules:

- relevant core-class instances go to instance_core_*.json artifacts
- non-relevant core-class instances must not be mixed into those artifacts
- non-relevant instances may be written separately under explicit naming such as not_relevant_instance_core_*.json

This keeps downstream consumers deterministic and relevance-aware.

## Hydration Capture Requirements

To make relevance auditable and reproducible, hydration must capture relevance-related fields as first-class properties.

At minimum, capture and persist per node:

- relevant (boolean)
- relevant_seed_source (for seed-derived relevance, e.g. listed_broadcasting_program)
- relevance_propagated_via_property_qid (if propagated)
- relevance_propagated_via_property_label (if available)
- relevance_propagated_from_qid (source node that transferred relevance)
- relevance_propagation_direction (outlink or inlink)
- relevance_first_assigned_at (timestamp)

For relation-context artifacts, persist:

- subject_class_qid
- property_qid
- object_class_qid
- decision_last_updated_at
- can_inherit

These fields must be added to the list of hydration-captured properties so reruns and diagnostics can reconstruct why a node became relevant.

## Relevancy Projection Contract

Use one projection file for relevancy state:

- data/20_candidate_generation/wikidata/projections/relevancy.csv

One row per entity QID (latest derived relevancy state).

Minimum columns:

- qid
- is_core_class_instance
- relevant
- relevant_seed_source
- relevance_first_assigned_at
- relevance_last_updated_at
- relevance_inherited_from_qid
- relevance_inherited_via_property_qid
- relevance_inherited_via_direction
- relevance_evidence_event_sequence

Semantics:

- relevant is monotonic (false -> true allowed, true -> false forbidden)
- inheritance columns are nullable for seed-assigned relevance
- relevance_evidence_event_sequence points to the latest event that supports current projected state

Projection ownership:

- relevancy.csv is written by the relevancy event handler only
- notebooks/process modules consume it as derived state and must not hand-edit it

## Relationship To Expansion Rules Contract

This document augments Stage A expansion policy and does not weaken the core-class/root-class distinction.

In particular:

- Q35120 (entity) remains a root class only, not a core class target.
- Relevance inheritance uses approved relation contexts between core-class instance neighborhoods.

## Open Implementation Notes

- Keep relation-context approval artifacts user-editable (CSV-friendly).
- Use stable merge keys: subject_class_qid + property_qid + object_class_qid.
- Treat any non-empty can_inherit value as approval to minimize manual friction.
- Prefer additive schema evolution (new fields) over destructive rewrites.
