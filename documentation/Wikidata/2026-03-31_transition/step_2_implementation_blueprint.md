# Step 2: Concrete Implementation Blueprint

Date: 2026-03-31
Status: Design ready for implementation
Scope: Module-by-module target APIs, event schemas, and acceptance tests mapped to each section of the production spec

---

## 1. Purpose and Constraints

This blueprint translates the production spec into implementable module contracts.

Input authorities:
- documentation/Wikidata/2026-03-31_transition/wikidata_future_V2.md
- documentation/Wikidata/2026-03-31_transition/gap_analysis.md
- documentation/Wikidata/2026-03-31_transition/step_1_graph_artifacts_design.md

Locked decisions inherited from Step 1:
- Option B is selected: consolidated entities.json + selective CSV projections.
- Runtime lookups use in-memory dictionaries/sets.
- CSV materialization is checkpoint-batched plus final consistency pass.
- Checkpoint-first recovery with raw_queries replay fallback.

Non-goals of Step 2:
- No implementation code yet.
- No backward compatibility layer for old artifact schema.

---

## 2. Target Package Layout

Target package root:
- speakermining/src/process/candidate_generation/wikidata

Keep and refactor existing modules:
- cache.py
- entity.py
- inlinks.py
- outlinks.py
- common.py

Split or replace current behavior:
- bfs_expansion.py -> expansion_engine.py (new authoritative graph expansion)
- aggregates.py -> materializer.py (artifact projections from node/triple/event stores)
- classes.py -> class_resolver.py (class path resolution + class counters)
- targets.py -> candidate_targets.py (post-graph string matching targets)

Add new modules:
- bootstrap.py
- event_log.py
- node_store.py
- triple_store.py
- query_inventory.py
- checkpoint.py
- schemas.py

Rationale:
- Separate fetch/cache/event concerns from expansion semantics and projections.
- Make acceptance tests possible per module contract.

---

## 3. Spec-to-Module Responsibility Map

| Spec section | Primary module(s) | Secondary module(s) | Main output |
|---|---|---|---|
| Scope and migration target | 21_candidate_generation_wikidata.ipynb | bootstrap.py | target path lifecycle |
| Naming freeze (organizations) | schemas.py | materializer.py | normalized class filenames |
| Cache and query event policy | cache.py, event_log.py | query_inventory.py | raw_queries + dedup inventory |
| Input sources and seed loading | bootstrap.py | common.py | validated seeds/core classes |
| Bootstrap requirement | bootstrap.py | schemas.py | required dirs/files |
| Node storage model | node_store.py | entity.py, class_resolver.py | entities.json, properties.json |
| Expansion predicates and graph semantics | expansion_engine.py | triple_store.py, class_resolver.py | expansion frontier + triples |
| Canonical queue ordering | expansion_engine.py | common.py | deterministic BFS order |
| Stop conditions and precedence | expansion_engine.py | checkpoint.py | stop_reason + counters |
| Class and instance discovery policy | class_resolver.py | node_store.py | class resolution metadata |
| Materialization and dedup policy | materializer.py | query_inventory.py, triple_store.py | CSV views + summary |
| End-to-end execution outline | 21_candidate_generation_wikidata.ipynb | all modules | per-seed execution flow |
| Checkpoint policy | checkpoint.py | materializer.py | manifests + resume safety |
| Resume and rollback semantics | checkpoint.py | 21_candidate_generation_wikidata.ipynb | run continuation/restart/revert |

---

## 4. Module-by-Module Target APIs

## 4.1 schemas.py (new)

Purpose:
- Single source for schema constants, stop reasons, file paths, column order.

Target API:
```python
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ArtifactPaths:
    root: Path
    wikidata_dir: Path
    raw_queries_dir: Path
    classes_csv: Path
    instances_csv: Path
    properties_csv: Path
    aliases_en_csv: Path
    aliases_de_csv: Path
    triples_csv: Path
    entities_json: Path
    properties_json: Path
    query_inventory_csv: Path
    summary_json: Path
    core_classes_csv: Path
    broadcasting_programs_csv: Path

STOP_REASONS = {
    "seed_complete",
    "per_seed_budget_exhausted",
    "total_query_budget_exhausted",
    "queue_exhausted",
    "user_interrupted",
    "crash_recovery",
}

def build_artifact_paths(repo_root: Path) -> ArtifactPaths: ...
def canonical_class_filename(name: str) -> str: ...  # enforces organizations spelling
```

Acceptance criteria:
- Path builder returns all required paths under data/20_candidate_generation/wikidata.
- canonical_class_filename enforces organizations and rejects organisations.

## 4.2 bootstrap.py (new)

Purpose:
- Validate inputs and initialize output schema from empty directory.

Target API:
```python
def load_core_classes(repo_root: Path) -> list[dict]: ...
def load_seed_instances(repo_root: Path) -> tuple[list[dict], list[dict]]:
    """Returns (valid_seeds, skipped_rows_with_reason)."""

def ensure_output_bootstrap(repo_root: Path) -> None: ...
def initialize_bootstrap_files(repo_root: Path, core_classes: list[dict], seeds: list[dict]) -> None: ...
```

Rules implemented:
- Seed QID validation via ^Q[1-9][0-9]*$.
- Skip NONE/blank/non-QID with diagnostics.
- Create required folders/files unconditionally.
- Copy setup references to core_classes.csv and broadcasting_programs.csv.

## 4.3 cache.py (refactor)

Purpose:
- HTTP access with contact policy, delay, retries, budget accounting.

Target API changes:
```python
@dataclass
class RequestContext:
    total_query_budget: int
    per_seed_query_budget: int
    query_delay_seconds: float
    network_queries_total: int
    network_queries_current_seed: int
    last_query_time: float

def begin_request_context(total_query_budget: int, per_seed_query_budget: int, query_delay_seconds: float) -> None: ...
def end_request_context() -> dict: ...
def http_get_json(url: str, *, endpoint: str, timeout: int = 30) -> dict: ...
```

Notes:
- Keep retry behavior for 429/5xx.
- Budget and delay must be centrally enforced here.

## 4.4 event_log.py (new)

Purpose:
- Append immutable raw query event records and read them back.

Target API:
```python
def write_query_event(
    repo_root: Path,
    *,
    endpoint: str,
    normalized_query: str,
    query_hash: str,
    source_step: str,
    status: str,
    key: str,
    payload: dict,
    http_status: int | None,
    error: str | None,
) -> Path: ...

def list_query_events(repo_root: Path) -> list[Path]: ...
def read_query_event(path: Path) -> dict: ...
```

Key decision:
- One file per network reply, append-only.
- No schema adapters for old files; archive and delete legacy files as migration step.

## 4.5 entity.py (refactor)

Purpose:
- Cache-first entity/inlinks/outlinks retrieval using event_log envelope.

Target API:
```python
def get_or_fetch_entity(repo_root: Path, qid: str, cache_max_age_days: int, timeout: int = 30) -> dict: ...
def get_or_fetch_inlinks(repo_root: Path, qid: str, cache_max_age_days: int, limit: int, timeout: int = 30) -> dict: ...
def get_or_build_outlinks(repo_root: Path, qid: str, entity_payload: dict, cache_max_age_days: int) -> dict: ...
```

Required deltas from current behavior:
- Event metadata must include endpoint + normalized_query + hash + status.
- Inlinks query shape must support deterministic chunking strategy (cursor/offset style where feasible).

## 4.6 inlinks.py and outlinks.py (refactor)

inlinks.py target API:
```python
def build_inlinks_query(qid: str, *, limit: int, offset: int = 0) -> str: ...
def parse_inlinks_results(payload: dict) -> list[dict[str, str]]: ...
```

outlinks.py target API:
```python
def extract_outlinks(qid: str, entity_doc: dict) -> dict:
    """Returns property_ids, linked_qids, and item-to-item edges."""
```

Rules:
- Edge domain remains item-to-item only for expansion graph.
- Non-item values are attributes, never queue neighbors.

## 4.7 node_store.py (new)

Purpose:
- Maintain consolidated entities.json and properties.json with merge semantics.

Target API:
```python
def upsert_discovered_item(repo_root: Path, qid: str, entity_doc: dict, discovered_at_utc: str) -> None: ...
def upsert_expanded_item(repo_root: Path, qid: str, expanded_payload: dict, expanded_at_utc: str) -> None: ...
def upsert_discovered_property(repo_root: Path, pid: str, property_doc: dict, discovered_at_utc: str) -> None: ...
def get_item(repo_root: Path, qid: str) -> dict | None: ...
def iter_items(repo_root: Path): ...
```

Merge policy:
- Dedup by ID.
- Merge observed fields across discoveries.
- Expanded payload overwrites discovered-only payload fields for same node.

## 4.8 class_resolver.py (new, replaces classes.py role)

Purpose:
- Resolve class and instance paths to core classes and compute class aggregates.

Target API:
```python
def resolve_class_path(entity_doc: dict, core_class_qids: set[str], get_entity_fn) -> dict:
    """Returns class_id, class_filename, path_to_core_class, subclass_of_core_class."""

def compute_class_rollups(items_iterable) -> list[dict]:
    """Produces classes.csv rows including discovered_count and expanded_count."""
```

Rules:
- P279 present => class-capable.
- Else classify via P31 and BFS to nearest core class.
- Cycle protection required.

## 4.9 triple_store.py (new)

Purpose:
- Persist and deduplicate triple facts for triples.csv projection.

Target API:
```python
def record_item_edges(repo_root: Path, subject_qid: str, edges: list[dict], discovered_at_utc: str, source_query_file: str) -> None: ...
def iter_unique_triples(repo_root: Path): ...
```

Dedup key:
- (subject, predicate, object), keep first observed timestamp.

## 4.10 query_inventory.py (new)

Purpose:
- Build deduplicated query inventory from raw events.

Target API:
```python
def rebuild_query_inventory(repo_root: Path) -> list[dict]: ...
```

Dedup key:
- query_hash + endpoint; keep latest successful response.

## 4.11 materializer.py (new, replaces aggregates.py role)

Purpose:
- Build CSV snapshots from JSON stores and triple/query event stores.

Target API:
```python
def materialize_checkpoint(repo_root: Path, *, run_id: str, checkpoint_ts: str, seed_id: str | None) -> dict: ...
def materialize_final(repo_root: Path, *, run_id: str) -> dict: ...
```

Outputs:
- classes.csv
- instances.csv
- properties.csv
- aliases_en.csv
- aliases_de.csv
- triples.csv
- query_inventory.csv
- summary.json

Runtime model:
- Build DataFrames from in-memory indexes at checkpoint boundaries.
- Atomic write for every artifact.
- Final full pass ensures deterministic ordering.

## 4.12 checkpoint.py (new)

Purpose:
- Checkpoint manifests, resume decisions, rollback markers.

Target API:
```python
@dataclass
class CheckpointManifest:
    run_id: str
    start_timestamp: str
    latest_checkpoint_timestamp: str
    stop_reason: str
    seeds_completed: int
    seeds_remaining: int
    total_nodes_discovered: dict[str, int]
    total_nodes_expanded: dict[str, int]
    total_queries: int
    incomplete: bool


def write_checkpoint_manifest(repo_root: Path, manifest: CheckpointManifest) -> Path: ...
def load_latest_checkpoint(repo_root: Path) -> CheckpointManifest | None: ...
def decide_resume_mode(repo_root: Path, requested_mode: str | None) -> dict: ...
```

Semantics:
- Append-only checkpoints; no overwrite of prior checkpoints.
- Mark partial checkpoint with incomplete=true.

## 4.13 expansion_engine.py (new, replaces bfs_expansion.py)

Purpose:
- Authoritative graph expansion per spec predicates and ordering.

Target API:
```python
@dataclass(frozen=True)
class ExpansionConfig:
    max_depth: int
    max_nodes: int
    total_query_budget: int
    per_seed_query_budget: int
    inlinks_limit: int
    query_timeout_seconds: int
    query_delay_seconds: float
    cache_max_age_days: int
    max_neighbors_per_node: int


def run_seed_expansion(
    repo_root: Path,
    *,
    seed_qid: str,
    core_class_qids: set[str],
    config: ExpansionConfig,
) -> dict: ...

def is_expandable_target(
    candidate_qid: str,
    *,
    seed_qids: set[str],
    direct_link_to_seed: bool,
    instance_of_qids: set[str],
    core_class_qids: set[str],
    is_class_node: bool,
) -> bool: ...
```

Mandatory behavior:
- Expand each seed fully before next seed.
- Neighbor candidates: canonicalize, dedup, sort by lexical QID, FIFO queue.
- Apply decision table from spec.
- Inlinks to class nodes are discovered/persisted but never enqueued.

## 4.14 candidate_targets.py (refactor from targets.py)

Purpose:
- Build string-match targets used only after graph expansion pass.

Target API:
```python
def build_targets_from_phase2_lookup(repo_root: Path) -> tuple[list[dict], dict, object]: ...
```

Required delta:
- Align schema with setup file using label column where present (not only name).

## 4.15 Notebook Orchestration Contract

Purpose:
- Notebook-first end-to-end run control: bootstrap, per-seed expansion, checkpoint materialization, resume.

Notebook file:
- 21_candidate_generation_wikidata.ipynb

Execution contract:
- The notebook is the orchestrator.
- Process modules expose deterministic functions; notebook cells call them in strict order.
- Each major execution step has one markdown cell followed by one code cell.

Control flow:
1. Bootstrap and input validation.
2. Resume decision.
3. For each seed in csv order: run_seed_expansion, then materialize checkpoint.
4. Final materialization and run summary.

Required notebook cell structure:
1. Setup and imports (code)
2. Step markdown: Bootstrap and input validation (markdown)
3. Bootstrap and validation execution (code)
4. Step markdown: Resume decision (markdown)
5. Resume execution (code)
6. Step markdown: Per-seed expansion and checkpoint materialization (markdown)
7. Seed loop execution (code)
8. Step markdown: Final materialization and summary (markdown)
9. Finalization execution (code)

---

## 5. Canonical Event Schema (Implementation Contract)

This event schema is implemented in Step 3, but fixed here as a contract for module APIs.

Raw query event record JSON:
```json
{
  "event_version": "v2",
  "event_type": "query_response",
  "endpoint": "wikidata_api|wikidata_sparql",
  "normalized_query": "entity:Q1499182|sparql:SELECT ...",
  "query_hash": "md5_hex",
  "timestamp_utc": "2026-03-31T10:05:12Z",
  "source_step": "entity_fetch|inlinks_fetch|outlinks_build|property_fetch",
  "status": "success|http_error|timeout|fallback_cache",
  "key": "Q1499182|Q1499182_limit200",
  "http_status": 200,
  "error": null,
  "payload": {}
}
```

Normalization rules:
- Query hash = md5(endpoint + "|" + normalized_query).
- normalized_query is deterministic and stable across reruns.
- timestamp format fixed to UTC ISO second precision.

---

## 6. Acceptance Test Blueprint (Mapped to Spec Sections)

Target test root:
- speakermining/test/process/wikidata

## 6.1 Test file plan

- test_bootstrap.py
- test_seed_loading.py
- test_cache_event_policy.py
- test_expansion_predicates.py
- test_queue_ordering.py
- test_stop_conditions.py
- test_node_store_merge.py
- test_class_resolution.py
- test_triple_dedup.py
- test_query_inventory_dedup.py
- test_materialization_outputs.py
- test_checkpoint_resume.py
- test_end_to_end_small_fixture.py

## 6.2 Spec-to-test mapping

| Spec section | Acceptance tests | Assertions |
|---|---|---|
| Naming freeze | test_bootstrap.py::test_organizations_spelling_enforced | organizations accepted, organisations rejected |
| Cache and query event policy | test_cache_event_policy.py::test_one_raw_file_per_network_reply | raw file count equals network replies |
| Cache and query event policy | test_cache_event_policy.py::test_raw_event_required_fields | endpoint, normalized_query, query_hash, timestamp, source_step present |
| Input seed loading | test_seed_loading.py::test_invalid_qids_skipped_with_reason | NONE/blank/non-QID skipped and logged |
| Bootstrap requirement | test_bootstrap.py::test_empty_target_bootstraps_required_tree | all required folders/files created |
| Node storage discovered | test_node_store_merge.py::test_discovered_minimal_fields_written | en/de labels descriptions aliases, P31/P279 persisted |
| Expanded overwrite behavior | test_node_store_merge.py::test_expanded_payload_merges_existing_node | expanded fields merged into same ID record |
| Edge domain semantics | test_expansion_predicates.py::test_only_item_to_item_edges_enqueued | literals never become queue neighbors |
| Expandable target rule | test_expansion_predicates.py::test_expandability_decision_table | all 5 cases from table pass |
| Class inlink guard | test_expansion_predicates.py::test_class_inlinks_not_enqueued | discovered yes, queued no |
| Canonical queue ordering | test_queue_ordering.py::test_neighbors_dedup_canonical_sort_fifo | dedup+sort+FIFO stable |
| Seed ordering | test_queue_ordering.py::test_seed_order_matches_setup_csv | per-row seed order preserved |
| Stop condition precedence | test_stop_conditions.py::test_precedence_order | total budget > per-seed budget > queue exhausted |
| Class/instance path BFS | test_class_resolution.py::test_shortest_path_with_cycle_protection | shortest path found, cycles handled |
| Triple dedup policy | test_triple_dedup.py::test_subject_predicate_object_dedup | first timestamp retained |
| Query inventory dedup | test_query_inventory_dedup.py::test_hash_endpoint_dedup_keep_latest_success | latest success kept |
| Materialization outputs | test_materialization_outputs.py::test_all_csv_outputs_exist_with_columns | classes, instances, properties, aliases, triples present |
| Runtime lookup model | test_materialization_outputs.py::test_alias_lookup_fast_path | alias to qid lookup works via in-memory map |
| Checkpoint manifest | test_checkpoint_resume.py::test_manifest_required_fields | run_id stop_reason counters present |
| Resume semantics | test_checkpoint_resume.py::test_resume_append_restart_revert | all modes behave per spec |
| End-to-end deterministic rerun | test_end_to_end_small_fixture.py::test_deterministic_outputs_same_fixture | same inputs produce byte-identical CSV ordering |

## 6.3 Fixtures and deterministic controls

Required fixtures:
- Minimal setup classes fixture (including organizations spelling check).
- Minimal broadcasting programs fixture with valid and invalid rows.
- Frozen raw query fixture set for deterministic replay.
- Tiny graph fixture to trigger all expandability cases.

Determinism controls:
- Fixed seed order from fixture file.
- Fixed timestamps in unit tests where possible via injection.
- Stable lexical sort at all projection layers.

---

## 7. Migration Actions by Sequence Step

Action list for implementing this blueprint (code phase):
1. Create new modules and schema constants (schemas.py, bootstrap.py, event_log.py, node_store.py, triple_store.py, query_inventory.py, checkpoint.py, expansion_engine.py).
2. Refactor cache.py and entity.py to emit v2 event schema.
3. Replace bfs_expansion.py behavior with expansion_engine.py and keep notebook-facing wrapper if needed.
4. Replace aggregates.py with materializer.py projections for Option B outputs.
5. Refactor targets.py to candidate_targets.py and fix setup column mapping label/name handling.
6. Add full acceptance test tree under speakermining/test/process/wikidata.
7. Update notebook orchestration in 21_candidate_generation_wikidata.ipynb to execute the four-step control flow in dedicated markdown/code cell pairs.

---

## 8. Explicit Decisions and Open Items

Decisions finalized in this blueprint:
- Step 1 Option B remains authoritative.
- Runtime lookups are in-memory, persisted at checkpoints.
- Checkpoint manifests are append-only and include incomplete marker.
- No backward compatibility adapters for old raw schema; archive then remove legacy files.

Open items requiring confirmation before implementation starts:
### 1. Inlinks chunking strategy details at SPARQL level (offset pagination strategy constraints).
* **Confirmation**: fully frozen for Step 3 implementation.

#### Frozen parameters:
- chosen_strategy: hybrid
- page_size_default: 200
- page_size_max: 1000
- ordering_clause: ORDER BY ?source ?prop
- page query template: LIMIT {page_size} OFFSET {offset}
- dedup key across pages: (source_qid, pid)

#### Cursor schema persisted in checkpoint manifest:
- inlinks_cursor.target_qid: str
- inlinks_cursor.seed_qid: str
- inlinks_cursor.page_index: int
- inlinks_cursor.offset: int
- inlinks_cursor.last_source_qid: str | null
- inlinks_cursor.last_pid: str | null
- inlinks_cursor.page_size: int
- inlinks_cursor.exhausted: bool

#### Retry/backoff and paging interaction:
- max_retries_per_page: 4
- retry policy: exponential backoff with jitter, shared with cache HTTP policy
- page commit rule: cursor is persisted only after successful page parse and dedup merge
- failure rule after max retries: write incomplete checkpoint and stop with stop_reason=crash_recovery
- resume rule: continue from persisted cursor values without replaying successful pages

#### Acceptance tests required for this contract:
- test_inlinks_paging_no_duplicates_across_offsets
- test_inlinks_resume_from_cursor_no_missing_rows
- test_inlinks_retry_failure_writes_incomplete_checkpoint

### 2. Whether properties are fetched beyond those discovered in item claims.
* **Confirmation**: No, they are not. Only those specified in `data/00_setup/properties.csv` and those discovered in item claims are fetched. 
* Remember: Some objects of claims may be properties, too, for example of as object of "main Wikidata property (P1687)"

### 3. Whether checkpoint manifests live as separate files or embedded only in summary.json (recommended: separate manifest plus summary.json projection).
* **Confirmation**: separate manifest plus summary.json projection

---

## 8.1 Coding-Principles Compliance Notes

Alignment with documentation/coding-principles.md:
- Process logic remains module-first; notebook keeps orchestration role only.
- Explicit schemas, deterministic ordering, and acceptance tests are defined.
- Runtime checkpoint persistence is explicitly required.

Required follow-up actions for full compliance in implementation PRs:
1. If schema or filenames change during Step 3/4 coding, update contracts.md in same PR.
2. If execution flow or phase outputs change, update workflow.md and README.md in same PR.
3. Record implementation tasks and remaining work in open-tasks.md.
4. Keep findings and evidence updates in findings.md.

Notes:
- This blueprint intentionally gives implementation detail because it is a transition artifact.
- Governance ownership still resides in workflow.md, repository-overview.md, contracts.md, open-tasks.md, and findings.md.

---

## 9. Definition of Done for Step 2

Step 2 is complete when:
1. This blueprint is accepted as authoritative implementation contract.
   * **Confirmation**: blueprint is accepted as authoritative implementation contract.
2. Each production-spec section has a mapped module owner and acceptance test.
   * **Confirmation**: There are no module owners, yet the acceptance test should be implemented. Assume we are the sole owner.
3. Event schema contract is frozen for Step 3 implementation.
    * **Confirmation**: complete. Event schema and inlinks paging contract are fully parameterized in Section 8.
4. Migration action list is approved for execution in code.
    * **Confirmation**: complete. Migration actions are approved with notebook-first orchestration and dedicated markdown/code cells per major step.