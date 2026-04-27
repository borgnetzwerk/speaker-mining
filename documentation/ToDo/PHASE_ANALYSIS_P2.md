# Phase Analysis: Phase 2 — Candidate Generation

> Part of the phase-by-phase analysis pass.  
> See [PHASE_ANALYSIS_INDEX.md](PHASE_ANALYSIS_INDEX.md) for the full index.

---

## Overview

Phase 2 generates candidates for all mentions identified in Phase 1 by querying three external sources:
1. **Phase 2a** (`20_candidate_generation_wikibase.ipynb`) — Local Wikibase (legacy/placeholder)
2. **Phase 2b** (`21_candidate_generation_wikidata.ipynb`) — Wikidata graph expansion (**primary**)
3. **Phase 2c** (`22_candidate_generation_fernsehserien_de.ipynb`) — fernsehserien.de web scraping
4. **Phase 2d** (`23_candidate_generation_other.ipynb`) — Placeholder (not implemented)

All outputs go to `data/20_candidate_generation/`.

### Status
**Phase 2b and 2c are complete and active.** The Wikidata v3 event-sourced engine and fernsehserien.de pipeline both produce full projection artifacts. Phase 2a is legacy; 2d is not implemented.

---

## Phase 2b: Wikidata Candidate Generation

### Files

#### [21_candidate_generation_wikidata.ipynb](../speakermining/src/process/notebooks/21_candidate_generation_wikidata.ipynb)
Highly complex notebook with 12 major steps:

| Step | Description |
|------|-------------|
| 1 | Project setup |
| 2 | Workflow configuration (budget, rate-limit, adaptive backoff, language, fallback) |
| 2.4 | Preflight subclass expansion — P279 BFS from core classes, cache-first |
| 2.4.1 | Conflict analysis across class resolution map |
| 2.5 | Class hierarchy clarification (core vs root classes) |
| 3 | Decide resume mode (`append` vs `revert`) |
| 4 | Bootstrap seeds from `data/00_setup/broadcasting_programs.csv` |
| 5 | Build mention targets from Phase 2 lookup outputs |
| 6 | Stage A: graph-first expansion (deterministic, seed-ordered, checkpointed) |
| 6.5 | Node integrity pass (repair + re-expand) |
| 7 | Build unresolved handoff for Stage B |
| 8 | Stage B: fallback string matching (only unresolved targets) |
| 9 | Re-check + expand eligible fallback discoveries |
| 10 | Review deterministic graph artifacts |
| 11 | Handler materialization benchmark (optional) |
| 12 | Runtime evidence bundle closeout |

**Key configuration parameters (Step 2):**
```python
max_depth=2                           # BFS depth from seeds
subclass_expansion_max_depth=3        # P279 crawl depth
max_nodes=500000
max_queries_per_run=-1               # -1=unlimited, 0=cache-only
query_delay_seconds=0.25
adaptive_backoff_enabled=True
wikidata_entity_languages={"en": True, "de": True}
fallback_enabled_mention_types={"person": False, ...}  # all off by default
```

#### Wikidata Module Architecture (35+ Python files)

**Core Engine:**
- [expansion_engine.py](../speakermining/src/process/candidate_generation/wikidata/expansion_engine.py) — Main BFS orchestration, `ExpansionConfig`, `GraphExpansionResult`, `run_graph_expansion_stage()`
- [bootstrap.py](../speakermining/src/process/candidate_generation/wikidata/bootstrap.py) — Loads seed classes, root classes, and broadcasting program seeds
- [entity.py](../speakermining/src/process/candidate_generation/wikidata/entity.py) — Fetches Wikidata entities (cache-first, HTTP fallback)
- [cache.py](../speakermining/src/process/candidate_generation/wikidata/cache.py) — Atomic disk cache, HTTP client

**Storage Layer:**
- [node_store.py](../speakermining/src/process/candidate_generation/wikidata/node_store.py) — In-memory + disk entity storage, `upsert_discovered_item()`, `upsert_expanded_item()`
- [triple_store.py](../speakermining/src/process/candidate_generation/wikidata/triple_store.py) — Tracks RDF triples, `record_item_edges()`, `iter_unique_triples()`

**Event Sourcing:**
- [event_log.py](../speakermining/src/process/candidate_generation/wikidata/event_log.py) — Append-only JSONL event stream
- [event_handler.py](../speakermining/src/process/candidate_generation/wikidata/event_handler.py) — Event replay / materialization
- [event_writer.py](../speakermining/src/process/candidate_generation/wikidata/event_writer.py) — v3 JSONL chunk writer
- [chunk_catalog.py](../speakermining/src/process/candidate_generation/wikidata/chunk_catalog.py) — Index and manage JSONL chunks

**Handlers (8 files in `handlers/`):**
- `candidates_handler.py` — Candidate matching events
- `classes_handler.py` — Class discovery
- `instances_handler.py` — Instance discovery
- `triple_handler.py` — Triple (RDF edge) events
- `relevancy_handler.py` — Relevancy filtering
- `backoff_learning_handler.py` — Rate-limit adaptation
- `query_inventory_handler.py` — Query history tracking
- `orchestrator.py` — Handler coordination

**Expansion & Traversal:**
- [inlinks.py](../speakermining/src/process/candidate_generation/wikidata/inlinks.py) — SPARQL inlink queries, paging
- [outlinks.py](../speakermining/src/process/candidate_generation/wikidata/outlinks.py) — Outlink property extraction

**Class Resolution:**
- [class_resolver.py](../speakermining/src/process/candidate_generation/wikidata/class_resolver.py) — P279 subclass hierarchy, `compute_class_rollups()`

**Materialization:**
- [materializer.py](../speakermining/src/process/candidate_generation/wikidata/materializer.py) — `materialize_final()` — converts event log to deterministic CSV/JSON artifacts in `projections/`

**Checkpointing:**
- [checkpoint.py](../speakermining/src/process/candidate_generation/wikidata/checkpoint.py) — `decide_resume_mode()`, `restore_checkpoint_snapshot()`, `write_checkpoint_manifest()`

**Fallback:**
- [fallback_matcher.py](../speakermining/src/process/candidate_generation/wikidata/fallback_matcher.py) — String matching for unresolved targets
- [candidate_targets.py](../speakermining/src/process/candidate_generation/wikidata/candidate_targets.py) — Target QID resolution from Phase 1 mentions

**Quality & Observability:**
- [node_integrity.py](../speakermining/src/process/candidate_generation/wikidata/node_integrity.py) — Validate + repair graph consistency
- [backoff_learning.py](../speakermining/src/process/candidate_generation/wikidata/backoff_learning.py) — Adaptive rate-limit learning
- [conflict_analysis.py](../speakermining/src/process/candidate_generation/wikidata/conflict_analysis.py) — Class resolution conflicts
- [handler_benchmark.py](../speakermining/src/process/candidate_generation/wikidata/handler_benchmark.py) — Performance metrics
- [runtime_evidence.py](../speakermining/src/process/candidate_generation/wikidata/runtime_evidence.py) — Structured runtime evidence bundles
- [graceful_shutdown.py](../speakermining/src/process/candidate_generation/wikidata/graceful_shutdown.py) — Signal-based termination
- [heartbeat_monitor.py](../speakermining/src/process/candidate_generation/wikidata/heartbeat_monitor.py) — Progress callbacks

**Common utilities:**
- [common.py](../speakermining/src/process/candidate_generation/wikidata/common.py) — `canonical_qid()`, `normalize_text()`, `pick_entity_label()`
- [schemas.py](../speakermining/src/process/candidate_generation/wikidata/schemas.py) — `build_artifact_paths()`, artifact naming
- [relevancy.py](../speakermining/src/process/candidate_generation/wikidata/relevancy.py) — Relevancy filtering

### Wikidata Output Artifacts (data/20_candidate_generation/wikidata/)

| Artifact | Description |
|----------|-------------|
| `projections/instances.csv` | All discovered instances |
| `projections/instances_core_persons.json` | 640 persons with 767 properties |
| `projections/instances_core_episodes.json` | 997 episodes with 60 properties |
| `projections/instances_core_organizations.json` | 51 orgs with 881 properties |
| `projections/instances_core_series.json` | 397 series with 383 properties |
| `projections/instances_core_broadcasting_programs.json` | 20 programs with 66 properties |
| `projections/instances_core_roles.json` | 0 rows (empty) |
| `projections/triples.csv` | 120,930 RDF triples (subject/predicate/object) |
| `projections/classes.csv` | 2,522 class entries |
| `projections/properties.csv` | 1,665 property definitions |
| `projections/aliases_de.csv` | 6,585 German aliases |
| `projections/aliases_en.csv` | 13,749 English aliases |
| `projections/class_resolution_map.csv` | Subclass resolution mapping |
| `projections/query_inventory.csv` | Query history and budgets |
| `projections/fallback_stage_candidates.csv` | Stage B fallback results |
| `chunks/*.jsonl` | Canonical append-only event log |
| `node_integrity/` | Integrity pass diagnostics |
| `runtime_evidence/` | Structured closeout bundles |

### Known Issues
- `wikidata_roles` contains 0 rows — roles are currently not populated via Wikidata. This affects Phase 31 role alignment.
- Season entities misclassify (Q3464665 entities entering broadcasting_program path without series visibility) — documented in F-012.

---

## Phase 2c: Fernsehserien.de Candidate Generation

### Files

#### [22_candidate_generation_fernsehserien_de.ipynb](../speakermining/src/process/notebooks/22_candidate_generation_fernsehserien_de.ipynb)
5-section notebook:

| Section | Description |
|---------|-------------|
| 1 | Project setup; optional projection reset |
| 2 | Configure `MAX_NETWORK_CALLS`, `QUERY_DELAY_SECONDS`, `USER_AGENT` |
| 3 | Execute workflow (deterministic, event-sourced, cache-first) |
| 4 | Verify run behavior (budget assertions) |
| 5 | Inspect projections + deep diagnostics (guest coverage, no-guest markup audit) |

**Key runtime parameter:**
```python
MAX_NETWORK_CALLS = 5000  # 0=cache-only, >0=bounded, <0=unlimited
QUERY_DELAY_SECONDS = 1.0
```

The notebook has extensive diagnostics for the guest coverage problem (F-013):
- URL-level comparison between episodes with/without guests
- HTML markup audit (`Cast-Crew` anchor, `cast-crew` class, `data-event-category`, `href=/personen/`)
- Parser re-inspection of no-guest cached pages

#### Fernsehserien.de Module (14 Python files)

- [orchestrator.py](../speakermining/src/process/candidate_generation/fernsehserien_de/orchestrator.py) — Full pipeline: program → index → episodes → guests → normalization → projection
- [config.py](../speakermining/src/process/candidate_generation/fernsehserien_de/config.py) — `FernsehserienRunConfig` (budget, network, traversal)
- [parser.py](../speakermining/src/process/candidate_generation/fernsehserien_de/parser.py) — HTML parsing: `parse_episode_leaf_fields()`, `parse_guest_rows()`, title/duration/broadcast extraction
- [fetcher.py](../speakermining/src/process/candidate_generation/fernsehserien_de/fetcher.py) — HTTP fetching with cache
- [event_store.py](../speakermining/src/process/candidate_generation/fernsehserien_de/event_store.py) — Append-only JSONL event storage
- [checkpoint.py](../speakermining/src/process/candidate_generation/fernsehserien_de/checkpoint.py) — Resumable execution snapshots
- [projection.py](../speakermining/src/process/candidate_generation/fernsehserien_de/projection.py) — CSV projections from event replay
- [paths.py](../speakermining/src/process/candidate_generation/fernsehserien_de/paths.py) — Runtime directory layout
- [handler_progress.py](../speakermining/src/process/candidate_generation/fernsehserien_de/handler_progress.py) — Per-handler `last_processed_sequence` tracking
- [notebook_runtime.py](../speakermining/src/process/candidate_generation/fernsehserien_de/notebook_runtime.py) — `run_pipeline_with_notebook_heartbeat()`
- [fragment_cleanup.py](../speakermining/src/process/candidate_generation/fernsehserien_de/fragment_cleanup.py) — URL fragment removal

### Fernsehserien.de Output Artifacts (data/20_candidate_generation/fernsehserien_de/)

| Artifact | Rows | Description |
|----------|------|-------------|
| `projections/episode_metadata_normalized.csv` | 6,459 | Episode titles, dates, durations |
| `projections/episode_guests_normalized.csv` | 25,452 | Guest names per episode |
| `projections/episode_broadcasts_normalized.csv` | 15,929 | Broadcast schedule entries |
| `projections/episode_urls.csv` | — | All discovered episode URLs |
| `projections/program_pages.csv` | — | Program-level pages |
| `projections/episode_index_pages.csv` | — | Season/index pages |
| `projections/summary.json` | — | Run summary and stats |
| `chunks/*.jsonl` | — | Canonical event log |
| `cache/pages/*.html` | — | Cached episode HTML |
| `eventhandler.csv` | — | Per-handler `last_processed_sequence` |

### ~~Known Issues / Bug Site: Row 3 Missing~~ — CLOSED 2026-04-22 (Non-Issue)

**Original symptom:** "The third row of the fernsehserien.de guest description appears to be missing."

**Investigation result (2026-04-22):** Not a bug. Both `episode_guests_discovered.csv` and `episode_guests_normalized.csv` have exactly 25,452 rows with zero per-episode discrepancy. Guest descriptions are correctly propagated to Phase 31 (`fs_episode_guests_normalized.csv`, 71.7% coverage). Sample check: Ute Teichert's "Vorsitzende Bundesverband der Ärztinnen und Ärzte des Öffentlichen Gesundheitsdienstes (BVÖGD)" is present in `aligned_persons.csv`. The parser correctly splits `<br>` within `<dd><p>...</p></dd>` into `guest_role` (line 0) and `guest_description` (lines 1+). Empty descriptions in the data (28.3%) are genuine — those guests have no description line in the source HTML.

**Connection to F-013:** Many episodes on fernsehserien.de have no guests at all (esp. Hart aber fair early episodes). This is a data source limitation, not a parsing bug.

---

## Phase 2a & 2d (Legacy / Placeholder)

### [20_candidate_generation_wikibase.ipynb](../speakermining/src/process/notebooks/20_candidate_generation_wikibase.ipynb)
- **Status:** Legacy placeholder. Outputs setup copies and lookup tables that notebook 21 depends on.
- **Must run before notebook 21** to generate `data/20_candidate_generation/episodes.csv` and `broadcasting_programs.csv`.

### [23_candidate_generation_other.ipynb](../speakermining/src/process/notebooks/23_candidate_generation_other.ipynb)
- **Status:** Placeholder only. Not implemented.

---

## Cross-Cutting Phase 2 Python Modules

These modules are shared by Phase 2 notebooks and their initialization:

- [broadcasting_program.py](../speakermining/src/process/candidate_generation/broadcasting_program.py) — `load_broadcasting_program_seeds()`
- [episode.py](../speakermining/src/process/candidate_generation/episode.py) — `load_episodes_context()`, `build_episodes_lookup()`
- [person.py](../speakermining/src/process/candidate_generation/person.py) — `load_persons_context()`, `clean_mixed_uppercase_name()`, `split_duplicate_person_mentions()`
- [season.py](../speakermining/src/process/candidate_generation/season.py) — `load_seasons_context()`, `build_seasons_lookup()`
- [topic.py](../speakermining/src/process/candidate_generation/topic.py) — Topic loading utilities
- [persistence.py](../speakermining/src/process/candidate_generation/persistence.py) — Central CSV write helpers; `persist_dataframe()`, `persist_setup_outputs()`

---

## Open Tasks for Phase 2

| ID | Priority | Description |
|----|----------|-------------|
| ~~(bug)~~ | ~~HIGH~~ | ~~fernsehserien.de guest description row 3 missing~~ — **CLOSED 2026-04-22 (non-issue, descriptions confirmed present)** |
| F-012 | MEDIUM | Season misclassification (Q3464665 entering broadcasting_program path) — document in governance |
| F-013 | INFO | Many fernsehserien.de episodes have no guests — structural limitation, not a bug |
| `wikidata_roles` empty | LOW | Roles instance table is 0 rows — review expansion config for roles class |

## Key Interdependencies
- Phase 2b runs after Phase 2a (needs `episodes.csv` + `broadcasting_programs.csv`)
- Phase 2c runs independently of 2b
- Phase 31 reads **all** Phase 2 projections (Wikidata JSON + fernsehserien.de CSVs)
- The triples.csv (120,930 rows) is available for page-rank analysis in Phase 4
