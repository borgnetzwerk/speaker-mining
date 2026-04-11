# Wikidata Documentation Map

This folder contains the canonical and historical documentation for the Wikidata candidate-generation pipeline.

## Current Canonical Entry Points

Read these first for current behavior:

1. `Wikidata.md`
	- Service interaction policy (request identification, pacing, caching).
2. `Wikidata_specification.md`
	- Normative persistence and artifact requirements.
3. `expansion_and_discovery_rules.md`
	- Stage A eligibility and subclass preflight rules (including Active/Inactive class model).
4. `node-integrity-pass.md`
	- Node-integrity pass purpose, bottlenecks, and implementation notes.
5. `wikidata_todo_tracker.md`
	- Active follow-up ideas and unresolved operational TODOs.

## Implementation Alignment Snapshot (2026-04-11)

This snapshot maps key current implementation behavior to documentation anchors.

1. Subclass preflight crawler (Notebook 21, Step 2.4):
	- Code: `speakermining/src/process/candidate_generation/wikidata/materializer.py` (`crawl_subclass_expansion`).
	- Docs: `expansion_and_discovery_rules.md`, `Wikidata_specification.md`.
2. Active/Inactive two-pass class hydration:
	- Pass 1: deep subclass structure crawl.
	- Pass 2: activate classes from local `P31` evidence intersected with discovered core-subclass set; hydrate active set only.
	- Docs: `expansion_and_discovery_rules.md`, `Wikidata_specification.md`.
3. Instance-driven upward superclass branch discovery:
	- During preflight, active instance classes may traverse upward along `P279` parent chains (depth-bounded) to find a bridge into discovered core-subclass structure.
	- This improves class-lineage connectivity without requiring full hydration of inactive branches.
	- Docs: `expansion_and_discovery_rules.md`, `Wikidata_specification.md`.
4. Triple evidence source for activation:
	- Code: `speakermining/src/process/candidate_generation/wikidata/triple_store.py` (`iter_unique_triples`).
	- Docs: `Wikidata_specification.md` (triple completeness).
5. Cache-first query handling and progress budgets:
	- Code: `speakermining/src/process/candidate_generation/wikidata/cache.py`.
	- Docs: `Wikidata.md`.

## Branch/Archive Documentation

The following subfolders are historical design, migration, and analysis branches. They are valuable context but not automatically authoritative for current runtime behavior.

1. `2026-03-31_transition/`
2. `2026-04-02_jsonl_eventsourcing/`
3. `2026-04-03_eventsourcing_potential_unlock/`
4. `2026-04-07_todo_resolution/`
5. `2026-04-09_design_improvements/`
6. `2026-04-10_great_rework/`

Use these branches for rationale, migration traceability, and decision history.

## Governance Rule

If implementation and documentation diverge:

1. Update canonical docs in this folder in the same change set as code behavior changes.
2. Record historical context in branch folders without overriding canonical current behavior.
