# runtime-statistics

* priority: medium
* scope: workflow
* legacy-id: TODO-051

## Summary

Notebook cells and key functions emit no machine-readable timing or output statistics. Without this, performance regressions and progress visibility require manual inspection.

## Definition of done

1. A lightweight statistics emitter (function decorator or context manager) is implemented that records function name, start time, elapsed time, and a configurable output summary dict to a JSON-lines log.
2. All notebook cells' key functions are instrumented.
3. A verbosity level config controls output detail: level 0 = heartbeat only (always on), level 1 = cell-level stats, level 2 = function-level stats.
4. Statistics from the previous run are visible in the notebook output on re-run.

## Notes

Heartbeat is already implemented in Phase 21 (F1/F2 fixes). This task extends the concept to all notebooks.
