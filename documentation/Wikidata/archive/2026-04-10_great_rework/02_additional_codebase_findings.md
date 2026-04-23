# Wikidata Great Rework - Additional Codebase Findings

Date: 2026-04-09
Source: open git changes and current runtime/test updates

Note:

1. This file is a retained source inventory.
2. Canonical planning and execution order lives in `documentation/Wikidata/2026-04-10_great_rework/00_master_rework_map.md`.

## Findings To Track In Great Rework

### FND-001 (P0): Notebook text encoding corruption in tracked notebook JSON

Observed:

- Unicode symbols in notebook source are currently mojibake (`✓`, `->`, bullet symbols rendered as `â...`).
- This appears in tracked JSON source lines of `21_candidate_generation_wikidata.ipynb`.

Risk:

- Operator-facing notebook readability regression.
- Potential false diffs/churn and accidental semantic edits in notebook cells.

Action:

1. Normalize notebook encoding in source control.
2. Add notebook text sanity check in CI/pre-commit for common mojibake signatures.

### FND-002 (P1): Materializer currently rewrites chunk artifacts per run

Observed:

- `_write_entity_lookup_artifacts(...)` removes existing chunk files and rewrites chunk/index artifacts in full.

Risk:

- Large-runtime rewrite costs remain high.
- Conflicts with strict event-sourcing/deprecation goals for full rebuild paths.

Action:

1. Design incremental chunk writer/update strategy.
2. Limit full rebuild to explicit maintenance mode only.

### FND-003 (P1): Eligibility resolution path can trigger network fetches during Stage A decisions

Observed:

- `_resolve_direct_or_subclass_core_match(...)` may call `get_or_fetch_entity(...)` while deciding expandability.

Risk:

- Additional network pressure in hot eligibility loops.
- Harder to reason about deterministic performance envelopes.

Action:

1. Bound class-chain hydration network behavior explicitly.
2. Separate decision-time cache-only mode from optional hydration mode.

### FND-004 (P1): Repeated seed-neighborhood degree recomputation can become expensive

Observed:

- `seed_neighbor_degrees(...)` constructs adjacency from triples in full scans when invoked.

Risk:

- Repeated O(E) traversals for large triple volumes.

Action:

1. Cache/derive neighborhood degree map incrementally.
2. Recompute only on relevant triple deltas.

### FND-005 (P1): Resume-mode contract changed (restart removed), migration impact must be explicit

Observed:

- Resume modes now accept only `append` and `revert`; `restart` rejected.

Risk:

- Existing operator procedures or scripts may still assume `restart`.

Action:

1. Add migration note/changelog entry for operators.
2. Validate notebook/documentation consistency in all runbooks.

### FND-006 (P2): Fallback runtime now hard-requires explicit mention-type config

Observed:

- `run_fallback_string_matching_stage(...)` raises `ValueError` if `fallback_enabled_mention_types` missing.

Risk:

- External callers/tests/scripts without updated config will fail.

Action:

1. Keep this strict requirement, but document in API contract docs and operational templates.
2. Add one compatibility diagnostic helper for callers that omit required key.

## Recommendation

Treat FND-001 and FND-005 as immediate pre-rerun hygiene, and execute FND-002/FND-003/FND-004 as core Great Rework performance tracks.
