# Notebook Observability

This document defines the append-only notebook event log design used to track
major runtime behavior across multiple notebook runs.

Primary goal:

1. Keep a simple lifetime history of what happened during notebook execution,
   especially events that involve network calls.
2. Make long-run behavior understandable without reading transient notebook
   output.

Secondary goal:

1. Use a shared event shape across notebooks so rates, budgets, and failure
   patterns are comparable.

## Scope

This contract applies first to:

1. `speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb`

Then extends to all production notebooks.

## Implementation Status

Notebook 21 implementation is active as of 2026-04-01.

Integrated components:

1. Shared append-only writer utility: `speakermining/src/process/notebook_event_log.py`.
2. Network decision/call/backoff/budget event emission at request boundary:
   `speakermining/src/process/candidate_generation/wikidata/cache.py`.
3. Phase lifecycle events for graph stage, node integrity, and fallback stage:
   `expansion_engine.py`, `node_integrity.py`, `fallback_matcher.py`.
4. Runtime tests for append behavior and request-boundary event coverage:
   `speakermining/test/process/wikidata/test_notebook_event_log_runtime.py`.

## Principles

1. Append-only event stream: never rewrite or truncate historical log records.
2. One event per meaningful action: avoid verbose debug noise.
3. Network-centered observability: include all decisions that trigger, skip,
   retry, or stop network calls.
4. Run-spanning continuity: each run has its own `run_id`, all runs share one
   notebook log file.
5. Machine-readable first: JSON Lines (`.jsonl`) format with one JSON object per
   line.
6. Human-readable enough: event fields must support simple grep/filter and
   compact notebook-side summaries.

## Storage Contract

Base path:

1. `data/logs/notebooks/`

Per-notebook append-only log file:

1. `data/logs/notebooks/notebook_21_candidate_generation_wikidata.events.jsonl`

Optional run snapshot companion files (derived, replaceable):

1. `data/logs/notebooks/runs/notebook_21_<run_id>_summary.json`

Only `*.events.jsonl` is canonical append-only history.

## Event Taxonomy

All events use one `event_type` from this controlled set:

1. `run_started`
2. `run_finished`
3. `phase_started`
4. `phase_finished`
5. `network_decision`
6. `network_call_started`
7. `network_call_finished`
8. `network_backoff_applied`
9. `network_budget_blocked`
10. `network_error`
11. `checkpoint_written`
12. `log_repaired`

Minimum policy for notebook 21:

1. Log all `network_decision` events where an action may lead to remote access
   (cache hit/miss, stale refresh, skipped due to budget, etc.).
2. Log all actual network attempts (`network_call_started`/
   `network_call_finished`).
3. Log all throttling/backoff decisions (`network_backoff_applied`).

## Common Event Schema

Required fields for every event:

1. `timestamp_utc`: ISO-8601 UTC timestamp.
2. `notebook_id`: stable identifier, for example `notebook_21_candidate_generation_wikidata`.
3. `run_id`: UUID-like id created once per notebook execution.
4. `phase`: controlled name (for notebook 21: `stage_a_graph_expansion`,
   `node_integrity_discovery`, `node_integrity_expansion`,
   `stage_b_fallback_matching`, `fallback_reentry`).
5. `event_type`: value from taxonomy.
6. `event_id`: deterministic or random unique id within run.

Required fields for network-aware events (`event_type` starts with `network_`):

1. `network.endpoint`: endpoint key, for example `wikidata_api` or
   `wikidata_sparql`.
2. `network.request_kind`: logical call type, for example `entity_by_qid`,
   `inlinks_query`, `label_search`.
3. `network.decision`: one of `call`, `skip_cache_hit`, `skip_budget`,
   `retry`, `abort`.
4. `rate_limit.query_delay_seconds_configured`: configured delay.
5. `rate_limit.query_delay_seconds_effective`: effective delay after backoff.
6. `rate_limit.backoff_factor`: applied factor (1.0 if none).
7. `budget.max_queries_per_run`: configured budget semantics (`-1` for unlimited).
8. `budget.queries_used_before`: usage before decision/call.
9. `budget.queries_used_after`: usage after decision/call.

Strongly recommended fields:

1. `entity.qid` when a specific entity is involved.
2. `query.query_hash` for deterministic query identity where available.
3. `result.status`: `success`, `timeout`, `http_error`, `parse_error`, `skipped`.
4. `result.http_status` when applicable.
5. `result.duration_ms` for completed calls.
6. `result.records_count` for query result cardinality.
7. `message`: concise plain-language context.

## Example Event Records

```json
{"timestamp_utc":"2026-04-01T08:10:12Z","notebook_id":"notebook_21_candidate_generation_wikidata","run_id":"20260401T081001Z_8d4a","phase":"node_integrity_discovery","event_type":"network_decision","event_id":"dec_000184","network":{"endpoint":"wikidata_api","request_kind":"entity_by_qid","decision":"call"},"rate_limit":{"query_delay_seconds_configured":1.0,"query_delay_seconds_effective":1.0,"backoff_factor":1.0},"budget":{"max_queries_per_run":-1,"queries_used_before":21,"queries_used_after":21},"entity":{"qid":"Q1020038"},"message":"cache stale; refreshing entity"}
{"timestamp_utc":"2026-04-01T08:10:14Z","notebook_id":"notebook_21_candidate_generation_wikidata","run_id":"20260401T081001Z_8d4a","phase":"node_integrity_discovery","event_type":"network_call_finished","event_id":"call_000184","network":{"endpoint":"wikidata_api","request_kind":"entity_by_qid","decision":"call"},"rate_limit":{"query_delay_seconds_configured":1.0,"query_delay_seconds_effective":1.5,"backoff_factor":1.5},"budget":{"max_queries_per_run":-1,"queries_used_before":21,"queries_used_after":22},"entity":{"qid":"Q1020038"},"result":{"status":"success","http_status":200,"duration_ms":640,"records_count":1},"message":"entity payload stored"}
```

## Writer Behavior

1. Open log file in append mode only.
2. Write exactly one JSON record per line.
3. Flush line writes promptly for crash resilience.
4. Use guarded atomic helpers only for derived summary files, not for the
   canonical append stream.
5. Never delete old event lines automatically.

## Corruption Handling

1. Notebook log writers must tolerate malformed JSONL lines caused by abrupt
   interruption, external edits, or partial writes.
2. On logger initialization, if malformed lines are detected, they must be
   quarantined into a sibling `*.corrupt.<timestamp>` file and removed from the
   canonical stream.
3. Valid historical lines must be preserved in the canonical `*.events.jsonl`
   file.
4. A `log_repaired` event must be appended so repairs are auditable in-band.
5. This is a soft recovery path: repair should not block a normal notebook run
   unless file-lock constraints prevent rewriting the canonical log.

## Cross-Notebook Standardization

To compare notebooks, keep these fields identical everywhere:

1. `notebook_id`
2. `run_id`
3. `phase`
4. `event_type`
5. `network.*`
6. `rate_limit.*`
7. `budget.*`
8. `result.*`

Notebook-specific detail should live under namespaced objects, for example:

1. `wikidata.*`
2. `wikibase.*`
3. `mention_detection.*`

## Operational Reporting

Notebook heartbeat printouts should summarize the same event stream, not a
separate ad hoc metric set.

Recommended heartbeat snapshot fields:

1. elapsed runtime
2. calls per minute (rolling and total)
3. cache hit vs network call ratio
4. latest example action in plain language
5. current phase

## Retention And Review

1. Keep append logs in repository data storage unless a privacy/size policy
   requires archival.
2. Build optional derived monthly summaries from append logs for trend review.
3. Do not treat derived summaries as source of truth.

## Implementation Guidance

1. Add a small shared writer utility under `speakermining/src/process` that
   emits schema-valid records.
2. Integrate this utility at the network decision boundary, not only at
   successful responses.
3. Add tests for schema fields, append-only behavior, and budget/rate-limit
   field population.
4. Track rollout by notebook in `documentation/open-tasks.md`.
