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

### F21 — Forward triples that passed constraint with unknown class not re-evaluated when class resolves 🟡 Deferred (post-deadline 2026-05-03)

**Rules violated:** E4 (constraint precision degrades after class data becomes available)

**Symptom:** When a `class_resolved` event fires (after F20 fix), `RelevancyHandler` updates `_class_to_core` but does not re-check existing forward triples that were propagated using relaxed (unknown-class) constraints. Entities that would fail the stricter known-class check remain marked relevant.

**Root cause:** No "pending constrained triples" structure exists in `RelevancyHandler`. Constraint re-evaluation on `class_resolved` would require storing all forward triples by subject.

**Impact:** Relaxed constraints (F20b) produce some false positives (extra entities marked relevant) but these are filtered at the output stage — entities that don't match a core class land in `not_relevant_core_<class>.json`. The tradeoff (some extra basic_fetches + cleaner output files) is acceptable for the current deadline.

**Deferred because:** Does not affect Phase 5's ability to read or use the output files. False-positive relevant entities appear in `not_relevant_core_*.json`, not in `core_*.json`. No Phase 5 analysis is blocked by this gap.

---

### F23 — `FullFetchHandler` never reacts to `entity_marked_relevant` 🔴 ✅ Fixed

**Rules violated:** G1 (all relevant entities must be full_fetched), architecture §6.1

**Symptom:** The handler docstring lists `entity_marked_relevant` as a handled event, but the implementation has no handler for it. Entities marked relevant via propagation (persons, orgs discovered via P371/P449 etc.) are never enqueued for full_fetch. Only seeds (from `seed_registered`) and objects passing `full_fetch_rules.csv` (which only match P31 triples, not relevancy predicates) enter the queue.

**Root cause:** Missing `entity_marked_relevant` case in `FullFetchHandler._on_event`.

**Resolution:** Added `entity_marked_relevant` handler: enqueues the newly-relevant entity at `depth=1` (one hop from seed). Already-full_fetched entities are skipped via the existing `_done` check.

---

### F16 — Inlinks (incoming triples) not fetched in v4 🟡 Deferred (post-deadline 2026-05-03)

**Rules violated:** C2 (inlinks must be fetched for full_fetch entities)

**Symptom:** `full_fetch.py` only fetches outgoing claims from the entity page. Wikidata inlinks (entities that reference this QID) require a SPARQL query. These are never issued in v4.

**Root cause:** Not implemented — inlink fetching was present in v3 but not carried over.

**Resolution (future):** After the main `wbgetentities` fetch, issue a SPARQL query for inlinks; emit additional `triple_discovered` events with direction `inbound`. FetchDecisionHandler and RelevancyHandler must be updated to handle inbound triples.

**Deferred because:** Highest-effort open item. Does not affect Phase 5's ability to read or use current output files. No analysis in Phase 5 depends on inlinks being present in the event log.

---

### F22 — Heartbeat payload nesting grows unboundedly 🟢 ✅ Fixed

**Symptom:** Each `runtime_heartbeat` event stores the full previous heartbeat dict in `extra.heartbeat`. That dict contains `latest_payload_snapshot` from `snapshot_recent_activity()`, which is the payload of the most recently seen event — i.e., the previous `runtime_heartbeat` event. This creates recursive nesting: heartbeat N embeds heartbeat N-1's full payload, which embeds N-2's, etc. After 7 heartbeats (visible in the run output) the printed snapshot is already thousands of characters deep.

**Root cause:** In `_pump()`, `heartbeat` (the result of `emit_event_derived_heartbeat`) is stored verbatim as `extra["heartbeat"]` in the `runtime_heartbeat` event. `heartbeat["latest_payload_snapshot"]` is always the payload of the most recent event, which is the previous `runtime_heartbeat` — causing the recursive embedding.

**Resolution:** In `_pump()`, strip `latest_payload_snapshot` from the dict before storing it in the `runtime_heartbeat` event: `heartbeat_for_event = {k: v for k, v in heartbeat.items() if k != "latest_payload_snapshot"}`.

---

### F24 — `class_resolved` event missing `core_class_qid` field 🔴 ✅ Fixed

**Rules violated:** D2 (class hierarchy resolution must propagate to all consumers), G1 (output files depend on class assignment)

**Symptom:** Even with F19/F20 applied, `core_*.json` files remain empty. `class_resolution_map.csv` is populated correctly by `ClassHierarchyHandler._write()`, but all entities in `core_<class>.json` are absent. `RelevancyHandler._class_to_core` is also never updated from `class_resolved` events, so core class constraints (F10) remain unenforced even after class hierarchy is walked.

**Root cause:** Two independent bugs compound:  
1. `build_class_resolved_event` only emits `class_qid`, `parent_qids`, `depth` — it never includes `core_class_qid`. Both `RelevancyHandler._on_event("class_resolved")` and `CoreClassOutputHandler._on_event("class_resolved")` read `core_class_qid` (or `core_class_ancestor`) from the event payload; since the field is absent they can never update `_class_to_core`.  
2. In `ClassHierarchyHandler._walk()`, `core = self._find_core_ancestor(parent_qids)` was computed **after** `self._emit(event)` — meaning even if the event builder were fixed, the computed core value was computed too late (after the event was already in the log).

As a consequence, `CoreClassOutputHandler._resolve_core_classes(entity_qid)` always returns `[]` for entities whose P31 class is not a direct core class (i.e., is a subclass of one), and `relevant_by_core` / `not_relevant_by_core` remain empty for those entities → empty JSON files.

**Resolution:**  
1. `build_class_resolved_event` in `event_log.py`: added `core_class_qid: str = ""` parameter; field included in emitted payload.  
2. `ClassHierarchyHandler._walk()`: moved `core = self._find_core_ancestor(parent_qids)` and `self._resolved[qid] = {...}` to **before** `build_class_resolved_event` / `self._emit()` — ensuring core is computed before the event is emitted. `core_class_qid=core` passed to builder.  
3. `ClassHierarchyHandler._write()`: renamed CSV column header from `core_class_ancestor` to `core_class_qid` (matches architecture §5 spec).  
4. `RelevancyHandler._on_event("class_resolved")`: changed `payload.get("core_class_ancestor", "")` → `payload.get("core_class_qid", "")` for consistent field name.  
5. `CoreClassOutputHandler._on_event("class_resolved")`: already read `core_class_qid` — now correctly receives the field. Fallback via `parent_qids` retained for backward compatibility with old events already in the log.

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

### F26 — `basic_fetch_state.csv` missing classification, predicate, and subject columns 🟡 ✅ Fixed

**Rules violated:** Architecture §5 (BasicFetchHandler projection spec)

**Symptom:** `basic_fetch_state.csv` only contains `qid` and `status`. There is no way to tell from the projection how an entity was classified, which predicate connected it to its relevant subject, or which subject triggered the queue entry. The spec requires `qid, classification, status, predicate_pid, subject_qid`.

**Root cause:** `BasicFetchHandler._write()` wrote only two columns. The handler stored no provenance from `fetch_decision` events — only the QID and queue membership. Additionally, when a rule change promoted an entity from `unlikely_relevant` to `potentially_relevant`, the old deferred entry was never removed from `_pending_deferred`, leaving it in both queues simultaneously.

**Resolution:** Added `_info: dict[str, dict]` to `BasicFetchHandler` storing `{classification, subject_qid, predicate_pid}` per QID, populated on every `fetch_decision` event. For promotion events (`potentially_relevant` arriving for a previously-deferred QID), the entry is now removed from `_pending_deferred` before being added to `_pending_immediate`. Extended `build_fetch_decision_event` in `event_log.py` to include `subject_qid` and `predicate_pid` fields; `FetchDecisionHandler._classify()` now passes both. `_write()` outputs all five spec columns with statuses `pending`, `deferred`, `complete`.

---

### F27 — `full_fetch_state.csv` missing `reason` and `fetched_at` columns 🟢 ✅ Fixed

**Rules violated:** Architecture §5 (FullFetchHandler projection spec)

**Symptom:** `full_fetch_state.csv` wrote `qid, status, depth`. The spec requires `qid, status, reason, fetched_at`. There was no timestamp for when a full_fetch completed, and the queue entry's queuing reason (seed vs. relevancy propagation vs. rule match) was not recorded.

**Root cause:** `_done` was a `set[str]`, holding no timestamp. `_queue` was a `list[tuple[str, int]]` with no reason field.

**Resolution:** Changed `_done` to `dict[str, str]` (`qid → fetched_at`) — timestamp captured from `event["timestamp_utc"]` when `entity_fetched` fires. Changed `_queue` to `list[tuple[str, int, str]]` (`qid, depth, reason`). Reason values: `"seed"` (seed_registered), `"entity_marked_relevant"` (relevancy propagation), `"full_fetch_rule"` (triple_discovered matching rules). `_write()` outputs five columns: `qid, status, depth, reason, fetched_at`. All internal tuple-unpacking updated accordingly.

---

### F25 — v4 has no dedicated entity store; all entity data lives in the event log 🟢 ✅ Fixed (Phase 5 access interface)

**Observation:** In v3, `entity_store.jsonl` and `entity_chunks/*.jsonl` provided a persistent mutable key-value store for full entity records (all claims, labels, descriptions, aliases). Downstream code could look up any entity by QID without touching the event log.

In v4, this store was eliminated. All entity data is reconstructed from event-log replay at startup: `triple_discovered` events carry individual claims and `entity_fetched` carries the label/description/aliases. `CoreClassOutputHandler` accumulates the full record in-memory dicts (`_triples`, `_labels`, `_descriptions`, `_aliases`) during each run and writes them out as `core_*.json` at the end.

**Current state (updated 2026-04-29):** The `_latest_cached_record(root, "entity", qid)` + `_entity_from_payload(...)` pattern provides O(1) QID-based lookup for any entity that has been full_fetched. This is the v4 equivalent of the v3 entity store for relevant entities. After the F29 fix (per-QID basic_fetch events), the lookup also covers non-full_fetched entities via `_latest_cached_record(root, "basic_fetch", qid)`. The pattern is demonstrated in `CoreClassOutputHandler._get_entity_from_cache()` and is usable by later pipeline stages. Basic_fetch records contain only `labels|claims` (no descriptions/aliases); full_fetch records contain the complete Wikidata document.

**Resolution (2026-04-29) — Public Phase 5 access API:** Created `entity_access.py` exposing three functions for downstream phases:

- `get_cached_entity_doc(qid, repo_root)` — O(1) lookup of the best available raw Wikidata entity doc from the event log cache (full_fetch preferred, basic_fetch fallback). Returns `None` if not cached.
- `ensure_basic_fetch(qid, repo_root, languages)` — cache hit returns same as above; on miss, issues a network call via `basic_fetch_batch`, stores the result in the event log cache, then returns the doc. Returns `None` only on network failure or QID not found.
- `load_core_entities(repo_root, class_filename)` — reads `core_<class_filename>.json` from the projections directory and returns it as `{QID: entity_doc}`.
- `load_all_core_entities(repo_root)` — merges all `core_*.json` files into a single `{QID: entity_doc}` dict.

All calls that result in network fetches still populate the event log cache.

**Deferred (post-deadline 2026-05-03) — `all_outlink_fetch`:** A third fetch tier — full claims without the inlinks expansion — is needed for manually curated QIDs that need more than basic_fetch but must not trigger the full inlinks fetch. Implementation deferred; callers needing this before then should use `full_fetch.full_fetch()` directly.

**Deferred (post-deadline) — append-only entity index:** If the dataset grows to the point where startup replay becomes a bottleneck, reintroduce an incremental entity index as a handler projection. Not needed at current scale.

---

### F29 — `basic_fetch_batch` stores one event per batch (key=batch[0]); other QIDs unindexable 🟢 ✅ Fixed

**Rules violated:** B1 (cache must be consulted before network), later-stage QID lookup

**Symptom:** `basic_fetch_batch` issues one `wbgetentities` API call per batch of up to 50 QIDs, then stores a single query event with `key=batch[0]` and the full `entities` block in the payload. Only the first QID is indexed in `_LATEST_QUERY_EVENT_INDEX`. Looking up any other QID from that batch — via `_latest_cached_record(root, "basic_fetch", qid)` or `_try_entity_cache` — returns None even though the data is in the event log. Additionally, `_try_entity_cache` only searched `source_step="entity_fetch"` (full_fetch records) and never fell back to `source_step="basic_fetch"`, so previously basic_fetched entities were always re-fetched from the network on clean state.

**Root cause:** The original batch implementation emitted one event per API call for compactness, and the cache lookup only covered full_fetch (entity_fetch source_step).

**Resolution (2026-04-29):**
1. `basic_fetch_batch` now emits one event per QID — each with `key=qid` and `payload={"entities": {qid: entity_doc}}`. The single API call is still made; events are emitted per-QID inside the response loop.
2. `_try_entity_cache` now searches `("entity", "basic_fetch")` in order, using the first hit. This means previously basic_fetched entities are served from cache without a network call.

---

### F30 — `not_relevant_core_*.json` always empty for basic_fetch-only entities 🟢 ✅ Fixed

**Rules violated:** G2 (output files must include classified non-relevant entities for audit purposes)

**Symptom:** `CoreClassOutputHandler._get_entity_from_cache` looked up only `source_step="entity_fetch"` (full_fetch data). Non-relevant entities are typically only basic_fetched (not enqueued for full_fetch). These entities had data in the event log but returned None from the cache lookup → they were silently skipped → `not_relevant_core_*.json` = `{}` even when many entities were discovered but classified not-relevant.

**Root cause:** `_get_entity_from_cache` used a single `_latest_cached_record(root, "entity", qid)` call without falling back to basic_fetch. Combined with F29 (basic_fetch not per-QID indexed), this meant no non-relevant entity was ever retrievable.

**Resolution (2026-04-29):** `CoreClassOutputHandler._get_entity_from_cache` now searches `("entity", "basic_fetch")` in order — full Wikidata JSON if available (relevant entities that were full_fetched), sparse record (labels + claims only, no descriptions/aliases) otherwise. This populates `not_relevant_core_*.json` with basic_fetch-level data for non-relevant entities. The F29 fix is a prerequisite.

---

### F31 — Entity count gap: 0 episodes and 0 topics after 2026-04-28 run 🟡 Resolved (root cause was Bugs A+B)

**Symptom:** After the 2026-04-28 run: `core_episodes.json` and `core_topics.json` had 0 entries despite prior run having substantial counts.

**Root cause (confirmed 2026-04-29):** The entire 4216s run budget was consumed by Bugs A and B — 1279s spinning on stale `_pending` entries before the first real network call, then 17 network calls in the remaining time. Episodes and topics require a propagation chain of at least 2 hops: seeds → series (via P527 backward or P179) → episodes (via P527 forward). With 17 calls covering only 12 seeds + 5 organizations, the chain never reached episodes or topics.

**Discovery rules are correctly configured:** `relevancy_relation_contexts.csv` row: `Q7725310 (series), P527 (has part(s)), Q1983062 (episode), can_inherit=TRUE` — this forward rule propagates relevancy from a relevant series to its episodes.

**Verdict:** This is not a logic bug. After Bugs A+B are fixed (this session), a run with sufficient budget should discover episodes via the series→P527→episode chain. Requires verification run to confirm.

---

### F32 — `ClassHierarchyHandler._walk()` emits empty `core_class_qid` for intermediate nodes 🔴 ✅ Fixed

**Rules violated:** D2 (class hierarchy must correctly propagate core class to all subclasses), G1/G2 (output files depend on correct class→core mapping)

**Symptom:** After a full run, many entities that should appear in `core_*.json` are absent. The `class_resolution_map.csv` has rows with empty `core_class_qid` for class nodes that sit more than one hop away from a core class (e.g. `Q_subtype --P279--> Q_type --P279--> Q_core_class`). Entities with P31=Q_subtype are never placed in any core class output file.

**Root cause:** `_walk()` processes P279 levels in order of increasing depth. For a node at depth N, it calls `_find_core_ancestor(parent_qids)` immediately — but the parents at depth N+1 haven't been fetched yet. So `core = ""` is recorded in `self._resolved[qid]` and emitted in the `class_resolved` event. When the parent is resolved in the next batch, the child's entry in `_resolved` and in the event log is never updated. `CoreClassOutputHandler._class_to_core[Q_subtype]` therefore remains empty, and `_resolve_core_classes(entity_qid)` returns `[]` for any entity whose P31 points only to Q_subtype.

**Resolution (2026-04-29):**

1. **`ClassHierarchyHandler._walk()` — deferred emission + backpropagation:** Instead of committing nodes to `_resolved` and emitting events during the walk, all newly resolved nodes are collected into a walk-local `new_nodes` dict first. After all batches complete, a multi-pass backpropagation loop iterates `new_nodes` until stable: any node with `core_class_ancestor=""` checks its parents in both `_resolved` and `new_nodes`; if a parent now has a known core, the child inherits it. Only after the loop converges are nodes committed to `_resolved` and events emitted — ensuring every emitted `class_resolved` event carries the correct `core_class_qid`.

2. **`ClassHierarchyHandler._load_snapshot()` — post-load backpropagation:** After loading `class_resolution_map.csv`, `_backpropagate_cores()` is called. This multi-pass loop repairs any `core_class_ancestor=""` entries that were written by pre-fix runs, using the full loaded graph to walk from child to parent until the core is found.

3. **`CoreClassOutputHandler` — backpropagation in `_write()`:** Added `_class_parent_qids: dict[str, list[str]]` field. The `class_resolved` event handler now always stores parent_qids regardless of whether the core was resolved. `_backpropagate_class_to_core()` is called at the start of `_write()` — it iterates `_class_parent_qids` in multi-pass until stable, filling any gaps in `_class_to_core` left by old events where `core_class_qid=""` was emitted before this fix.

---

### F33 — Cache index only keys on `event.key`; old batch events leave N−1 QIDs unindexable 🟡 ✅ Fixed

**Rules violated:** B1 (cache must be consulted before any network call), requirement that every prior fetch is usable as a cache hit

**Symptom:** Before the F29 fix, `basic_fetch_batch` stored one event per API call with `key=batch[0]` and all 50 entity docs in the payload. After F29 was applied (per-QID events going forward), these old batch events remained in the event log. `_prime_latest_cached_record_index` only indexed each event by its `key` field, so `batch[1]` through `batch[49]` were not findable by QID lookup. A `basic_fetch_batch` call for any of those QIDs would return a cache miss and issue a redundant network call even though the data was already in the event log.

The same issue applied to any other past or future event type that stores multiple entity documents in its payload but uses only one QID as the event key.

**Root cause:** `_remember_latest_cached_record` and `_prime_latest_cached_record_index` keyed the index solely on `get_query_event_field(record, "key", "")`. The entities block in the payload was never inspected for additional QIDs.

**Resolution (2026-04-29):** Added `_all_qids_for_record(record, primary_key) -> set[str]` helper in `cache.py`. It combines the `key` field with every QID found in `response_data["entities"]`. Both `_remember_latest_cached_record` and `_prime_latest_cached_record_index` now call this helper and index the event record under every entity QID it contains. Old batch events in the log are now fully indexed on the next startup, and any future event type that stores multiple entities in its payload is automatically covered.

---

### F28 — Handlers lose all accumulated state on every restart 🔴 ✅ Fixed

**Rules violated:** I1 (pipeline must be resumable), H3 (correct state on restart)

**Symptom:** After a successful run (projections populated), re-running the notebook produces empty output: `0 relevant, 0 not-relevant` for all 7 core classes. All projection CSVs are overwritten with header-only files. Every `*_progress.txt` file is at a sequence N; re-running produces no work and writes empty state.

**Root cause:** `V4Handler.replay()` starts from `self._last_seq + 1`. All setup events (`seed_registered`, `rule_changed`, `full_fetch_rule_registered`, `entity_marked_relevant`, `entity_fetched`, `triple_discovered`, `class_resolved`, `fetch_decision`, etc.) are at sequences ≤ last_seq. Handlers start each run with completely empty in-memory state (`_relevant = {}`, `_done = {}`, `_queue = []`, etc.) and the incremental replay finds zero new events — so the state stays empty, work queues are never populated, the loop exits immediately, and `_write()` emits empty CSVs.

Additionally: `ClassHierarchyHandler._on_event("class_resolved")` did not remove the resolved class from `_pending`, causing O(N) wasted `resolve_next()` iterations when replaying from 0 because every class QID that ever appeared in a `triple_discovered` would stay in `_pending` even after resolution.

**Resolution — Snapshot+Delta:**  
Each handler now loads its accumulated state from its projection CSV in `__init__` via `_load_snapshot()`, called after all instance variables are initialized:

- `FullFetchHandler._load_snapshot()`: reads `full_fetch_state.csv` → populates `_done` (complete rows) and `_queue` (pending rows).
- `BasicFetchHandler._load_snapshot()`: reads `basic_fetch_state.csv` → populates `_done`, `_pending_immediate`, `_pending_deferred`, and `_info`.
- `RelevancyHandler._load_snapshot()`: loads rules from `relevancy_relation_contexts.csv` (prevents silent empty `_rule_pids` when `rule_changed` events are behind last_seq); reads `class_resolution_map.csv` + `core_class_registry.csv` → populates `_class_to_core`; reads `relevancy_map.csv` → populates `_relevant`.
- `ClassHierarchyHandler._load_snapshot()`: reads `core_class_registry.csv` → `_core_classes` + base `_resolved`; reads `class_resolution_map.csv` → full `_resolved`.
- `FetchDecisionHandler._load_snapshot()`: loads rule PIDs from CSV; reads `full_fetch_state.csv` → `_full_fetched`; `relevancy_map.csv` → `_relevant`; `basic_fetch_state.csv` → `_basic_fetched`; `discovery_classification.csv` → `_decisions`.
- `CoreClassOutputHandler`: overrides `_load_seq()` to return 0 — always replays all events to reconstruct `_labels` (entity registry), `_p31_map`, `_class_to_core`, `_core_classes`, `_core_class_mode`, and `_relevant` (full replay is fast, O(N) in-memory dict ops only, no network calls). Note: `_triples`, `_descriptions`, `_aliases` were subsequently removed (see output format fix below).
- `ClassHierarchyHandler._on_event("class_resolved")`: now removes the class from `_pending` if present.

**Bootstrap note:** If projections are missing (first run ever, or projections deleted), `_load_snapshot()` is a no-op and the handlers start empty. They must then replay from seq 0 — reset all `*_progress.txt` to `0` to trigger a full rebuild. With projections populated, subsequent runs are fully incremental.

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
| F24 | `build_class_resolved_event`: added `core_class_qid` parameter, emitted in payload. `ClassHierarchyHandler._walk()`: moved `_find_core_ancestor` call to before `_emit` so core is computed first; passes `core_class_qid` to builder. `_write()`: renamed column header to `core_class_qid`. `RelevancyHandler._on_event("class_resolved")`: reads `core_class_qid` (was `core_class_ancestor`). | `event_log.py`, `handlers/class_hierarchy_handler.py`, `handlers/relevancy_handler.py` |
| F11 | `entity_rewired` event type + builder added to `event_log.py`; `RewireCatalogueReader` created (reads `rewiring_catalogue.csv`, emits one `entity_rewired` per row, idempotent via `(subject,predicate,object,rule)` key); `ClassHierarchyHandler` handles `entity_rewired` with P279 predicate — queues subject+object for hierarchy resolution; `RelevancyHandler` treats `entity_rewired` like a synthetic `triple_discovered` (forward + backward propagation, constraint checks); notebook Step 2 cell updated to instantiate and run reader | `event_log.py`, `external_readers/rewire_catalogue_reader.py`, `handlers/class_hierarchy_handler.py`, `handlers/relevancy_handler.py`, `21_candidate_generation_wikidata.ipynb` |
| F1, F2 | Wrapped work loop in `run_with_progress_heartbeat` | `21_candidate_generation_wikidata.ipynb` (Step 4 + Step 5) |
| CSV column | `SeedReader`/`CoreClassReader` now read `wikidata_id` column | `external_readers/seed_reader.py`, `external_readers/core_class_reader.py` |
| CoreClass label | `CoreClassReader` uses `filename` column for output file naming | `external_readers/core_class_reader.py` |
| F26 | `build_fetch_decision_event`: added `subject_qid`, `predicate_pid` fields. `FetchDecisionHandler._classify()`: passes both. `BasicFetchHandler`: added `_info` dict storing provenance per QID; fixed promotion path (deferred→immediate removes from deferred queue); `_write()` outputs `qid, classification, status, predicate_pid, subject_qid`. | `event_log.py`, `handlers/fetch_decision_handler.py`, `handlers/basic_fetch_handler.py` |
| F27 | `FullFetchHandler`: `_done` changed to `dict[str, str]` (qid→fetched_at); `_queue` changed to 3-tuple adding reason; reason values: `seed`, `entity_marked_relevant`, `full_fetch_rule`; `fetched_at` captured from event timestamp; `_write()` outputs `qid, status, depth, reason, fetched_at`. | `handlers/full_fetch_handler.py` |
| Missing rules file | Created `data/00_setup/full_fetch_rules.csv` with default rules | `data/00_setup/full_fetch_rules.csv` |
| FullFetchRuleReader | Raises `FileNotFoundError` if rules file missing (was silent) | `external_readers/full_fetch_rule_reader.py` |
| F28 | Snapshot+Delta: each handler adds `_load_snapshot()` to restore accumulated state from projection CSVs at startup; `CoreClassOutputHandler` overrides `_load_seq()` → 0 (always full replay); `ClassHierarchyHandler._on_event("class_resolved")` removes resolved class from `_pending`. | `handlers/class_hierarchy_handler.py`, `handlers/relevancy_handler.py`, `handlers/fetch_decision_handler.py`, `handlers/basic_fetch_handler.py`, `handlers/full_fetch_handler.py`, `handlers/output_handler.py` |
| Bug A (runtime) | `ClassHierarchyHandler._on_event("class_resolved")` now removes the class from `_pending` — stale entries after replay no longer cause O(N_pending × N_events) spin. Covered by F28 `_pending` cleanup above. | `handlers/class_hierarchy_handler.py` |
| Bug B (runtime) | Work loop `_work_loop()` guards every `replay_all()` call: `if handler.do_work(...) > 0: replay_all()`. Prevents replay cascade when `resolve_next()` / `do_next_batch()` / `do_next()` finds a stale/already-done entry and returns 0. | `21_candidate_generation_wikidata.ipynb` |
| Wrong output format | `CoreClassOutputHandler._write()` rewritten: reads full raw Wikidata JSON from entity cache via `_latest_cached_record` + `_entity_from_payload`; writes `{QID: entity_doc}` dicts (not minimal internal records). `_triples`, `_descriptions`, `_aliases` tracking removed. | `handlers/output_handler.py` |
| CSV blank lines | `V4Handler._atomic_write_csv_rows` changed to `csv.writer(buf, lineterminator="\n")` — eliminates `\r\r\n` (blank line per row) caused by Python CSV default `\r\n` doubled by `write_text()` text-mode on Windows. | `handlers/__init__.py` |
| F29 | `basic_fetch_batch` now emits one event per QID (`key=qid`, `payload={"entities": {qid: doc}}`) instead of one per batch. `_try_entity_cache` searches `("entity", "basic_fetch")` in order — previously basic_fetched entities no longer trigger unnecessary network re-fetches. | `basic_fetch.py` |
| F30 | `CoreClassOutputHandler._get_entity_from_cache` searches `("entity", "basic_fetch")` in order — `not_relevant_core_*.json` now includes entities that were only basic_fetched (sparse record: labels + claims). F29 is a prerequisite. | `handlers/output_handler.py` |
| F32 | `ClassHierarchyHandler._walk()` rewritten: nodes staged in `new_nodes` dict instead of emitted immediately; multi-pass backpropagation loop fills `core_class_ancestor` for all staged nodes before committing to `_resolved` and emitting events. `_backpropagate_cores()` added and called at end of `_load_snapshot()` to repair CSV rows with empty core from pre-fix runs. `CoreClassOutputHandler`: added `_class_parent_qids` field; `class_resolved` handler always stores parent QIDs; `_backpropagate_class_to_core()` added and called at start of `_write()` to fill gaps in `_class_to_core` from old events. | `handlers/class_hierarchy_handler.py`, `handlers/output_handler.py` |
| F33 | `_all_qids_for_record(record, primary_key)` added to `cache.py`; returns union of event `key` field and all QIDs in `response_data["entities"]`. Both `_remember_latest_cached_record` and `_prime_latest_cached_record_index` now index every entity QID from the payload — old-style batch events (key=batch[0], payload has 50 entities) are fully indexed on next startup. | `cache.py` |
| F25 | `entity_access.py` created: public Phase 5 API with `get_cached_entity_doc(qid, repo_root)` (O(1) cache lookup, full then basic), `ensure_basic_fetch(qid, repo_root, languages)` (cache hit or network call), `load_core_entities(repo_root, class_filename)` (reads a `core_*.json` file), `load_all_core_entities(repo_root)` (merges all core files). All network calls populate the event log cache. | `entity_access.py` |

---

## Deferred to Post-Deadline (2026-05-03)

These items are known issues that do not block Phase 5 analysis. They are explicitly out of scope until after the deadline.

| ID | Summary | Why deferred |
|----|---------|--------------|
| F16 | Inlinks (incoming triples) not fetched in v4 | Highest-effort open item; Phase 5 analysis does not depend on inlinks data |
| F21 | Forward triples with unknown class not re-evaluated on class resolution | False positives land in `not_relevant_core_*.json`, not in `core_*.json`; no Phase 5 analysis blocked |
| F25-outlink | `all_outlink_fetch` function (full claims without inlinks expansion) | Needed only for manually curated QIDs not yet in the pipeline; not required for current analysis scope |
| Fetch decision review | Verify V3→V4 fetch logic alignment (broadcasting programs → episodes → guests chain) | Requires re-running notebook 21; deferred until post-deadline run |
| F25-index | Append-only incremental entity index for large-dataset startup performance | Not needed at current dataset scale |
