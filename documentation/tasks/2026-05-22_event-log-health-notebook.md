# event-log-health-notebook

**Identified by:** Data Engineer (review 05), task 5

## Problem

The pipeline writes event logs during execution (fetch decisions, errors, skipped items), but there is no tool to summarise the health of a completed run. After running a pipeline phase, a developer must read raw log files or inspect intermediate CSVs to answer basic operational questions: how many fetches succeeded? How many failed? What is the error rate by error type? Are there anomalous failure clusters by show or date?

Without a health summary, silent degradation (e.g., fernsehserien.de structure change causing 30% fetch failures) goes unnoticed until a downstream phase produces visibly wrong outputs.

## Action (code-scope, deferred)

Create a notebook or script `speakermining/src/process/notebooks/event_log_health.ipynb` (or `.py`) that:

1. Reads all event log files from a configurable run directory
2. Computes and displays: total events by type, success/failure ratio, error type distribution, fetch volume by date (to spot rate-limiting events), top-N error messages by frequency
3. Flags any metric outside a configurable threshold (e.g., error rate > 5%, fetch volume drop > 50% from prior run)
4. Outputs a one-page Markdown summary to the run directory as `health_summary.md`

The threshold configuration should live in the pipeline config, not hardcoded in the notebook.

## Definition of done

1. The health summary notebook/script exists and runs without error on a completed pipeline run directory.
2. It reports at minimum: total events, success/failure ratio, error type distribution.
3. It writes a `health_summary.md` to the run directory.
4. Threshold checks flag anomalous conditions with a clear message.
