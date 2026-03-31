# Step 4: Separate Graph Expansion Engine From Candidate Matching

Date: 2026-03-31
Status: Design and implementation contract
Scope: Explicit separation of graph-first discovery and secondary string-based candidate matching, including rules, interfaces, sequencing, and acceptance tests

---

## 1. Objective

This step enforces a strict two-stage candidate generation strategy:

1. Graph-first candidate discovery (authoritative):
- Discover candidates through direct Wikidata graph connectivity around seed broadcasting programs.
- Use only item-to-item edges and expansion eligibility rules.
- No literal/name matching in this stage.

2. Secondary string-based candidate matching (fallback only):
- Run only for unresolved targets not already discovered by graph expansion.
- Restrict search scope using known core class information (P31) wherever possible.
- Any newly discovered candidate must be re-evaluated for graph expansion eligibility.

The design goal is to reduce endpoint stress and maximize deterministic, policy-aligned discovery from existing Wikidata graph structure before using broader heuristic search.

---

## 2. Why Separation Is Required

## 2.1 Problems in current prototype behavior

Current prototype behavior gates neighbor expansion based on text match events, which causes architectural inversion:
- graph traversal depends on literal matching,
- graph coverage is incomplete for non-matching but structurally relevant nodes,
- endpoint budget is consumed by mixed responsibilities.

## 2.2 Required architecture outcome

Separation solves this by:
- making graph expansion independent of mention strings,
- ensuring deterministic, reproducible graph capture around seeds,
- reducing broad string-search pressure until graph-first pass is exhausted,
- making fallback matching measurable and reviewable as a second-stage operation.

---

## 3. Scope and Non-Goals

In scope:
- Explicit engine boundaries between graph expansion and string matching.
- Contracts for handoff data between stages.
- Eligibility re-check for new string-discovered candidates.
- Deterministic sequencing in notebook orchestration.

Out of scope:
- Final ranking model for string matches.
- Property allowlist/blacklist tuning (future iteration).
- UI/visualization concerns.

---

## 4. Canonical Two-Stage Pipeline

## 4.1 Stage A: Graph Expansion (authoritative)

Input:
- Valid seed QIDs from data/00_setup/broadcasting_programs.csv
- Core class QIDs from data/00_setup/classes.csv

Mechanics:
- Expand each seed fully before processing next seed.
- For each expanded item:
  - fetch entity payload,
  - build outlinks,
  - fetch paged inlinks,
  - persist discovered/expanded nodes and triples,
  - evaluate discovered neighbors with expandable target rule.

Expansion eligibility (must be enforced):
1. Seed node: expandable yes.
2. Non-seed: expandable only if direct link to any seed AND P31 in core classes.
3. Class node inlinks: discovered/persisted, never enqueued.

Output:
- Graph-discovered candidate set (authoritative stage output)
- Unresolved target set for Stage B
- Updated node/triple/event stores and checkpoint summary

## 4.2 Stage B: String-Based Matching (fallback)

Input:
- Unresolved targets only (not already resolved in Stage A)
- Existing graph context and known class scope

Mechanics:
- Perform string-based lookup restricted by known type scope where possible:
  - use mention type and known class expectations,
  - prefer candidates with P31 in relevant core classes,
  - avoid broad unconstrained search where scope can be narrowed.

Mandatory post-processing:
- For each newly discovered candidate from Stage B:
  - run expansion eligibility check using Stage A rule,
  - if eligible, enqueue into graph expansion queue and process,
  - if ineligible, keep as discovered-only fallback candidate.

Output:
- Additional fallback candidates for previously unresolved mentions
- Optional graph expansion enrichment for newly eligible nodes

---

## 5. Separation Contract (Module Interfaces)

## 5.1 Graph engine contract

Primary module:
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py

Contract:
```python
@dataclass(frozen=True)
class GraphExpansionResult:
    discovered_candidates: list[dict]
    resolved_target_ids: set[str]
    unresolved_targets: list[dict]
    newly_discovered_qids: set[str]
    expanded_qids: set[str]
    checkpoint_stats: dict


def run_graph_expansion_stage(
    repo_root: Path,
    *,
    seeds: list[dict],
    targets: list[dict],
    core_class_qids: set[str],
    config: ExpansionConfig,
) -> GraphExpansionResult: ...
```

## 5.2 Fallback matching contract

Primary module:
- speakermining/src/process/candidate_generation/wikidata/candidate_targets.py (target preparation)
- new matching module proposed: speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py

Contract:
```python
@dataclass(frozen=True)
class FallbackMatchResult:
    fallback_candidates: list[dict]
    newly_discovered_qids: set[str]
    eligible_for_expansion_qids: set[str]
    ineligible_qids: set[str]


def run_fallback_string_matching_stage(
    repo_root: Path,
    *,
    unresolved_targets: list[dict],
    core_class_qids: set[str],
    class_scope_hints: dict,
    config: dict,
) -> FallbackMatchResult: ...
```

## 5.3 Re-entry contract from Stage B to Stage A

Required function:
```python
def enqueue_eligible_fallback_qids(
    repo_root: Path,
    *,
    candidate_qids: set[str],
    seeds: set[str],
    core_class_qids: set[str],
    expansion_config: ExpansionConfig,
) -> dict: ...
```

Behavior:
- apply same expandable target rule used in Stage A,
- expand only eligible QIDs,
- persist events and update checkpoint/materialization.

---

## 6. Decision Rules (Explicit)

## 6.1 Authoritative discovery priority

Rule:
- Stage A output is authoritative whenever a mention is resolved by graph connectivity.

Implication:
- Stage B must not overwrite Stage A candidates for the same mention unless explicitly flagged as additional alternatives.

## 6.2 Stage B entry condition

Rule:
- Stage B runs only on unresolved targets.

Implication:
- Prevents redundant literal matching for already graph-resolved mentions.

## 6.3 Class-scope narrowing in Stage B

Rule:
- If mention type implies a class scope (for example person, organization, episode), prioritize candidates with compatible P31.

Implication:
- Reduces broad search and endpoint stress.

## 6.4 Re-check expansion eligibility for Stage B discoveries

Rule:
- Every newly found QID from Stage B must be checked against direct-link + core-class rule.

Implication:
- Ensures fallback discoveries can still enrich graph coverage when structurally relevant.

## 6.5 Determinism and replay safety

Rule:
- Both stages must write deterministic events and checkpoint state so reruns reproduce the same sequence under same inputs.

---

## 7. Notebook Orchestration Contract (Step 4)

Notebook remains orchestrator per coding principles.

Notebook file:
- 21_candidate_generation_wikidata.ipynb

Required execution cell sequence:
1. Setup/bootstrap cell (repo path, imports, configs)
2. Markdown: Stage A intent
3. Code: run graph expansion stage
4. Markdown: unresolved handoff intent
5. Code: build unresolved target set and class-scope hints
6. Markdown: Stage B intent
7. Code: run fallback string matching on unresolved targets
8. Markdown: eligibility re-check intent
9. Code: expand eligible fallback discoveries
10. Markdown: checkpoint and materialization intent
11. Code: run checkpoint materialization and summary display

Constraint:
- No orchestration wrapper module should replace notebook-level stage sequencing.

---

## 8. Data Artifacts and Handoff Tables

## 8.1 Required stage handoff artifacts

1. graph_stage_resolved_targets.csv
- mention_id, candidate_id, source=graph

2. graph_stage_unresolved_targets.csv
- mention_id, mention_type, mention_label, context

3. fallback_stage_candidates.csv
- mention_id, candidate_id, source=fallback_string, class_scope_match

4. fallback_stage_eligible_for_expansion.csv
- candidate_qid, eligibility_reason

5. fallback_stage_ineligible.csv
- candidate_qid, ineligibility_reason

These can be physical CSVs or checkpoint-projected tables from in-memory structures.

## 8.2 Merge policy for final candidates

Final candidates output is merged by priority:
1. graph source candidates
2. fallback source candidates for still-unresolved mentions
3. additional fallback alternatives retained as non-authoritative candidates

Dedup key:
- (mention_id, candidate_id)

---

## 9. Acceptance Tests (Step 4)

Target directory:
- speakermining/test/process/wikidata

Required tests:

1. test_graph_stage_runs_before_fallback_stage
- verifies stage order and that fallback receives unresolved targets only

2. test_graph_stage_not_literal_gated
- verifies graph neighbor expansion does not depend on string match presence

3. test_fallback_only_for_unresolved_targets
- verifies already resolved mentions are excluded from fallback stage input

4. test_fallback_class_scope_narrowing
- verifies fallback candidate selection uses P31 scope hints when available

5. test_fallback_discoveries_rechecked_for_graph_eligibility
- verifies new fallback QIDs are evaluated with direct-link + core-class rule

6. test_eligible_fallback_qids_are_expanded
- verifies eligible fallback QIDs are enqueued and expanded

7. test_ineligible_fallback_qids_are_not_expanded
- verifies ineligible fallback QIDs remain discovered-only

8. test_final_candidate_merge_priority
- verifies graph candidates remain authoritative over fallback for same mention

9. test_stage_determinism_on_rerun
- verifies stable stage outputs under identical inputs

---

## 10. Implementation Tasks

1. Refactor expansion_engine.py to remove any literal-match gate from neighbor expansion.
2. Add explicit unresolved-target output from Stage A.
3. Implement fallback_matcher.py for unresolved-target-only string matching.
4. Implement class-scope narrowing logic in fallback matcher.
5. Implement re-entry expansion function for eligible fallback discoveries.
6. Add stage handoff artifact writers or checkpoint-projected equivalents.
7. Update notebook orchestration cells for explicit two-stage control flow.
8. Add Step 4 acceptance tests.

---

## 11. Risk Assessment and Mitigations

Risk 1: fallback stage reintroduces broad endpoint load
- Mitigation: unresolved-only input + class-scope narrowing + strict budgets

Risk 2: stage merge ambiguity in final candidates
- Mitigation: explicit source priority and dedup contract

Risk 3: nondeterministic reruns due to mixed stage ordering
- Mitigation: fixed notebook cell execution order + deterministic sorting

Risk 4: accidental return to match-gated graph expansion
- Mitigation: dedicated acceptance test test_graph_stage_not_literal_gated

---

## 12. Definition of Done (Step 4)

Step 4 is complete when:
1. Graph expansion stage runs independently of literal matching and is the first authoritative discovery pass.
2. Fallback string matching runs only on unresolved targets.
3. Fallback discoveries are re-checked for expansion eligibility and expanded if eligible.
4. Final candidate merge preserves graph-stage authority.
5. Step 4 acceptance tests pass.
