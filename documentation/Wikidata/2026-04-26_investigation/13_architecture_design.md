# Notebook 21 Redesign — Architecture Design (v4)
> Created: 2026-04-27  
> Status: DRAFT — open design questions marked ❓. OD6 resolved.  
> Stage: Stage 3. Satisfies Stage 3 exit condition: module layout defined, all EventHandlers named with responsibilities, fetch engine design specified, config file structures defined, handover projection spec complete.

---

## 1. Design Principles

1. **Event store is the only source of truth.** All state is derived from events. No projection is authoritative — every projection is rebuildable by replaying the event store from sequence 0.

2. **No post-hoc repair.** The v3 node integrity pass is eliminated. Every entity is classified at discovery time; what gets fetched is governed by that classification, not by a separate repair step. `unlikely_relevant` objects may legitimately remain unfetched for the entire run — this is correct behavior, not a gap. Rule I1 in `08_known_rules.md` has been updated to reflect this exemption.

3. **Two actor types: EventHandlers and ExternalEventReaders.** EventHandlers replay the event store, maintain projections, and may emit derived events — they do not pull work from external sources. ExternalEventReaders are a separate class: they run once at startup, read external data (CSV config files) that is not natively in the event store, and translate it into internal events. Once emitted, those events are processed by EventHandlers like any other. This is what "gets the ball rolling" each run. Derivation handlers (ClassHierarchyHandler, RelevancyHandler, FetchDecisionHandler) also write events as part of their normal operation; this does not break the passive-read model — they react to events and may emit computed conclusions.

4. **Queues are persisted in handler projections.** Work queues (full_fetch, basic_fetch, class_hierarchy_resolution, deferred) are not held in transient memory — each queue is the pending-work projection of a dedicated handler. If a run ends prematurely, the handler resumes from its `last_processed_sequence` on the next run and picks up where it left off. Only `last_processed_sequence` needs to be persisted separately; the full queue state is reconstructible from events.

5. **Rules are config — and can evolve.** No relevancy rule, core class definition, fetch eligibility condition, or traversal constraint is hardcoded. All are loaded from CSV files in `data/00_setup/`. Default rule files are provided in `paths.projections` as starting points and may be continuously updated as new potentially relevant properties are discovered throughout runs. User-provided files in `paths.setup` take authority over defaults.

6. **Backward compatibility is permanent.** All v3 event types remain valid in the event store forever. v4 handlers must skip or tolerate unknown v3-only fields gracefully.

---

## 2. Module Layout

OD6 resolved: Option (c) — pure handler model. `fetch_engine.py` is not a standalone active engine; fetching is handled by `FullFetchHandler` and `BasicFetchHandler`. Config file ingestion is handled by ExternalEventReaders.

```
speakermining/src/process/candidate_generation/wikidata/
│
├── _v3_archive/                          # v3 modules moved here (Stage 4 task)
│
├── # Category A — kept unchanged from v3
├── cache.py                              # Cache-first Wikidata API response storage
├── event_log.py                          # EventStore append / read primitives
├── event_handler.py                      # EventHandler base class (last_processed_sequence)
├── wikidata_api.py                       # Wikidata API wrapper (rate limiting, User-Agent)
├── contact_loader.py                     # Reads contact_info file; formats User-Agent string
│
├── # New v4 — infrastructure
├── config.py                             # Config YAML loading; auto-create with defaults
│
├── # New v4 — external event readers (run once per startup; convert CSV data to events)
├── external_readers/
│   ├── seed_reader.py                    # Reads broadcasting_programs.csv → seed_registered
│   ├── core_class_reader.py              # Reads core_classes.csv → core_class_registered
│   ├── relevancy_rule_reader.py          # Reads relevancy_relation_contexts.csv → rule_changed
│   └── full_fetch_rule_reader.py         # Reads full_fetch_rules.csv → full_fetch_rule_registered
│
├── # New v4 — fetch operations (pure API functions; called by handlers)
├── basic_fetch.py                        # Mass-capable basic_fetch (label + P31 + P279 payload)
├── full_fetch.py                         # Single-QID full_fetch (all claims)
│
└── handlers/
    ├── seed_handler.py                   # SeedHandler — reacts to seed_registered; projection of seeds
    ├── full_fetch_handler.py             # FullFetchHandler — executes full_fetch; owns full_fetch_queue
    ├── basic_fetch_handler.py            # BasicFetchHandler — executes basic_fetch; owns basic_fetch_queue
    ├── class_hierarchy_handler.py        # ClassHierarchyHandler — P279 walk to core class
    ├── relevancy_handler.py              # RelevancyHandler — propagates relevancy via rules
    ├── fetch_decision_handler.py         # FetchDecisionHandler — classifies discovered objects
    ├── entity_lookup_handler.py          # EntityLookupIndexHandler — QID → label index
    └── output_handler.py                # CoreClassOutputHandler — writes core_*.json files
```

Category A modules are listed in `06_old_code_strategy.md` and verified intact before Stage 4 begins. `contact_loader.py` is already implemented in v3.

---

## 3. Execution Model

### 3.1 Run Lifecycle

```
1.  Load config (config.py)
2.  Run ExternalEventReaders (once per run, before handler replay):
    - SeedReader → emits seed_registered for any seeds not yet in the event store
    - CoreClassReader → emits core_class_registered for new core classes
    - RelevancyRuleReader → emits rule_changed if relevancy_relation_contexts.csv changed
    - FullFetchRuleReader → emits full_fetch_rule_registered if full_fetch_rules.csv changed
    Each reader is idempotent: it checks whether events already exist before emitting.
3.  Replay event store: each EventHandler processes events from its last_processed_sequence
    (includes events just emitted in step 2; all handlers fully current before work begins)
4.  All work queues are now current in handler projections — no separate reconstruction step.
    Seeds registered in step 2 are already in FullFetchHandler's pending projection.
5.  Main work loop (coordinate handlers in priority order until all queues empty or budget gone):
    a.  ClassHierarchyHandler drains its class_hierarchy_resolution_queue (highest priority)
    b.  BasicFetchHandler drains its immediate_basic_fetch_queue (batch where possible)
    c.  FullFetchHandler processes one item from its full_fetch_queue:
        → emits entity_discovered (if new), triple_discovered × N, entity_fetched
        → FetchDecisionHandler reacts → classifies new triple objects
        → new potentially_relevant objects enter BasicFetchHandler's queue → return to (a)
    d.  New entity_basic_fetched events processed by ClassHierarchyHandler + RelevancyHandler
        → new class QIDs enter ClassHierarchyHandler queue → return to (a)
    e.  New class_resolved events processed by RelevancyHandler
        → pending triples re-evaluated → may emit entity_marked_relevant
    f.  New entity_marked_relevant processed by FullFetchHandler
        → evaluates full_fetch eligibility → may add to full_fetch_queue → return to (a)
6.  If deferred_basic_fetch_mode = "end_of_run": BasicFetchHandler drains deferred queue
7.  CoreClassOutputHandler writes core_*.json and not_relevant_core_*.json output files
```

**When is data available?** The event store is written continuously throughout step 5. Intermediate projections (`class_resolution_map.csv`, `relevancy_map.csv`, etc.) are updated continuously as handlers process each event. The `core_<class>.json` output files are written once in step 7.

### 3.2 Queue Priority

| Priority | Queue | Owner (handler) | Rationale |
|----------|-------|-----------------|-----------|
| 1 (highest) | `class_hierarchy_resolution_queue` | ClassHierarchyHandler | No relevancy decision is possible without knowing the class tree |
| 2 | `immediate_basic_fetch_queue` | BasicFetchHandler | Identity of potentially_relevant nodes needed before relevancy can propagate |
| 3 | `full_fetch_queue` | FullFetchHandler | Main graph traversal; depends on class and relevancy info |
| 4 (lowest) | `deferred_basic_fetch_queue` | BasicFetchHandler | Only processed if config permits; never at expense of higher-priority work |

### 3.3 Handler Processing Order

When multiple handlers react to the same event, the following order must be enforced:

| Order | Handler | Reason |
|-------|---------|--------|
| 1 | ClassHierarchyHandler | Resolves class QIDs first; all downstream depends on this |
| 2 | RelevancyHandler | Needs class resolution; marks entities relevant before fetch decisions |
| 3 | FetchDecisionHandler | Needs relevancy state to classify and populate queues |
| 4 | BasicFetchHandler | Drains its queue after classification updates |
| 5 | FullFetchHandler | Drains its queue after relevancy updates |
| 6 | EntityLookupIndexHandler | Independent; processes after primary handlers |
| 7 | CoreClassOutputHandler | Accumulates all derived state; processes last |

---

## 4. Event Types Reference

Authoritative reference: `12_event_catalogue.md`. New v4 events added for the pure-handler model:

| Event | Emitter | Signal |
|-------|---------|--------|
| `seed_registered` | SeedReader | A seed QID is added to the system |
| `core_class_registered` | CoreClassReader | A core class is added to the system |
| `full_fetch_rule_registered` | FullFetchRuleReader | A full_fetch eligibility rule is registered |
| `entity_discovered` | FullFetchHandler | New QID first seen in the system |
| `entity_fetched` | FullFetchHandler | `full_fetch` complete for a QID; all claims stored |
| `triple_discovered` | FullFetchHandler | A `(subject, predicate, object)` triple was stored |
| `fetch_decision` | FetchDecisionHandler | Audit record: one per classified discovered object |
| `entity_basic_fetched` | BasicFetchHandler | `basic_fetch` complete; label + P31 + P279 available |
| `class_resolved` | ClassHierarchyHandler | P279 walk complete for a class QID |
| `entity_marked_relevant` | RelevancyHandler | Entity transitioned to relevant (monotonic) |
| `rule_changed` | RelevancyRuleReader / FullFetchRuleReader | A rule config file changed since last run |
| `query_response` | cache.py | Raw API interaction recorded |

`seed_registered`, `core_class_registered`, and `full_fetch_rule_registered` should be added to `12_event_catalogue.md` as new v4 events.

---

## 5. EventHandler Inventory

Every EventHandler:
- Extends `EventHandler` base class from `event_handler.py`
- Persists `last_processed_sequence` so it can resume on restart
- Maintains exactly one projection (its output contract; rebuildable from events)
- May emit new events as part of its reaction (derivation handlers: FullFetchHandler, BasicFetchHandler, ClassHierarchyHandler, RelevancyHandler, FetchDecisionHandler)

Every ExternalEventReader:
- Runs once at startup before handler replay
- Reads an external data source (CSV)
- Emits events only for new or changed items (idempotent: checks event store before emitting)
- Does not maintain a `last_processed_sequence` — it always reads the full CSV and checks against the event store

---

### SeedHandler

**Responsibility:** React to `seed_registered` events and maintain the authoritative seed list. The seed projection is used by FullFetchHandler to populate its initial queue.

| Aspect | Detail |
|--------|--------|
| **Events read** | `seed_registered` |
| **Events written** | *(none)* |
| **Projection** | `seeds.csv` — columns: `qid`, `label`, `registered_at` |

---

### FullFetchHandler

**Responsibility:** Execute `full_fetch` for every seed and every entity that is relevant AND meets full_fetch eligibility criteria. Owns the `full_fetch_queue` projection.

| Aspect | Detail |
|--------|--------|
| **Events read** | `seed_registered` (seeds always queue for full_fetch); `entity_marked_relevant` (relevant entities evaluated for eligibility); `entity_fetched` (marks QID as done); `full_fetch_rule_registered` + `rule_changed` (reload eligibility criteria) |
| **Events written** | `entity_discovered`, `triple_discovered`, `entity_fetched` |
| **Projection** | `full_fetch_state.csv` |
| **Eligibility** | Calls `full_fetch.py` for QIDs that are: (a) a seed, OR (b) `entity_marked_relevant` AND pass `full_fetch_rules.csv` criteria. Class-only nodes (entities that have P279 claims and no permit rule match) are excluded. |
| **Budget** | Each network call decrements `max_queries_per_run`. Stops when budget is exhausted. |

**`full_fetch_state.csv` columns:**

| Column | Type | Description |
|--------|------|-------------|
| `qid` | string | The entity QID |
| `status` | string | `pending` \| `complete` \| `ineligible` |
| `reason` | string | Why ineligible, or which rule triggered queuing |
| `fetched_at` | ISO 8601 | When full_fetch completed (empty if not yet complete) |

---

### BasicFetchHandler

**Responsibility:** Execute `basic_fetch` for all `potentially_relevant` nodes. Owns both the immediate and deferred `basic_fetch_queue` projections.

| Aspect | Detail |
|--------|--------|
| **Events read** | `fetch_decision` (with classification `potentially_relevant` → immediate queue; `unlikely_relevant` → deferred queue); `entity_basic_fetched` (marks QID as done); `rule_changed` (re-evaluate deferred items — any promoted to `potentially_relevant` move to immediate queue) |
| **Events written** | `entity_basic_fetched` |
| **Projection** | `basic_fetch_state.csv` |
| **Batching** | Calls `basic_fetch.py` with up to 50 QIDs per request. |
| **Budget** | One network call per batch (not per QID). Counts against `max_queries_per_run`. |

**`basic_fetch_state.csv` columns:**

| Column | Type | Description |
|--------|------|-------------|
| `qid` | string | The entity QID |
| `classification` | string | `potentially_relevant` \| `unlikely_relevant` |
| `status` | string | `pending` \| `complete` \| `deferred` |
| `predicate_pid` | string | Predicate that connected this object to its relevant subject |
| `subject_qid` | string | The relevant subject QID whose full_fetch produced this object |

---

### ClassHierarchyHandler

**Responsibility:** Walk the P279 chain for every class QID referenced in any P31 or P279 claim, until a core class, root class, or depth limit is reached.

| Aspect | Detail |
|--------|--------|
| **Events read** | `entity_basic_fetched` (P31/P279 targets); `triple_discovered` (P31/P279 triples from full_fetched entities); `core_class_registered` (new core classes); `rule_changed` (core class list changed) |
| **Events written** | `class_resolved` |
| **Projection** | `class_resolution_map.csv` |
| **Priority queue** | Maintains own in-memory `class_hierarchy_resolution_queue` (backed by projection); drained before any other work |
| **Walk termination** | Core class QID reached → `status = resolved` |
| | Q35120 (entity) or Q1 (Universe) reached without core class → `status = unresolved` |
| | Depth limit exceeded (default n = 8) → `status = unresolved` |
| **Scope** | Fires for `potentially_relevant` nodes only. |
| **Rewiring** | Applies `rewiring_catalogue.csv` overrides at projection write time. The `class_resolved` event records the computed path; the projection records the effective (overridden) result. |

**`class_resolution_map.csv` columns:**

| Column | Type | Description |
|--------|------|-------------|
| `class_qid` | string | The class QID that was walked |
| `core_class_qid` | string | The core class it resolved to (empty if unresolved) |
| `path` | string | Pipe-separated P279 chain from `class_qid` to `core_class_qid` |
| `depth` | integer | Number of hops |
| `status` | string | `resolved` \| `unresolved` \| `conflict` \| `overridden` |
| `overridden_by` | string | Rewiring catalogue entry QID if status = `overridden`; empty otherwise |

---

### RelevancyHandler

**Responsibility:** Mark entities as relevant by evaluating relevancy rules. Seeds are marked relevant when `seed_registered` is observed. All other relevancy is propagated via approved triples.

| Aspect | Detail |
|--------|--------|
| **Events read** | `seed_registered` (seeds are authoritatively relevant); `triple_discovered` (evaluate propagation); `class_resolved` (re-evaluate pending triples); `entity_marked_relevant` (update known-relevant set); `rule_changed` (reload rules) |
| **Events written** | `entity_marked_relevant` |
| **Projection** | `relevancy_map.csv` |
| **Pending evaluation** | Triples where the object's class is not yet in `class_resolution_map.csv` are held in an in-memory pending set keyed by the unresolved class QID. When `class_resolved` arrives for that class, pending triples are re-evaluated. This state is rebuilt during startup replay. |
| **Monotonicity** | Relevancy is binary and monotonically increasing. `entity_marked_relevant` is emitted at most once per QID. |

**`relevancy_map.csv` columns:**

| Column | Type | Description |
|--------|------|-------------|
| `entity_qid` | string | The entity |
| `relevant` | boolean | Always `true` |
| `first_marked_at` | ISO 8601 | When relevancy was first assigned |
| `source_seed_qid` | string | Which seed originated this relevancy chain |
| `inherited_from_qid` | string | QID that propagated relevancy (empty for seeds) |
| `inherited_via_pid` | string | PID of the propagation triple (empty for seeds) |
| `direction` | string | `forward` \| `reverse` \| `` (for seeds) |

---

### FetchDecisionHandler

**Responsibility:** Classify every object of a `full_fetch`ed relevant entity's triples as `potentially_relevant` or `unlikely_relevant`. Emit `fetch_decision` audit events; BasicFetchHandler reads these to populate its queues.

| Aspect | Detail |
|--------|--------|
| **Events read** | `triple_discovered`; `entity_fetched` (marks subject as full_fetched); `entity_marked_relevant` (marks subject as relevant — triggers re-classification of its already-discovered triples); `entity_basic_fetched` (marks object as already processed); `rule_changed` (re-evaluate `unlikely_relevant` entries) |
| **Events written** | `fetch_decision` |
| **Projection** | `discovery_classification.csv` |
| **Classification rule** | Object O of triple `(S, P, O)` is classified when S is both `entity_fetched` AND `entity_marked_relevant`. Classification: `potentially_relevant` if P appears in `relevancy_relation_contexts.csv`; `unlikely_relevant` otherwise. |

**`discovery_classification.csv` columns:**

| Column | Type | Description |
|--------|------|-------------|
| `object_qid` | string | The discovered object QID |
| `subject_qid` | string | Subject whose full_fetch produced this object |
| `predicate_pid` | string | Connecting predicate |
| `classification` | string | `potentially_relevant` \| `unlikely_relevant` |
| `basic_fetch_status` | string | `pending` \| `complete` \| `deferred` |

---

### EntityLookupIndexHandler

**Responsibility:** Maintain a complete QID → label index.

| Aspect | Detail |
|--------|--------|
| **Events read** | `entity_discovered` (first-seen label); `entity_basic_fetched` (confirmed label — overwrites); `entity_fetched` (confirmed label — overwrites) |
| **Events written** | *(none)* |
| **Projection** | `entity_lookup_index.csv` — columns: `qid`, `label`, `last_updated_at` |

---

### CoreClassOutputHandler

**Responsibility:** Write the handover output JSON files for all core classes.

| Aspect | Detail |
|--------|--------|
| **Events read** | All entity, triple, relevancy, and class resolution events |
| **Events written** | *(none)* |
| **Projections** | `core_<class>.json` and `not_relevant_core_<class>.json` for each core class |
| **Write timing** | Files are written once at the end of the run (step 7). All other projections are updated continuously. |
| **Data completeness** | All data the system holds for each entity: all triples, qualifier PIDs, reference PIDs, has_qualifier/has_reference flags, label, description, aliases, core class assignment. No field is optional (Rule G4). |
| **Assignment source** | Per-entity class = join entity's P31 values against `class_resolution_map.csv`. Rewiring overrides already applied in that projection. |
| **Conflict handling** | Entity resolving to multiple core classes appears in all matching output files with `conflict: true` (Rule D5). |

**Per-entity record schema in `core_<class>.json`:**
```json
{
  "qid": "Q123456",
  "label": "...",
  "description": "...",
  "aliases": ["...", "..."],
  "core_class": "Q215627",
  "conflict": false,
  "triples": [
    {
      "predicate_pid": "P31",
      "object_qid": "Q5",
      "has_qualifier": true,
      "qualifier_pids": ["P580", "P582"],
      "has_reference": true,
      "reference_pids": ["P248", "P813"]
    }
  ]
}
```

---

## 6. Fetch Operation Contracts

`full_fetch.py` and `basic_fetch.py` are pure API functions — no state, no projections. They are called by FullFetchHandler and BasicFetchHandler respectively.

### 6.1 full_fetch

**What:** Retrieve all Wikidata claims for a single QID.  
**API:** Wikidata entities endpoint; single QID per call.  
**Budget:** One network call unless cache hit.

**Events emitted by FullFetchHandler (in order):**
1. `entity_discovered` — if first time the QID is seen
2. `triple_discovered` × N — one per claim; each with `has_qualifier`, `qualifier_pids`, `has_reference`, `reference_pids` fields
3. `entity_fetched` — signals completion

### 6.2 basic_fetch

**What:** Retrieve a fixed minimal payload: label + description + aliases + P31 + P279 only.  
**API:** Wikidata `wbgetentities` endpoint; up to 50 QIDs per batch. Preferred over SPARQL because claims can have multiple values and qualifiers that SPARQL cannot compactly represent.  
**Budget:** One network call per batch.

**Events emitted by BasicFetchHandler (one per QID in the batch):**
1. `entity_basic_fetched` — with label, p31_qids, p279_qids, source (network or cache)

### 6.3 class_hierarchy_resolution

**What:** Walk the P279 chain upward from a class QID until core class, root class, or depth limit.  
**Operated by:** ClassHierarchyHandler entirely. Uses `basic_fetch.py` API calls internally.

**Events emitted:** `class_resolved` — with class_qid, core_class_qid, path, depth, status

---

## 7. Config File Structure

Single YAML file: `data/00_setup/wikidata_config.yaml`. Auto-created with defaults if absent; run aborts asking the user to review.

```yaml
run:
  # Maximum number of live Wikidata API calls per run.
  # 0 = cache-only mode. -1 = unlimited. Any positive integer = hard cap.
  max_queries_per_run: 500

  # What to do with unlikely_relevant nodes at deferred basic_fetch time.
  # "never":      skip entirely unless rules change and promote them.
  # "end_of_run": process after all immediate work is complete.
  deferred_basic_fetch_mode: "never"

  # Maximum BFS traversal depth from any seed (0 = seeds only; 1 = seed neighbors).
  # VERY expensive to increase. Depth 3 = full neighborhood of neighborhoods. Default: 2.
  depth_limit: 2

  # Maximum P279 walk depth in class_hierarchy_resolution.
  # Cheap to set high — only NEW class QIDs trigger a walk; results are cached permanently.
  # Walk exits early when a core class is found. Default: 8 (lower to ~6 once paths are known).
  class_hierarchy_depth_limit: 8

wikidata:
  # User-Agent is assembled from data/00_setup/contact_info by contact_loader.py at runtime.
  # Do not set a user_agent string here — configure contact_info instead.

  # Base delay for exponential HTTP retry backoff. Actual wait after attempt N = base * 2^N.
  # Applied on 429 and 503 responses. Default matches v3 implementation: 1.0s.
  http_backoff_base_seconds: 1.0

  # Maximum retry attempts per HTTP request before giving up.
  http_max_retries: 4

languages:
  # Languages for labels/descriptions/aliases in all fetch operations.
  # Wikidata's default-language label is always included regardless of this setting.
  labels: ["de", "en"]

# These paths are stable across deployments; change only if the project layout changes.
paths:
  event_store: "data/20_.../wikidata/chunks/"
  projections: "data/20_.../wikidata/projections/"
  setup: "data/00_setup/"
```

---

## 8. Rule Config File Designs

Default copies are shipped in `paths.projections` as starting points. User copies in `paths.setup` take authority. All files can be extended as new relevant properties are discovered in runs.

---

### `core_classes.csv`

| Column | Type | Description |
|--------|------|-------------|
| `qid` | string | Core class QID |
| `label` | string | Human-readable label |
| `output_file_prefix` | string | Used to construct output file names |

```
qid,label,output_file_prefix
Q215627,person,person
Q214339,role,role
Q1983062,episode,episode
```

---

### `broadcasting_programs.csv` (seed list)

| Column | Type | Description |
|--------|------|-------------|
| `qid` | string | Seed QID |
| `label` | string | Human-readable label |

```
qid,label
Q15820,NDR Talk Show
Q688720,Das literarische Quartett
```

---

### `relevancy_relation_contexts.csv`

**Dual role:** governs relevancy propagation AND determines `potentially_relevant` vs `unlikely_relevant` classification (any predicate PID in this file triggers immediate `basic_fetch`).

| Column | Type | Description |
|--------|------|-------------|
| `subject_core_class_qid` | string | Core class QID of subject (`*` = any) |
| `predicate_pid` | string | Wikidata PID |
| `object_core_class_qid` | string | Core class QID of object (`*` = any) |
| `direction` | string | `forward` \| `backward` \| `both` |
| `note` | string | Why this rule exists |

```
subject_core_class_qid,predicate_pid,object_core_class_qid,direction,note
Q1983062,P161,Q215627,forward,Episode cast → person relevant (potential speaker/guest)
Q1983062,P57,Q215627,forward,Episode director → person relevant
Q215627,P106,Q214339,forward,Person occupation → role relevant
Q7725310,P527,Q1983062,forward,Series has part → episode relevant
```

---

### `rewiring_catalogue.csv`

Manual class assignment overrides. Applied by ClassHierarchyHandler at projection write time.

| Column | Type | Description |
|--------|------|-------------|
| `qid` | string | QID whose assignment is overridden |
| `override_core_class_qid` | string | The core class to assign |
| `reason` | string | Why the override exists |

```
qid,override_core_class_qid,reason
Q12345,Q215627,"Wikidata models this as role but it is a person in our domain"
```

---

### `full_fetch_rules.csv` ❓ OD3

Governs which relevant entities qualify for `full_fetch`. Permit rules take priority over exclude rules.

| Column | Type | Description |
|--------|------|-------------|
| `rule_type` | string | `permit` \| `exclude` |
| `condition_property` | string | P31 or P279 (which claim to check) |
| `condition_value_qid` | string | Required claim value (`*` = any value) |
| `note` | string | Plain language description |

```
rule_type,condition_property,condition_value_qid,note
permit,P31,Q5,Human instances — always full_fetch
permit,P31,Q1983062,Episode instances — always full_fetch
exclude,P279,*,Has any subclass-of claim without a permit match — hierarchy node only
```

---

## 9. Handover Projection Specification

All projections are stored under `paths.projections`. All are rebuildable from the event store.

| File | Owner | Updated | Notes |
|------|-------|---------|-------|
| `seeds.csv` | SeedHandler | On seed_registered | All registered seeds |
| `full_fetch_state.csv` | FullFetchHandler | Continuously | Per-QID full_fetch queue state |
| `basic_fetch_state.csv` | BasicFetchHandler | Continuously | Per-QID basic_fetch queue state |
| `class_resolution_map.csv` | ClassHierarchyHandler | Continuously | Per-class P279 walk result |
| `relevancy_map.csv` | RelevancyHandler | Continuously | Per-entity relevancy state |
| `discovery_classification.csv` | FetchDecisionHandler | Continuously | Per-discovered-object classification |
| `entity_lookup_index.csv` | EntityLookupIndexHandler | Continuously | Universal QID → label index |
| `core_<class>.json` | CoreClassOutputHandler | Once at end of run | Relevant entities per core class |
| `not_relevant_core_<class>.json` | CoreClassOutputHandler | Once at end of run | Known-but-not-relevant per core class |

**Downstream consumers (Phase 31+) read `core_<class>.json` files only.** All other projections are Phase 2 internal state, also readable for diagnostics.

---

## 10. Open Design Questions

| # | Question | Affects | Direction |
|---|----------|---------|-----------|
| ✓ OD1 | **RelevancyHandler pending evaluation:** In-memory pending set keyed by class_qid; rebuilt during startup replay. Resolved naturally by pure-handler model — no extra mechanism needed. | `relevancy_handler.py` | ✓ Resolved |
| ❓ OD2 | **basic_fetch API endpoint:** `wbgetentities` is preferred over SPARQL (better for multi-valued claims/qualifiers/references). Confirm: (a) batch limit = 50 QIDs per call, (b) property filter `props=labels|descriptions|aliases|claims` with claim filter `P31|P279` works with the existing v3 cache layer. | `basic_fetch.py` | Direction: `wbgetentities`; batch 50; property filter |
| ❓ OD3 | **full_fetch eligibility default rules:** `full_fetch_rules.csv` approach agreed (see §8). Default rule set needs finalization before Stage 5. Initial proposal in §8 is a starting point; real-world testing will refine it. | `full_fetch_rules.csv` | Approach resolved; defaults TBD |
| ✓ OD4 | **rewiring_catalogue application point:** ClassHierarchyHandler applies overrides at projection write time. | `class_hierarchy_handler.py` | ✓ Resolved |
| ❓ OD5 | **Qualifier AND reference data in events:** `triple_discovered` must be extended with both `has_qualifier: bool`, `qualifier_pids: list[str]` AND `has_reference: bool`, `reference_pids: list[str]`. The output schema already includes both (see §5 CoreClassOutputHandler). For full qualifier/reference VALUES (not just PIDs), a `TripleQualifierHandler` and `TripleReferenceHandler` are deferred to Stage 5 as non-blocking enhancements. The `12_event_catalogue.md` entry for `triple_discovered` must be updated to include all four new fields. | `12_event_catalogue.md`, `full_fetch.py` | Direction: extend `triple_discovered`; full data handlers deferred |
| ✓ OD6 | **fetch_engine vs fetch_handler architecture:** Resolved — Option (c). FullFetchHandler + BasicFetchHandler + SeedHandler replace `fetch_engine.py`. ExternalEventReaders handle CSV ingestion. No standalone active engine. | module layout | ✓ Resolved |
