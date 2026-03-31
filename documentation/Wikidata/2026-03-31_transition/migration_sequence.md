### Migration Sequence
Policy note:
- Legacy data cleanup was completed manually. No data from before v2 remains or should ever be considered.
- Future coding must follow `documentation/Wikidata/2026-03-31_transition/v2_only_policy.md` and must not reintroduce pre-v2 compatibility paths.

1. Freeze design contracts (completed)
- Finalize graph artifact model and storage decision (Option B), including node-level discovered/expanded fields and derived CSV projections.
- Finalize module-level implementation blueprint, including node/triple stores, checkpoint manifests, resume semantics, and notebook orchestration contract.
- Finalize canonical v2 raw event schema and legacy raw archive/remove policy.
- Finalize strict separation of graph-first expansion and fallback string matching.
- Design artifacts already produced:
	- `documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md`
	- `documentation/Wikidata/2026-03-31_transition/step_2_implementation_blueprint.md`
	- `documentation/Wikidata/2026-03-31_transition/step_3_canonical_event_schema.md`
	- `documentation/Wikidata/2026-03-31_transition/step_4_separate_graph_expansion_from_candidate_matching.md`

1. Implement frozen contracts (single rollout phase)
- Implement the Step 1-4 contracts in code as one coherent migration wave:
	- consolidated node and property stores,
	- triple event persistence and deterministic triples.csv materialization,
	- checkpoint manifests and deterministic resume (including inlinks cursor state),
	- notebook-orchestrated deterministic stage execution,
	- graph-authoritative candidate discovery plus fallback-only unresolved matching.
- Remove deprecated development-era contracts/artifacts where they conflict with the new model (including obsolete candidates.csv-era assumptions). Backward compatibility is not required for this migration.

1. Validate and publish as one gated change set
- Testing gate (mandatory): add and run contract-level tests for artifact existence, schema headers, determinism, resume behavior, canonical event schema, paging continuity, and graph/fallback stage separation.
- Documentation gate (same change set): synchronize workflow.md, contracts.md, repository-overview.md, open-tasks.md, and findings.md per documentation governance in `README.md`.
- Ship only when both gates pass.