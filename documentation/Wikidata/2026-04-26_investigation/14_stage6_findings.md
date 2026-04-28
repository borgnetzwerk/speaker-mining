# Stage 6 — Verification Findings
> Created: 2026-04-27  
> Purpose: Track issues discovered during verification runs. Each entry has a severity, status, and a clear resolution path.

---

## Severity Legend

- 🔴 **Critical** — prevents correct output or crashes the run
- 🟡 **Medium** — degrades correctness or performance significantly
- 🟢 **Low** — minor correctness gap or code quality issue

---

## Issues Found

---

### F1 — Heartbeat thread not running 🔴 ✅ Fixed

**Symptom:** No time-based progress output during the work loop. The specification requires output at least every 60 seconds and after every 50 network calls.

**Root cause:** The notebook work loop was not wrapped with `run_with_progress_heartbeat`. The per-call progress (every 50 calls) is already implemented in `cache._http_get_json` and works correctly. The time-based heartbeat (every 60 seconds) requires the background thread started by `run_with_progress_heartbeat`.

**Resolution:** Wrap Step 5 work loop function in `run_with_progress_heartbeat(repo_root, phase="main_loop", ...)`. The background thread calls `emit_event_derived_heartbeat` on the configured interval and also manages adaptive backoff adjustments.

---

### F2 — Graceful shutdown: SIGINT kills cell immediately 🔴 ✅ Fixed

**Symptom:** Ctrl+C raises `KeyboardInterrupt` mid-iteration (e.g., during `replay_all()` file I/O), leaving handlers in inconsistent partially-updated state.

**Root cause:** `should_terminate()` is checked at loop entry, but no signal handler converts SIGINT to the termination flag. Raw SIGINT propagates as `KeyboardInterrupt` through file I/O and interrupts mid-replay.

**Behavior requirement:** SIGINT should set the termination flag; the currently active handler finishes its current save point (one `_write()` call completes); then the loop exits cleanly.

**Resolution:** `run_with_progress_heartbeat` installs `_interrupt_handler` on `SIGINT`/`SIGTERM` which calls `request_termination()` instead of raising. After the flag is set, the work loop's `not should_terminate()` check exits at the next iteration boundary — the current handler finishes its `_write()` before the loop checks.

---

### F3 — `iter_events_from` scans entire log on every replay call 🟡 ✅ Fixed

**Symptom:** Each `replay_all()` call reads ALL events from sequence 0, even when `last_seq = 63880` and only 5 new events exist. This is O(total events) per handler per replay. For 8 handlers × frequent replays, this dominates runtime.

**Root cause:** `iter_events_from` calls `iter_all_events` which iterates every chunk from the first. No chunk-skipping based on known `first_sequence`.

**Resolution options:**
- (a) Skip chunks entirely where `first_sequence < from_sequence — chunk_size`. Requires reading chunk headers efficiently.
- (b) Reduce replay frequency: only call `replay_all()` every N operations, not after every single fetch. Acceptable if handlers can tolerate N-fetch lag.
- (c) Track a per-handler chunk cursor so replay starts mid-chain.

Option (b) is the simplest short-term fix. Track outstanding-event count and replay only every 10 operations or when a handler has work to do.

---

### F4 — `entity_marked_relevant` payload fields don't survive replay 🟡 ✅ Fixed

**Symptom:** `relevancy_map.csv` has empty `inherited_from_qid`, `inherited_via_pid`, `source_seed_qid` for all non-seed entities after a restart.

**Root cause:** `build_entity_marked_relevant_event` emits `{qid, core_class_qid, via_rule}`. But `RelevancyHandler._on_event` reads `{source_seed_qid, inherited_from_qid, via_pid}` when replaying `entity_marked_relevant`. The keys don't match — the handler fills these from its in-memory state during the live run, but can't recover them from the event on restart.

**Resolution:** Extend `build_entity_marked_relevant_event` payload to include `source_seed_qid`, `inherited_from_qid`, `inherited_via_pid`, `direction`. Update `RelevancyHandler._mark_relevant` to pass these fields. The event then becomes self-contained for replay.

---

### F5 — `entity_discovered` event not emitted before full_fetch 🟢 ✅ Fixed

**Symptom:** `EntityLookupIndexHandler` reacts to `entity_discovered` for first-encounter labels. Since `full_fetch.py` never emits `entity_discovered`, the lookup handler only learns labels from `entity_fetched` and `entity_basic_fetched` — which is sufficient, but doesn't match the §6.1 event contract.

**Root cause:** `full_fetch.py` emits `entity_fetched` + `triple_discovered × N` but not the preceding `entity_discovered`. Architecture doc §6.1 specifies `entity_discovered` as step 1.

**Resolution:** Add `build_entity_discovered_event` call at the start of `full_fetch()` before `entity_fetched`. Only emit if the QID is first-seen (needs a check, or FullFetchHandler can emit it before calling `full_fetch()`).

---

### F6 — `RelevancyHandler._reload_rules_from_events` iterates entire log inside event dispatch 🟢 ✅ Fixed

**Symptom:** Every `rule_changed` event during replay triggers a full event log scan inside `_on_event`. For a log with 100k events and multiple `rule_changed` events, this is O(n²).

**Root cause:** `_reload_rules_from_events` calls `iter_all_events` — a full scan — to find the latest hash, then loads the CSV. Called for every `rule_changed` event seen.

**Resolution:** Remove the inner `iter_all_events` scan. On `rule_changed`, simply reload the CSV directly (the event itself carries the hash; the file is always at a fixed path). Keep the last-seen hash in memory to avoid redundant reloads.

---

### F7 — ExternalEventReader readers read entire log for idempotency check 🟢 ✅ Fixed

**Symptom:** `SeedReader._get_registered_qids()` and `CoreClassReader._get_registered_qids()` each scan all 63880+ v3 events to build the "already registered" set. On startup this is slow, though it only runs once per notebook run.

**Root cause:** `_get_registered_qids` calls `iter_all_events` which reads every chunk.

**Resolution:** The fix from F3 (chunk-skipping) helps here too. Alternatively, maintain a compact index file (e.g. `seed_registered_index.txt`) written by `SeedHandler` that lists known QIDs — readers check this instead of scanning the log.

---

---

### F8 — `V4Handler.replay()` not interruptible; `_write()` not atomic 🔴 ✅ Fixed

**Rules violated:** H3 (graceful shutdown everywhere), H4 (heartbeat everywhere)

**Symptom:** If SIGINT arrives during `replay_all()` inside the work loop, the currently replaying handler is mid-event-loop with no chance to exit cleanly. Even after the work loop was wrapped with `run_with_progress_heartbeat`, the handler's own `replay()` method never checks the termination flag — it processes all queued events in a single blocking call. Additionally, `_write()` calls `path.write_text()` directly; a crash or interrupt mid-write produces a truncated file with no recovery path.

**Root cause:** `V4Handler.replay()` calls `process_batch(new_events)` in one shot with no termination check between events. `_write()` and `_save_seq()` write directly (no temp-file + rename pattern).

**Resolution:**  
1. `replay()` must iterate events one at a time, checking `should_terminate()` after each. On early exit it still calls `_write()` and `_save_seq()` for the events processed so far — the handler resumes from a consistent checkpoint on next run.  
2. Base class adds `_atomic_write_text(path, content)` helper (writes to `.tmp`, then `path.replace()`). All subclass `_write()` implementations must use this for every file they produce.  
3. `_save_seq()` must also be atomic (it persists the sequence pointer; corruption here causes replay from 0).

---

### F9 — Reverse-direction relevancy propagation not implemented 🟡 ✅ Fixed

**Rules violated:** E3 (backward propagation), E5 (bidirectional propagation)

**Symptom:** `RelevancyHandler` only propagates relevancy forward along triples (from subject to object). Rules with `direction: backward` or `direction: both` are never applied as reverse links — discovered objects are never marked relevant because of their inbound connections.

**Root cause:** `RelevancyHandler._propagate()` only checks `(subject, predicate, object)` in one direction. The `direction` field from `relevancy_relation_contexts.csv` is read but never used to trigger reverse evaluation.

**Resolution:** When propagating, check the rule's `direction` field. For `backward`/`both` rules, also check whether the object of a triple is already relevant and mark the subject relevant. Requires iterating discovered triples in reverse (object → subject) in addition to the forward pass.

---

### F10 — Core class constraint on relevancy rules not checked 🟡 ✅ Fixed

**Rules violated:** E4 (subject_core_class_qid / object_core_class_qid constraints)

**Symptom:** Relevancy rules in `relevancy_relation_contexts.csv` may specify `subject_core_class_qid` or `object_core_class_qid` to restrict which core class context the rule applies in. `RelevancyHandler` currently ignores these columns — rules are applied globally regardless of which core class is being evaluated.

**Root cause:** `_propagate()` and `_reload_rule_pids()` read only the `predicate_pid` column. The `subject_core_class_qid` / `object_core_class_qid` columns are never read.

**Resolution:** Store rules as `{predicate_pid: [(subject_core_class_qid, object_core_class_qid), ...]}` and filter during propagation by checking whether the entity being marked relevant is reachable under the matching core class.

---

### F11 — `rewiring_catalogue.csv` not implemented 🟡 ✅ Fixed

**Rules violated:** D4 (rewiring for cross-domain entities), D5/D6 (conflict resolution via rewiring)

**Symptom:** The architecture specifies a `rewiring_catalogue.csv` that remaps class membership for entities that span domain boundaries (e.g., a person classified under the wrong core class). No reader or handler for this file exists in v4.

**Root cause:** Not implemented — omitted during Stage 5.

**Resolution:** Add `RewireCatalogueReader` in `external_readers/`. On startup it emits `entity_rewired` events for each catalogue entry. `ClassHierarchyHandler` (or a new `RewiringHandler`) must react to `entity_rewired` by overriding the entity's effective class membership in the projection.

---

### F12 — Output handler doesn't differentiate P31 instances vs P279 subclass chain 🟡 ✅ Fixed

**Rules violated:** G3 (roles output must use the P279 subclass chain, not P31 instances)

**Symptom:** `CoreClassOutputHandler._write()` populates both `core_<class>.json` and `not_relevant_core_<class>.json` with all entities marked relevant, regardless of how they were found relevant. For the `roles` core class, the required output is entities connected via the P279 subclass chain — not P31 instances. The current handler writes P31 instances for all classes including roles.

**Root cause:** `output_handler.py` makes no distinction between core classes when building output. The same logic applies to all entries in `_core_classes`.

**Resolution:** Per-core-class output strategy. The architecture doc specifies that `roles` uses the P279 walk; other classes use P31 instances. Add a `strategy` or `output_mode` column to `core_classes.csv` (or hard-code by `filename` value) and branch in `_write()` accordingly.

---

### F13 — `description` and `aliases` always empty in output 🟢 ✅ Fixed

**Rules violated:** G4 (output must include description and aliases per entity)

**Symptom:** All entities in `core_<class>.json` have `"description": ""` and `"aliases": []`. The wbgetentities API response includes both fields and they are requested, but `full_fetch.py` never extracts them from the response.

**Root cause:** `full_fetch.py` only extracts labels (for the specified languages) and claims. Description/alias extraction was not implemented.

**Resolution:** In `full_fetch.py`, after extracting labels, also extract `descriptions[lang]` and `aliases[lang]` from the wbgetentities response. Pass them through `entity_fetched` event payload. `CoreClassOutputHandler` must read and populate these fields when building output entries.

---

### F14 — `rule_changed` does not trigger re-evaluation of deferred entities 🟡 ✅ Fixed

**Rules violated:** F8 (rule changes must invalidate prior `unlikely_relevant` classifications)

**Symptom:** When relevancy rules change (`rule_changed` event), `FetchDecisionHandler` reloads its `_rule_pids` set. However, entities previously classified as `unlikely_relevant` (basic_fetch deferred) are not re-evaluated against the new rules. They remain deferred indefinitely even if the new rules would have promoted them to `potentially_relevant`.

**Root cause:** `FetchDecisionHandler._on_event` handles `rule_changed` by calling `_reload_rule_pids()` only. It does not iterate `_deferred` to re-classify entries.

**Resolution:** After reloading rule PIDs on `rule_changed`, iterate all QIDs in `_deferred`. Re-run the fetch decision logic for each: if now `potentially_relevant`, move from `_deferred` to the immediate queue and emit a new `fetch_decision` event with `decision: immediately`.

---

### F15 — Cache age not checked against configured limit 🟢 ✅ Fixed

**Rules violated:** B2 (cached data older than 365 days must be treated as a cache miss)

**Symptom:** `full_fetch.py` checks whether a cached record exists (via `_latest_cached_record`) but never checks the record's `age_days` or timestamp. Records from years ago are used without re-fetching.

**Root cause:** `_latest_cached_record` returns the record dict; `full_fetch.py` returns early if any record exists, ignoring its age.

**Resolution:** After retrieving the cached record, check `record.get("timestamp_utc")` against `datetime.now(UTC)`. If the age exceeds `cfg.cache_max_age_days` (default 365), treat as a miss and proceed with a network fetch.

---

### F19 — Column name mismatch: `relevancy_relation_contexts.csv` vs handler code 🔴 ✅ Fixed

**Rules violated:** E1 (relevancy must propagate), E3/E4 (direction and constraint rules must apply)

**Symptom:** After a full run, `Entities relevant: 12` = exactly the 12 seeds. Zero propagation. All 106 discovered triple objects classified `unlikely_relevant`. `basic_fetch_state.csv` shows 106 entries all `pending_deferred`. Zero basic_fetch iterations. `Classes resolved: 0`.

**Root cause:** `FetchDecisionHandler._reload_rule_pids()` reads column `predicate_pid`, `RelevancyHandler._reload_rules_from_csv_direct()` reads columns `predicate_pid`, `subject_core_class_qid`, `object_core_class_qid`, and `direction`. The actual CSV uses `property_qid`, `subject_class_qid`, `object_class_qid`, and `can_inherit` (boolean TRUE/FALSE). All column reads return empty strings → `_rule_pids` is always empty → `FetchDecisionHandler` classifies every object as `unlikely_relevant` → `BasicFetchHandler` never has immediate-pending items → `RelevancyHandler` never propagates relevancy → zero expansion from seeds.

**Resolution:** Updated `FetchDecisionHandler._reload_rule_pids()` to read `property_qid`. Updated `RelevancyHandler._reload_rules_from_csv_direct()` to read `property_qid`, `subject_class_qid`, `object_class_qid`; map `can_inherit=TRUE` → `direction=forward` and skip non-inheritable rows entirely (only propagation-enabled rules matter for RelevancyHandler; FetchDecisionHandler includes all predicates regardless).

---

### F20 — P31/P279 triples from full_fetch don't reach ClassHierarchyHandler or `_p31_map` 🔴 ✅ Fixed

**Rules violated:** E4 (core class constraints require P31 data), D2 (class hierarchy must be walked for all discovered class nodes)

**Symptom:** `Classes resolved: 0` even after 12 full_fetches. `RelevancyHandler._p31_map` empty for all seed entities. All core class constraint checks fail → no propagation even after F19 fix.

**Root cause:** `ClassHierarchyHandler._on_event` only handles `entity_basic_fetched` for class node discovery. `RelevancyHandler._on_event` only handles `entity_basic_fetched` for `_p31_map` population. Seeds are full_fetched (not basic_fetched), so `entity_basic_fetched` never fires for them. Their P31 and P279 data arrives as `triple_discovered` events (emitted by `full_fetch.py`) but both handlers ignore `triple_discovered`.

**Resolution:** Added `triple_discovered` handler in `ClassHierarchyHandler`: P31 object → class node queued; P279 subject and object → class nodes queued. Added P31 tracking in `RelevancyHandler._on_event(triple_discovered)`: when `pid == "P31"`, updates `_p31_map[subject]`.

---

### F20b — Constraint check fails for all entities with unknown class (companion to F20) 🔴 ✅ Fixed

**Rules violated:** E4 (constraints must not silently block all propagation)

**Symptom:** Even with F19 and F20 applied, propagation would fail for newly discovered entities whose P31 class hasn't been resolved yet by `ClassHierarchyHandler`. All rules in `relevancy_relation_contexts.csv` have non-empty `subject_class_qid` and `object_class_qid`. With the strict check (`actual != expected`), an unknown class (empty string) would fail because `"" != "Q215627"`.

**Root cause:** `_constraints_match` fails when `_get_core_class()` returns `""` (class not yet resolved) by comparing `"" != expected_class`.

**Resolution:** Changed `_constraints_match` to only fail when the actual class is **known and wrong** — i.e., `if actual and actual != expected_class`. Unknown class (empty string) passes. Class hierarchy resolution then refines constraints over time as `class_resolved` events arrive.

---

### F21 — Forward triples that passed constraint with unknown class not re-evaluated when class resolves 🟡 Open

**Rules violated:** E4 (constraint precision degrades after class data becomes available)

**Symptom:** When a `class_resolved` event fires (after F20 fix), `RelevancyHandler` updates `_class_to_core` but does not re-check existing forward triples that were propagated using relaxed (unknown-class) constraints. Entities that would fail the stricter known-class check remain marked relevant.

**Root cause:** No "pending constrained triples" structure exists in `RelevancyHandler`. Constraint re-evaluation on `class_resolved` would require storing all forward triples by subject.

**Note:** The practical impact is limited. Relaxed constraints (F20b) produce some false positives (extra entities marked relevant) but these are filtered at the output stage — entities that don't match a core class land in `not_relevant_core_<class>.json`. The tradeoff (some extra basic_fetches + cleaner output files) is acceptable for now.

---

### F23 — `FullFetchHandler` never reacts to `entity_marked_relevant` 🔴 ✅ Fixed

**Rules violated:** G1 (all relevant entities must be full_fetched), architecture §6.1

**Symptom:** The handler docstring lists `entity_marked_relevant` as a handled event, but the implementation has no handler for it. Entities marked relevant via propagation (persons, orgs discovered via P371/P449 etc.) are never enqueued for full_fetch. Only seeds (from `seed_registered`) and objects passing `full_fetch_rules.csv` (which only match P31 triples, not relevancy predicates) enter the queue.

**Root cause:** Missing `entity_marked_relevant` case in `FullFetchHandler._on_event`.

**Resolution:** Added `entity_marked_relevant` handler: enqueues the newly-relevant entity at `depth=1` (one hop from seed). Already-full_fetched entities are skipped via the existing `_done` check.

---

### F16 — Inlinks (incoming triples) not fetched in v4 🟡 Open

**Rules violated:** C2 (inlinks must be fetched for full_fetch entities)

**Symptom:** `full_fetch.py` only fetches outgoing claims from the entity page. Wikidata inlinks (entities that reference this QID) require a SPARQL query (`haswbstatement:` or `wikibase:directClaim`). These are never issued in v4.

**Root cause:** Not implemented — inlink fetching was present in v3 but not carried over.

**Resolution:** After the main `wbgetentities` fetch, issue a SPARQL query for inlinks. The existing `_sparql_get_json` or equivalent can be used. Emit additional `triple_discovered` events with direction `inbound` for each inlink found. FetchDecisionHandler and RelevancyHandler must be updated to handle inbound triples.

**Note:** This is the highest-effort open item. Defer until all 🔴/🟡 items above are resolved.

---

### F22 — Heartbeat payload nesting grows unboundedly 🟢 ✅ Fixed

**Symptom:** Each `runtime_heartbeat` event stores the full previous heartbeat dict in `extra.heartbeat`. That dict contains `latest_payload_snapshot` from `snapshot_recent_activity()`, which is the payload of the most recently seen event — i.e., the previous `runtime_heartbeat` event. This creates recursive nesting: heartbeat N embeds heartbeat N-1's full payload, which embeds N-2's, etc. After 7 heartbeats (visible in the run output) the printed snapshot is already thousands of characters deep.

**Root cause:** In `_pump()`, `heartbeat` (the result of `emit_event_derived_heartbeat`) is stored verbatim as `extra["heartbeat"]` in the `runtime_heartbeat` event. `heartbeat["latest_payload_snapshot"]` is always the payload of the most recent event, which is the previous `runtime_heartbeat` — causing the recursive embedding.

**Resolution:** In `_pump()`, strip `latest_payload_snapshot` from the dict before storing it in the `runtime_heartbeat` event: `heartbeat_for_event = {k: v for k, v in heartbeat.items() if k != "latest_payload_snapshot"}`.

---

### F17 — No explicit root class terminator in class hierarchy walk 🟢 ✅ Fixed

**Rules violated:** D3 (walk must terminate at root classes Q35120 / Q1)

**Symptom:** `ClassHierarchyHandler` walks P279 upward until no new P279 targets are found. It does not explicitly check for Q35120 (entity) or Q1 (universe) and stop. In practice these root QIDs will eventually return empty P279 sets from the API, but if Wikidata ever adds a P279 for Q35120, the walk could continue indefinitely.

**Root cause:** No explicit `_ROOT_CLASSES` set checked during the walk.

**Resolution:** Add `_ROOT_CLASSES = {"Q35120", "Q1"}` to `ClassHierarchyHandler`. In `resolve_next()`, skip enqueueing any QID in `_ROOT_CLASSES`.

---

### F18 — No startup validation: relevancy rules vs known core classes 🟢 ✅ Fixed

**Rules violated:** I5 (config validation on startup)

**Symptom:** `relevancy_relation_contexts.csv` rows may reference `subject_core_class_qid` or `object_core_class_qid` values that are not in `core_classes.csv`. No validation catches this — the misconfigured rules are silently ignored.

**Root cause:** `RelevancyRuleReader` emits events without cross-referencing the core class registry. There is no startup validation step.

**Resolution:** After all readers run (end of Step 2), validate that every `subject_core_class_qid` and `object_core_class_qid` in the relevancy rules matches a registered core class QID. Log a warning (or raise) for any mismatch.

---

## Fixes Applied This Session

| ID | Description | Files Changed |
|----|-------------|---------------|
| F12 | `projection_mode` column read from `core_classes.csv` by `CoreClassReader`; carried in `core_class_registered` event; `CoreClassOutputHandler` stores it and branches in `_write()`: instances strategy uses P31 map, subclasses strategy uses `_subclass_entities_for_core()` (P279 chain via `_class_to_core`) | `event_log.py`, `external_readers/core_class_reader.py`, `handlers/output_handler.py` |
| F9, F10 | `RelevancyHandler` rewritten: `_rules_by_pid` stores direction + core class constraints per rule; `_triples_by_object` reverse index built during replay; `triple_discovered` checks both forward and backward directions; `entity_marked_relevant` triggers `_propagate_backward_from()`; `_constraints_match()` filters by `subject/object_core_class_qid` using `_p31_map` + `_class_to_core` | `handlers/relevancy_handler.py` |
| F3 | `_chunk_boundary_summary` rewritten to read only first+last lines (O(1) per chunk via `_read_first_jsonl_event`/`_read_last_jsonl_event`); `iter_events_from` now builds chunk order from already-computed infos and skips any chunk whose successor starts ≤ `from_sequence` | `event_log.py` |
| F4 | `build_entity_marked_relevant_event` extended with `source_seed_qid`, `inherited_from_qid`, `inherited_via_pid`, `direction`; `_mark_relevant` passes all fields; `_on_event` reads correct key `inherited_via_pid` (was `via_pid`) | `event_log.py`, `handlers/relevancy_handler.py` |
| F5 | `FullFetchHandler.do_next()` emits `entity_discovered` before calling `full_fetch()` | `handlers/full_fetch_handler.py` |
| F6 | `_reload_rules_from_events` replaced with `_reload_rules_from_csv_direct(rule_file)` — reads CSV directly, no log scan | `handlers/relevancy_handler.py` |
| F8 | `V4Handler.replay()` checks `should_terminate()` after each event; all `_write()` calls use atomic temp+rename via `_atomic_write_csv_rows()` / `_atomic_write_json()` / `_atomic_write_text()`; `_save_seq()` atomic | `handlers/__init__.py`, all 7 handler `_write()` methods |
| F13 | `build_entity_fetched_event` extended with `description`/`aliases`; `full_fetch.py` extracts both from API response; `output_handler._on_event` reads and stores them | `event_log.py`, `full_fetch.py`, `handlers/output_handler.py` |
| F14 | `_reevaluate_deferred()` added to `FetchDecisionHandler`; called after `_reload_rule_pids()` on `rule_changed`; promotes `unlikely_relevant` entries whose predicate now matches updated rules | `handlers/fetch_decision_handler.py` |
| F7 | `_registered_qids_from_projection_csv()` added to base reader; `SeedReader` reads `seeds.csv`; `CoreClassOutputHandler._write()` writes `core_class_registry.csv`; `CoreClassReader` reads it — no event-log scan on second run | `external_readers/__init__.py`, `seed_reader.py`, `core_class_reader.py`, `handlers/output_handler.py` |
| F18 | `RelevancyRuleReader._validate_core_class_refs()` added; reads `core_class_registry.csv` and prints warnings for any `subject/object_core_class_qid` not in the registered set; skipped on first run when registry doesn't exist yet | `external_readers/relevancy_rule_reader.py` |
| F15 | `full_fetch()` gains `max_cache_age_days=365` parameter; cache hit is discarded if `age_days > max_cache_age_days`, forcing a network re-fetch | `full_fetch.py` |
| F17 | `ClassHierarchyHandler._ROOT_CLASSES = frozenset({"Q35120", "Q1"})` added; walk no longer enqueues root class QIDs | `handlers/class_hierarchy_handler.py` |
| F19 | `FetchDecisionHandler._reload_rule_pids()`: reads `property_qid` (was `predicate_pid`). `RelevancyHandler._reload_rules_from_csv_direct()`: reads `property_qid`, `subject_class_qid`, `object_class_qid`; maps `can_inherit=TRUE` → `direction=forward`; skips non-inheritable rows | `handlers/fetch_decision_handler.py`, `handlers/relevancy_handler.py` |
| F20 | `ClassHierarchyHandler._on_event`: added `triple_discovered` case — P31 object and P279 subject/object queued for hierarchy resolution. `RelevancyHandler._on_event`: added P31 tracking in `triple_discovered` — updates `_p31_map[subject]` | `handlers/class_hierarchy_handler.py`, `handlers/relevancy_handler.py` |
| F20b | `RelevancyHandler._constraints_match`: changed to pass when class is unknown (`actual == ""`); only rejects when class is known and wrong | `handlers/relevancy_handler.py` |
| F23 | `FullFetchHandler._on_event`: added `entity_marked_relevant` case — enqueues newly-relevant QID at depth=1 | `handlers/full_fetch_handler.py` |
| F22 | `heartbeat_monitor._pump()`: strips `latest_payload_snapshot` from heartbeat dict before storing in `runtime_heartbeat` event extra | `heartbeat_monitor.py` |
| F11 | `entity_rewired` event type + builder added to `event_log.py`; `RewireCatalogueReader` created (reads `rewiring_catalogue.csv`, emits one `entity_rewired` per row, idempotent via `(subject,predicate,object,rule)` key); `ClassHierarchyHandler` handles `entity_rewired` with P279 predicate — queues subject+object for hierarchy resolution; `RelevancyHandler` treats `entity_rewired` like a synthetic `triple_discovered` (forward + backward propagation, constraint checks); notebook Step 2 cell updated to instantiate and run reader | `event_log.py`, `external_readers/rewire_catalogue_reader.py`, `handlers/class_hierarchy_handler.py`, `handlers/relevancy_handler.py`, `21_candidate_generation_wikidata.ipynb` |
| F1, F2 | Wrapped work loop in `run_with_progress_heartbeat` | `21_candidate_generation_wikidata.ipynb` (Step 4 + Step 5) |
| CSV column | `SeedReader`/`CoreClassReader` now read `wikidata_id` column | `external_readers/seed_reader.py`, `external_readers/core_class_reader.py` |
| CoreClass label | `CoreClassReader` uses `filename` column for output file naming | `external_readers/core_class_reader.py` |
| Missing rules file | Created `data/00_setup/full_fetch_rules.csv` with default rules | `data/00_setup/full_fetch_rules.csv` |
| FullFetchRuleReader | Raises `FileNotFoundError` if rules file missing (was silent) | `external_readers/full_fetch_rule_reader.py` |
