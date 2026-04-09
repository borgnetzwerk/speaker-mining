# Wikidata Great Rework - Master Map

Date created: 2026-04-09
Status: Canonical navigation and execution map
Scope: single top-to-bottom map covering backlog, findings, learnings, and implementation flow

## How To Use This Document

1. Start here for all planning and execution decisions.
2. Treat linked documents as source inventories and detail appendices.
3. Add new issues to the Intake section first, then map them into the ordered workstreams below.
4. Keep this map updated whenever priorities, dependencies, or closure evidence changes.

## Source Documents (Retained)

1. Backlog inventory: `documentation/Wikidata/2026-04-10_great_rework/01_rework_backlog.md`
2. Codebase findings inventory: `documentation/Wikidata/2026-04-10_great_rework/02_additional_codebase_findings.md`
3. Fernsehserien transfer learnings: `documentation/Wikidata/2026-04-10_great_rework/03_fernsehserien_de_event_learnings.md`
4. Fernsehserien transfer implementation slices: `documentation/Wikidata/2026-04-10_great_rework/04_fernsehserien_transfer_execution_plan.md`
5. GRW-011 code-level implementation plan: `documentation/Wikidata/2026-04-10_great_rework/05_grw_011_lineage_recovery_implementation_plan.md`
6. Closeout baseline: `documentation/Wikidata/2026-04-10_great_rework/00_status_quo_closeout.md`

## Mission And Constraints

Mission:

1. Rebuild Wikidata candidate-generation workflow to maximize determinism, observability, and efficiency before high-volume rerun.
2. Use the rework window to remove legacy shape constraints when a cleaner architecture is justified by the coding principles and specification contracts.

Constraints:

1. No destructive or ambiguous runtime behavior.
2. Event history and query provenance remain first-class assets.
3. Operator-visible progress must remain clear during long-running phases.
4. Changes must be testable and checkpoint-safe.
5. The notebook structure is provisional; architecture may be consolidated when that better serves the workflow contract.

## Rework Philosophy

1. Treat this rework as a clean slate, not a patch-only exercise.
2. Prefer the simplest architecture that still preserves provenance, replayability, and operator clarity.
3. Reconsider open tasks continuously; if a broader redesign is lower-risk and higher-value than piecemeal edits, document it and take it seriously.
4. Optimize around the authoritative contracts in `documentation/Wikidata/expansion_and_discovery_rules.md`, `documentation/Wikidata/Wikidata_specification.md`, and `documentation/coding-principles.md`.
5. Keep legacy baggage only when it is still justified by the current contract.

## Reverse-Engineering Evidence To Harvest

1. `data/20_candidate_generation/wikidata/reverse_engineering_potential/class_hierarchy.csv` is the most valuable legacy artifact for this rework because it can recover subclass closure, `path_to_core_class`, parent counts, and core-class rollups that are otherwise expensive to infer repeatedly at runtime.
2. `classes.csv` and `core_classes.csv` remain the authoritative contract inputs; reverse-engineering artifacts are only for reconstructing missing structure, not for redefining the contract.
3. `triples.csv`, `instances.csv`, `fallback_stage_candidates.csv`, and `query_inventory.csv` are useful for debugging and validation, but they should be mined for evidence rather than preserved as runtime architecture.
4. The reverse-engineering folder is old baggage in operational terms, yet it is still valuable as a recovery lens when it reveals contract-aligned structure.
5. Ignore legacy forms that do not improve the current contracts; keep only the parts that help recover lineage, eligibility, provenance, or replay safety.

## Core Candidate-Generation Principles

1. Contract first: expansion eligibility, class lineage, and output schemas are governed by the Wikidata specification docs, not by notebook convenience.
2. Graph-first authority: graph evidence decides expansion; string matching only proposes candidates that must be re-validated against graph and class rules.
3. Class context is first-class: when the class is known, acquisition should use that context explicitly instead of treating every unknown string as a generic label search.
4. Event history is the durable record: all long-running decisions, discoveries, and repairs should be explainable from append-only event history and replayable projections.
5. Cache-first and incremental: reuse local state before network calls, and prefer deltas over full rebuilds wherever a projection can be updated safely.
6. Notebook as orchestrator: the notebook should explain and sequence workflow phases; the actual candidate-generation logic belongs in modules that can be tested and reused.
7. Operator clarity is part of correctness: every mode, flag, and fallback path must state its consequences explicitly in code and nearby markdown.
8. Clean-slate redesign is allowed: when a larger structural simplification reduces complexity without breaking contracts, it should be treated as a primary option rather than a last resort.

## Lineage Recovery Principle

1. Rebuild subclass logic from preserved evidence before inventing new heuristics.
2. Use the reverse-engineered hierarchy to recover local class closure, then validate it against the authoritative Wikidata contracts.
3. Let recovered class lineage drive both expansion eligibility and class-scoped acquisition paths.
4. Keep lineage recovery modular so it can be reused by expansion, fallback, node integrity, and notebook review steps.

## Highest-Potential Solution Hypothesis

Current best direction:

1. Recover and centralize class-lineage logic first, using `reverse_engineering_potential/class_hierarchy.csv` to rebuild subclass closure and core-class rollups locally.
2. Split candidate acquisition into a staged, context-aware strategy layer that can consume the recovered lineage.
3. Keep Stage A graph-first and authoritative.
4. Replace the current generic fallback-only mindset with a class-scoped acquisition path for long unresolved string sets, especially where the mention type or class is already known.
5. Make generic fallback string matching the last-resort branch, not the main growth path.
6. Re-enter all successful discoveries into the existing graph-first expansion and integrity flow.
7. Use a thin notebook shell to orchestrate setup, stage selection, and review, while moving more decision logic into testable modules.
8. Preserve append-only event history and handler progress so the new acquisition layer remains replay-safe.

Why this is the strongest opportunity:

1. It directly reduces pressure on Wikidata by narrowing search to known class context.
2. It recovers lost subclass logic from evidence instead of recreating it by hand or repeating network calls.
3. It reuses the existing expansion/eligibility machinery instead of bypassing it.
4. It scales to the user’s stated future case: thousands of known-class but unknown-identifier strings.
5. It creates a cleaner seam for later notebook consolidation because orchestration and acquisition logic become more modular.
6. It aligns with the fernsehserien_de lessons on clear phase boundaries, evented repair, and explicit handler/projection progress.

Analysis loop for the rework:

1. Inspect existing code and docs for the strictest governing rule, not just the easiest path.
2. Identify the smallest change that unlocks the highest downstream leverage.
3. Prefer solutions that improve both operator experience and runtime cost.
4. Re-evaluate whether the notebook shape itself should shrink whenever the module layer becomes more expressive.
5. Record the current best hypothesis here and revise it as implementation evidence improves.

## Workstream 0: Lineage Recovery Foundation

Priority: P0/P1

Objectives:

1. Reconstruct the lost subclass closure and class rollup logic from preserved reverse-engineering evidence.
2. Make recovered lineage available to expansion, fallback, integrity, and notebook review paths.
3. Keep the recovered model aligned with the normative Wikidata contracts.

Primary items:

1. GRW-011

Completion gate:

1. Class hierarchy recovery is available as a reusable local module or documented derivation path.
2. Recovered subclass logic matches the specification contracts on representative classes.
3. The lineage recovery layer can be consumed by Workstream 5 without duplicating logic.

Implementation detail:

1. Use `documentation/Wikidata/2026-04-10_great_rework/05_grw_011_lineage_recovery_implementation_plan.md` for code-level slicing, tests, rollout gates, and rollback policy.

## Ordered Workstreams (Top To Bottom)

### Workstream 1: Safety And Correctness Gate (must pass before large rerun)

Priority: P0

Objectives:

1. Eliminate silent misconfiguration risk in fallback mention-type behavior.
2. Ensure long-run timeout resilience and non-silent runtime progress.
3. Enforce handler-progress governance for deterministic resume/replay.

Primary items:

1. GRW-006
2. GRW-005
3. GRW-003 (handler-governance subset)
4. FND-001
5. FND-005

Completion gate:

1. Notebook 21 runs with explicit config behavior and no silent fallback to unintended defaults.
2. Long-run Step 6.5 emits regular heartbeat and survives transient timeout patterns.
3. Handler progress is auditable per run with before/after sequence visibility.

### Workstream 2: Runtime Cost And Throughput Gate

Priority: P0/P1

Objectives:

1. Reduce avoidable full rebuild costs.
2. Reduce query volume/wall-time for large refresh workloads.

Primary items:

1. GRW-003 (incremental materialization core)
2. GRW-004
3. FND-002
4. FND-003
5. FND-004

Completion gate:

1. Incremental mode is default and measurable.
2. Non-zero-network benchmark shows improved throughput and lower redundant calls.
3. Full rebuild retained only as explicit maintenance/recovery path.

### Workstream 3: Artifact Lifecycle Cutover

Priority: P1

Objectives:

1. Finish legacy JSON consumer cutover and writer removal.
2. Decide final lifecycle of `triple_events.json` with evidence.

Primary items:

1. GRW-007
2. GRW-008

Completion gate:

1. Consumer inventory complete with zero active runtime dependency on retired artifacts.
2. Triple-events retain/deprecate decision implemented and documented.

### Workstream 4: Architecture Simplification And Contract Hardening

Priority: P1/P2

Objectives:

1. Move toward clearer handler-first event workflow.
2. Formalize event-phase contracts.
3. Complete Parquet-first internal transition while preserving external contracts.

Primary items:

1. GRW-001
2. GRW-002
3. Phase-contract actions from transfer plan (Slice 4)

Completion gate:

1. Handler-first execution paths are demonstrably simpler and replay-safe.
2. Event phase contract is documented and test-enforced.
3. Runtime is Parquet-first where intended, with contract CSV outputs preserved.

### Workstream 5: Context-Aware Candidate Acquisition

Priority: P1

Objectives:

1. Add a faster lookup path for long string sets when the class context is known but the Wikidata identifier is not.
2. Reduce pressure on Wikidata by preferring class-scoped lookup strategies over generic fallback matching where appropriate.
3. Re-enter any successful discoveries into the existing graph-first expansion flow.

Primary items:

1. GRW-009

Completion gate:

1. At least one class-aware retrieval path is implemented and documented.
2. The notebook can choose between generic fallback and class-scoped retrieval based on context.
3. Successful results are merged back into the authoritative graph workflow without bypassing expansion rules.

### Workstream 6: Notebook Architecture Re-evaluation

Priority: P1/P2

Objectives:

1. Reassess the notebook’s cell boundaries and orchestration shape against the current event-sourcing direction.
2. Consolidate functionality where that reduces complexity and improves maintainability.
3. Deprecate unnecessary code paths once a cleaner architecture is proven.

Primary items:

1. GRW-010

Completion gate:

1. Notebook structure is intentionally justified rather than inherited.
2. Major orchestration can live in fewer cells or a more centralized control flow when that is the better fit.
3. Structural changes are documented against the rework philosophy and contract docs.

## Crosswalk Matrix (Backlog + Findings + Learnings)

1. GRW-006 <- WDT-020 <- Safety gate <- no direct fernsehserien dependency.
2. GRW-005 <- WDT-016 <- Workstream 1 <- fernsehserien heartbeat pattern (Learning 1).
3. GRW-003 <- WDT-014 <- Workstream 1 and 2 <- handler-progress + evented-repair patterns (Learning 2 and 3).
4. GRW-004 <- WDT-015 <- Workstream 2 <- observability support from Learning 1.
5. GRW-007 <- design step 05 <- Workstream 3 <- lifecycle discipline from Learning 5.
6. GRW-008 <- design step 06 <- Workstream 3 <- phase-boundary and event-contract guidance from Learning 4.
7. GRW-002 <- WDT-013 <- Workstream 4 <- independent of fernsehserien traversal model.
8. GRW-001 <- WDT-011 <- Workstream 4 <- handler-first orchestration patterns from Learning 2 and 4.

9. FND-001 supports Workstream 1 hygiene.
10. FND-002 supports Workstream 2 incremental materialization.
11. FND-003 supports Workstream 2 deterministic decision-cost controls.
12. FND-004 supports Workstream 2 graph-neighborhood performance optimization.
13. FND-005 supports Workstream 1 operator contract clarity.
14. FND-006 supports Workstream 1 external-caller compatibility hardening.
15. GRW-009 supports Workstream 5 class-scoped lookup efficiency.
16. GRW-010 supports Workstream 6 notebook consolidation and architecture review.
17. GRW-011 supports Workstream 0 lineage recovery and Workstream 5 class-aware acquisition.

## Execution Sequence (Canonical)

0. Workstream 0
1. Workstream 1
2. Workstream 5
3. Workstream 2
4. Workstream 4
5. Workstream 3
6. Workstream 6

Execution logic:

1. Recover lineage first (Workstream 0) so class-aware decisions have stable local structure.
2. Lock safety/correctness next (Workstream 1) so later optimization does not amplify bad assumptions.
3. Add class-aware acquisition early (Workstream 5) because it directly addresses high-volume unknown-string workloads.
4. Optimize throughput once acquisition direction is clear (Workstream 2).
5. Simplify and harden architecture after core behavior stabilizes (Workstream 4).
6. Perform legacy artifact cutover after new architecture paths are proven (Workstream 3).
7. Consolidate notebook shape last to avoid repeated orchestration churn during upstream redesign (Workstream 6).

Inside Workstream 1 and 2, use the detailed slices and code touchpoints from:

1. `documentation/Wikidata/2026-04-10_great_rework/04_fernsehserien_transfer_execution_plan.md`

## Intake Process For New Issues (Growth Mechanism)

When a new issue is discovered:

1. Assign new ID using prefix:
   - `GRW-XXX` for backlog-level work item
   - `FND-XXX` for codebase finding
2. Record it in source inventory document first.
3. Add a crosswalk row in this master map.
4. Place it into one workstream with priority and dependency notes.
5. Update execution sequence only if it changes critical path.

## Tracking Fields For Ongoing Updates

For each mapped item, maintain:

1. Status: not-started, in-progress, blocked, complete
2. Owner
3. Evidence link (test output, notebook run, docs)
4. Last updated date
5. Blocking dependency (if any)

## Change Log

1. 2026-04-09: Created canonical master map; source documents retained as referenced inventories.
