# Phase 31 Step 311 Implementation Runbook

**Purpose**: Complete operator guide for running automated entity disambiguation  
**Last Updated**: 2026-04-11  
**Version**: 1.0 (Final Design, MVP Implementation)

---

## 1. Quick Start

### Running the Notebook

```bash
# Navigate to repository root
cd c:\workspace\git\borgnetzwerk\speaker-mining

# Open notebook in VS Code
code speakermining/src/process/notebooks/31_entity_disambiguation.ipynb

# Run all cells
# Menu: Run → Run All Cells
# Or: Ctrl+Shift+Enter (VS Code)
```

### Expected Behavior

**Execution Flow**:
1. Bootstrap cell: Discovers repository root and sets up path
2. Recovery cell: Checks for interrupted checkpoints
3. Orchestration cell: Runs complete alignment workflow
4. Verification cell: Displays output summary
5. Inspection cells: Show DataFrames for each core class

**Expected Runtime**: 5-30 minutes (depends on data volume)

### Output Location

All outputs are written to:
```
data/31_entity_disambiguation/
├── projections/
│   ├── aligned_broadcasting_programs.csv
│   ├── aligned_episodes.csv
│   ├── aligned_persons.csv
│   ├── aligned_series.csv
│   ├── aligned_topics.csv
│   ├── aligned_roles.csv
│   └── aligned_organizations.csv
├── events/
│   ├── chunk_0000.jsonl
│   ├── chunk_0001.jsonl
│   └── ...
├── checkpoints/
│   ├── 20260411T120000Z-checkpoint/
│   │   ├── events/
│   │   ├── projections/
│   │   ├── checkpoint_metadata.json
│   │   └── ...
│   └── ...
└── handler_progress.db
```

### Success Criteria

✓ All 7 aligned_*.csv files exist  
✓ Each file has > 0 rows  
✓ All baseline columns present  
✓ No error messages in notebook  
✓ Notebook completes without exceptions  

---

## 2. Architecture Overview

### 4-Layer Alignment Model

```
Layer 1: Broadcasting Programs
┌────────────────────────────────┐
│ Identity validation from setup  │
│ Confidence: 1.0 (always aligned)│
└────────────────────┬────────────┘
                     │
Layer 2: Episodes
┌────────────────────▼────────────┐
│ Time/ID-based cross-source match│
│ Confidence: 0.95 (shared ID) or │
│            0.0 (unresolved)     │
└────────────────────┬────────────┘
                     │
Layer 3: Persons
┌────────────────────▼──────────────────┐
│ Name-based matching within episodes   │
│ Confidence: 0.95 (exact multi-source) │
│            0.90 (ZDF+Wikidata)        │
│            0.70 (substring match)     │
│            0.0 (unresolved)           │
└────────────────────┬──────────────────┘
                     │
Layer 4: Roles/Organizations
┌────────────────────▼────────────┐
│ Context enrichment (optional)    │
│ Confidence boost: +0.03 to +0.05 │
│ Never downgrades alignment       │
└────────────────────┬────────────┘
                     │
Output: aligned_*.csv files (all 7 core classes)
```

### Data Flow

```
Phase 10: Mention Detection (CSVs)        Phase 20: Candidate Generation
  ├── episodes.csv                          ├── Wikidata/
    ├── persons.csv                           │   ├── instances_core_episodes.json
    ├── publications.csv                      │   ├── instances_core_persons.json
    ├── seasons.csv                           │   ├── instances_core_series.json
    ├── topics.csv                            │   ├── instances_core_broadcasting_programs.json
    └── broadcasting_programs.csv             │   ├── instances_core_topics.json
                                                                                        │   ├── instances_core_roles.json
                                                                                        │   └── instances_core_organizations.json
                                            └── Fernsehserien/
                                                ├── episode_metadata_normalized.csv
                                                ├── episode_broadcasts_normalized.csv
                                                └── episode_guests_normalized.csv
                        │
                        ▼
            ┌─────────────────────────┐
            │   Data Loading Layer    │
            │ (normalization.py,      │
            │  data_loading.py)       │
            └────────────┬────────────┘
                         │
            ┌────────────▼────────────┐
            │  Deterministic Matching │
            │ (alignment.py)          │
            │ - Layer 1-4 aligners    │
            └────────────┬────────────┘
                         │
            ┌────────────▼────────────┐
            │   Event Emission        │
            │ (event_log.py)          │
            │ - Metadata persistence  │
            └────────────┬────────────┘
                         │
            ┌────────────▼────────────┐
            │  Projection Building    │
            │ (event_handlers.py)     │
            │ - CSV generation        │
            └────────────┬────────────┘
                         │
            ┌────────────▼────────────┐
            │   Checkpoint Save       │
            │ (checkpoints.py)        │
            │ - Recovery snapshot     │
            └─────────────────────────┘
                         │
                         ▼
            aligned_*.csv files (output)
```

### Precision-First Philosophy

The system enforces a **precision-first** matching strategy:

- **Prefer UNRESOLVED over INCORRECT**: Ambiguous cases are marked as "unresolved" rather than forcing a potentially wrong match
- **All Orphans Preserved**: Entities that don't match across sources are kept in output with status UNRESOLVED (never silently dropped)
- **Human Review Transparency**: Every alignment decision includes method + reason (human-readable)
- **Confidence Thresholds**: Clear confidence scoring guides which alignments are most reliable

This approach reduces false positives that could propagate errors through subsequent phases. Manual reconciliation in OpenRefine handles remaining ambiguities.

---

## 3. Data Input Requirements

### Required Files - Phase 10 (Mention Detection)

Must exist:
```
data/10_mention_detection/
├── episodes.csv                  ✓ Required
├── persons.csv                   ✓ Required
├── publications.csv              ✓ Required
├── seasons.csv                   ✓ Required
├── topics.csv                    ✓ Required
└── broadcasting_programs.csv    (from 00_setup)
```

**Schema Requirements**:

**episodes.csv**:
```
episode_id, publikationsdatum, dauer, season, staffel, folge, folgennr, sendungstitel, ...
```

**persons.csv**:
```
mention_id, episode_id, name, beschreibung, confidence, ...
```

**publications.csv**:
```
publikation_id, episode_id, date, time, duration, program, ...
```

### Required Files - Phase 20 (Candidate Generation)

Must exist:
```
data/20_candidate_generation/wikidata/projections/
├── instances_core_episodes.json                 ✓ Required
├── instances_core_persons.json                  ✓ Required
├── instances_core_series.json                   ✓ Required
├── instances_core_broadcasting_programs.json    ✓ Required
├── instances_core_topics.json                   ✓ Optional (produces aligned_topics.csv even if empty)
├── instances_core_roles.json                    ✓ Optional
└── instances_core_organizations.json            ✓ Optional
```

```
data/20_candidate_generation/fernsehserien_de/projections/
├── episode_metadata_normalized.csv       ✓ Required
├── episode_broadcasts_normalized.csv     ✓ Required
└── episode_guests_normalized.csv         ✓ Required
```

### Required Files - Phase 00 (Setup)

Must exist:
```
data/00_setup/
└── broadcasting_programs.csv             ✓ Required (single source of truth)
```

### Validation Checklist

Run this before executing notebook:

```python
from pathlib import Path

# Check all required files
required = [
    Path("data/10_mention_detection/episodes.csv"),
    Path("data/10_mention_detection/persons.csv"),
    Path("data/10_mention_detection/publications.csv"),
    Path("data/10_mention_detection/seasons.csv"),
    Path("data/20_candidate_generation/wikidata/projections/instances_core_episodes.json"),
    Path("data/20_candidate_generation/wikidata/projections/instances_core_persons.json"),
    Path("data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv"),
]

missing = [f for f in required if not f.exists()]
if missing:
    print(f"ERROR: Missing {len(missing)} required files:")
    for f in missing:
        print(f"  - {f}")
else:
    print("✓ All required input files present")
```

---

## 4. Output Validation

### Step 1: Verify Output Files Exist

```python
from pathlib import Path
from process.entity_disambiguation.config import CORE_CLASSES, get_aligned_csv_path

missing = []
for core_class in CORE_CLASSES:
    path = get_aligned_csv_path(core_class)
    if not path.exists():
        missing.append(f"{core_class}: {path}")

if missing:
    print("ERROR: Missing output files:")
    for msg in missing:
        print(f"  - {msg}")
else:
    print("✓ All 7 aligned_*.csv files present")
```

### Step 2: Check Row Counts

```python
import pandas as pd
from process.entity_disambiguation.config import CORE_CLASSES, get_aligned_csv_path

for core_class in CORE_CLASSES:
    path = get_aligned_csv_path(core_class)
    df = pd.read_csv(path)
    rows = len(df)
    cols = len(df.columns)
    print(f"{core_class}: {rows} rows × {cols} columns")
```

**Expected Ranges** (ballpark for typical show like Markus Lanz):

| Core Class | Min Rows | Typical Rows | Max Rows | Notes |
|------------|----------|-------------|----------|-------|
| broadcasting_programs | 1 | 5-20 | 50 | Usually small (main show + variants) |
| episodes | 100 | 1500-2500 | 5000 | All episodes across all seasons |
| persons | 500 | 2000-3000 | 10000 | Mentions (not deduped; one per episode) |
| series | 10 | 50-100 | 500 | Seasons, spin-offs |
| topics | 50 | 100-300 | 1000 | Topics/themes |
| roles | 5 | 20-100 | 500 | Occupation roles |
| organizations | 5 | 20-100 | 500 | Institutions/orgs |

### Step 3: Check Baseline Columns

All 7 files must have these columns (in order):

```python
baseline_columns = [
    "alignment_unit_id",
    "core_class",
    "broadcasting_program_key",
    "episode_key",
    "source_zdf_value",
    "source_wikidata_value",
    "source_fernsehserien_value",
    "deterministic_alignment_status",
    "deterministic_alignment_score",
    "deterministic_alignment_method",
    "deterministic_alignment_reason",
    "requires_human_review",
]

for core_class in CORE_CLASSES:
    path = get_aligned_csv_path(core_class)
    df = pd.read_csv(path)
    missing = [col for col in baseline_columns if col not in df.columns]
    if missing:
        print(f"ERROR {core_class}: Missing columns: {missing}")
    else:
        print(f"✓ {core_class}: All baseline columns present")
```

### Step 4: Spot-Check Alignment Quality

Sample 5 rows from persons and verify manually:

```python
import pandas as pd
from process.entity_disambiguation.config import get_aligned_csv_path

df = pd.read_csv(get_aligned_csv_path("persons"))

# Show earliest aligned persons
aligned = df[df["deterministic_alignment_status"] == "aligned"].head(5)
print(aligned[["source_zdf_value", "source_wikidata_value", 
               "deterministic_alignment_score", "deterministic_alignment_method"]])
```

**Expected**:
- Scores mostly 0.90-0.95 for ALIGNED
- Methods are descriptive ("name_exact_multi_source", "name_substring_match")
- Reasons explain which sources matched

### Step 5: Check No Duplicates

```python
for core_class in CORE_CLASSES:
    path = get_aligned_csv_path(core_class)
    df = pd.read_csv(path)
    
    has_dupes = df.duplicated(subset=["alignment_unit_id"], keep=False).any()
    if has_dupes:
        print(f"ERROR {core_class}: Duplicate alignment_unit_ids found")
    else:
        print(f"✓ {core_class}: No duplicates")
```

---

## 5. Checkpoint & Recovery

### How Checkpointing Works

When execution completes successfully, Step311Orchestrator saves a checkpoint automatically:

**Checkpoint Contents**:
1. Event log chunks (all JSONL files with alignment events)
2. Projection CSVs (aligned_*.csv snapshots)
3. Handler progress DB (tracking replay state)
4. Metadata file (timestamp, checksums, manifest)

**Two Forms**: 
- Unzipped: `data/31_entity_disambiguation/checkpoints/20260411T083000Z-checkpoint/`
- Zipped: `data/31_entity_disambiguation/checkpoints/20260411T083000Z-checkpoint.zip`

### Recovering from Interruption

If the notebook is interrupted mid-execution:

**Option 1: Automatic Resume (Default)**
```python
# In notebook cell "Check for Recovery Checkpoint"
# RESET_STATE = False  (default)
# FORCE_FRESH_RUN = False  (default)

# When you re-run notebook:
# 1. Checkpoint detected
# 2. Events replayed
# 3. Projections rebuilt
# 4. Output identical to non-interrupted run
```

**Option 2: Start Fresh**
```python
# In notebook cell "Check for Recovery Checkpoint"
RESET_STATE = True    # Wipes all local Step 311 state

# Re-run notebook - starts from scratch (full import pass)
```

### Retention Policy

Automatically enforced when checkpoints are saved:

- **Keep**: 3 most recent unzipped checkpoints (for inspection)
- **Keep**: 7 most recent zipped backups (for remote storage)
- **Delete**: Older checkpoints (automatic cleanup)

To manually clean up:

```bash
# Remove all checkpoints  
rm -r data/31_entity_disambiguation/checkpoints/*
rm data/31_entity_disambiguation/checkpoints.db

# Remove all events
rm -r data/31_entity_disambiguation/events/*

# Next run: complete fresh import
```

### Validating Checkpoint Integrity

Before resuming from checkpoint:

```python
from process.entity_disambiguation.checkpoints import CheckpointManager

mgr = CheckpointManager()
latest = mgr.find_latest_checkpoint()

if latest:
    valid = mgr.validate_checkpoint(latest)
    if valid:
        print(f"✓ Checkpoint valid: {latest}")
    else:
        print(f"ERROR: Checkpoint corrupted: {latest}")
        print("  Run with RESET_STATE=True to start fresh")
else:
    print("No checkpoint found; will start fresh")
```

---

## 6. Configuration

### Key Config Constants

**File**: `speakermining/src/process/entity_disambiguation/config.py`

```python
# Input paths (Phase 10, Phase 20, Phase 00)
BROADCASTING_PROGRAMS_CSV   # data/00_setup/broadcasting_programs.csv
EPISODES_CSV                # data/10_mention_detection/episodes.csv
PERSONS_CSV                 # data/10_mention_detection/persons.csv
# ... etc

# Wikidata JSON paths (now JSON-first)
WD_EPISODES                 # data/20_candidate_generation/wikidata/projections/instances_core_episodes.json
WD_PERSONS
WD_SERIES
WD_BROADCASTING_PROGRAMS
WD_TOPICS
WD_ROLES
WD_ORGANIZATIONS

# Fernsehserien CSV paths
FS_EPISODE_METADATA        # fernsehserien_de/projections/episode_metadata_normalized.csv
FS_EPISODE_BROADCASTS
FS_EPISODE_GUESTS

# Output paths
PHASE_DIR                  # data/31_entity_disambiguation/
EVENTS_DIR                 # data/31_entity_disambiguation/events/
CHECKPOINTS_DIR            # data/31_entity_disambiguation/checkpoints/
HANDLER_PROGRESS_DB        # data/31_entity_disambiguation/handler_progress.db

# Core classes (7-tuple)
CORE_CLASSES = (
    "broadcasting_programs", "episodes", "persons",
    "series", "topics", "roles", "organizations"
)
```

### Overriding Paths

To use custom paths, modify config before running orchestrator:

```python
from pathlib import Path
from process.entity_disambiguation import config

# Override config paths
config.EPISODES_CSV = Path("/custom/path/episodes.csv")

# Then run orchestrator
orchestrator = Step311Orchestrator()
projections = orchestrator.run()
```

### Adjusting Aligner Sensitivity

**Currently**: All alignment logic is deterministic (no tuning needed for MVP)

**Future**: If time-based episode matching is implemented, thresholds here:

```python
class EpisodeAligner:
    TIME_TOLERANCE_SECONDS = 30  # Episodes within 30s = same broadcast
```

---

## 7. Troubleshooting

### Error: "Critical upstream data missing"

**Cause**: Required Phase 10 or Phase 20 files not found

**Solution**:
```bash
# Verify all required files exist (see section 3)
python -c "
from pathlib import Path
required = [
    Path('data/10_mention_detection/episodes.csv'),
    Path('data/20_candidate_generation/wikidata/projections/instances_core_episodes.json'),
    # ... add all required paths
]
missing = [f for f in required if not f.exists()]
print(f'Missing: {missing}')
"
```

### Error: "Checkpoint corrupted" or "recovery failed"

**Cause**: Event log chunks have incorrect checksums or are incomplete

**Solution**:
```python
# Option 1: Start fresh (loses recovered state)
RESET_STATE = True  # In notebook recovery cell

# Option 2: Manually validate and fix
from process.entity_disambiguation.checkpoints import CheckpointManager
mgr = CheckpointManager()
checkpoint = mgr.find_latest_checkpoint()
if checkpoint:
    valid = mgr.validate_checkpoint(checkpoint)
    if not valid:
        print(f"Checkpoint {checkpoint} is corrupted")
        # Back it up, then reset
        import shutil
        shutil.move(str(checkpoint), f"{checkpoint}.backup")
```

### Notebook executes but no output files created

**Cause**: Orchestrator ran but failed silently, or output paths incorrect

**Solution**:
```python
# Verify orchestrator returns non-empty projections
from process.entity_disambiguation import Step311Orchestrator

orchestrator = Step311Orchestrator()
projections = orchestrator.run()

for core_class, df in projections.items():
    rows = 0 if df is None else len(df)
    print(f"{core_class}: {rows} rows")
    
# If all are 0, check that input data is being loaded
upstream = orchestrator._load_upstream_data()
print(upstream.keys())  # Should show all loaded frames
```

### Execution is very slow (> 30 min)

**Cause**: Possible large data volume or first-time JSON parsing is taking time

**Solutions**:
1. Check data volume (Episodes > 5000, Persons > 10000 may take longer)
2. Monitor disk space (checkpoint snapshots can be large)
3. Try running subset first (create test dataset with 1 show only)

### Output CSVs have unexpected row counts

**Cause**: Normal - depends on input data quality and source coverage

**Expected Behavior**:
- Some episodes may UNRESOLVED (not enough cross-source signals)
- Some persons may UNRESOLVED (guest not in Wikidata/Fernsehserien)
- This is correct (precision-first philosophy)

**To Investigate**:
```python
import pandas as pd
df = pd.read_csv("data/31_entity_disambiguation/projections/aligned_episodes.csv")
status_counts = df["deterministic_alignment_status"].value_counts()
print(status_counts)
# Should show: aligned=N, unresolved=M, conflict=0
```

### "JSON decode error" or "Wikidata projection invalid"

**Cause**: Phase 20 JSON files may be corrupted or incomplete

**Solution**:
```bash
# Verify JSON files are valid
python -c "
import json
from pathlib import Path

for json_file in Path('data/20_candidate_generation/wikidata/projections').glob('*.json'):
    try:
        with open(json_file) as f:
            json.load(f)
        print(f'✓ {json_file.name} valid')
    except json.JSONDecodeError as e:
        print(f'ERROR {json_file.name}: {e}')
"
```

### Alignment quality seems too low (many UNRESOLVED)

**Expected**: Some amount of UNRESOLVED is normal
- Early episodes may have poor source coverage
- Minor guests may not be in Wikidata
- This is by design (precision-first)

**To Verify**:
```python
import pandas as pd
df = pd.read_csv("data/31_entity_disambiguation/projections/aligned_persons.csv")

# High quality threshold
high_conf = df[df["deterministic_alignment_score"] >= 0.90]
print(f"High confidence alignments: {len(high_conf)} / {len(df)} ({100*len(high_conf)/len(df):.1f}%)")

# Show low-confidence aligned rows
mid_conf = df[(df["deterministic_alignment_score"] >= 0.70) & 
              (df["deterministic_alignment_score"] < 0.90)]
print(f"Mid confidence (substring): {len(mid_conf)}")

# Show unresolved
unresolved = df[df["deterministic_alignment_status"] == "unresolved"]
print(f"Unresolved: {len(unresolved)}")
```

---

## Additional Resources

- **Specification**: `documentation/31_entity_disambiguation/99_REDESIGN_TARGET_SPECIFICATION.md`
- **Progress Report**: `documentation/31_entity_disambiguation/PHASE31_REDESIGN_PROGRESS.md`
- **Code**: `speakermining/src/process/entity_disambiguation/`

---

## Questions?

For implementation issues, consult:
1. This runbook (section 7: Troubleshooting)
2. Specification (section 8: Contracts & Non-Negotiables)
3. Code docstrings (each module has comprehensive documentation)

For architectural decisions:
- See Specification section 9: Design Rationale
- See Specification Appendix B: Answers to Open Questions
