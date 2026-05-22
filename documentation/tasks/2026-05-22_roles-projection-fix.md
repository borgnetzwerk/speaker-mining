# roles-projection-fix

* priority: high
* scope: pipeline
* status: in-progress
* legacy-id: TODO-042

## Summary

Role-type Wikidata entities (journalist, politician, etc.) are defined via P279 (subclass-of), making them class nodes. The pipeline filtered ALL class nodes out of `core_roles.json`, producing an empty file. A redesign using `projection_mode=subclasses` and a parallel class-node relevancy path was implemented and requires a Phase 2 re-run to verify.

## Evidence

`data/20_candidate_generation/wikidata/projections/core_roles.json` (currently `{}`); `data/00_setup/core_classes.csv`; `speakermining/src/process/candidate_generation/wikidata/materializer.py` `_write_core_instance_projections`; `speakermining/src/process/candidate_generation/wikidata/bootstrap.py` `_load_class_setup_rows`.

## Definition of done

1. `core_roles.json` contains role entities (e.g. journalist Q1930187, politician Q82955) after re-running Phase 2 materialization.
2. Phase 31 `aligned_roles.csv` contains Wikidata-matched role rows (currently 0 Wikidata matches).
3. Finding documented in `documentation/findings.md`: role class uses P279 subclass mode.

## Implementation notes

- `projection_mode` column added to `core_classes.csv` and `bootstrap.py` (2026-04-24).
- `class_nodes_df` built alongside `non_class_instances_df` in materializer; used when `projection_mode=subclasses`.
- All `instances_core_*.json` renamed to `core_*.json` throughout codebase and on disk (2026-04-24).
- Finding (2026-04-24): after re-running Phase 2, `core_roles.json` still empty — role class nodes ended up in `not_relevant_core_roles.json`. Root cause: relevancy propagation only operates on instance-instance relationships; `occupation` property (P106) absent from `relevancy_relation_contexts.csv`.
- Redesign (2026-04-26): `bootstrap_relevancy_events` builds a parallel `class_qid_to_core_class` dict; BFS propagation accepts class nodes as targets; approved context `(Q215627, P106, Q214339)` added to `relevancy_relation_contexts.csv` with `can_inherit=TRUE`.
- Phase 2 re-run required to verify fix.
