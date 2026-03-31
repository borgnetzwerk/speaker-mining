# Step 1: Revise Required Graph Artifacts — Design Analysis and Decision

**Date:** 2026-03-31  
**Status:** Analysis and Decision  
**Scope:** Specifications, design trade-offs, and final artifact schema for the new Wikidata graph store

---

## 1. Current State: Spec Requirements

The production spec ([wikidata_future_V2.md](wikidata_future_V2.md)) defines the following required artifacts:

### Portfolio of Artifacts (Spec Section: "Bootstrap Requirement")

**Top-level files:**
- `classes.csv` — deduplicated class nodes (overview/index)
- `triples.csv` — deduplicated relationship records (subject, predicate, object, more_info_path)
- `summary.json` — run metadata  
- `query_inventory.csv` — query log (dedup key: query hash + endpoint)

**Class/instance partition pairs** (one per core class filename from `data/00_setup/classes.csv`):

Example: for filename `persons`:
- `classes/persons.csv` — label, description, alias, label_de, description_de, alias_de, path
- `classes/persons.json` — rich payload (all properties)
- `instances/persons.csv` — same structure
- `instances/persons.json` — same structure

**Properties pair:**
- `properties/properties.csv` — label, description, alias, label_de, description_de, alias_de, path
- `properties/properties.json` — rich payload

**Raw query cache:**
- `raw_queries/` (append-only event records, one per network response)

### Nested Structure Example

Assuming core classes: `persons`, `organizations`, `episodes`, `series`, `broadcasting_programs`, `roles`, `topics`, `entities`, `privacy_properties`:

```
data/20_candidate_generation/wikidata/
  classes.csv
  triples.csv
  summary.json
  query_inventory.csv
  raw_queries/
    {timestamp}__{query_type}__{key}.json (append-only)
  classes/
    persons.csv
    persons.json
    organizations.csv
    organizations.json
    episodes.csv
    episodes.json
    series.csv
    series.json
    broadcasting_programs.csv
    broadcasting_programs.json
    roles.csv
    roles.json
    topics.csv
    topics.json
    entities.csv
    entities.json
    privacy_properties.csv
    privacy_properties.json
  instances/
    [same structure as classes/]
  properties/
    properties.csv
    properties.json
```

---

## 2. Rationale in Spec: Why This Design?

### 2.1 JSON vs. CSV Principle

**From spec (Section: "Data model and artifacts"):**

> JSON is the source of truth for rich payloads. CSV files are redundant overview and indexing tables derived from JSON and raw query events.

**Implication:**
- JSON files preserve complete Wikidata entity payloads (all properties, qualifiers, references, language variants).
- CSV files are **derived, redundant, read-optimized** views for human inspection and fast lookup.
- This supports **recoverability**: if a CSV is corrupted, regenerate it deterministically from JSON. If even this JSON gets corrupted, the JSON can be regenerated from the raw_queries.

### 2.2 Class/Instance Partitioning Rationale

**From spec (Section: "Node storage model" and "Class and instance discovery policy"):**

1. **Class detection** — any entity with P279 statement is class-capable.
2. **Instance detection** — any entity without P279 is an instance.
3. **Path resolution** — for discovered classes and instances, run BFS over subclass/instance relations to find shortest path to a core class.
4. **Persist path** — store resolved class ancestry in overview rows.

**Why partition by class?**

- **Semantic grouping**: all instances (or classes) of type `persons` are together for human review and downstream analysis.
- **Garbage collection**: easy cleanup per category if patterns are discovered.
- **Parallel processing**: in future, class partitions can be processed independently without locking.
- **Discovery tracking**: partition-level statistics (count of discovered vs. expanded) are first-class.

### 2.3 Triples.csv Purpose

**From spec:**

> Triple table dedup: Dedup key: (subject, predicate, object). Immutable facts keep first observed timestamp.

**Rationale:**
- Store all item-to-item relationships extracted from entity claims.
- Enable **graph topology analysis** without loading full JSON payloads.
- Support **triple-level provenance**: which query discovered this edge, when.
- Dedup prevents inflation from discovery-only vs. expanded re-processing of the same entity.

### 2.4 Raw Query Cache

**From spec (Section: "Cache and query event policy"):**

> Raw query results are append-only event records, one file per remote reply. Number of raw query files equals number of remote replies received.

**Rationale:**
- **Immutable provenance**: each network response is stored exactly once with timestamp, query hash, endpoint.
- **Recovery guarantee**: if any aggregate or derived file is corrupted, regenerate from raw files.
- **Audit trail**: every request to Wikidata is logged with source step (entity, inlinks, outlinks, etc.).

---

## 3. Current Implementation State

### 3.1 What Exists in the Old Implementation

Resources that can be built upon.
From gap analysis ([gap_analysis.md](gap_analysis.md)):

- ✓ Raw query cache with append-only semantics: `raw_queries/` directory with timestamped JSON records
- ✓ Atomic writes, rebuild-from-raw mindset
- ✓ `classes.csv` with aggregated class counts (instance_count, subclass_count)
- ✓ `query_inventory.csv` with query metadata (file, query_type, key, requested_at_utc, age_days, source)
- ✓ `summary.json` with basic run metadata (raw_files, candidate_rows, candidates_csv paths)
- ✓ **Partial** class/instance partitions in `wikidata/new/` folder

### 3.2 What Is Missing or Incomplete

- ✗ `triples.csv` — not materialized from raw edge facts
- ✗ `properties/properties.csv` and `properties/properties.json` — not extracted or indexed
- ✗ Full class/instance partition pairs (missing many `.json` files, incomplete `.csv` content)
- ✗ Path resolution (P31/P279 paths to core classes) — spec requires BFS shortest-path, current code only counts P31/P279 occurrences
- ✗ Query inventory dedup by hash+endpoint — current version is raw file-derived with no dedup
- ✗ Checkpoint manifests (run_id, stop_reason, seeds_completed/remaining) — absent
- ✗ Node storage distinguishing discovered-only vs. expanded payloads — no flag in current data

### 3.3 Dual-Path State

- Current pipeline outputs to `data/20_candidate_generation/wikidata/` (candidates.csv, query_inventory.csv, etc.)
- Partial new graph outputs to `data/20_candidate_generation/wikidata/new/` (classes partitions, instances partitions)
- Spec migration target: merge into `data/20_candidate_generation/wikidata/` only

---

## 4. Design Trade-Off Analysis

### Option A: Full Spec — All Artifacts (classes/, instances/, properties/, triples.csv)

**Description:** Implement exactly as specified with class/instance partitions, properties index, and triple materialization.

**Pros:**
- ✓ Spec-compliant and well-defined semantics
- ✓ Class partitions enable cleanup and analysis by semantic type
- ✓ Triples.csv provides fast graph topology queries without loading all entity JSON
- ✓ Properties index allows property-specific analyses and discovery
- ✓ Partition-level statistics (discovered, expanded per class) first-class
- ✓ Future parallelization by partition is natural
- ✓ Path resolution (P31/P279 ancestry) is persistent and queryable

**Cons:**
- ✗ Large total artifact volume (~9 class partitions × 2 (classes+instances) × 2 (csv+json) + 2 property files = ~40 files minimum)
- ✗ CSV materialization is expensive (full scan of JSON to extract fields, deduplicate, sort)
- ✗ More moving parts = higher complexity in rebuild logic
- ✗ Harder to spot missing data (spreads across many files)

**File count estimate:** ~45–50 files at stabilization

---

### Option B: Hybrid — Consolidated JSON + Selective CSV

**Description:** Store one unified `entities.json` (all discovered and expanded nodes) + one `properties.json` (all properties). CSV materialization only for top-level `classes.csv`, `instances.csv`, `properties.csv` (not per-partition).

**Rationale:**
- Simplify by eliminating partition file explosion
- Maintain JSON as source of truth
- Preserve CSV for type-based lookup and top-level statistics

**Schema sketch:**
```json
// entities.json
{
  "entities": {
    "Q1499182": {
      "id": "Q1499182",
      "type": "item",
      "discovered_at_utc": "2026-03-26T14:52:24Z",
      "expanded_at_utc": "2026-03-26T14:52:28Z",  // null if discovered-only
      "labels": {...},
      "descriptions": {...},
      "instance_of": ["Q11578774"],  // P31
      "subclass_of": [],              // P279
      "outlinks": {"Q56418119": {...}, ...},
      "inlinks": {"Q130559283": {...}, ...},
      "path_to_core_class": {
        "class_qid": "Q11578774",
        "class_filename": "broadcasting_programs",
        "path_length": 0,
        "path": ["Q1499182"]  // ancestor path
      }
    },
    ...
  }
}

// properties.json
{
  "properties": {
    "P31": {
      "id": "P31",
      "type": "property",
      "discovered_at_utc": "2026-03-26T14:52:24Z",
      "labels": {...},
      "descriptions": {...},
      "instance_of": [...],
      "subproperty_of": []  // P1647
    },
    ...
  }
}

// classes.csv
id,label_en,label_de,description_en,description_de,alias_en,alias_de,path_to_core_class,subclass_of_core_class,discovered_count,expanded_count
Q215627,person,Person,human being,Mensch,"human being|individual","Mensch|Individuum",Q35120,true,512,487
Q43229,organization,Organisation,organized group with a common purpose,organisierte Gruppe mit gemeinsamem Zweck,"organisation|institution","Organisation|Institution",Q35120,true,234,198
...

// instances.csv
id,class_id,class_filename,label_en,label_de,description_en,description_de,alias_en,alias_de,path_to_core_class,discovered_at_utc,expanded_at_utc
Q1499182,Q11578774,broadcasting_programs,Markus Lanz,Markus Lanz,German talk show,Talkshow im ZDF,"Markus Lanz","Markus Lanz","[Q1499182]",2026-03-26T14:52:24Z,2026-03-26T14:52:28Z
...

// properties.csv
id,label_en,label_de,description_en,description_de,alias_en,alias_de
P31,instance of,ist ein(e),that class of which this subject is a particular example and member,diese Klasse, zu der das Subjekt als konkretes Beispiel gehoert,"type|class membership","Instanz von"
P279,subclass of,Unterklasse von,relationship between two classes where instances of the first class are also instances of the second class,Beziehung zwischen zwei Klassen wobei Instanzen der ersten auch Instanzen der zweiten sind,"class hierarchy","Unterklasse"
...

// aliases_en.csv
alias,qid
Psychologist,Q12345
Psychologin,Q67890

// aliases_de.csv
alias,qid
Psychologe,Q12345
Psychologin,Q67890
```

**First Intersection Resolution (Integrated):**
- `discovered_count` in `classes.csv`: number of unique entities assigned to this class that were observed at least once in the run, independent of expansion status.
- `expanded_count` in `classes.csv`: number of unique entities assigned to this class for which a full entity expansion (claims traversal) was completed.
- `subclass_of_core_class` added to `classes.csv`: boolean (`true`/`false`) showing whether the class is in a direct or transitive subclass chain below any configured core class.
- Every table that exposes a label/description now has bilingual and alias coverage:
  - `label_en`, `label_de`
  - `description_en`, `description_de`
  - `alias_en`, `alias_de` (pipe-separated within the row)
- Dedicated language alias lookup tables are added for O(1)-style lookup workflows:
  - `aliases_en.csv` with `alias,qid`
  - `aliases_de.csv` with `alias,qid`
- Example lookup becomes trivial:
  - read alias lists once, then evaluate `if label in alias_list_en or label in alias_list_de`.

**Pros:**
- ✓ Simple, unified JSON structure (two files: entities.json, properties.json)
- ✓ Smaller file count (~5 core files vs. 40+)
- ✓ CSV materialization is simple (single-pass from entities.json)
- ✓ Path resolution and discovered/expanded flags are queryable from CSV
- ✓ Still preserves JSON as source of truth
- ✓ Easier to spot missing data (consolidated view)
- ✓ Rebuild is straightforward

**Cons:**
- ✗ Entities.json can become very large (100k+ nodes × full payloads = 500MB–2GB risk)
- ✗ Corruption of single JSON file impacts a larger logical scope at once
  - Mitigation: roll back to last checkpoint and regenerate from `raw_queries/` when needed
  - Requires reliable checkpointing and atomic writes
- ✗ Loading full entities.json for small queries is wasteful (not partitioned)
- ✗ Can't parallelize by class category
- ✗ Deviates from spec (partition design rationale isn't addressed)

**File count estimate:** ~5 core files + raw_queries/

---

### Option C: Pragmatic Middle Ground — Partition by Node Type Only (discovered vs. expanded)

**Description:** Partition by **state** (discovered-only vs. expanded), not by semantic class. Store:
- `discovered_nodes.json` / `discovered_nodes.csv` — basic fields only
- `expanded_nodes.json` / `expanded_nodes.csv` — full payloads
- `triples.csv` — all discovered edges
- `properties.json` / `properties.csv` — all discovered properties

**Rationale:**
- Separates immutable cache (discovered) from enriched payloads (expanded)
- Enables efficient rebuild: discovered nodes are never invalidated
- Avoids explosion of per-class files
- Triples table provides explicit relationship index

**Pros:**
- ✓ Aligns with spec's discovered/expanded distinction
- ✓ Cleaner separation of concerns (cache vs. enrichment)
- ✓ Triples.csv enables fast graph queries
- ✓ Smaller file count (~8 core files)
- ✓ Natural recovery model: discovered nodes are append-only, expanded nodes can be rebuilt from triples+properties

**Cons:**
- ✗ Harder to analyze "all persons" or "all episodes" without class partition
- ✗ Triples.csv requires triple-level dedup logic (not in current code)
- ✗ Still deviates from spec (but with clearer rationale)

**Status after First Intersection:** Rejected as primary recommendation. The discovered/expanded distinction remains useful as a field, but not as the main partition strategy.

**File count estimate:** ~8 files + raw_queries/

---

## 5. Comparative Analysis Table

| Dimension | Option A (Full Spec) | Option B (Consolidated) | Option C (State-based) |
|-----------|----------------------|------------------------|----------------------|
| **Spec Compliance** | ✓ Full | ⚠ Partial (simplifies partitioning) | ⚠ Partial (different partition logic) |
| **File Count** | 45–50 | ~5 | ~8 |
| **JSON Size Risk** | Distributed (lower per-file) | Single point (500MB–2GB risk) | Distributed (lower per-file) |
| **Corruption Recovery** | Per-partition rebuild | Checkpoint rollback plus full regeneration from `raw_queries/` | Partial rebuild possible |
| **CSV Materialization Complexity** | High (per-partition logic) | Simple (single pass) | Medium (dedup triples) |
| **Parallelization Support** | ✓ By class | ✗ Not applicable | ⚠ By state, limited |
| **Semantic/Analytical Grouping** | ✓✓ Strong (class-based) | ⚠ Top-level only | ⚠ By state, not class |
| **Path Resolution Visibility** | ✓ Per-class CSVs | ⚠ Single instances.csv | ⚠ In nodes only |
| **Implementation Complexity** | High | Low | Medium |
| **Testability** | Moderate (many files to verify) | High (fewer artifacts) | Medium |
| **Migration Effort** | High (significant refactor) | Low–Medium (focus on dedup logic) | Medium (introduce triples) |

---

## 6. Risk Assessment

### Option A: Full Spec
- **Highest implementation effort**
- **Path resolution BFS algorithm is complex** and not yet implemented
- **Per-partition CSV materialization** is error-prone
- But **strongest spec alignment** and **best long-term maintainability**

### Option B: Consolidated
- **Lowest implementation effort**
- **Single-file concentration risk:** a bad write affects a larger logical scope
- **Mitigation path is strong:** checkpoint rollback and full regeneration from `raw_queries/` remain available
- **Operational risk is acceptable** when atomic writes and checkpoint frequency are implemented

### Option C: State-based
- **Medium implementation effort**
- **Triples dedup logic** must be correct (subject, predicate, object uniqueness)
- **Split discovered/expanded** is natural and defensible
- **Good middle ground** between complexity and risk

---

## 7. Recommendation: **Adopt Option B (Consolidated JSON + Selective CSV)**

### Rationale

1. **First Intersection decision:**
  - Partitioning by discovered/expanded status is not important enough to drive the file model.
  - Discovered/expanded remains a node-level field, not a storage partition.

2. **Consolidation with explicit language support:**
  - One consolidated `entities.json` plus `properties.json` keeps the architecture small.
  - CSV outputs explicitly carry bilingual fields and alias columns for direct analytics use.
  - Added alias lookup tables satisfy fast lookup use cases such as "Psychologin" matching.

3. **Corruption fallback is operationally robust:**
  - Checkpoint and backup restore remain primary recovery path.
  - Full regeneration from immutable `raw_queries/` is retained as worst-case fallback.

4. **Balanced migration effort:**
  - Smaller refactor footprint than Option A.
  - Keeps enough structure for downstream filtering via `class_id`, `class_filename`, and `subclass_of_core_class`.

### Final Artifact Schema (Option B)

```
data/20_candidate_generation/wikidata/
  
  # Core node stores
  entities.json              # All entities; each node includes discovered/expanded timestamps and full claims when available
  properties.json            # All discovered properties with metadata
  
  # Relationship store
  triples.csv                # Deduplicated (subject, predicate, object, timestamp, source)
  
  # CSV indexing and analytics views
  classes.csv                # Class index with bilingual metadata and expansion stats
  instances.csv              # Instance index with bilingual metadata and resolved class path
  properties.csv             # CSV view for property lookup
  aliases_en.csv             # alias -> qid lookup (English)
  aliases_de.csv             # alias -> qid lookup (German)
  
  # Top-level metadata
  summary.json               # Run metadata: run_id, stop_reason, counts, timestamps
  query_inventory.csv        # Query log: endpoint, query hash, key, timestamp, source (deduplicated)
  
  # Raw query cache (source of truth)
  raw_queries/
    {timestamp}__{query_type}__{key}.json  # Append-only event records
    
  # Bootstrap files copied from setup
  core_classes.csv           # Stable copy of data/00_setup/classes.csv
  broadcasting_programs.csv  # Seed reference (copied from 00_setup)
```

### Schema Details

**entities.json:**
```json
{
  "entities": {
    "Q1499182": {
      "id": "Q1499182",
      "type": "item",
      "discovered_at_utc": "2026-03-26T14:52:24Z",
      "expanded_at_utc": "2026-03-26T14:52:28Z",
      "labels": {"en": {"value": "Markus Lanz"}, "de": {"value": "Markus Lanz"}},
      "descriptions": {"en": {"value": "German talk show"}, "de": {"value": "Talkshow im ZDF"}},
      "aliases": {"en": [{"value": "Lanz"}], "de": [{"value": "Lanz"}]},
      "instance_of": ["Q11578774"],
      "subclass_of": [],
      "class_resolution": {
        "class_id": "Q11578774",
        "class_filename": "broadcasting_programs",
        "path_to_core_class": ["Q1499182"],
        "subclass_of_core_class": true
      },
      "claims": {
        "P31": [...],
        "P449": [...]
      }
    }
  }
}
```

**classes.csv:**
```csv
id,label_en,label_de,description_en,description_de,alias_en,alias_de,path_to_core_class,subclass_of_core_class,discovered_count,expanded_count
Q215627,person,Person,human being,Mensch,"human|individual","Mensch|Individuum",Q35120,true,512,487
```

**instances.csv:**
```csv
id,class_id,class_filename,label_en,label_de,description_en,description_de,alias_en,alias_de,path_to_core_class,discovered_at_utc,expanded_at_utc
Q1499182,Q11578774,broadcasting_programs,Markus Lanz,Markus Lanz,German talk show,Talkshow im ZDF,Lanz,Lanz,"[Q1499182]",2026-03-26T14:52:24Z,2026-03-26T14:52:28Z
```

**properties.json:**
```json
{
  "properties": {
    "P31": {
      "id": "P31",
      "type": "property",
      "discovered_at_utc": "2026-03-26T14:52:24Z",
      "labels": {"en": {"value": "instance of"}, "de": {"value": "ist ein(e)"}},
      "descriptions": {"en": {"value": "that class of which this subject is a particular example and member"}, "de": {"value": "diese Klasse, zu der das Subjekt als konkretes Beispiel gehoert"}},
      "aliases": {"en": [{"value": "class membership"}], "de": [{"value": "Instanz von"}]},
      "instance_of": [],
      "subproperty_of": []
    }
  }
}
```

**properties.csv:**
```csv
id,label_en,label_de,description_en,description_de,alias_en,alias_de
P31,instance of,ist ein(e),that class of which this subject is a particular example and member,diese Klasse, zu der das Subjekt als konkretes Beispiel gehoert,class membership,Instanz von
```

**triples.csv:**
```csv
subject,predicate,object,discovered_at_utc,source_query_file
Q1499182,P371,Q43773,2026-03-26T14:52:24Z,20260326T145224278856Z__entity__Q1499182.json
Q1499182,P449,Q48989,2026-03-26T14:52:24Z,20260326T145224278856Z__entity__Q1499182.json
```

**aliases_en.csv / aliases_de.csv:**
```csv
alias,qid
Psychologe,Q212980
Psychologin,Q212980
```

**summary.json:**
```json
{
  "run_id": "2026-03-26T14:52:24Z_seed_1",
  "start_timestamp": "2026-03-26T14:52:24Z",
  "latest_checkpoint_timestamp": "2026-03-26T14:53:00Z",
  "stop_reason": "seed_complete",
  "seeds_completed": 1,
  "seeds_remaining": 14,
  "total_discovered_entities": 42,
  "total_expanded_entities": 38,
  "total_discovered_properties": 15,
  "total_triples": 156,
  "total_network_queries": 6,
  "cache_hits": 2,
  "raw_query_files": 8
}
```

---

## 8. Implementation Roadmap (Option B)

### Phase 1: Refactor Raw Event Schema
- Add endpoint, query hash, normalized query descriptor to raw record envelope
- Archive existing raw_queries/ files (no loss, but backward-incompatible)
- Implement canonical event record format

### Phase 2: Implement Node Storage
- Build unified `entities.json` from raw entity records
- Add node-level `expanded_at_utc` flag (null until expanded)
- Implement path resolution (P31/P279 BFS to core classes)

### Phase 3: Implement Triple Materialization
- Extract subject-predicate-object from expanded entity payloads
- Deduplicate triples by (subject, predicate, object)
- Persist first-discovery timestamp and source query file
- Build properties index from discovered P-IDs

### Phase 4: Implement CSV Materialization
- Generate `classes.csv` with `discovered_count`, `expanded_count`, `subclass_of_core_class`
- Generate `instances.csv` with bilingual fields and class resolution columns
- Generate properties.csv from properties.json
- Generate `aliases_en.csv` and `aliases_de.csv` from entity and property aliases
- Generate triples.csv from triple event records (dedup by key)

#### Runtime Lookup and Materialization Strategy
- Use in-memory lookup indexes during runtime; do not wait for end-of-run CSV generation.
- Initialize runtime state at start:
  - load `entities.json` and `properties.json` into dictionaries keyed by ID (`qid`/`pid`)
  - load alias indexes into hash sets/maps (`alias_en -> {qid}`, `alias_de -> {qid}`)
  - load lightweight tabular views only when needed for analytics, not as the primary write path
- Update runtime indexes immediately when new entities/properties are discovered or expanded.
- Maintain dirty flags per artifact (`classes_dirty`, `instances_dirty`, `properties_dirty`, `aliases_dirty`, `triples_dirty`).
- Materialize CSVs incrementally at checkpoints (per-seed) instead of full end-only pass.
- Keep a final full consistency pass at run end to guarantee deterministic ordering and dedup.

#### Why Not Append Every Row Directly to DataFrames/CSVs?
- Row-wise append to CSV per event increases IO overhead and fragmentation.
- Frequent DataFrame append operations are inefficient and can increase memory churn.
- Per-event writes complicate crash consistency and dedup guarantees.
- Checkpoint-batch materialization gives most runtime lookup benefits while preserving deterministic outputs.

#### Recommended Hybrid Pattern
- Runtime lookup path: dictionaries and sets for O(1)-style checks.
- Snapshot path: DataFrame creation from runtime indexes at checkpoint boundaries.
- Persistence path: atomic overwrite of CSV snapshots and JSON stores at checkpoint.
- Recovery path: restore from last checkpoint, then replay remaining `raw_queries/` events.

### Phase 5: Implement Checkpoint Manifests
- Add run_id, stop_reason, seed progress to summary.json
- Implement resume logic (read latest checkpoint, continue from next seed)
- Add incomplete checkpoint markers

### Phase 6: Implement Deterministic Materialization at Checkpoints
- After each seed completes, materialize all CSVs
- After all seeds complete, final materialization with summary statistics

---

## 9. Decision Summary

| Aspect | Outcome |
|--------|---------|
| **Chosen Option** | Option B: Consolidated JSON + selective CSV |
| **Rationale** | First Intersection override: discovered/expanded is a field, not a partition axis |
| **Artifacts** | 10 core files + raw_queries/ (entities/properties JSON, triples, summary, query inventory, classes/instances/properties CSV, alias lookups) |
| **Key Change from Spec** | Consolidate per-class JSON partitions into unified `entities.json` |
| **Path Resolution** | Persist as metadata in `entities.json` and projected to `instances.csv`/`classes.csv` |
| **Triples.csv** | Essential for graph queries, required for spec compliance |
| **JSON Source of Truth** | Maintained (`entities.json`, `properties.json`) |
| **CSV as Derived Views** | Maintained (easy human lookup, statistics, dedup) |
| **Runtime Lookup Model** | In-memory ID and alias indexes; checkpoint-batch CSV snapshots |
| **Migration Path** | Refactor aggregates.py/classes.py for unified stores and multilingual projections |
| **Testing Priority** | Determinism (same input → same output), corruption recovery, dedup correctness |

---

## 10. Open Questions for Further Discussion

1. **Triples completeness:** Should triples include property-to-property relationships (subproperty_of edges), or only item-to-item?
   - **Recommendation:** Item-to-item only for now (simpler, covers known use cases)

2. **Path resolution scope:** Should path BFS respect core-class boundaries (stop at first core class), or continue to entity (Q35120)?
  - **Recommendation:** Stop at first core class; store that as `class_resolution.class_filename` in `entities.json` and project it into CSV views.

3. **Query hash algorithm:** Should query hash include parameters, or just query structure?
   - **Recommendation:** MD5(normalized_query_text + endpoint) for dedup key; store full query in raw record for audit

4. **Expanded flag semantics:** If a node is later expanded, should we update the row in-place or append a new versioned node event?
  - **Recommendation:** Update in-place in `entities.json` while keeping immutable raw event history in `raw_queries/`.

5. **Checkpoint frequency:** Materialize after each seed, or batch multiple seeds before materialization?
   - **Recommendation:** Materialize after each seed (provides progress milestones and enables resume granularity)

---

## Conclusion

**Option B (Consolidated JSON + Selective CSV)** is the accepted Step 1 decision. The First Intersection has been fully integrated: clarified class counters, new `subclass_of_core_class`, mandatory bilingual label/description/alias fields, and dedicated per-language alias lookup tables. Corruption handling is explicitly checkpoint-first with full raw-query regeneration fallback. Phase 1 is complete and internally consistent; ready for Step 2 implementation blueprinting.
