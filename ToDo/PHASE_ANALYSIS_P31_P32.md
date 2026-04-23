# Phase Analysis: Phase 31 & 32 — Disambiguation & Deduplication

> Part of the phase-by-phase analysis pass.  
> See [PHASE_ANALYSIS_INDEX.md](PHASE_ANALYSIS_INDEX.md) for the full index.

---

## Phase 31: Entity Disambiguation

### Purpose
Aligns entities from three heterogeneous sources — ZDF archive, Wikidata, and fernsehserien.de — into a canonical cross-source table for each entity class (broadcasting programs, seasons, episodes, persons, topics, roles, organizations).

Two-step model:
- **Step 311:** Fully automated deterministic bootstrap (single `Run All`)
- **Step 312:** Human reconciliation via OpenRefine or similar, over handoff tables produced by 311

### Status
**Step 311 is implemented and running.** The notebook executes successfully and produces 7 aligned tables. However, the majority of entities remain `unresolved` (notably seasons: 410/412; this is expected for many classes as they span all Wikidata series, not just Markus Lanz).

Step 312 (manual reconciliation) has a specification but no tooling is yet built.

---

### Files

#### [31_entity_disambiguation.ipynb](../speakermining/src/process/notebooks/31_entity_disambiguation.ipynb)
Entry-point notebook. 5 phases:

| Phase | Description |
|-------|-------------|
| 1 | Project setup; repo root discovery; `CLASS_SOURCE_PLANS` definition |
| 2 | Value normalization (`normalize_inputs()`) |
| 3 | Schema harmonization (`write_schema_mapping()`) |
| 4 | Layered alignment and persistence (7 entity classes) |
| 5 | Quality gates and run summary |

**CLASS_SOURCE_PLANS:** Defines which sources contribute to each class:
```python
"persons": [
    ("zdf_archive", "zdf_persons"),        # 10,381 rows
    ("wikidata", "wikidata_persons"),       # 640 rows
    ("fernsehserien_de", "fs_episode_guests"),  # 25,452 rows
]
```

**Run Statistics (from notebook output):**
| Source | Instances | Properties |
|--------|-----------|------------|
| zdf_persons | 10,381 | 9 |
| wikidata_persons | 640 | 767 |
| fs_episode_guests | 25,452 | 13 |
| wikidata_series | 397 | 383 |
| wikidata_episodes | 997 | 60 |
| wikidata_roles | **0** | **0** |
| wikidata_organizations | 51 | 881 |

**Normalized shape after normalization:**
```
zdf_persons:  (10381, 18)
wikidata_persons: (640, 2465)
fs_episode_guests: (25452, 26)
wikidata_roles: (0, 0)    ← empty, no role alignment possible
wikidata_organizations: (51, 6489)
```

#### entity_disambiguation/ Module (13+ Python files)

**[contracts.py](../speakermining/src/process/entity_disambiguation/contracts.py)**
Defines all input/output paths and tier constants:
- `INPUT_FILES` — 21 source file paths (ZDF, Wikidata, fernsehserien.de)
- `OUTPUT_FILES` — 8 output files in `data/31_entity_disambiguation/aligned/`
- `SHARED_COLUMNS` — 15 alignment columns including `match_tier`, `match_confidence`, `evidence_summary`
- `EXACT_TIER`, `HIGH_TIER`, `MEDIUM_TIER`, `UNRESOLVED_TIER` — confidence tiers
- `UNRESOLVED_REASON_CODES` — `{no_candidate, low_confidence, contradiction, insufficient_context}`

**[orchestrator.py](../speakermining/src/process/entity_disambiguation/orchestrator.py)**
- `build_source_inventory_report()` — inventory table with row counts + property lists
- `_build_aligned_broadcasting_programs(normalized)` — broadcasting program alignment
- `_build_aligned_seasons(normalized)` — season alignment

**[person_alignment.py](../speakermining/src/process/entity_disambiguation/person_alignment.py)**
- `build_aligned_persons(normalized, aligned_episodes)` — main person cross-source alignment
- `_indexed_wikidata_persons()` — builds QID lookup by normalized label
- `_build_fs_guest_index(fs_guests)` — episode-URL-keyed guest index
- Matching strategy: label normalization → `normalize_text()` cross-match between ZDF names and Wikidata labels

**[episode_alignment.py](../speakermining/src/process/entity_disambiguation/episode_alignment.py)**
- `build_aligned_episodes()` — aligns ZDF episodes to Wikidata episodes and fernsehserien.de metadata

**[topic_alignment.py](../speakermining/src/process/entity_disambiguation/topic_alignment.py)**
- `build_aligned_topics()` — topic cross-source alignment

**[role_org_alignment.py](../speakermining/src/process/entity_disambiguation/role_org_alignment.py)**
- `build_aligned_organizations()`, `build_aligned_roles()` — org and role alignment

**[normalization.py](../speakermining/src/process/entity_disambiguation/normalization.py)**
- `normalize_inputs()` — returns normalized DataFrames for all 21 sources; adds `_norm` suffix columns

**[io_staging.py](../speakermining/src/process/entity_disambiguation/io_staging.py)**
- `stage_inputs()` — copies all source files into `data/31_entity_disambiguation/raw_import/` with staged filenames; returns manifest

**[schema_mapping.py](../speakermining/src/process/entity_disambiguation/schema_mapping.py)**
- `write_schema_mapping(normalized)` — produces 11,629-row source→canonical column mapping table

**[evidence.py](../speakermining/src/process/entity_disambiguation/evidence.py)**
- `combine_evidence_rows(...)` — aggregates evidence from all 7 alignment functions

**[quality_gates.py](../speakermining/src/process/entity_disambiguation/quality_gates.py)**
- `run_quality_gates()` — validates written artifacts

**[utils.py](../speakermining/src/process/entity_disambiguation/utils.py)**
- `normalize_text()`, `label_from_wikidata_item()`, `description_from_wikidata_item()`, `aliases_from_wikidata_item()`, `stable_id()`, `read_json_dict()`, `prefixed_row_values()`

### Output Contract (data/31_entity_disambiguation/aligned/)

| File | Description |
|------|-------------|
| `aligned_broadcasting_programs.csv` | Cross-source broadcasting program alignment |
| `aligned_seasons.csv` | 412 rows; 410 unresolved (Wikidata series not matched to ZDF) |
| `aligned_episodes.csv` | ZDF × Wikidata × fernsehserien.de episodes |
| `aligned_persons.csv` | ZDF × Wikidata × fernsehserien.de persons |
| `aligned_topics.csv` | ZDF × Wikidata topics |
| `aligned_roles.csv` | Roles (empty — `wikidata_roles` is 0 rows) |
| `aligned_organizations.csv` | Wikidata organizations |
| `match_evidence.csv` | Evidence summary for all aligned rows |
| `run_summary.json` | Per-class counts, unresolved counts, quality gate results |
| `raw_import/` | Staged copies of all 21 source files |
| `normalized/` | Normalized DataFrames with `_norm` columns |
| `aligned/examples/` | One-row example files for each output |

### Current Alignment State
The notebook ran and produced output. Key observations:
- **Seasons (412 rows): 410 unresolved** — Most Wikidata series rows have no ZDF season counterpart; this is expected (Wikidata series are for all programs, not just Markus Lanz seasons).
- **Roles: 0 aligned rows** — Because `wikidata_roles` JSON file is empty. Roles are not discoverable until the Wikidata expansion configuration includes the roles core class properly.
- **Persons: 10,381 ZDF mentions vs 640 Wikidata persons** — Many ZDF person mentions will not match Wikidata entries; this is expected and is the key output for Step 312 reconciliation.

### OpenRefine Integration (Step 312)
**Disambiguation question from ToDo:** How is the OpenRefine match stored?

**Proposed answer (from `speaker_mining_code.md`):**
> "Idee: in einer neuen Spalte speichern — dafür einfach die existierende duplizieren und umbenennen in `open_refine_name` o.ä."

**Recommended implementation:**
1. The Step 311 output `aligned_persons.csv` is the OpenRefine input
2. Add an `open_refine_name` column — a copy of `canonical_label` that the human can overwrite
3. Add an `open_refine_wikidata_id` column — a copy of `wikidata_id` that the human can overwrite with a correct QID
4. After OpenRefine reconciliation, re-import the modified CSV as the Step 312 output
5. Document this contract in `contracts.md`

### Design Documentation (in documentation/)

Extensive design documentation exists in the archive:
- `documentation/31_entitiy_disambiguation/archive/2026-04-11_redesign/` — Full redesign specs (12+ files)
- `documentation/31_entitiy_disambiguation/archive/2026-04-12_restart/` — Restart approach

Key archived documents:
- `311_automated_disambiguation_specification.md` — Step 311 spec
- `311_implementation_guide.md` — How-to walkthrough
- `312_manual_reconciliation_specification.md` — Step 312 design
- `99_REDESIGN_TARGET_SPECIFICATION.md` — Target architecture
- `PHASE31_REDESIGN_PROGRESS.md` — Progress tracker

### Open Tasks for Phase 31

| ID | Priority | Description |
|----|----------|-------------|
| (question) | HIGH | OpenRefine match storage — add `open_refine_name` + `open_refine_wikidata_id` columns to Step 311 handoff |
| (bug/empty) | MEDIUM | Wikidata roles is 0 rows — affects role alignment; investigate expansion config |
| (design) | MEDIUM | Step 312 tooling — define import/export workflow for OpenRefine |
| TODO-004 | MEDIUM | Missing `mention_category` in Phase 1 propagates into ambiguous person alignment |
| F-012 | LOW | Season misclassification — document upstream handover requirements |

---

## Phase 32: Entity Deduplication

### Purpose
Detect and merge duplicate entities after cross-source alignment. Two-step model:
- **Step 321:** Automated deduplication recommendation
- **Step 322:** Human validation and merge decisions

### Status
**✓ IMPLEMENTED 2026-04-23** — Step 321 automated deduplication is complete.

### Files

#### [32_entity_deduplication.ipynb](../speakermining/src/process/notebooks/32_entity_deduplication.ipynb)
10-cell notebook: setup, `run_phase32()` call, summary display, cluster distribution, top clusters, Wikidata clusters.

#### Module: `speakermining/src/process/entity_deduplication/`
- `contracts.py` — paths and column schemas
- `person_deduplication.py` — `build_person_clusters()`: 3-strategy clustering
- `orchestrator.py` — `run_phase32()`: entry point, atomic writes

### Actual Output (2026-04-23)

**31,811 alignment units → 8,976 canonical entities (71.8% reduction)**

```
data/32_entity_deduplication/
    dedup_persons.csv           # 8,976 rows — one per canonical entity
    dedup_cluster_members.csv   # 31,811 rows — alignment_unit_id → canonical_entity_id
    dedup_summary.json          # run statistics
```

Cluster breakdown:
- `wikidata_qid_match` (high confidence): 640 clusters — avg 8.6 alignment units each
- `normalized_name_match` (medium confidence): 2,968 clusters
- `singleton` (low confidence): 5,368 clusters

### Open Tasks for Phase 32

| ID | Priority | Description |
|----|----------|-------------|
| ~~(implement)~~ | ~~HIGH~~ | ~~Create Step 321 implementation~~ — **DONE 2026-04-23** |
| ~~(design)~~ | ~~MEDIUM~~ | ~~Define output schema~~ — **DONE 2026-04-23** (`contracts.md`) |
| ~~(design)~~ | ~~MEDIUM~~ | ~~Link misspelling clusters~~ — **DONE** (`normalize_name_for_matching` symmetric) |
| (design) | LOW | Step 322 manual review workflow — not yet needed |

---

## Key Interdependencies (Phase 31/32)

- Phase 31 reads all Phase 1 and Phase 2 outputs
- Phase 31 `aligned_persons.csv` → Phase 32 deduplication input ✓ (flowing)
- Phase 32 `dedup_persons.csv` → Phase 4 / analysis input ✓ (flowing; `41_analysis.ipynb` uses this)
- Fixing TODO-004 (mention categories) will make person alignment more precise
- Empty `wikidata_roles` means roles will not be properly aligned until the Wikidata expansion is corrected
