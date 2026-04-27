# Notebook 21 Redesign — Events Catalogue
> Created: 2026-04-26  
> Purpose: Document every event type in the event store. For each type: what it means, who emits it, who reads it, required payload fields, statistics, backward-compat status, and the decided v4 name.  
> Resolves: Q1 (Glossary), §7 of `11_naming_decisions.md`

This document is the authoritative reference for event types. It covers all existing v3 types and all planned v4 types. All v4 name decisions made here are final.

---

## Event Envelope (all events)

Every event written by `EventStore.append_event()` carries these top-level fields:

| Field | Type | Description |
|-------|------|-------------|
| `event_type` | string | Type name (see sections below) |
| `timestamp_utc` | ISO 8601 | When the event occurred (caller-supplied or defaulted to now) |
| `event_version` | string | Always `"v3"` for current store; v4 events will use `"v4"` |
| `recorded_at` | ISO 8601 | When the event was appended to disk (set by EventStore, may differ from `timestamp_utc`) |
| `sequence_num` | integer | Monotonically increasing across all chunks; used by EventHandlers to track `last_processed_sequence` |
| `payload` | dict | Event-specific fields; always a dict (never null) |

---

## Infrastructure Events (store-internal; not domain events)

These are emitted by `EventStore` itself, not by domain code. Handlers must skip them.

### `eventstore_opened`

| Field | Value |
|-------|-------|
| **Emitter** | `EventStore.__init__` / `EventStore.rotate_chunk()` |
| **Readers** | `event_log._chunk_boundary_summary()` (for ordering chunks) |
| **v4 status** | ✓ Keep as-is |

**Payload fields:**
- `chunk_id` — identifier of the chunk being opened
- `prev_chunk_id` — identifier of the previous chunk (empty string if first)

---

### `eventstore_closed`

| Field | Value |
|-------|-------|
| **Emitter** | `EventStore.rotate_chunk()` |
| **Readers** | `event_log._chunk_boundary_summary()` |
| **v4 status** | ✓ Keep as-is |

**Payload fields:**
- `chunk_id` — identifier of the chunk being closed
- `next_chunk_id` — identifier of the next chunk

---

## Domain Events — v3 Types

The current event store (as of the last run 2026-04-26) holds 56,466 events across 2 JSONL chunks.

---

### `query_response`

**What it is:** Records every Wikidata API interaction — network calls, cache hits, timeouts, and errors. This is the primary data lineage event: from a `query_response` event the full API response can be reconstructed.

| Field | Value |
|-------|-------|
| **Emitter** | `cache.py` — `write_query_event()` called on every fetch attempt |
| **Readers** | `event_log.iter_query_events()` for cache replay; `query_inventory_handler` for stats; `cache._remember_latest_cached_record()` |
| **v4 status** | ✓ Keep as-is — name is clear, format is stable |
| **v4 name** | ✓ **`query_response`** (no change) |
| **Stats (last run)** | Dominates the event store; budget calls + cache hits = bulk of 56,466 total |

**Payload fields:**
- `endpoint` — `"wikidata_api"` | `"wikidata_sparql"` | `"derived_local"`
- `normalized_query` — normalized query descriptor string
- `query_hash` — MD5 of `endpoint|normalized_query`
- `source_step` — one of `SOURCE_STEPS` (e.g. `entity_fetch`, `inlinks_fetch`)
- `status` — `"success"` | `"cache_hit"` | `"http_error"` | `"timeout"` | `"fallback_cache"` | `"not_found"` | `"skipped"`
- `key` — the QID or PID queried
- `http_status` — integer or null
- `error` — error message or null
- `response_data` — the full API response payload (large — why events are 654 MB)

**Notes:** The `response_data` field is the largest contributor to event store size. In v4, consider whether query_response events need to store the full payload or just metadata. This is a performance design decision, not a correctness one — the entity_store already caches entity documents separately.

---

### `entity_discovered`

**What it is:** Emitted the first time a QID is seen and added to the node store. In v3, discovery and full_fetch happen together (both happen in `run_seed_expansion`), so this event overlaps heavily with `entity_expanded`.

| Field | Value |
|-------|-------|
| **Emitter** | `expansion_engine.py` (v4: `fetch_engine`) — `run_seed_expansion()` |
| **Readers** | `materializer.py` — `_build_instances_df()` scans for all entity state; `bootstrap_relevancy_events()` |
| **v4 status** | ✓ Keep as-is — "discovered" is clear and consistent with `triple_discovered` |
| **v4 name** | ✓ **`entity_discovered`** (no change) |
| **Stats (last run)** | Roughly 36,890 (one per entity in node store, though some entities are discovered without explicit events in v3) |

**Payload fields:**
- `qid` — the Wikidata QID
- `label` — human-readable label at time of discovery
- `source_step` — where discovery occurred (e.g. `entity_fetch`, `inlinks_fetch`)
- `discovery_method` — how entity was reached (e.g. `seed`, `seed_neighbor`, `inlink`, `outlink`)

**v4 semantics note:** In v4, `entity_discovered` is emitted at the moment the QID *first appears* in the system — which may be before any fetch occurs. The `fetch_decision` operation separately queues it for `full_fetch`, which then emits `entity_fetched` on completion. This cleanly separates first-contact from data retrieval.

---

### `entity_expanded`

**What it is:** Emitted after an entity's full neighborhood (outlinks, inlinks, claims) has been fetched and its triples have been recorded. In v3 this is conflated with discovery — both happen in the same expansion loop iteration.

| Field | Value |
|-------|-------|
| **Emitter** | `expansion_engine.py` (v4: `fetch_engine`) — `run_seed_expansion()` |
| **Readers** | `materializer.py`; `event_handler.py` derivation handlers |
| **v4 status** | ⚠ Rename — "expanded" is the old conflated term; see decision below |
| **v4 name** | ✓ **`entity_fetched`** — see §2 below |
| **Stats (last run)** | Roughly equal to `entity_discovered` count in v3 (both emitted together); Step 6.5 expanded ~530 of 1,525 seeds |

**Payload fields:**
- `qid` — the Wikidata QID
- `label` — entity label
- `expansion_type` (v4: retired — `full_fetch` always fetches all claims; no type distinction needed) — type of expansion performed (e.g. `"neighbors"`)
- `inlink_count` — number of inlinks fetched
- `outlink_count` — number of outlinks fetched

**v4 semantics change:** `entity_fetched` is emitted exactly once per QID when its `full_fetch` completes — all claims retrieved, triples recorded. This event is the signal used by the ClassHierarchyHandler to check for new class QIDs that need their P279 chains walked.

---

### `triple_discovered`

**What it is:** Emitted for each (subject, predicate, object) triple recorded from an entity's claims.

| Field | Value |
|-------|-------|
| **Emitter** | `triple_store.py` — `record_item_edges()` |
| **Readers** | `materializer.py` — `_build_triples_df()`; triple handler; relevancy handler reads triples to propagate relevance |
| **v4 status** | ✓ Keep as-is — "discovered" is clear and parallel to `entity_discovered` |
| **v4 name** | ✓ **`triple_discovered`** (no change) |
| **Stats (last run)** | 120,930 triples recorded — the densest event type by count |

**Payload fields:**
- `subject_qid` — subject entity QID
- `predicate_pid` — Wikidata property ID (e.g. `P31`, `P106`)
- `object_qid` — object entity QID
- `source_step` — where triple was derived from (e.g. `outlinks_build`, `inlinks_fetch`)
- `qualifier_pids` — list of PID strings for each qualifier property present on the claim; empty list if no qualifiers
- `reference_pids` — list of PID strings for each reference property present on the claim; empty list if no references

**v4 note (OD5):** The two list fields are new in v4. An empty list means "none present" — no separate boolean flags are needed (they would be strictly redundant with `len(list) > 0`). The lists record *which* properties are present, not the values — sufficient for filtering and completeness checks without bloating the event with full qualifier/reference data. Consumers that need full values read the raw `query_response` for the entity.

---

### `class_membership_resolved`

**What it is:** Emitted when the system evaluates whether a class QID resolves to a core class via P279 chain traversal. In v3 this fires during the seed filter stage when checking whether a seed's class is a broadcasting_program subclass.

| Field | Value |
|-------|-------|
| **Emitter** | `expansion_engine.py` (v4: `fetch_engine`) — `_filter_seed_instances_by_broadcasting_program()` via `resolve_class_path(on_resolved=...)` |
| **Readers** | Not systematically read in v3 — primarily a diagnostic event |
| **v4 status** | ⚠ Rename + semantic change — in v4 this becomes the ClassHierarchyHandler's per-class-QID output event |
| **v4 name** | ✓ **`class_resolved`** — see §4 below |
| **Stats (last run)** | Low count — only fires during seed filter for class QIDs in the broadcasting_program subclass check |

**Payload fields:**
- `entity_qid` — the QID being resolved (in v3 this is a class QID, not an entity QID — naming is misleading)
- `class_id` — the core class QID it resolved to
- `path_to_core_class` — the P279 chain path as a string
- `subclass_of_core_class` — boolean
- `is_class_node` — boolean

**v4 semantic change:** In v3, `class_membership_resolved` records "entity X's class resolved to core class Y." In v4, the ClassHierarchyHandler emits `class_resolved` once per *class QID* when its class_hierarchy_resolution is complete — recording the class QID's own position in the hierarchy. Per-entity class assignment is then derived by joining entity P31 values against the class_resolution_map, not from per-entity events.

---

### `expansion_decision`

**What it is:** A diagnostic/audit event emitted for each candidate neighbor when the fetch_engine decides whether to queue that candidate for `full_fetch`.

| Field | Value |
|-------|-------|
| **Emitter** | `expansion_engine.py` (v3) / `fetch_engine` (v4) — per candidate evaluated |
| **Readers** | Not systematically read — purely diagnostic |
| **v4 status** | ⚠ Rename — "expansion" is retired; aligns with `fetch_decision` operation |
| **v4 name** | ✓ **`fetch_decision`** — mirrors the `fetch_decision` operation name |
| **Stats (last run)** | One per candidate neighbor evaluated — potentially high count |

**Payload fields:**
- `qid` — the candidate QID
- `label` — entity label
- `decision` — `"queue_for_fetch"` | `"skip_fetch"` (v4; v3 used `"queue_for_expansion"` | `"skip_expansion"`)
- `decision_reason` — why (e.g. `"eligible_neighbor"`, `"not_eligible_or_depth_limit"`)
- `eligibility` — dict with eligibility signals: `has_direct_link_to_seed`, `seed_neighbor_degree`, `direct_or_subclass_core_match`, `p31_core_match`, `is_class_node`, `depth`, `max_depth`

---

### `relevance_assigned`

**What it is:** Emitted when an entity transitions from not-relevant to relevant. Monotonically increasing: never emitted for relevance reversal (relevance is never removed per C15).

| Field | Value |
|-------|-------|
| **Emitter** | `relevancy.py` — `write_relevance_assigned_event()` |
| **Readers** | `materializer.py` — `_load_existing_relevance_qids()` (full scan); `_build_instances_df()` |
| **v4 status** | ⚠ Rename — passive voice; slightly ambiguous about who assigned |
| **v4 name** | ✓ **`entity_marked_relevant`** — see §5 below |
| **Stats (last run)** | Proportional to number of relevant entities; relatively sparse compared to triples |

**Payload fields:**
- `entity_qid` — the entity being marked relevant
- `relevant` — always `true` (relevance is monotonically increasing; false-relevance events are never emitted)
- `assignment_type` — how relevance was assigned (e.g. `"seed"`, `"inherited"`)
- `relevant_seed_source` — which seed QID originated this relevance chain
- `relevance_first_assigned_at` — ISO timestamp of first relevance assignment
- `relevance_inherited_from_qid` — QID of the entity that propagated relevance (empty for seeds)
- `relevance_inherited_via_property_qid` — PID of the triple used for propagation
- `relevance_inherited_via_direction` — `"forward"` | `"reverse"` | `""` (for seeds)
- `is_core_class_instance` — whether entity is a CoreClassInstance at time of marking

---

### `candidate_matched`

**What it is:** Emitted by the fallback string-matching stage when a mention target is matched by label.

| Field | Value |
|-------|-------|
| **Emitter** | `fallback_matcher.py` |
| **Readers** | Used by Phase 3 downstream; not systematically read in Phase 2 output |
| **v4 status** | ✓ Out of v4 scope — fallback stage is retired from Phase 2 per C9. This event type is retained for backward compatibility but will not be emitted by v4 code. |

**Payload fields:**
- `mention_id`, `mention_type`, `mention_label` — the mention being matched
- `candidate_id`, `candidate_label` — the matched candidate
- `source` — always `"fallback_string_match"` in v3
- `context` — additional context string

---

### `eligibility_transition`

**What it is:** Emitted by the node integrity pass when an entity's eligibility state is reclassified (e.g., from ineligible to eligible after graph repair).

| Field | Value |
|-------|-------|
| **Emitter** | `node_integrity.py` |
| **Readers** | `materializer.py` — used to update projection state after integrity pass |
| **v4 status** | ✗ **Retired** — the node integrity pass is eliminated in v4 per C6 (integrity-by-construction). This event type will not be emitted by v4 code and will not be processed by v4 handlers. |

**Payload fields:**
- `entity_qid`, `previous_eligible`, `current_eligible`, `previous_reason`, `current_reason`, `path_to_core_class`

---

## New v4 Events (no v3 equivalent)

### `entity_basic_fetched`

**What it is:** Emitted when a `basic_fetch` completes for a QID — the fixed identity payload (label, description, aliases, P31, P279) has been retrieved and stored.

| Field | Value |
|-------|-------|
| **Emitter** | The new `basic_fetch` operation (v4, not yet implemented) |
| **Readers** | ClassHierarchyHandler (to check for new P31/P279 class QIDs); RelevancyHandler (to check if entity is now classifiable); output handlers |
| **v4 status** | ✓ **New in v4** |

**Payload fields (proposed):**
- `qid` — the QID fetched
- `label` — label retrieved
- `p31_qids` — list of P31 values (instance-of targets)
- `p279_qids` — list of P279 values (subclass-of targets; non-empty means this QID is a class node)
- `source` — `"network"` | `"cache"`

**Why this event matters:** Before v4, there was no distinction between basic_fetch and full_fetch. This event lets the ClassHierarchyHandler react specifically to the identity payload arriving, rather than waiting for full_fetch. This is what enables incremental class_hierarchy_resolution without the two-pass preflight.

---

### `seed_registered`

**What it is:** Emitted once per seed QID at startup by `SeedReader` when it reads `broadcasting_programs.csv` and that QID has not already been registered in the event store. Idempotent: `SeedReader` checks existing `seed_registered` events before emitting.

| Field | Value |
|-------|-------|
| **Emitter** | `SeedReader` (ExternalEventReader) — runs once at notebook startup |
| **Readers** | `SeedHandler` — adds QID to `seeds.csv` projection and queues it for `full_fetch` |
| **v4 status** | ✓ **New in v4** |

**Payload fields:**
- `qid` — the seed QID (broadcasting program)
- `source_file` — `"broadcasting_programs.csv"` (for audit trail)

---

### `core_class_registered`

**What it is:** Emitted once per core class QID at startup by `CoreClassReader` when it reads `core_classes.csv` and that class has not already been registered. Idempotent.

| Field | Value |
|-------|-------|
| **Emitter** | `CoreClassReader` (ExternalEventReader) — runs once at notebook startup |
| **Readers** | `ClassHierarchyHandler` — knows which QIDs are terminal core class targets; `RelevancyHandler` — knows which core classes exist for rule validation |
| **v4 status** | ✓ **New in v4** |

**Payload fields:**
- `qid` — the core class QID
- `label` — human-readable class name from the CSV
- `source_file` — `"core_classes.csv"`

---

### `full_fetch_rule_registered`

**What it is:** Emitted once per rule row at startup by `FullFetchRuleReader` when it reads `full_fetch_rules.csv` and that rule has not already been registered. Idempotent.

| Field | Value |
|-------|-------|
| **Emitter** | `FullFetchRuleReader` (ExternalEventReader) — runs once at notebook startup |
| **Readers** | `FetchDecisionHandler` — uses these rules to decide which discovered QIDs qualify for `full_fetch` |
| **v4 status** | ✓ **New in v4** |

**Payload fields:**
- `rule_id` — stable identifier for the rule (row number or explicit ID from CSV)
- `core_class_qid` — which core class triggers full_fetch eligibility
- `source_file` — `"full_fetch_rules.csv"`

---

### `rule_changed`

**What it is:** Emitted when a rule configuration file changes — specifically when `relevancy_relation_contexts.csv` is updated. Signals to handlers that they must re-evaluate any work they deferred under the previous rules.

| Field | Value |
|-------|-------|
| **Emitter** | Config loader / notebook startup (v4, not yet implemented) |
| **Readers** | `basic_fetch` handler (to promote `unlikely_relevant` QIDs whose predicate is now whitelisted); ClassHierarchyHandler (to check if new class QIDs need walking) |
| **v4 status** | ✓ **New in v4** |

**Payload fields (proposed):**
- `rule_file` — which config file changed (e.g. `"relevancy_relation_contexts.csv"`)
- `previous_version_hash` — hash or timestamp of the previous rule file
- `current_version_hash` — hash or timestamp of the new rule file

**Why this event matters:** The `basic_fetch` handler tracks the rule version it last applied to its deferred (`unlikely_relevant`) queue. On observing `rule_changed`, it re-evaluates deferred QIDs — any whose connecting predicate is now in the updated rules is promoted to `potentially_relevant` and queued for immediate `basic_fetch`. Without this event, rule changes would silently leave stale deferred data.

---

## Summary: All Event Names Decided

| v3 name | v4 name | Status | Notes |
|---------|---------|--------|-------|
| `query_response` | `query_response` | ✓ Keep | Stable format; no rename needed |
| `entity_discovered` | `entity_discovered` | ✓ Keep | "discovered" is clear and consistent with `triple_discovered` |
| `entity_expanded` | `entity_fetched` | ✓ Rename | Matches `full_fetch` operation name |
| `expansion_decision` | `fetch_decision` | ✓ Rename | Matches `fetch_decision` operation name; "expansion" retired |
| `triple_discovered` | `triple_discovered` | ✓ Keep | Parallel to `entity_discovered`; consistent pair |
| `class_membership_resolved` | `class_resolved` | ✓ Rename + semantic change | See note below |
| `relevance_assigned` | `entity_marked_relevant` | ✓ Rename | Active voice; clearer subject |
| `candidate_matched` | `candidate_matched` | ✓ Keep (out of scope) | Fallback stage retired; event kept for compat |
| `eligibility_transition` | *(retired)* | ✗ Retired | Node integrity pass eliminated |
| `eventstore_opened` | `eventstore_opened` | ✓ Keep | Infrastructure; no rename |
| `eventstore_closed` | `eventstore_closed` | ✓ Keep | Infrastructure; no rename |
| *(none)* | `entity_basic_fetched` | ✓ New in v4 | basic_fetch completion signal |
| *(none)* | `rule_changed` | ✓ New in v4 | Rule config file changed; triggers re-evaluation of deferred `unlikely_relevant` QIDs |
| *(none)* | `seed_registered` | ✓ New in v4 | SeedReader translates `broadcasting_programs.csv` into events; idempotent |
| *(none)* | `core_class_registered` | ✓ New in v4 | CoreClassReader translates `core_classes.csv` into events; idempotent |
| *(none)* | `full_fetch_rule_registered` | ✓ New in v4 | FullFetchRuleReader translates `full_fetch_rules.csv` into events; idempotent |

**On `class_resolved` semantic change:** The v3 event records per-entity class resolution (entity X maps to core class Y). The v4 event records per-class P279 walk completion (class QID Z resolves to core class Y via path P). These are structurally different. v4 handlers that need per-entity class assignment read the `class_resolution_map.csv` projection, not per-entity events.

---

## Name Decisions (resolves §7 of `11_naming_decisions.md`)

### §1 — `entity_discovered` — kept

**Reasoning:** "Discovered" is clear and consistent with `triple_discovered`. Renaming to `entity_encountered` would create an asymmetry — if consistency demanded a parallel rename of `triple_discovered` to `triple_encountered`, that sounds worse. Both "discovered" events stay as-is.

**Decision:** ✓ **`entity_discovered`** (no change)

---

### §2 — `entity_expanded` → `entity_fetched`

**Reasoning:** "Expanded" was the old conflated term covering both discovery and data retrieval. Now that these are separated, the data retrieval event should match the operation name: `full_fetch` → `entity_fetched`.

**Decision:** ✓ **`entity_fetched`**

---

### §3 — `triple_discovered` — kept

**Reasoning:** Parallel to `entity_discovered`. Renaming to `triple_recorded` would suggest "entity_recorded" is next — but "entity_recorded" sounds wrong. Both "discovered" events form a consistent pair.

**Decision:** ✓ **`triple_discovered`** (no change)

---

### §4 — `expansion_decision` → `fetch_decision`

**Reasoning:** "Expansion" is retired from v4 vocabulary entirely. The operation this event reports on is now called `fetch_decision`. Decision values in the payload also update: `"queue_for_expansion"` → `"queue_for_fetch"`.

**Decision:** ✓ **`fetch_decision`**

---

### §5 — `class_membership_resolved` → `class_resolved`

**Reasoning:** "Class membership resolved" reads as per-entity ("this entity's class membership was resolved"), but in v4 the ClassHierarchyHandler works per-class-QID. "Class resolved" is shorter, and in v4 context it unambiguously means "the P279 chain walk for this class QID is complete."

**Decision:** ✓ **`class_resolved`**

---

### §5 — `relevance_assigned` → `entity_marked_relevant`

**Reasoning:** "Assigned" is passive — who assigned it? "Marked relevant" is active and explicit. The event fires only when an entity transitions false→true; the name reinforces that it is a marking operation, not a status sync.

**Decision:** ✓ **`entity_marked_relevant`**
