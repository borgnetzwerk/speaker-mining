## Phase 2: learn from prior implementation

### Sources inspected
1. `documentation/31_entitiy_disambiguation/2026-04-11_redesign/99_REDESIGN_TARGET_SPECIFICATION.md`
2. `documentation/31_entitiy_disambiguation/2026-04-11_redesign/01_disambiguation_artifact_contract_draft.md`
3. `documentation/31_entitiy_disambiguation/2026-04-11_redesign/311_automated_disambiguation_specification.md`
4. `documentation/31_entitiy_disambiguation/2026-04-11_redesign/312_manual_reconciliation_specification.md`
5. `documentation/31_entitiy_disambiguation/2026-04-11_redesign/PHASE31_REDESIGN_PROGRESS.md`

### What remains valid and is adopted
1. Precision-first policy: unresolved is preferred over low-confidence false positives.
2. Deterministic, reproducible outputs for unchanged input.
3. Human-readable method and reason fields for manual review handoff.
4. Stable baseline alignment columns across all aligned core tables.
5. Canonical person matching unit: one person mention in one episode of one broadcasting program.
6. Layer interaction rule: role/organization evidence can enrich confidence but must not override stronger episode/program constraints.
7. Deterministic row ordering contract for aligned CSV handoff.

### What is explicitly not adopted from legacy
1. Legacy implementation layout and module internals under `analyze_then_delete`.
2. Legacy event-sourcing architecture details as mandatory design constraints for this restart.
3. Any assumptions tied to old non-functional skeleton code.

### Documentation improvements applied after refinement
1. `01_approach.md` now includes:
	- canonical person matching unit,
	- explicit status vocabulary (`aligned`, `unresolved`, `conflict`),
	- Layer 4 non-overwrite rule,
	- deterministic handoff readiness rules.
2. `02_implementation.md` now includes:
	- single flattened row schema with authoritative shared metadata fields,
	- source-suffixed wide-column expansion rules for repeated properties,
	- deterministic ordering contract (including person two-pass ordering),
	- Layer 4 enrichment-only constraint,
	- structural quality gate for single-schema column presence.

### Remaining refinement opportunities (optional)
1. Add a short worked example per layer showing one aligned and one unresolved case.
2. Add a compact worked example that shows deterministic repeated-property expansion (for example guests_1..n and publications_1..n) in one aligned episode row.