# Phase 31 Step 311 - Target Design Specification for Complete Redesign

**Date**: 2026-04-10  
**Status**: Design v1.0 (pre-implementation)  
**Purpose**: Comprehensive specification for rebuilding Step 311 from current non-functional skeleton

---

## 1. Executive Summary

Phase 31 Step 311 (Automated Entity Disambiguation) is currently in a non-functional skeleton state with incomplete aligners, missing data loading logic, and unfinished event-sourcing infrastructure.

This specification provides a complete redesign blueprint following the 4-layer matching model and the artifact contract, grounded in empirical analysis of actual data structures from all three sources (ZDF Archive, Wikidata, Fernsehserien.de).

**Key Design Principles**:
1. **Layer-based constraints**: Higher layers (broadcasting, episodes) must align before lower layers (persons, roles) are considered
2. **Precision-first alignment**: Unresolved is preferred over incorrect matches
3. **Event-sourced reproducibility**: Every decision logged as immutable events, supporting recovery and replay
4. **Deterministic matching only**: No probabilistic scoring used to make final decisions (though scores inform review flags)
5. **Human-review transparency**: All machine decisions must include a clear method and reason
6. **Baseline column contract**: All aligned_*.csv files maintain identical baseline columns for uniform handoff to OpenRefine

---

## 2. Current Skeletal State Assessment

### 2.1 What Exists But Is Non-Functional

| Module | Status | Issue |
|--------|--------|-------|
| `alignment.py` | Partial stub | `PersonAligner` logic incomplete; `EpisodeAligner` missing time-based matching; `BroadcastingProgramAligner` missing entirely |
| `orchestrator.py` | Partial stub | `run()` method skeleton incomplete; all `_run_*` methods are stubs or missing |
| `event_log.py` | Unknown | Likely incomplete; unclear if event emission actually works |
| `event_handlers.py` | Unknown | Likely incomplete; projection building unclear |
| `checkpoints.py` | Unknown | Likely incomplete |
| Notebook `31_entity_disambiguation.ipynb` | Functional shell | Contains orchestrator calls but no real data processing; recovery logic placeholder |
| `config.py` | Partial | Defines paths but many input paths use outdated file patterns (e.g., `instances_core_*.csv` which may not exist) |

### 2.2 Root Causes of Non-Functionality

1. **Data loading layer is missing**: No code to read and normalize ZDF CSV, Wikidata JSON, Fernsehserien CSV into usable in-memory structures
2. **Matching logic is incomplete**: Time-based episode matching never implemented; person name matching too simplistic
3. **Event schema unclear**: No clear definition of what events should be emitted and how replay rebuilds projections
4. **No intermediate data flow**: Aligner → Event → Handler pipeline undefined
5. **Projection building is stub**: No code to actually construct the aligned_*.csv files with proper columns and ordering

---

## 3. Complete Redesign: Data Loading Layer

### 3.1 Data Loading Strategy

**Principle**: Normalize all source data into uniform in-memory indices before matching begins.

#### 3.1.1 ZDF Archive Load (Phase 10 Mention Detection)

**Source Files**:
```
data/10_mention_detection/
├── broadcasting_programs.csv        (via 00_setup, single authoritative copy)
├── episodes.csv                     (zdf_episode_id, publikationsdatum, dauer, season, staffel, folge, folgennr)
├── persons.csv                      (mention_id, episode_id, name, beschreibung, confidence)
├── publications.csv                 (publikation_id, episode_id, date, time, duration, program)
├── seasons.csv                      (season_id, season_label, start_time, end_time, episode_count)
└── topics.csv                       (topic_id, episode_id, topic_name, ...)
```

**Normalized In-Memory Indices**:

```python
# Index 1: Episodes indexed by ZDF episode_id
zdf_episodes: dict[str, dict] = {
    "episode_id": str,           # Primary key
    "publikationsdatum": date,   # For time-based matching
    "dauer": int,                # Duration in seconds
    "season_id": str,            # Link to seasons index
    "season_label": str,         # e.g., "Markus Lanz, Staffel 1"
    "folge": int,                # Episode number within season
    "folgennr": int,             # Global episode number
    "description": str,          # Parsed from `infos` field
}

# Index 2: Persons indexed by mention_id
zdf_persons: dict[str, dict] = {
    "mention_id": str,           # Primary key
    "episode_id": str,           # FK to zdf_episodes
    "name": str,                 # Extracted person name
    "description": str,          # Role/occupation if extracted
    "confidence": float,         # Parsing confidence (0-1)
    "parsing_rule": str,         # How name was extracted
}

# Index 3: Publications indexed by publikation_id
zdf_publications: dict[str, dict] = {
    "publikation_id": str,       # Primary key
    "episode_id": str,           # FK to zdf_episodes
    "publication_date": date,    # Broadcast date
    "publication_time": time,    # Broadcast start time
    "duration": int,             # In seconds
    "broadcaster": str,          # "ZDF", "ZDFdokukanal", etc
    "is_primary": bool,          # First broadcast vs repeat
}

# Index 4: Seasons indexed by season_id
zdf_seasons: dict[str, dict] = {
    "season_id": str,            # Primary key
    "season_label": str,         # Exactly as stored (e.g., "Markus Lanz, Staffel 1")
    "start_date": date,          # From start_time
    "end_date": date,            # From end_time
    "episode_count": int,
}
```

**Loading Code Belongs In**: `process.entity_disambiguation.data_loading.ZDFLoader`

#### 3.1.2 Wikidata Projection Load (Phase 20 Candidate Generation)

**Source Files**:
```
data/20_candidate_generation/wikidata/projections/
├── broadcasting_programs.json    (instances with type=broadcasting_program)
├── series.json                   (instances with type=series)
├── episodes.json                 (instances with type=episode)
├── persons.json                  (instances with type=person)
├── topics.json                   (instances with type=topic)
├── roles.json                    (instances with type=role)
├── organizations.json            (instances with type=organization)
└── triples.csv                   (optional: fallback for claims lookup)
```

**Data Structure** (Wikidata JSON format):
```json
{
  "Q130559283": {
    "type": "item",
    "id": "Q130559283",
    "labels": { "de": { "value": "Markus Lanz, Staffel 17" }, "en": { "value": "Markus Lanz, season 17" } },
    "descriptions": { "de": { "value": "Staffel der deutschen Fernsehtalkshow..." } },
    "aliases": { "de": [{ "value": "Markus Lanz 17" }] },
    "claims": {
      "P31": [...],     // instance of
      "P179": [...],    // part of the series
      "P580": [...],    // start time
      "P364": [...],    // original language
      "P449": [...]     // original broadcaster
    }
  }
}
```

**Normalized In-Memory Indices**:

```python
# Index 1: Episodes indexed by Wikidata Q-ID
wd_series: dict[str, dict] = {
    "qid": str,                  # Primary key (e.g., "Q130559283")
    "label_de": str,             # German label
    "label_en": str,             # English label
    "description_de": str,
    "aliases": list[str],        # All aliases from all languages
    "part_of_series": str,       # P179 target QID if present
    "season_number": int,        # P1545 qualifier if present
    "start_date": date,          # P580 if present
    "end_date": date,            # P582 if present
    "broadcaster_qid": str,      # P449 target if present
}

# Index 2: Episodes indexed by Wikidata Q-ID
wd_episodes: dict[str, dict] = {
    "qid": str,                  # Primary key
    "label_de": str,             # German label
    "label_en": str,             # English label
    "description_de": str,
    "part_of_series_qid": str,   # P179 target
    "part_of_season_qid": str,   # P278 or similar if available
    "broadcast_date": date,      # P580 or inferred from label
    "broadcast_time": time,      # Extracted from label if available
    "season_number": int,        # From P1545 or label
    "episode_number": int,       # From P1545 or label
}

# Index 3: Persons indexed by Wikidata Q-ID
wd_persons: dict[str, dict] = {
    "qid": str,                  # Primary key
    "label": str,                # Primary label (typically English or German)
    "aliases": list[str],        # All known aliases
    "description": str,          # Short description
    "occupations": list[str],    # P106 targets (occupation QIDs)
    "positions_held": list[str], # P39 targets (position QIDs)
    "native_language": str,      # P103 value if present
}
```

**Loading Code Belongs In**: `process.entity_disambiguation.data_loading.WikidataLoader`

#### 3.1.3 Fernsehserien.de Projection Load (Phase 20 Candidate Generation)

**Source Files**:
```
data/20_candidate_generation/fernsehserien_de/projections/
├── episode_metadata_normalized.csv     (fernsehserien_de_id, episode_title, premiere_date)
├── episode_broadcasts_normalized.csv   (fernsehserien_de_id, broadcast_date, broadcast_start_time, broadcaster)
├── episode_guests_normalized.csv       (fernsehserien_de_id, guest_name, guest_role, guest_description, guest_url)
└── (possibly more depending on normalized output structure)
```

**Data Structure** (CSV format):
- **episode_metadata**: `fernsehserien_de_id`, `program_name`, `episode_url`, `episode_title`, `premiere_date`, `premiere_broadcaster`
- **episode_broadcasts**: `fernsehserien_de_id`, `broadcast_date`, `broadcast_start_time`, `broadcast_end_time`, `broadcast_timezone_offset`, `broadcast_broadcaster`, `broadcast_is_premiere`
- **episode_guests**: `fernsehserien_de_id`, `guest_name`, `guest_role`, `guest_description`, `guest_url`

**Normalized In-Memory Indices**:

```python
# Index 1: Episodes indexed by fernsehserien_de_id
fs_episodes: dict[str, dict] = {
    "fs_id": str,                     # Primary key (e.g., "markus-lanz")
    "episode_url": str,               # Full episode URL
    "episode_title": str,             # Episode title from metadata
    "premiere_date": date,            # First broadcast date
    "premiere_broadcaster": str,      # Usually "ZDF"
    "broadcasts": list[dict],         # All broadcast records
}

# Index 2: Episode broadcasts indexed by (fs_id, broadcast_date, broadcast_time) tuple
fs_episode_broadcasts: dict[tuple, dict] = {
    "fs_id": str,
    "broadcast_date": date,
    "broadcast_start_time": time,
    "broadcast_end_time": time,
    "broadcast_timezone_offset": str,
    "broadcast_broadcaster": str,
    "is_premiere": bool,
}

# Index 3: Persons indexed by guest_url (when available) or guest_name
fs_persons: dict[str, dict] = {
    "fs_url": str,                    # Primary key or guest_url
    "name": str,                      # guest_name
    "role": str,                      # guest_role (e.g., "Gast", "Moderator")
    "description": str,               # guest_description
    "episodes_appeared_in": list[str], # List of fs_ids where this person appeared
}
```

**Loading Code Belongs In**: `process.entity_disambiguation.data_loading.FernsehserienLoader`

### 3.2 Normalization Functions (Critical for Matching)

**In `process.entity_disambiguation.normalization` module**:

```python
def normalize_name(name: str) -> str:
    """
    Normalize person/role name for matching.
    - Remove titles, particles, case-insensitive
    - Handle German umlauts and special chars
    - Remove parenthetical qualifiers
    
    Examples:
    "Verona POOTH" -> "verona pooth"
    "Dr. Georg PIEPER" -> "georg pieper"
    "Ralph Morgenstern-Nolting" -> "ralph morgenstern nolting"
    """

def normalize_date(date_value: str | date) -> date:
    """Parse date from multiple formats (ZDF: "03.06.2008", Wikidata: ISO, Fernsehserien: ISO)."""

def normalize_time(time_value: str | time) -> time:
    """Parse time from multiple formats."""

def normalize_season_label(label: str) -> tuple[str, int | None]:
    """
    Extract show name and season number from label.
    
    Examples:
    "Markus Lanz, Staffel 1" -> ("Markus Lanz", 1)
    "Markus Lanz (2024/2025)" -> ("Markus Lanz", None)  # Ambiguous, handle separately
    """

def extract_episode_number_from_label(label: str) -> int | None:
    """Extract episode/part number from Wikidata/Fernsehserien labels."""

def similarity_score(str1: str, str2: str, method: str = "normalized_substring") -> float:
    """
    Compute string similarity for human-name matching.
    
    Methods:
    - "exact": 1.0 if identical, 0.0 otherwise
    - "normalized_exact": normalized form identical
    - "normalized_substring": normalized form of one is substring of other (0.7)
    - "levenshtein": edit distance-based (not used for final decision, only review flagging)
    
    Returns: 0.0 to 1.0 confidence.
    """
```

**Loading Code Belongs In**: `process.entity_disambiguation.normalization`

---

## 4. Complete Redesign: Deterministic Matching Algorithms

### 4.1 Layer 1: Broadcasting Programs (No New Disambiguation)

**Input**: `data/00_setup/broadcasting_programs.csv` (single authoritative source)  
**Output**: One aligned row per broadcasting program (identity alignment)

**Algorithm**:
1. Load broadcasting_programs.csv
2. For each row, emit alignment event with status=ALIGNED, score=1.0, method="identity_from_setup"
3. No matching needed; this is the union root

**Implementation**: `process.entity_disambiguation.alignment.BroadcastingProgramAligner`

```python
class BroadcastingProgramAligner:
    def align_all_broadcasting_programs(self, programs_df: pd.DataFrame) -> list[AlignmentEvent]:
        """Emit one aligned event per broadcasting program."""
```

---

### 4.2 Layer 2: Episodes (Deterministic Cross-Source Matching)

**Priority Order**:
1. Shared episode_id across sources (if found in all three)
2. Time + publication signals matching
3. Season/episode number matching
4. Unresolved (orphan)

#### 4.2.1 Algorithm: Shared ID Matching

**Precondition**: 
- ZDF episode_id exists
- Found in Wikidata projections with matching metadata
- Found in Fernsehserien projections with matching metadata

**Confidence**: 0.95 (very high, but not 1.0 because sources could be out of sync)

**Example**:
```
ZDF: episode_id="ep_a371a3777018", publikationsdatum="03.06.2008", dauer=69
Wikidata: searches for episodes with broadcast_date="2008-06-03"
Fernsehserien: searches for broadcasts with broadcast_date="2008-06-03"
If all three found: ALIGNED by shared_id + date confirmation
```

#### 4.2.2 Algorithm: Time-Based Matching (Fallback)

**Precondition**:
- ZDF episode has publikationsdatum + dauer
- Wikidata has P580 (broadcast start) or extracted from label
- Fernsehserien has premiere_date or broadcast_date

**Matching Logic**:
```
For each ZDF episode:
  zdf_date = publikationsdatum
  zdf_duration = dauer (in seconds)
  zdf_time_window = [publication_time, publication_time + zdf_duration]
  
  # Search Wikidata episodes
  wd_candidates = [wd_ep for wd_ep in wd_episodes 
                   if date_distance(wd_ep.broadcast_date, zdf_date) <= 1 day]
  
  # Search Fernsehserien episodes
  fs_candidates = [fs_ep for fs_ep in fs_episodes 
                   if date_distance(fs_ep.premiere_date, zdf_date) <= 1 day
                   or any broadcast in fs_ep.broadcasts 
                      with date_distance(broadcast.date, zdf_date) <= 1 day]
  
  If len(wd_candidates) == 1 and len(fs_candidates) <= 2:
    # Single unambiguous match across sources
    alignment_status = ALIGNED
    confidence = 0.85
    method = "time_based_unique_candidate"
  ElseIf len(wd_candidates) == 0 or len(fs_candidates) == 0:
    # Some sources missing but not contradictory
    alignment_status = UNRESOLVED
    reason = "Time-based matching found no candidates in some sources; requires manual confirmation"
    requires_human_review = True
  Else:
    # Multiple candidates - ambiguous
    alignment_status = CONFLICT
    reason = "Time-based matching found multiple candidates; cannot deterministically choose"
    requires_human_review = True
    candidate_count = len(wd_candidates) + len(fs_candidates)
```

**Confidence Scoring**:
- 0.95: Shared ID across multiple sources + date confirmation
- 0.85: Time window match with unique candidate in each source
- 0.70: Time window match with partial source coverage
- 0.00: Unresolved or conflict (status != ALIGNED)

#### 4.2.3 Algorithm: Season/Episode Number Matching (Last Resort)

**Precondition**:
- ZDF has season label + episode number (folge or folgennr)
- Wikidata has P1545 (series ordinal) or label parsing
- Fernsehserien has episode metadata

**Matching Logic** (if time-based matching fails):
```
For each ZDF episode:
  zdf_season_label = season_label  # e.g., "Markus Lanz, Staffel 1"
  zdf_episode_num = folge or folgennr
  
  # Extract show name and season number
  (show_name, zdf_season_num) = normalize_season_label(zdf_season_label)
  
  # Search Wikidata for series with matching show name
  wd_series_candidates = [s for s in wd_series if similarity(s.label, show_name) > 0.9]
  
  If no unique series: UNRESOLVED
  
  # Search for season/episode within series
  wd_season = find_season_in_series(wd_series, zdf_season_num)
  wd_episode = find_episode_in_season(wd_season, zdf_episode_num)
  
  (analogous for Fernsehserien)
  
  If found in multiple sources with consistent numbering:
    alignment_status = ALIGNED
    confidence = 0.70  # Lower because number-based matching is weaker than time-based
    method = "season_episode_number_match"
  Else:
    alignment_status = UNRESOLVED
    reason = "Season/episode number matching did not find consistent candidates"
```

**Important**: Season/episode numbers can be ambiguous or inconsistent across sources. Use only when time-based fails.

#### 4.2.4 Orphans: Episodes Not Matched

**Handling**:
1. If ZDF episode not found in any other source → mark as UNRESOLVED, requires_human_review=True
2. If Wikidata episode not found in ZDF → also mark as UNRESOLVED orphan (valid; may be unreleased or regional version)
3. If Fernsehserien episode not found in ZDF → also mark as UNRESOLVED orphan
4. **Do not silently drop orphans** - they are valid rows in aligned_episodes.csv with reason explaining why unresolved

**Implementation**: `process.entity_disambiguation.alignment.EpisodeAligner`

```python
class EpisodeAligner:
    def align_all_episodes_layer2(
        self, 
        broadcasting_program_key: str,
        zdf_episodes: dict[str, dict],
        wd_episodes: dict[str, dict],
        fs_episodes: dict[str, dict],
    ) -> list[AlignmentEvent]:
        """
        Run deterministic episode matching for one broadcasting program.
        
        Algorithm priority:
        1. Shared ID + date confirmation
        2. Time window matching
        3. Season/episode number matching
        4. Unresolved orphans
        
        Emits one AlignmentEvent per episode (aligned or unresolved).
        """
```

---

### 4.3 Layer 3: Persons (Episode-Scoped Matching)

**Canonical Matching Unit**: One person mention in one episode of one broadcasting program

**Input**:
- ZDF person mention: (mention_id, episode_id, name, description, confidence)
- Wikidata person candidates: list of QIDs with labels/aliases/descriptions
- Fernsehserien person candidates: from episode_guests table for this episode

#### 4.3.1 Algorithm: Exact Name Match

**Priority 1**: Exact normalized name match across sources

```
For each ZDF person mention (mention_id, episode_id, name):
  
  zdf_name_norm = normalize_name(name)   # e.g., "verona pooth"
  
  # Search for ZDF episode in aligned episodes
  aligned_episode = find_aligned_episode(episode_id)
  If not found: UNRESOLVED (episode not aligned yet)
  
  # Search Wikidata for persons in this episode
  wd_person_candidates = search_wd_persons_for_episode(aligned_episode, zdf_name_norm)
  
  For each wd_person in wd_person_candidates:
    for each wd_alias in [wd_person.label] + wd_person.aliases:
      if normalize_name(wd_alias) == zdf_name_norm:
        wd_match_score = 1.0
        break
  
  # Search Fernsehserien for persons in this episode
  fs_person_candidates = find_fs_guests_in_episode(aligned_episode)
  
  For each fs_person in fs_person_candidates:
    if normalize_name(fs_person.name) == zdf_name_norm:
      fs_match_score = 1.0
      break
  
  If wd_match_score == 1.0 and fs_match_score == 1.0:
    alignment_status = ALIGNED
    confidence = 0.95
    method = "name_exact_multi_source"
    reason = f"Exact name match across ZDF, Wikidata ({wd_qid}), and Fernsehserien"
    
  ElseIf wd_match_score == 1.0 and fs_match_score == 0.0:
    alignment_status = ALIGNED
    confidence = 0.90
    method = "name_exact_zdf_wd"
    reason = f"Exact name match in ZDF and Wikidata ({wd_qid}); not in Fernsehserien"
    
  ElseIf wd_match_score == 0.0 and fs_match_score == 1.0:
    alignment_status = ALIGNED
    confidence = 0.85
    method = "name_exact_zdf_fs"
    reason = f"Exact name match in ZDF and Fernsehserien; not in Wikidata"
    
  Else:
    # No exact match; try partial matching
    (continue to Priority 2)
```

**Confidence Tiers**:
- 0.95: Exact match across all 3 sources (ZDF, Wikidata, Fernsehserien)
- 0.90: Exact match across ZDF + Wikidata (Fernsehserien may lack data)
- 0.85: Exact match across ZDF + Fernsehserien (Wikidata may lack entity)
- 0.80: Exact match in ZDF + partial substring match in Wikidata/Fernsehserien

#### 4.3.2 Algorithm: Substring Name Match (Medium Confidence)

**Priority 2**: One name is normalized substring of another

```
For each ZDF person mention where exact match failed:
  
  zdf_name_norm = normalize_name(name)
  
  wd_substring_matches = [wd_p for wd_p in wd_candidates 
                          if zdf_name_norm in normalize_name(wd_p.label) 
                          or normalize_name(wd_p.label) in zdf_name_norm]
  
  If len(wd_substring_matches) == 1:
    alignment_status = ALIGNED
    confidence = 0.70
    method = "name_substring_match_wd"
    reason = f"Substring match in Wikidata ({wd_qid}); ZDF name '{name}' is substring of or contains Wikidata label"
    requires_human_review = True  # Always flag substring matches for human review
  ElseIf len(wd_substring_matches) > 1:
    alignment_status = CONFLICT
    confidence = 0.0
    reason = f"Substring match found {len(wd_substring_matches)} candidates; ambiguous"
    requires_human_review = True
  Else:
    # No match in Wikidata; check Fernsehserien
    (analogous logic for Fernsehserien)
```

#### 4.3.3 Algorithm: Unresolved / Orphan Persons

**Priority 3**: If no match found

```
If no exact or substring match:
  alignment_status = UNRESOLVED
  confidence = 0.0
  method = "no_deterministic_match"
  reason = f"No match found in Wikidata or Fernsehserien for ZDF mention '{name}'"
  requires_human_review = True  # All unresolved go to OpenRefine
  candidate_count = len(wd_candidates) + len(fs_candidates)
```

**Valid Orphans**:
- ZDF mention with no corresponding entry in Wikidata/Fernsehserien (person may be minor guest, or sources incomplete)
- Wikidata person matched to episode but not found in ZDF (linked after broadcast; rarely seen on older shows)
- Fernsehserien person not in ZDF (documentation of guest list but no mention in PDF)

**Must keep all orphans in output** - they are valid rows requiring human review.

**Implementation**: `process.entity_disambiguation.alignment.PersonAligner`

```python
class PersonAligner:
    def align_persons_in_episode(
        self,
        broadcasting_program_key: str,
        episode_key: str,
        zdf_persons: list[dict],
        wd_persons: dict[str, dict],
        fs_guests: list[dict],
    ) -> list[AlignmentEvent]:
        """
        Run deterministic person matching within one episode context.
        
        Algorithm priority:
        1. Exact normalized name match across sources
        2. Substring matches (lower confidence, requires review)
        3. Unresolved orphans
        
        Emits one AlignmentEvent per person mention (aligned or unresolved).
        """
```

---

### 4.4 Layer 4: Roles & Organizations (Optional Context Signals)

**Note**: Layer 4 does **not** make new alignment decisions. Instead, it increases confidence of existing Layer 3 matches.

#### 4.4.1 Role Information Extraction

**Source 1**: ZDF person description field
- "Moderator", "Schauspieler", "Journalist", etc.
- Often includes org reference: "President of the CDU", "Direktor der XYZ"

**Source 2**: Wikidata P39 (positions held), P106 (occupations)

**Source 3**: Fernsehserien guest_role field

#### 4.4.2 Organization Information Extraction

**Source 1**: ZDF description parsing for org names

**Source 2**: Wikidata P27 (country of citizenship), P131 (located in), P108 (employer)

**Source 3**: Fernsehserien guest description text

#### 4.4.3 Use Case: Confidence Boost

**Example**:
```
ZDF person "John Smith, CEO of XYZ Corp" partially matched to Wikidata person "John Smith" (similarity 0.7)

Layer 4 analysis:
- Wikidata person has P39 = CEO, P108 = XYZ Corporation (Q12345)
- Fernsehserien role = "CEO"
- Description contains "XYZ Corp" in multiple sources

Result: Confidence increases from 0.70 to 0.85
Reason: "Substring match strengthened by alignment of role (CEO) and organization (XYZ Corp) across sources"
```

**Important Rule**:
- Layer 4 evidence **never overwrites** a Layer 1-2 decision
- Layer 4 can only increase confidence or downgrade from ALIGNED to requires_human_review if contradictions exist
- Never use Layer 4 to change status from UNRESOLVED to ALIGNED (that would violate precision-first principle)

**Implementation**: `process.entity_disambiguation.alignment.RoleOrganizationAligner`

```python
class RoleOrganizationAligner:
    def enrich_person_alignment_with_layer4_signals(
        self,
        alignment_result: AlignmentResult,
        zdf_person_desc: str,
        wd_person_occupations: list[str],
        wd_person_positions: list[str],
        fs_guest_role: str,
        fs_guest_description: str,
    ) -> AlignmentResult:
        """
        Optionally increase confidence if Layer 4 signals align.
        Does not change alignment_status; only updates score and reason if improved.
        """
```

---

## 5. Event-Sourcing Architecture

### 5.1 Event Schema

**Event Structure**:
```python
@dataclass
class AlignmentEvent:
    """
    Immutable record of one alignment decision (or attempt leading to UNRESOLVED).
    Append-only to event log; enables deterministic replay and recovery.
    """
    event_id: str                           # UUID for traceability
    timestamp: datetime                     # When event was created
    action_type: str                        # "align_episode", "align_person", etc.
    
    # Scope
    broadcasting_program_key: str           # Which show this aligns within
    core_class: str                         # "episodes", "persons", etc.
    
    # Input
    source_zdf_id: str | None              # ZDF primary key
    source_wikidata_qid: str | None        # Wikidata Q-code
    source_fernsehserien_id: str | None    # Fernsehserien URL or ID
    
    # Decision
    alignment_status: AlignmentStatus      # ALIGNED, UNRESOLVED, CONFLICT
    alignment_score: float                 # 0.0 to 1.0
    alignment_method: str                  # "name_exact_multi_source", "time_match", etc.
    alignment_reason: str                  # Human-readable explanation
    
    # Metadata for reproducibility
    metadata: dict[str, str]               # Additional context (e.g., {"name_distance": "0", "sources_agreeing": "3"})
    source_sequence_number: int            # Position in processing stream
    sequencer_source: str                  # "zdf_episodes", "wd_episodes", etc.
```

### 5.2 Event Emission Points

#### 5.2.1 Per Aligner

```
BroadcastingProgramAligner:
  - For each program row
  - Emit: action_type="seed_broadcasting_program", status=ALIGNED, score=1.0

EpisodeAligner:
  - For each ZDF episode
    - Emit: action_type="match_episode_zdf_...", status={ALIGNED|UNRESOLVED|CONFLICT}
  - For each Wikidata episode not yet matched
    - Emit: action_type="seed_episode_wikidata", status=UNRESOLVED (orphan)
  - For each Fernsehserien episode not yet matched
    - Emit: action_type="seed_episode_fernsehserien", status=UNRESOLVED (orphan)

PersonAligner:
  - For each ZDF person mention in aligned episode
    - Emit: action_type="match_person_zdf_...", status={ALIGNED|UNRESOLVED|CONFLICT}
  - For each Wikidata person not yet mentioned in ZDF
    - Emit: action_type="seed_person_wikidata", status=UNRESOLVED (orphan)
  - For each Fernsehserien guest not yet mentioned in ZDF
    - Emit: action_type="seed_person_fernsehserien", status=UNRESOLVED (orphan)

RoleOrganizationAligner:
  - For each existing person alignment where Layer 4 signals improve confidence
    - Emit: action_type="enrich_person_layer4", status={same as existing}
```

### 5.3 Event Log Persistence

**File Organization**:
```
data/31_entity_disambiguation/
├── events/
│   ├── chunk_0000.jsonl           # Events sequence 0-9999
│   ├── chunk_0001.jsonl           # Events sequence 10000-19999
│   └── ...
├── chunk_catalog.csv              # Index of chunks: start_seq, end_seq, file_path
└── checkpoints/
    ├── checkpoint_20260410_001/
    │   ├── events_chunk_*.jsonl   # Snapshot of events up to this point
    │   ├── handler_progress.db    # Which chunks have been replayed
    │   ├── projections/           # Current aligned_*.csv outputs
    │   └── checkpoint_metadata.json
    └── ...
```

**Append-Only Guarantee**: Never modify existing event or chunk files. Only append.

### 5.4 Event Replay and Projection Building

**Handler Architecture**:
```python
class ReplayableHandler:
    """
    Reads events from event log and builds deterministic projections.
    Can be replayed from any checkpoint without re-running aligners.
    """
    def __init__(self, handler_name: str, core_class: str):
        self.handler_name = handler_name          # e.g., "projection_builder_persons"
        self.core_class = core_class               # e.g., "persons"
        self.last_processed_sequence = 0          # Tracks progress
        self.progress_db = HandlerProgressDB()    # Persists progress
    
    def replay_events_from_checkpoint(self, chunk_dir: Path) -> dict[str, pd.DataFrame]:
        """
        Starting from checkpoint, process all new events and build projections.
        """
        self.last_processed_sequence = self.progress_db.get_last_sequence(self.handler_name)
        
        for chunk in iter_chunks_from(self.last_processed_sequence):
            for event in chunk.read_events(format="jsonl"):
                if event.core_class != self.core_class:
                    continue
                
                row = self._event_to_projection_row(event)
                self.projection_buffer.append(row)
        
        projections = self._build_final_projections()
        self.progress_db.save(self.handler_name, self.last_processed_sequence)
        return projections
    
    def _event_to_projection_row(self, event: AlignmentEvent) -> dict[str, str]:
        """
        Convert one event into one row of aligned_*.csv.
        Must be deterministic.
        """
        return {
            "alignment_unit_id": event.event_id,
            "core_class": event.core_class,
            "broadcasting_program_key": event.broadcasting_program_key,
            "episode_key": event.source_zdf_id if event.core_class == "persons" else "...",
            "source_zdf_value": event.source_zdf_id,
            "source_wikidata_value": event.source_wikidata_qid,
            "source_fernsehserien_value": event.source_fernsehserien_id,
            "deterministic_alignment_status": event.alignment_status,
            "deterministic_alignment_score": event.alignment_score,
            "deterministic_alignment_method": event.alignment_method,
            "deterministic_alignment_reason": event.alignment_reason,
            "requires_human_review": event.alignment_status != "aligned" or event.alignment_score < 0.9,
        }
    
    def _build_final_projections(self) -> dict[str, pd.DataFrame]:
        """
        Build final projection DataFrames with correct column order and sorting.
        """
```

---

## 6. CSV Output Contract (Baseline Columns)

### 6.1 Common Baseline Columns (All aligned_*.csv)

Every output file must include these in this exact order:

```
alignment_unit_id,                  # UUID or sequential ID
core_class,                         # "broadcasting_programs", "episodes", "persons", etc.
broadcasting_program_key,           # Reference to broadcasting program
episode_key,                        # Reference to aligned episode (NULL for Layer 1)
source_zdf_value,                  # ZDF identifier or representative value
source_wikidata_value,             # Wikidata Q-ID or label
source_fernsehserien_value,        # Fernsehserien URL or identifier
deterministic_alignment_status,    # "aligned", "unresolved", "conflict"
deterministic_alignment_score,     # 0.0 to 1.0
deterministic_alignment_method,    # Identifier of matching rule applied
deterministic_alignment_reason,    # Human-readable explanation
requires_human_review,             # Boolean
```

### 6.2 Class-Specific Extended Columns

#### aligned_broadcasting_programs.csv

```
...baseline_columns...,
label,                              # From 00_setup/broadcasting_programs.csv
description,
url,
```

#### aligned_episodes.csv

```
...baseline_columns...,
season_label,                       # From ZDF (e.g., "Staffel 1")
episode_label_zdf,                 # ZDF label
episode_label_wikidata,            # Wikidata label
episode_label_fernsehserien,       # Fernsehserien title
publication_date_zdf,              # ISO date
publication_date_wikidata,         # ISO date (from P580)
publication_date_fernsehserien,    # ISO date
duration_minutes_zdf,              # Duration in minutes
episode_number_zdf,                # folge or folgennr from ZDF
episode_number_wikidata,           # From P1545 or parsed
season_number_zdf,                 # Extracted from season_label
season_number_wikidata,            # From P1545 (P179)
```

#### aligned_persons.csv

```
...baseline_columns...,
mention_id,                         # ZDF mention_id (primary identifier)
episode_key,                        # Link to aligned episode
person_name_zdf,                   # Name as extracted in Phase 1
person_name_wikidata,              # Wikidata label
person_name_fernsehserien,         # Fernsehserien guest name
person_description_zdf,            # Role/occupation from ZDF  
person_description_wikidata,       # Description from Wikidata
person_description_fernsehserien,  # Description from Fernsehserien
parsing_confidence_zdf,            # Confidence from Phase 1 parser
wikidata_qid,                      # Q-ID if aligned
wikidata_aliases,                  # Comma-separated aliases
wikidata_occupations,              # Comma-separated occupation QIDs
wikidata_positions_held,           # Comma-separated position QIDs
fernsehserien_url,                 # Guest profile URL if known
fernsehserien_role,                # Role label from Fernsehserien
```

#### aligned_topics.csv, aligned_roles.csv, aligned_organizations.csv

```
...baseline_columns...,
[class-specific evidence columns TBD with OpenRefine SOP]
```

### 6.3 Sorting/Ordering Contract

**Global ordering rule** (for deterministic CSV output):

For each core class, rows must be ordered:
1. **By broadcasting_program_key** (ascending alphabetically)
2. **By episode_key** (if applicable, ascending; chronological oldest first)
3. **By alignment status** (ALIGNED first, then UNRESOLVED, CONFLICT last)
4. **By alignment_unit_id** (stable secondary tie-breaker)

**For persons specifically** (two-pass ordering per spec section 5.1):
1. Pass 1: Sort by episode appearance date (oldest episode first)
2. Pass 2: Within each episode, stable alphabetical sort by person name
3. Resulting behavior: Same person appearing in multiple episodes keeps chronological order across episodes while grouped alphabetically within each episode

---

## 7. Implementation Roadmap

### Phase A: Data Loading Layer (Foundation)
- [ ] Create `process.entity_disambiguation.data_loading` module
- [ ] Implement `ZDFLoader` to normalize Phase 10 CSVs into in-memory indices
- [ ] Implement `WikidataLoader` to normalize Phase 20 Wikidata JSON projections
- [ ] Implement `FernsehserienLoader` to normalize Phase 20 Fernsehserien CSV projections
- [ ] Create `process.entity_disambiguation.normalization` with all helper functions
- [ ] Write comprehensive unit tests for loading and normalization

### Phase B: Alignment Logic (Core)
- [ ] Refactor `alignment.py`:
  - [ ] Implement complete `EpisodeAligner` with all matching priorities
  - [ ] Implement complete `PersonAligner` with all matching priorities
  - [ ] Implement `BroadcastingProgramAligner` (identity)
  - [ ] Implement `RoleOrganizationAligner` (context enrichment)
- [ ] Write comprehensive unit tests for each aligner with realistic data

### Phase C: Event-Sourcing Infrastructure (Backbone)
- [ ] Clarify/implement `event_log.py` with deterministic event emission
- [ ] Implement `HandlerProgressDB` for tracking replay progress
- [ ] Implement `ReplayableHandler` for projection building
- [ ] Implement `CheckpointManager` with proper snapshot/restore
- [ ] Write unit tests for event replay from checkpoints

### Phase D: Orchestration & Integration (Conductor)
- [ ] Refactor `orchestrator.py`:
  - [ ] Implement complete `_run_broadcasting_program_seeds()`
  - [ ] Implement complete `_run_episode_alignments()`
  - [ ] Implement complete `_run_person_alignments()`
  - [ ] Implement complete `_run_role_organization_enrichment()`
  - [ ] Implement complete projection building
- [ ] Implement `RecoveryOrchestrator` for checkpoint recovery
- [ ] Write end-to-end integration tests

### Phase E: Notebook & Output (Interface)
- [ ] Update notebook `31_entity_disambiguation.ipynb` to use new orchestrator
- [ ] Verify CSV output files are created with correct columns and ordering
- [ ] Add output validation and summary statistics
- [ ] Write documentation for notebook operators

### Phase F: Validation & Polish (Hardening)
- [ ] Run on sample data; verify output against specification
- [ ] OpenRefine pilot import validation
- [ ] Performance testing (event replay should be fast)
- [ ] Documentation cleanup and operator runbook

---

## 8. Specification Contracts & Non-Negotiables

### 8.1 Must-Have (Blocking)

1. **Deterministic reproducibility**: Same input → Always same output (for any re-run)
2. **Precision-first matching**: Never force alignment below confidence threshold
3. **Baseline column stability**: All aligned_*.csv files contain baseline columns in defined order
4. **No upstream modifications**: Step 311 never writes to phases 10, 20, or 00_setup
5. **Human review visibility**: All non-aligned rows preserved in output; no silent dropping
6. **Event-sourced decisions**: Every alignment decision logged as immutable event

### 8.2 Strong Recommendations

1. **Time-based episode matching**: Use publication date/time signals when available (more reliable than name-based)
2. **Name normalization**: Implement proper German language handling (umlauts, particles)
3. **Per-core-class file organization**: One CSV per core class (simplified, matches specification)
4. **Checkpoint recovery**: Implement 3+ checkpoint retention for operator safety
5. **Incremental processing**: Support append-only updating (new source data added without full re-run when possible)

### 8.3 Known Limitations (Accept & Document)

1. **Fernsehserien data sparsity**: Older episodes may have minimal metadata; many may be UNRESOLVED
2. **Wikidata fallback dependency**: If Wikidata projection files are missing, step 311 should degrade gracefully (not fail)
3. **Cross-episode person consolidation deferred**: Phase 31 does not unify same-person across episodes (reserved for Phase 32)
4. **Orphan proliferation**: Expect many UNRESOLVED rows; this is correct behavior, not a bug

---

## 9. Key Design Decisions Rationale

### Decision 1: Layer-Based Constraints

**Why**: Episode identity must be established before person matching, because person matching requires episode_key as foreign key. Broadcasting program is the root (single source of truth from setup).

**Alternative rejected**: Probabilistic cross-layer scoring (would violate precision-first principle)

### Decision 2: Precision-First Over Recall

**Why**: False positives (incorrect alignments) are worse than false negatives (unresolved rows), because false positives propagate errors through subsequent phases and are hard to detect later. OpenRefine handles resolution (recall improvement) through human review.

**Alternative rejected**: Aggressive fuzzy matching with lower thresholds (too many false positives)

### Decision 3: Event-Sourced vs Imperative

**Why**: Event-sourcing enables deterministic replay from checkpoints (critical for long runs that may be interrupted), audit trail (why was this decision made?), and incremental updates (new data added without re-running all aligners).

**Alternative rejected**: Direct materialization (fast but non-recoverable; single-threaded)

### Decision 4: Separate Handler per Core Class

**Why**: Allows independent projection building for different core classes; handlers can be developed/tested in parallel; cleaner separation of concerns.

**Alternative rejected**: Monolithic projection builder (tight coupling; harder to extend)

### Decision 5: Baseline + Extended Columns

**Why**: Baseline columns ensure uniform interface for OpenRefine import; extended columns allow class-specific evidence without contract breaking. OpenRefine sees consistent structure across all classes.

**Alternative rejected**: Class-specific-only columns (harder for OpenRefine to normalize across classes)

---

## 10. Testing Strategy (Outline)

### 10.1 Unit Tests

- **Data loading**: Verify each loader correctly parses source formats and builds indices
- **Normalization**: Name/date/season token normalization with known inputs/outputs
- **Aligner logic**: Episode matching with synthetic test cases (exact match, time window, orphan cases)
- **PersonAligner**: Exact match, substring match, unresolved cases

### 10.2 Integration Tests

- **End-to-end orchestration**: Run complete pipeline on small sample data (1 show, 10 episodes, 20 persons)
- **Checkpoint recovery**: Run half-way, stop, checkpoint, recover, verify same output as full run
- **Output validation**: Verify aligned_*.csv files have correct columns, no duplicates, proper ordering

### 10.3 Sanity Checks (Non-Automated)

- Manual verification of alignment decisions for 1-2 shows
- OpenRefine pilot import of output CSVs
- Operator runbook walkthrough

---

## 11. Success Criteria

1. ✓ Notebook runs with single "Run All" without errors
2. ✓ All 7 aligned_*.csv files are generated with correct baseline columns
3. ✓ No rows are silently dropped; all orphans preserved with UNRESOLVED status
4. ✓ Deterministic: re-run with same input produces identical output (bit-for-bit CSV)
5. ✓ Checkpoint recovery: interrupt mid-run, restore, re-run produces same output as non-interrupted
6. ✓ OpenRefine can import aligned_*.csv files without schema errors
7. ✓ At least 85% of episodes align at ALIGNED status (reasonable for first pass; remaining UNRESOLVED go to manual)
8. ✓ At least 70% of ZDF person mentions align at ALIGNED status (precision > recall)
9. ✓ All alignment_reason strings are human-readable and informative (no internal codes)

---

## Appendix A: Data Volume Expectations

Based on Markus Lanz as representative show:

| Entity | ZDF Archive | Wikidata | Fernsehserien | Expected Alignment |
|--------|------------|----------|---------------|-------------------|
| Episodes (all seasons) | ~2500 | ~1500 (newer seasons only) | ~1100 | ~70% ZDF episodes align |
| Persons (distinct) | ~2000+ | ~800-1000 | ~600-800 | ~65% ZDF mentions align |
| Seasons | 20 | 17 | 20 | ~95% align |
| Organizations | ~50 extracted | ~30 | ~20 | ~40% align (lower priority) |
| Topics | ~100 | ~30 | Not in FS | ~20% align |

*Note*: Early episodes (2008-2015) have better source coverage; later episodes (2023+) have better Wikidata coverage.

---

## Appendix B: Open Questions for Resolution

1. **Exact file format/schema for Wikidata projections**: Are they `instances_core_episodes.csv` or `episodes.json`? Need to verify actual file names in Phase 20 output.
   * **Answer:** `episodes.json`. All `instances_core_*.csv` can be ignored, they are inferior to the .json files.
2. **Fernsehserien projection structure**: Do the CSV files exist as named, or different structure?
   * **Answer:** Those are the three files that are relevant:
     * data/20_candidate_generation/fernsehserien_de/projections/episode_broadcasts_normalized.csv
     * data/20_candidate_generation/fernsehserien_de/projections/episode_guests_normalized.csv
     * data/20_candidate_generation/fernsehserien_de/projections/episode_metadata_normalized.csv
3. **Phase 20 to Phase 31 join logic**: How are broadcasting program keys passed from Phase 20? Are they stable across reruns?
   * **Answer:** broadcasting programs remain stable, everyone reuses the same from input: data/00_setup/broadcasting_programs.csv
4. **Episode numbering semantics**: Are `folge` and `folgennr` always consistent in ZDF? Can they be NULL?
   * **Answer:** No, expect little consistency - many such things change and are often NULL.
5. **Orphan policy for cross-source entities**: If a Wikidata video exists but isn't a ZDF episode, should it still be in aligned_episodes.csv or dropped?
   * **Answer:** every instance from every file should be in the respective aligned file. We can always drop it later.
6. **Organization/Role handling**: Are there existing Phase 2 role/organization projections, or do we extract them from text descriptions?
   * **Answer:** For now, we mostly ignore them. Eventually, we may be able to retrieve them properly, but for now, we just can't track them correctly.