# claude-md-coding-conventions

* priority: high
* scope: workflow
* legacy-id: TODO-037

## Summary

No explicit warning against `run_phase*` wrapper functions exists in CLAUDE.md. This is the root cause of the orchestration drift in `phase-orchestration-drift` (TODO-036). CLAUDE.md must be extended to communicate notebook-first orchestration and coding conventions to AI assistants.

## Evidence

`documentation/coding-principles.md`; `phase-orchestration-drift` task. CLAUDE.md exists at repo root but does not address `run_phase*` wrappers or notebook-first orchestration.

## Definition of done

1. CLAUDE.md is updated to explicitly warn against `run_phase*` wrapper functions; instructs that all orchestration logic must live in notebook cells, not in module wrapper functions.
2. References `documentation/coding-principles.md` rather than duplicating it.
3. The rule is verified by confirming no new wrapper functions are introduced in Phase 31/32 refactor.

## Notes

CLAUDE.md was created (satisfying the original intent) but the specific coding convention content from the TODO-037 definition of done was not yet added. The current CLAUDE.md addresses synthesis work mode; it needs a separate section for coding conventions.
