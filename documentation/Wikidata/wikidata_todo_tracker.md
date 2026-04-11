# Wikidata TODO Tracker

Date created: 2026-03-31
Scope: Wikidata candidate-generation and graph-quality tasks only

## Status Legend

- [ ] not started
- [~] in progress
- [x] completed

### [x] Learn from backoff patterns
Implemented behavior:

1. Runtime adaptive congestion control (heartbeat-driven):
	- Every heartbeat observes newly emitted network events for the active phase.
	- If backoff is observed in the last N heartbeat windows (default N=3), delay increases by +5%.
	- If no backoff is observed in the last N heartbeat windows, delay is fine-tuned by -1%.
2. Live request pacing updates:
	- Delay adjustments are applied directly to the active request context and affect subsequent network calls in the same run.
3. Persistent learning artifacts:
	- Learning rows are appended to `data/20_candidate_generation/wikidata/backoff_delay_learning.csv` for cross-run evidence.
	- End-of-phase summary prints observed safe/backoff delay ranges and records a summary row.
4. Dedicated event-sourcing handler:
	- `BackoffLearningHandler` derives `data/20_candidate_generation/wikidata/projections/backoff_pattern_windows.csv` from canonical `query_response` events.
	- Handler progress is tracked in `eventhandler.csv`, so learning is incremental and remembers the last processed event sequence.
5. Pattern-first architecture (not single-number averaging):
	- Learning is stored in ordinal windows (`window_index`, default 100 calls per window) per `(endpoint, source_step)` scope.
	- This preserves time-varying behavior (for example early lenient calls vs later stricter behavior) and avoids skew from naive global averages.
6. Startup warning in Notebook 21 config cell:
	- Historical evidence is evaluated at config time.
	- If configured delay is known backoff-prone, a warning with recommended delay is printed immediately.

Operator knobs in Notebook 21 Step 2 config:

- `adaptive_backoff_enabled`
- `adaptive_backoff_pattern_heartbeats`
- `adaptive_backoff_increase_factor`
- `adaptive_backoff_decrease_factor`
- `adaptive_backoff_min_delay_seconds`
- `adaptive_backoff_max_delay_seconds`