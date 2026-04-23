# V2-Only Policy (Legacy Fully Removed)

Date: 2026-03-31  
Status: Mandatory

## Policy Decision

All legacy Wikidata code paths and legacy data handling are removed.

The repository is now canonical v2-only for Wikidata query events, graph expansion artifacts, and materialization flows.

## Binding Rules For Future Coding

1. Do not implement or reintroduce readers, adapters, migration shims, or fallback branches for pre-v2 raw event records.
2. Do not add runtime checks that branch behavior for old artifact schemas.
3. Do not reference legacy directories, filenames, or compatibility assumptions in production paths.
4. Delete obsolete legacy modules instead of keeping fail-fast wrappers or compatibility placeholders.
5. Treat pre-v2 artifacts as out-of-scope for runtime logic.
6. If a historical migration concern appears, resolve it operationally outside runtime code, not via compatibility implementation.
7. Tests must not import legacy module names solely to assert deprecation behavior.

## Scope

This policy applies to:
- speakermining/src/process/candidate_generation/wikidata/*
- speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb
- associated tests under speakermining/test/process/wikidata/*
- transition documentation in documentation/Wikidata/2026-03-31_transition/*

## Enforcement Guidance

- New pull requests should be reviewed for accidental reintroduction of legacy compatibility logic.
- Tests should validate canonical v2 schema behavior and deterministic pipeline contracts only.
- Documentation updates should preserve v2-only assumptions.
- Any legacy module that serves no canonical v2 runtime function should be removed from the repository.

## Rationale

The migration cleanup was completed manually, and no legacy artifacts remain.
Reintroducing legacy compatibility would increase complexity, create ambiguity, and conflict with deterministic contract-driven pipeline behavior.
