# Concrete Remediation Map (Quick Wins First)

Date: 2026-04-03  
Target: Notebook 21, Cell 15 (Step 6 graph-first expansion)

---

## Baseline Symptoms To Fix

Observed runtime behavior indicates local I/O and scanning overhead dominates:

- Very low effective request throughput in Step 6.
- Long delay before first useful progress.
- Event store currently dominated by query_response events, with limited domain semantics emitted.

Measured structural factors in current code path:

- Cache lookups scan the whole event stream repeatedly.
- Event appends repeatedly initialize writer state by scanning chunks.
- Node and triple stores are rewritten in full for incremental updates.
- Full materialization runs after each seed.

---

## Refactor Order (Exact Sequence)

The order below is mandatory unless a blocker is discovered.

### Step 1 - Build O(1) cache lookup index for latest query records (quick win)

Problem:

- Latest cache record retrieval repeatedly scans all query_response events.

Change:

- Introduce a process-local index keyed by source_step and key to resolve latest event in O(1) after initial load.
- Add invalidation only when new query_response is appended in current run.

File targets:

- speakermining/src/process/candidate_generation/wikidata/cache.py
- speakermining/src/process/candidate_generation/wikidata/event_log.py

Expected speedup:

- Step 6 runtime: 2.5x to 6x
- First progress latency: 3x to 10x improvement on large chunk stores

Risk:

- Medium: stale index bugs if invalidation is wrong.

Guardrail:

- Unit tests for cache hit freshness and age checks across append events.

---

### Step 2 - Reuse a single EventStore writer per run context (quick win)

Problem:

- Each event append reconstructs EventStore and rescans chunks for sequence and event count.

Change:

- Add a writer singleton or stage context writer so append operations are O(1) appends.
- Keep chunk rotation behavior identical.

File targets:

- speakermining/src/process/candidate_generation/wikidata/event_log.py
- speakermining/src/process/candidate_generation/wikidata/event_writer.py
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
- speakermining/src/process/candidate_generation/wikidata/entity.py

Expected speedup:

- Step 6 runtime: 1.4x to 2.5x
- Event append overhead: 5x to 20x faster for append-heavy sections

Risk:

- Low to medium: writer lifecycle and shutdown handling.

Guardrail:

- Integration test for monotonic sequence continuity across multiple appends in one run.

---

### Step 3 - Add expansion-loop write buffering for mutable JSON stores (quick win)

Problem:

- entities.json, properties.json, and triples_events.json are repeatedly loaded and fully rewritten.

Change:

- Introduce in-memory buffers for node and triple updates during seed expansion.
- Flush once per seed (or once per N updates) atomically.
- Preserve current file formats for compatibility in this step.

File targets:

- speakermining/src/process/candidate_generation/wikidata/node_store.py
- speakermining/src/process/candidate_generation/wikidata/triple_store.py
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py

Expected speedup:

- Step 6 runtime: 1.8x to 3.5x
- Disk write count reduction: often >90 percent in dense expansions

Risk:

- Medium: flush timing and crash recovery interaction.

Guardrail:

- Crash simulation test: interruption before flush must not corrupt existing store.

---

### Step 4 - Replace per-seed full materialization with checkpoint-lite mode (quick win)

Problem:

- Full rebuild of instances, classes, properties, triples, and query_inventory runs after every seed.

Change:

- Add checkpoint-lite mode at seed boundaries:
  - Persist checkpoint manifest and minimal counters.
  - Defer full materialization to every N seeds and final stage.
- Make N configurable, default 3 or 5.

File targets:

- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
- speakermining/src/process/candidate_generation/wikidata/materializer.py
- speakermining/src/process/candidate_generation/wikidata/checkpoint.py

Expected speedup:

- Total Step 6 wall-clock: 1.5x to 4x depending on seed count and projection size

Risk:

- Low to medium: checkpoint expectations in downstream notebook cells.

Guardrail:

- Ensure Step 10 still sees correct projections after final materialization.

---

### Step 5 - Activate incremental handler orchestration in Stage A

Problem:

- Handler framework exists but Stage A runtime still uses monolithic materializer path.

Change:

- Invoke handlers orchestrator incrementally at checkpoint boundaries using eventhandler progress.
- Only process unhandled sequences, not full event history each time.

File targets:

- speakermining/src/process/candidate_generation/wikidata/handlers/orchestrator.py
- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
- speakermining/src/process/candidate_generation/wikidata/handler_registry.py

Expected speedup:

- Projection update cost: 1.5x to 3x faster than full rebuild strategy
- Better scalability as chunks grow

Risk:

- Medium: ordering and idempotency across handlers.

Guardrail:

- Determinism tests comparing outputs across reruns and resume boundaries.

---

### Step 6 - Introduce missing domain events (true v3 semantics unlock)

Problem:

- Event stream mostly carries query_response and boundary events.
- Runtime decisions are not represented as first-class events.

Change:

- Emit domain events during Stage A:
  - entity_discovered
  - entity_expanded
  - triple_discovered
  - class_membership_resolved
  - expansion_decision
- Keep query_response for provenance, but projections should consume domain events where possible.

File targets:

- speakermining/src/process/candidate_generation/wikidata/expansion_engine.py
- speakermining/src/process/candidate_generation/wikidata/event_log.py
- speakermining/src/process/candidate_generation/wikidata/handlers/*.py
- speakermining/src/process/candidate_generation/wikidata/schemas.py

Expected speedup:

- Direct speedup: 1.1x to 1.5x
- Main benefit: architecture unlock for scalable incremental projection and diagnostics

Risk:

- Medium to high: schema migration and handler dual-support period.

Guardrail:

- Versioned event schema tests and replay tests from mixed event streams.

---

### Step 7 - Optional optimization pass after stabilization

Change candidates:

- Append-only binary or compact index sidecars for chunk lookups.
- Batch event append API for bursts from a single expansion node.
- Adaptive materialization frequency based on event volume and elapsed time.

Expected speedup:

- Additional 1.2x to 1.8x possible

Risk:

- Medium. Only run after Steps 1 to 6 are stable.

---

## Expected Cumulative Impact

Conservative cumulative expectation if Steps 1 to 5 are completed correctly:

- End-to-end Step 6: 5x to 12x faster on the same dataset and query budget settings.

Aggressive but plausible upper range with Step 6 included and well-tuned:

- End-to-end Step 6: 8x to 20x faster on warm-cache heavy runs.

Note:

- Speedups are multiplicative only when bottlenecks are independent. Realized gain will be lower where bottlenecks overlap.

---

## Why This Order Is Correct

1. Steps 1 and 2 remove repeated full scans that currently occur per query lookup and append.
2. Step 3 reduces catastrophic file rewrite amplification in the tight expansion loop.
3. Step 4 removes frequent full projection rebuild overhead.
4. Step 5 migrates runtime behavior onto eventhandler progress model already implemented.
5. Step 6 aligns runtime semantics with event sourcing goals and future maintainability.

This sequence minimizes migration risk while unlocking performance quickly.
