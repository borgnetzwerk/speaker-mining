# Episode Extraction Logic & Data Persistence

Date: 2026-04-08  
Scope: fernsehserien.de episode leaf parsing (phase 2)

## Overview

Episode pages contain deeply nested, semi-structured information about guests, broadcasts, and episode metadata. This document specifies:
1. What data to extract from episode HTML
2. How to identify these data structures reliably
3. How to persist nested hierarchies in an event-sourced system
4. The schema and normalization rules for downstream consumption

## Policy

This fernsehserien.de workflow does not preserve backward compatibility for legacy code, legacy projections, or legacy users.

It does preserve and build around two kinds of historical inputs:
- Cached source files remain authoritative and must be reused.
- Legacy append-only events remain authoritative history and must be replayed.

---

## Data Model: What We Extract

### 1. Episode Header (Top-level Metadata)

**Location:** `<h3 class="episode-output-titel"><span itemprop="name">...</span></h3>`

**Fields to extract:**
- `episode_title` (str): The episode name/number from `itemprop="name"` content
- `episode_duration_minutes` (int | null): Duration from `<div class=episoden-zeile-1000>` (e.g., "75 Min.")

**Confidence Scoring:** 
- H3 with class `episode-output-titel` → 0.95 (reliable CSS marker)
- Duration parsing from adjacent div → 0.8 (may be absent or malformed)

---

### 2. Episode Description & Metadata

**Location:** `<div class=episode-output-inhalt>` block

**Fields to extract:**
- `description_full_text` (str): Complete text content, preserving guest names and their descriptions
- `description_source` (str): Attribution text from `<span class=text-quelle>` (e.g., "Text: ZDF")
- `premiere_info` (dict):
  - `premiere_date` (str, ISO 8601): From `<ea-angabe-datum>` 
  - `premiere_broadcaster` (str): From `<ea-angabe-sender>`
  - `premiere_weekday` (str): Extracted from formatted date (e.g., "Do.")

**Normalization:**
1. Strip `<werbung>` (advertising) tags and normalize whitespace
2. Collapse multiple `<span class=br>` to single newlines
3. Parse German date format "Do. 07.09.2017" → ISO "2017-09-07" + weekday "Thursday"
4. Broadcaster names: "ZDF" → normalized to wikidata ID (future lookup)

**Confidence Scoring:**
- Description extraction from `.episode-output-inhalt-inner` → 0.85 (may contain ads, malformed tags)
- Date parsing from EA elements → 0.9 (structured `datetime` attributes)
- Source attribution → 0.75 (optional field, not always present)

**Schema in event store:**
```json
{
  "event_type": "episode_description_discovered",
  "payload": {
    "program_name": "Markus Lanz",
    "episode_url": "https://www.fernsehserien.de/markus-lanz/folgen/1034-...",
    "episode_title_raw": "Folge 1034",
    "duration_raw": "75 Min.",
    "description_raw_text": "Shania Twain, Sängerin\n85 Millionen Tonträger...",
    "description_source_raw": "Text: ZDF",
    "premiere_date_raw": "Do. 07.09.2017",
    "premiere_broadcaster_raw": "ZDF",
    "parsed_at_utc": "2026-04-08T10:30:00Z",
    "confidence": 0.85,
    "parser_rule": "episode_description_raw_v1"
  }
}
```

---

### 3. Guest/Cast List (Nested Records)

**Location:** `<section><header><h2 id=Cast-Crew>Cast & Crew</h2>...</header><ul class="cast-crew cast-crew-rest">...</ul></section>`

**Structure:** Each guest is an `<li itemscope itemtype="http://schema.org/Person">` with:
- Anchor link `<a title="..." itemprop="url" href="/person-slug/filmografie">`
- Person name from `<dt itemprop="name">` inside `<dl>`
- Role/description from `<dd><p>...<br>...</p></dd>` (may have multiple lines)
- Image URL (optional) from `<meta itemprop="image" content="...">` or `data-src` in lazy loader

**Fields per guest:**
- `guest_name` (str): Exact text from `dt[itemprop="name"]`
- `guest_role` (str): First line of `dd > p` (e.g., "Gast")
- `guest_description` (str): Second+ lines of `dd > p`, joined by space (e.g., "Sängerin", "Sohn von Hanns Martin Schleyer")
- `guest_url` (str): Href from anchor (e.g., `/shania-twain/filmografie`)
- `guest_image_url` (str | null): From `meta[itemprop="image"]` or lazy-load `data-src`
- `guest_order` (int): Position in list (0-indexed for deduplication)

**Normalization:**
1. Guest name: Trim whitespace, collapse internal spaces
2. Role: First `<br>`-separated segment (usually just "Gast")
3. Description: Everything after first `<br>`, join with space, strip `<br>` tags
4. URL: Absolute URL from relative href (prepend `https://www.fernsehserien.de`)
5. Image: Prioritize `meta[itemprop="image"]` over `data-src` (JSON-LD > lazy)

**Confidence Scoring:**
- Guest name extraction from schema.org Person block → 0.95
- Role/description parsing from `<dd>` → 0.9 (consistent HTML structure)
- URL extraction from anchor → 0.98
- Image URL → 0.85 (may be missing, lazy-load URLs may break)

**Per-guest event schema:**
```json
{
  "event_type": "episode_guest_discovered",
  "payload": {
    "program_name": "Markus Lanz",
    "episode_url": "https://www.fernsehserien.de/markus-lanz/folgen/1034-...",
    "guest_name": "Shania Twain",
    "guest_role": "Gast",
    "guest_description": "Sängerin",
    "guest_url": "/shania-twain/filmografie",
    "guest_image_url": "https://bilder.fernsehserien.de/fernsehserien.de/fs-2021/img/Person.svg",
    "guest_order": 0,
    "parsed_at_utc": "2026-04-08T10:30:00Z",
    "confidence": 0.95,
    "parser_rule": "cast_crew_schema_org_v1"
  }
}
```

**Multiple events per episode:** One event emitted **per guest** (not one bulk event), enabling:
- Incremental replay (add/remove guests independently)
- Granular deduplication (by program + episode_url + guest_name)
- Future guest-centric analysis (which guests appear most, co-appearance patterns)

---

### 4. Broadcast Schedule (Nested Records)

**Location:** `<section class=no-print><header><h2 id=Sendetermine>Sendetermine...</h2>...</header><div role=table id=episode-sendetermine>...</div></section>`

**Structure:** Each broadcast is a `<div role=row>` containing:
- Date/time from `<time itemprop="startDate" datetime="2017-09-07T23:15:00+02:00">` and `<time itemprop="endDate">`
- Broadcaster from `<span itemprop="name" content="ZDF">`
- Premiere badge from `<abbr title="TV-Premiere">NEU</abbr>`
- Weekday from text content (e.g., "Do.", "Fr.")

**Fields per broadcast:**
- `broadcast_date` (str, ISO 8601): From `startDate` datetime attribute
- `broadcast_start_time` (str, HH:MM): From `startDate` (e.g., "23:15")
- `broadcast_end_date` (str, ISO 8601): End-date after rollover handling
- `broadcast_end_time` (str, HH:MM): From `endDate` (e.g., "00:30")
- `broadcast_broadcaster` (str): From `itemprop="name" content`
- `broadcast_broadcaster_key` (str): Normalized lowercase broadcaster key
- `broadcast_timezone_offset` (str): From `datetime` (e.g., "+02:00")
- `broadcast_is_premiere` (bool): True if `<abbr title="TV-Premiere">` present
- `broadcast_spans_next_day` (bool): True if normalized end datetime is after midnight relative to start
- `broadcast_order` (int): Chronological order (0 = first broadcast, usually oldest)

**Normalization:**
1. Parse ISO 8601 datetime: `2017-09-07T23:15:00+02:00` → date + start_time + tz
2. Handle midnight boundary deterministically: if parsed `end <= start`, shift end by one day and set `broadcast_spans_next_day=true`
3. Broadcaster: Normalize "ZDF" → "zdf" (lowercase for dedup), future wikidata linkage
4. Premiere detection: Check for "NEU" abbr or first broadcast in chronological list

**Confidence Scoring:**
- Date/time extraction from structured `datetime` → 0.98
- Broadcaster name from `content` attribute → 0.95
- Premiere detection → 0.9 (may be inferred or explicit)

**Per-broadcast event schema:**
```json
{
  "event_type": "episode_broadcast_discovered",
  "payload": {
    "program_name": "Markus Lanz",
    "episode_url": "https://www.fernsehserien.de/markus-lanz/folgen/1034-...",
    "broadcast_date": "2017-09-07",
    "broadcast_start_time": "23:15",
    "broadcast_end_time": "00:30",
    "broadcast_broadcaster": "ZDF",
    "broadcast_timezone_offset": "+02:00",
    "broadcast_is_premiere": true,
    "broadcast_order": 0,
    "parsed_at_utc": "2026-04-08T10:30:00Z",
    "confidence": 0.98,
    "parser_rule": "broadcast_schedule_schema_org_v1"
  }
}
```

**Multiple events per episode:** One event **per broadcast** (not one bulk event), enabling:
- Incremental replay (add/remove broadcasts independently)
- Time-series analysis (when/where aired)
- Deduplication by (program + episode_url + broadcast_date + broadcaster)

---

## Persistence Strategy: Event-Sourced Nested Data

### Challenge: Flattening Hierarchies

Episode pages contain inherently nested structures:
```
Episode
  ├─ Metadata (1 record)
  ├─ Description (1 record)
  ├─ Guests (N records)
  └─ Broadcasts (M records)
```

Naive approach: Emit single `episode_leaf_parsed` event with all guests/broadcasts as arrays -> non-idempotent, non-decomposable.

**Solution:** Decompose into atomic events (one per entity), enabling independent replay and deduplication.

### Event Types

1. **`episode_description_discovered`** (1 per episode)
   - Top-level metadata: title, duration, description, premiere info
   - Emitted once per episode

2. **`episode_guest_discovered`** (N per episode, one per guest)
   - Individual guest record
   - Emitted once per guest in cast list
   - Multiple events in same run if multiple guests

3. **`episode_broadcast_discovered`** (M per episode, one per broadcast)
   - Individual broadcast schedule record
   - Emitted once per scheduled broadcast
   - Multiple events in same run if multiple air dates

### Projection Tables (Normalized, Flattened)

Each event family projects to separate discovered and normalized CSV tables:

#### `episode_metadata_discovered.csv` and `episode_metadata_normalized.csv`
```
program_name,episode_url,episode_title_raw,duration_raw,description_raw_text,description_source_raw,premiere_date_raw,premiere_broadcaster_raw,raw_extra_json,parsed_at_utc,parser_rule,confidence,source_event_sequence
Markus Lanz,https://...,Folge 1034,75 Min.,"Shania Twain, Sängerin...",Text: ZDF,Do. 07.09.2017,ZDF,"{\"guests_count\":7}",2026-04-08T10:30:00Z,episode_description_raw_v1,0.85,8500
```

**Key fields:** `(program_name, episode_url)` uniquely identifies episode; dedupe by these two fields.

#### `episode_guests_discovered.csv` and `episode_guests_normalized.csv`
```
program_name,episode_url,guest_name_raw,guest_role_raw,guest_description_raw,guest_url_raw,guest_image_url_raw,guest_order,parsed_at_utc,parser_rule,confidence,source_event_sequence
Markus Lanz,https://...,Shania Twain,Gast,Sängerin,/shania-twain/filmografie,https://bilder.fernsehserien.de/...,0,2026-04-08T10:30:00Z,cast_crew_schema_org_v1,0.95,8501
Markus Lanz,https://...,Joko Winterscheidt,Gast,Moderator,/joko-winterscheidt/filmografie,https://bilder.fernsehserien.de/...,1,2026-04-08T10:30:00Z,cast_crew_schema_org_v1,0.95,8502
```

**Key fields:** `(program_name, episode_url, guest_order)` uniquely identifies guest in episode context; dedupe by these three fields.

#### `episode_broadcasts_discovered.csv` and `episode_broadcasts_normalized.csv`
```
program_name,episode_url,broadcast_start_datetime_raw,broadcast_end_datetime_raw,broadcast_broadcaster_raw,broadcast_is_premiere_raw,broadcast_order,parsed_at_utc,parser_rule,confidence,source_event_sequence
Markus Lanz,https://...,2017-09-07T23:15:00+02:00,2017-09-08T00:30:00+02:00,ZDF,TV-Premiere,0,2026-04-08T10:30:00Z,broadcast_schedule_schema_org_v1,0.98,8503
Markus Lanz,https://...,2017-09-15T10:16:00+02:00,2017-09-15T11:32:00+02:00,3sat,,1,2026-04-08T10:30:00Z,broadcast_schedule_schema_org_v1,0.98,8504
```

**Key fields:** `(program_name, episode_url, broadcast_date, broadcast_broadcaster)` uniquely identifies broadcast; dedupe by these four fields.

### Handler Progress & Replay Safety

Each projection table gets its own handler in `eventhandler.csv`:

```
handler_name,last_processed_sequence,artifact_path,updated_at
episode_metadata_discovered_handler,8505,<path>/episode_metadata_discovered.csv,2026-04-08T10:30:00Z
episode_guests_discovered_handler,8505,<path>/episode_guests_discovered.csv,2026-04-08T10:30:00Z
episode_broadcasts_discovered_handler,8505,<path>/episode_broadcasts_discovered.csv,2026-04-08T10:30:00Z
episode_metadata_normalized_handler,8505,<path>/episode_metadata_normalized.csv,2026-04-08T10:30:00Z
episode_guests_normalized_handler,8505,<path>/episode_guests_normalized.csv,2026-04-08T10:30:00Z
episode_broadcasts_normalized_handler,8505,<path>/episode_broadcasts_normalized.csv,2026-04-08T10:30:00Z
```

**Deterministic replay:**
1. Read each handler's `last_processed_sequence`
2. Process events where `sequence_num > last_processed_sequence` and `event_type` matches handler's scope
3. Deduplicate rows by key fields before write
4. Update handler's `last_processed_sequence` to max processed sequence

**Example:** If re-run processes the same episode:
- Read `episode_guests_handler.last_processed_sequence = 8505`
- See events 8501-8502 already processed (sequences ≤ 8505)
- Skip re-emission; dedupe by (program_name, episode_url, guest_order) finds existing rows
- No duplicates appear in final CSV

---

## Extraction Implementation: Phase 2 Requirements (Revised)

### Core Principle: Two-Stage Persistence

Normalization must be a separate stage from extraction, and both stages must persist state.

1. Stage A persists structured but raw values exactly as found (for debugging and reprocessing).
2. Stage B persists interpreted and standardized values (for analytics and disambiguation).

Example:
- Raw: `duration_raw = "75 Min."` or `"31 minutes and 15 seconds"`
- Normalized: `duration_minutes = 75` or `31.25`

This separation guarantees that parser changes do not destroy source evidence and allows re-normalization without re-fetching/re-extracting HTML.

### Notebook Process Order (Required)

The notebook flow should run in this strict order:

1. Extract structured raw data from existing local leaf pages that are not yet extracted.
2. If no un-extracted local leaf pages remain, fetch leaf pages for known episode URLs that are not cached yet. If new pages were fetched, repeat from step 1.
3. Explore/discover new episode URLs. If new URLs were found, repeat from step 2.
4. After step 3 finishes (either completed or network limit reached), run normalization for extracted-but-not-yet-normalized records only.

Important: Step 4 is separate and must not trigger steps 1-3 again.

### Event Taxonomy: _discovered and _normalized

For each entity, persist one raw discovery event family and one normalization event family.

Raw discovery event types:
- `episode_description_discovered`
- `episode_guest_discovered`
- `episode_broadcast_discovered`

Normalization event types:
- `episode_description_normalized`
- `episode_guest_normalized`
- `episode_broadcast_normalized`

Each `_normalized` payload references the source discovery sequence.

### Parser Enhancements Needed

`parse_episode_leaf_fields()` should return raw, structured extraction only.

```python
def parse_episode_leaf_fields(*, html_text: str) -> dict:
  """
  Extract nested episode data from fernsehserien.de episode HTML.

  Returns raw structured values (no semantic normalization):
  - episode_title_raw (str)
  - duration_raw (str | None)
  - description_raw_text (str)
  - description_source_raw (str | None)
  - premiere_date_raw (str | None)
  - premiere_broadcaster_raw (str | None)
  - guests_raw (list[dict])
  - broadcasts_raw (list[dict])
  """
```

### Orchestrator Changes Needed

During extraction steps (1-3), emit only `_discovered` events. During normalization step (4), emit `_normalized` events.

```python
# Extraction stage: from parsed raw structures
event_store.append(
  event_type="episode_description_discovered",
  payload={
    "program_name": program_name,
    "episode_url": episode_url,
    "episode_title_raw": parsed["episode_title_raw"],
    "duration_raw": parsed["duration_raw"],
    "description_raw_text": parsed["description_raw_text"],
    "description_source_raw": parsed["description_source_raw"],
    "premiere_date_raw": parsed["premiere_date_raw"],
    "premiere_broadcaster_raw": parsed["premiere_broadcaster_raw"],
    "parsed_at_utc": _iso_now(),
    "parser_rule": "episode_description_raw_v1",
    "confidence": 0.85,
  },
)

# Normalization stage: references discovered event sequence
event_store.append(
  event_type="episode_description_normalized",
  payload={
    "program_name": program_name,
    "episode_url": episode_url,
    "episode_title": normalized["episode_title"],
    "duration_minutes": normalized["duration_minutes"],
    "premiere_date": normalized["premiere_date"],
    "premiere_broadcaster": normalized["premiere_broadcaster"],
    "source_discovered_sequence": discovered_sequence,
    "normalized_at_utc": _iso_now(),
    "normalizer_rule": "episode_description_norm_v1",
  },
)
```

### Projection Builder Extensions

Use separate projection artifacts and handler checkpoints for discovered and normalized layers.

Discovered handlers:
- `episode_description_discovered_handler`
- `episode_guests_discovered_handler`
- `episode_broadcasts_discovered_handler`

Normalized handlers:
- `episode_description_normalized_handler`
- `episode_guests_normalized_handler`
- `episode_broadcasts_normalized_handler`

Each handler writes one artifact and persists its own `last_processed_sequence` in `eventhandler.csv`.

### CSV Artifacts (Raw vs Normalized)

Raw artifacts:
- `episode_metadata_discovered.csv`
- `episode_guests_discovered.csv`
- `episode_broadcasts_discovered.csv`

Normalized artifacts:
- `episode_metadata_normalized.csv`
- `episode_guests_normalized.csv`
- `episode_broadcasts_normalized.csv`

To keep schema adaptable, raw artifacts should include a flexible overflow column for non-stable patterns:
- `raw_extra_json` (JSON string)

This supports evolving guest role/description patterns without schema churn.

### Raw Overflow Governance

1. Stable attributes with repeated analytical value must be promoted to explicit columns.
2. Attributes that are experimental, inconsistent, or low-frequency remain in `raw_extra_json`.
3. Promotion from `raw_extra_json` to explicit columns must retain the raw copy for auditability.
4. Projection handlers must never drop unknown keys silently when re-emitting raw records.

### Confidence & Rule Traceability

1. Confidence is recorded per discovered record type and can differ across metadata, guest, and broadcast rows.
2. `parser_rule` and `normalizer_rule` are versioned and persisted on every row/event.
3. Confidence should be derived from structural evidence checks (for example: marker presence, required attributes found) rather than fixed constants.

---

## Summary: Data Integrity & Scaling

| Aspect | Solution |
|--------|----------|
| **Nested hierarchy** | Decompose into atomic events (one per record type) |
| **Two-stage persistence** | Persist `_discovered` (raw) and `_normalized` (interpreted) separately |
| **Idempotency** | Deduplicate by natural key fields per table |
| **Incremental replay** | Per-handler progress checkpoints for both layers |
| **Auditability** | Every normalized record references its raw source sequence |
| **Extensibility** | Raw overflow via `raw_extra_json`; new normalizer rules can replay without re-fetch |
| **Observability** | Confidence distribution for extraction and rule/version tracking for normalization |

This design preserves source evidence, improves debugging at scale, and fully aligns with the repository coding-principles requirement for handler-level progress persistence.
