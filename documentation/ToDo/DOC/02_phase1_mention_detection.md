# Phase 1: Mention Detection — Exhaustive Reference

> Status: Draft — agent findings to be integrated when agents complete.  
> Covers: `11_mention_detection.ipynb`, `19_analysis.ipynb`, all `mention_detection/*.py` files.

---

## Overview

Phase 1 is the most upstream data-producing phase. It reads pre-exported ZDF archive text files and extracts five structured tables: episodes, publications, seasons, persons (guests), and topics. All outputs go to `data/10_mention_detection/`.

**Input:** 4 × `.pdf_episodes.txt` files in `data/01_input/zdf_archive/`  
**Output:** 5 × CSV files + 5 × duplicate-report CSVs in `data/10_mention_detection/`

---

## Notebook: `11_mention_detection.ipynb`

### Cell 1 — Project Setup
```python
ROOT = find_repo_root(Path.cwd())  # walks up max 8 levels, looks for data/ + speakermining/src/
SRC = ROOT / "speakermining" / "src"
sys.path.insert(0, str(SRC))
```
**Assumption:** Notebook can be opened from any subdirectory; root is detected by sentinel directories.

### Cell 2 — Input Discovery
```python
input_paths = [ROOT / ZDF_ARCHIVE_DIR / name for name in DEFAULT_PDF_TXT_INPUTS]
```
Loads paths for 4 files:
- `Markus Lanz_2008-2010.pdf_episodes.txt`
- `Markus Lanz_2011-2015.pdf_episodes.txt`
- `Markus Lanz_2016-2020.pdf_episodes.txt`
- `Markus Lanz_2021-2024.pdf_episodes.txt`

**No existence check performed here** — errors surface at read time in the next cell.

### Cell 3 — Episode and Season Extraction
```python
episode_blocks = load_episode_blocks_from_many(input_paths)
episodes_raw_df, publications_raw_df = extract_episode_and_publication_rows(episode_blocks)
seasons_raw_df = extract_season_rows(episodes_raw_df)
# exact-duplicate filtering:
episodes_df, episodes_dup_df, ...   = filter_exact_duplicates_with_report("episodes", ...)
publications_df, ...                = filter_exact_duplicates_with_report("publications", ...)
seasons_df, ...                     = filter_exact_duplicates_with_report("seasons", ...)
# write:
ep_path  = save_episodes(episodes_df, ROOT / PHASE_DIR)
pu_path  = save_publications(publications_df, ROOT / PHASE_DIR)
se_path  = save_seasons(seasons_df, ROOT / PHASE_DIR)
```
**Prints:** raw row count, kept row count, exact duplicate count for each table.  
**NOTE:** Duplicate filtering is row-level exact match only. Cross-archive content duplicates (same episode in two txt files with matching text) would survive if the episode block text differs by even one character (TODO-001).

### Cell 4 — Mention Extraction
```python
persons_raw_df = extract_person_mentions(episode_blocks, episodes_df)
topics_raw_df  = extract_topic_mentions(episode_blocks, episodes_df)
# exact-duplicate filtering:
persons_df, ...  = filter_exact_duplicates_with_report("persons", ...)
topics_df, ...   = filter_exact_duplicates_with_report("topics", ...)
pe_path = save_person_mentions(persons_df, ROOT / PHASE_DIR)
to_path = save_topic_mentions(topics_df, ROOT / PHASE_DIR)
```
**Contains a TODO cell** documenting gender inference and mention categorization as unimplemented.

### Cell 5 — Quantitative Validation (sub-cells)

**5.1 — Overview table:** seasons/episodes/publications/persons/topics row counts, unique counts, avg confidence.

**5.2 — Episodes detail:**
- `episodes_total`, `unique_episode_ids`, `duplicate_episode_ids`
- `date_coverage_start` / `date_coverage_end` (parsed as `%d.%m.%Y`)
- `missing_season`, `missing_staffel`, `missing_folge`, `missing_folgennr`
- Top 10 seasons by episode count
- `publications_per_episode_min/median/max`

**5.3 — Publications detail:**
- Row counts, primary vs non-primary split
- `date_start` / `date_end`
- Program distribution table (`program` column value counts)

**5.4 — Persons detail:**
- `mention_rows`, `unique_mention_ids`, `duplicate_mention_ids`
- `episodes_with_person_mentions`, `unique_person_names`
- `avg/p10/p50/p90 confidence`
- `avg/median/max mentions per episode`
- `missing_description` count
- Top 10 persons by mention frequency
- `parsing_rule` distribution table

**5.5 — Topics detail:**
- `mention_rows`, `unique_topic_labels`
- `avg/p10/p50/p90/max topics per episode`
- Top 10 topics by frequency
- `parsing_rule` distribution table

---

## Module: `mention_detection/config.py`

### Constants

```python
DATA_DIR   = Path("data")
INPUT_DIR  = DATA_DIR / "01_input"
PHASE_DIR  = DATA_DIR / "10_mention_detection"
ZDF_ARCHIVE_DIR = INPUT_DIR / "zdf_archive"
```
**IMPORTANT:** All paths are relative. Notebooks must `os.chdir(ROOT)` or use `ROOT / PHASE_DIR` when constructing absolute paths.

### Output File Names
```python
FILE_EPISODES        = "episodes.csv"
FILE_PERSON_MENTIONS = "persons.csv"
FILE_TOPIC_MENTIONS  = "topics.csv"
FILE_SEASONS         = "seasons.csv"
FILE_PUBLIKATION     = "publications.csv"
```

### Column Schemas

**`EPISODE_COLUMNS`** (14 columns):
| Column | Type | Description |
|--------|------|-------------|
| `episode_id` | str | SHA1-based stable ID (`ep_XXXXXXXXXXXX`) |
| `sendungstitel` | str | Episode title from `Sendetitel` line |
| `publikation_id` | str | Foreign key to primary publication row |
| `publikationsdatum` | str | Date as `DD.MM.YYYY` string |
| `dauer` | str | Duration (prefers publication row; fallback: `MM'SS` pattern) |
| `archivnummer` | str | Archive reference number |
| `prod_nr_beitrag` | str | Production number in `NNNNN/NNNNN` format |
| `zeit_tc_start` | str | Timecode start `HH:MM:SS` |
| `zeit_tc_end` | str | Timecode end `HH:MM:SS` |
| `season` | str | Season label e.g. `Markus Lanz, Staffel 3` |
| `staffel` | str | Raw Staffel number from text |
| `folge` | str | Raw Folge number from text |
| `folgennr` | str | Raw FolgenNr number from text |
| `infos` | str | Full `Sachinhalt … Jugendeignung` span, whitespace-collapsed |

**`PERSON_MENTION_COLUMNS`** (9 columns):
| Column | Type | Description |
|--------|------|-------------|
| `mention_id` | str | SHA1-based ID (`pm_XXXXXXXXXXXX`) over episode_id+name+beschreibung |
| `episode_id` | str | FK to episodes.csv |
| `name` | str | Extracted person name |
| `beschreibung` | str | Extracted description from parenthetical |
| `source_text` | str | Raw text block from which name was extracted |
| `source_context` | str | The infos section in which the name was found |
| `parsing_rule` | str | Which rule produced this row (see confidence table) |
| `confidence` | str | Float as string (0.45–0.95) |
| `confidence_note` | str | Human-readable justification |

**`PUBLIKATION_COLUMNS`** (11 columns):
| Column | Type | Description |
|--------|------|-------------|
| `publikation_id` | str | Stable ID (`pub_XXXXXXXXXXXX`) |
| `episode_id` | str | FK to episodes |
| `publication_index` | str | 0-based index within episode |
| `date` | str | Date as `DD.MM.YYYY` |
| `time` | str | Broadcast time |
| `duration` | str | Duration string |
| `program` | str | Channel/program name |
| `prod_nr_sendung` | str | Sendung production number |
| `prod_nr_secondary` | str | Secondary production number |
| `is_primary` | str | "1" or "0" |
| `raw_line` | str | Original line from archive text |

**`TOPIC_MENTION_COLUMNS`** (8 columns):
| Column | Type | Description |
|--------|------|-------------|
| `mention_id` | str | SHA1-based ID |
| `episode_id` | str | FK to episodes |
| `topic` | str | Extracted topic string |
| `source_text` | str | Raw source text |
| `source_context` | str | Context section |
| `parsing_rule` | str | Extraction rule |
| `confidence` | str | Float as string |
| `confidence_note` | str | Justification |

**`SEASON_COLUMNS`** (5 columns):
| Column | Type | Description |
|--------|------|-------------|
| `season_id` | str | Stable ID derived from season_label |
| `season_label` | str | e.g. `Markus Lanz, Staffel 3` |
| `start_time` | str | Earliest episode date in season |
| `end_time` | str | Latest episode date in season |
| `episode_count` | int | Number of episodes in season |

---

## Module: `mention_detection/episode.py`

### `_stable_episode_id(title, date_value, fallback_text) → str`
- Computes SHA1 over `"{title}|{date_value}|{fallback_text[:200]}"` encoded as UTF-8
- Returns `ep_{digest[:12]}`
- **Assumption:** First 200 chars of block text are sufficient for disambiguation when title+date are empty
- **Collision risk:** Two episodes with identical title, date, and first 200 chars of text would collide (unhandled)

### `_extract_title(text) → str`
- Pattern: `r"Sendetitel\s*(.+)"` with `IGNORECASE|DOTALL`
- Returns first line only (splits on `\n`, takes `[0]`)
- Returns `""` if no match

### `_extract_date(text) → str`
- **Primary:** calls `extract_publication_rows_from_text(text)` → takes `pub_rows[0]["date"]`
- **Fallback 1:** If `"Publikation"` in text: split on it, search `r"(\d{2}\.\d{2}\.\d{4})"` in tail
- **Fallback 2:** Search entire text for `r"(\d{2}\.\d{2}\.\d{4})"`
- Returns `""` if nothing found
- **Assumption:** First publication date = episode broadcast date

### `_extract_archivnummer(text) → str`
- Pattern: `r"Archivnummer\s*(\d+)"` with `IGNORECASE`
- Returns digits only, `""` if not found

### `_extract_prod_nr_beitrag(text) → str`
- Pattern: `r"Prod-Nr\s+Beitrag\s*([0-9]{5}/[0-9]{5})"` with `IGNORECASE`
- Expects exactly `NNNNN/NNNNN` format; returns `""` if not present

### `_extract_tc_range(text) → tuple[str, str]`
- Pattern: `r"Zeit\s+TC\s+(\d{2}:\d{2}:\d{2})\s*-\s*(\d{2}:\d{2}:\d{2})"` with `IGNORECASE`
- Returns `(tc_start, tc_end)` or `("", "")` if not found

### `_extract_info_block(text) → str`  ← **BUG SITE FOR TODO-009**
- Pattern: `r"Sachinhalt(.*?)Jugendeignung"` with `DOTALL|IGNORECASE`
- If no match → returns `""`
- If match → collapses whitespace: `" ".join(m.group(1).replace("\n", " ").split())`
- **Critical assumption:** Both `Sachinhalt` and `Jugendeignung` must appear in the block. If either is missing (e.g., EPISODE 363 which may be missing `Jugendeignung`), the entire infos field is lost, causing all guest extraction for that episode to fail.

### `_extract_time_length(text) → str`
- Pattern: `r"\b(\d{2,3}'\d{2})\b"` — matches `MM'SS` or `MMM'SS` format
- Fallback duration when publication row has none

### `_extract_field(label, text) → str`
- Generic: `r"\b{label}\s+(\d+)\b"` — used for `Staffel`, `Folge`, `FolgenNr`

### `_season_string(staffel, title, date_value) → str`
- If `staffel` is non-empty: returns `"Markus Lanz, Staffel {staffel}"`
- Else if title matches `r"^Markus Lanz \d{2}\.\d{2}\.\d{4}$"` and date_value is set:
  - Parses date as `%d.%m.%Y`
  - Returns `"Markus Lanz, Staffel {year - 2007}"`
  - **Assumption:** Show started in 2008 (year 1 = 2008 → `2008 - 2007 = 1`)
- Returns `""` otherwise

### `extract_episode_and_publication_rows(episode_blocks) → tuple[DataFrame, DataFrame]`
Main extraction loop. For each block:
1. Calls all `_extract_*` helpers
2. Computes `episode_id = _stable_episode_id(...)`
3. Calls `build_publication_rows(episode_id, parsed_publications)` → gets `primary_publication_id`
4. Builds episode row dict
5. **Sorting:** Sorts episodes by `pd.to_datetime(publikationsdatum, format="%d.%m.%Y")`, then by `sendungstitel` for ties. `na_position="last"`.
6. Reindexes to `EPISODE_COLUMNS` exactly
7. Sorts publications by `[_episode_order, _pub_idx, publikation_id]`
8. **Empty case:** Returns empty DataFrames with correct column schemas

### `extract_episode_rows(episode_blocks) → DataFrame`
Thin wrapper — calls `extract_episode_and_publication_rows()` and discards publication DataFrame.

### `save_episodes(df, output_dir) → Path`
- Writes to `{output_dir}/episodes.csv` via `atomic_write_csv()`
- Creates directory if needed
- No sorting at write time (already sorted)

---

## Module: `mention_detection/guest.py`

### Module-Level Constants

```python
_NAME_PATTERN = re.compile(
    r"\b(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.)(?:\s+(?:[A-ZÄÖÜ][a-zäöüß]+|[A-ZÄÖÜ]\.))*\s+"
    r"(?:[A-ZÄÖÜ][A-ZÄÖÜß-]+(?:\s+[A-ZÄÖÜ][A-ZÄÖÜß-]+)*|[A-ZÄÖÜ][a-zäöüß]+(?:-[A-ZÄÖÜ][a-zäöüß]+)?)\b"
)
```
Matches: TitleCase firstname(s) + UPPERCASE surname(s). Also handles `ß` in surnames.

```python
_MONONYM_PATTERN = re.compile(r"\b[A-ZÄÖÜ][A-ZÄÖÜß-]{3,}\b")
```
Matches all-caps tokens ≥4 chars (artist/stage names).

```python
_SURNAME_PRIMARY_NAME_PATTERN = re.compile(...)
```
Broader than `_NAME_PATTERN` — allows non-parenthetical context for surname-lead extraction.

```python
_MONONYM_STOPWORDS = {"LANZ", "OTON", "STUDIOGAST", "STUDIOGÄSTE", "STUDIOGÄSTEN", "STUDIOGASTS", "THEMEN", "THEMA", "SCHWERPUNKTTHEMEN"}
```
Prevents host name and section headers from being extracted as mononyms.

```python
_RELATION_CUE_PATTERN  # matches: ehefrau, ehemann, mutter, vater, sohn, tochter, ...
_GROUP_DESC_PATTERN    # matches: geschwister, eltern, ehepaar, familie, zwillinge, ...
```

### Confidence Tier System

| `parsing_rule` | `confidence` | Condition |
|----------------|-------------|-----------|
| `single_parenthetical` | 0.95 | One name, one parenthetical desc directly after |
| `last_name_parenthetical` | 0.82 | Last name in a multi-name chain gets the parenthetical |
| `surname_primary_no_parenthetical` | 0.68 | Name found via uppercase pattern, no descriptor |
| `group_parenthetical` | 0.70 | Group-style desc (`Familie`, `Eltern`, etc.) assigned to all names |
| `name_without_local_parenthetical` | 0.55 | Name in multi-chain, no relation cue |
| `name_without_local_parenthetical` | 0.45 | Name in multi-chain, WITH relation cue (lower — relation cues indicate not a direct guest) |
| `single_parenthetical_mononym` | 0.62 | Single artist/stage name with parenthetical |
| `legacy_sachinhalt_fallback` | 0.50 | Legacy path (should not appear in current runs) |

### `_extract_sachinhalt(text) → str`
- Pattern: `r"Sachinhalt(.*?)Jugendeignung"` with `DOTALL|IGNORECASE`
- Used only by the legacy fallback path in `extract_person_mentions`

### `_normalize_ws(text) → str`
- Replaces `\n` with space, collapses multiple spaces
- Applied to all text before pattern matching

### `_extract_infos_sections(infos) → list[str]`
**Primary extraction anchor logic:**
1. Normalizes whitespace
2. Searches for `r"(?:Interview(?:\s+und\s+Diskussion)?|Diskussion)?\s*Mark\w*\s+LANZ(?:\s*\([^)]+\))?\s+mit"` (IGNORECASE)
3. If matches found:
   - For each match: extract segment from anchor end to next anchor start (or end of text)
   - Strips `Thema(n):` tails, `(O-Ton)` tails
   - Returns list of cleaned segments
4. If NO matches found: calls `_extract_studiogast_sections(text)` as fallback

### `_extract_studiogast_sections(text) → list[str]`
**Conservative fallback** (only when no LANZ anchor):
- Searches for `\b(?:den\s+)?(?:Studiogast|Studiogäste|Studiogästen|Studiogasts)\b` (IGNORECASE)
- For each cue: extracts segment after cue, strips topic/Jugendeignung/O-Ton tails
- **Conservative gate:** Only returns segment if it contains BOTH `(` and `)` — requires parenthetical pairs
- Returns at most ONE section (breaks after first match)

### `_extract_opening_guest_sections(text) → list[str]`
**Structural fallback** for opening patterns:
Tries 4 patterns in order (first match wins):
1. `r"^(?:O-Ton\s+)?(?:Interview(?:\s+und\s+Diskussion)?\s+)?(?:Mark\w*\s+)?LANZ ... mit\s+"`
2. `r"^(?:O-Ton\s+)?Interview(?:\s+und\s+Diskussion)?\s+"`
3. `r"^(?:O-Ton\s+)?(?:den\s+)?Studiogästen?\s+"`
4. `r"^(?:O-Ton\s+)?(?:dem\s+)?Studiogast\s+"`

If no opening pattern: **last-resort fallback** — if `_SURNAME_PRIMARY_NAME_PATTERN` matches AND text contains `(...)`, returns trimmed segment.

### `_extract_person_rows_from_infos(episode_id, infos) → list[dict]`
Main person-row building function:
1. Calls `_extract_infos_sections(infos)` → primary sections
2. If empty: falls back to `_extract_opening_guest_sections(normalize_ws(infos))`
3. For each section:
   a. Finds all `([^)]+?)\(([^)]+)\)` matches (name-before-paren + paren-content)
   b. For each match: calls `_rule_rows_for_block(episode_id, raw_names, desc, block_text, section)`
   c. If no rows from parenthetical scan: calls `_extract_surname_fallback_rows(episode_id, section)`
4. Returns flat list of all rows

### `_rule_rows_for_block(episode_id, raw_names, desc, block_text, section) → list[dict]`
Assigns confidence tier to each name:
1. Calls `_candidate_names_with_spans(raw_names)` to enumerate names with positions
2. Applies group/multi/last logic to assign `beschreibung` and confidence
3. Checks left window (40 chars before name start) for `_RELATION_CUE_PATTERN`
4. For each name: builds a dict with all 9 `PERSON_MENTION_COLUMNS` fields

### `_extract_surname_fallback_rows(episode_id, section) → list[dict]`
Last-resort: finds names via `_SURNAME_PRIMARY_NAME_PATTERN` with no parenthetical:
1. Strips leading timecodes (`r"^\d{1,2}:\d{2}:\d{2}\s*-\s*..."`)
2. Splits on `\s+über\s+` and `;` to limit scope
3. Returns rows with `parsing_rule="surname_primary_no_parenthetical"`, `confidence="0.68"`, empty `beschreibung`

### `_candidate_names_with_spans(raw_names) → list[tuple[str, int, int, str]]`
Returns `(name, start, end, kind)` where kind is `"surname_name"` or `"mononym"`:
1. Tries `_NAME_PATTERN` first — returns with kind `"surname_name"` if any match
2. If no matches: tries `_MONONYM_PATTERN` with stopword filter — returns with kind `"mononym"`

### `_clean_name(raw_name) → str`
- Normalizes whitespace
- Strips leading relation words (`den`, `dem`, `die`, `der`, `mit`, `und`, `sowie`, family role words, `lebensgefährtin`, etc.) in a loop
- Removes age prefixes like `"34-jährige "`
- Strips leading/trailing ` ,.;:`

### `_is_plausible_person_name(name) → bool`
Rejects:
- Empty string
- Contains `"thema"`, `"themen"`, `"interview"`, `"o-ton"`, `"diskussion"`
- Fewer than 2 parts
- No part with uppercase char(s) AND length ≥ 3

### `_is_plausible_mononym(name) → bool`
Accepts all-uppercase tokens of length ≥ 4 not in `_MONONYM_STOPWORDS` and not containing `"THEMA"`.

### `_is_group_description(desc) → bool`
Tests `_GROUP_DESC_PATTERN` against desc string.

### `_mention_id(episode_id, name, beschreibung) → str`
SHA1 over `"{episode_id}|{name}|{beschreibung}"` → `"pm_{digest[:12]}"`

### `extract_person_mentions(episode_blocks, episodes_df) → DataFrame`
**Preferred path** (when `episodes_df` has `infos` column):
1. Iterates `episodes_df[["episode_id", "infos"]]`
2. Calls `_extract_person_rows_from_infos(episode_id, infos)` per row
3. Deduplicates on `["episode_id", "name", "beschreibung"]`
4. Sorts by `[_episode_order, name, beschreibung, mention_id]`
5. Returns `df[PERSON_MENTION_COLUMNS]`

**Legacy fallback** (when episodes_df lacks `infos`):
- Uses raw `_extract_sachinhalt()` on episode blocks directly
- Produces `parsing_rule="legacy_sachinhalt_fallback"`, `confidence="0.50"`

### `save_person_mentions(df, output_dir) → Path`
Writes `{output_dir}/persons.csv` via `atomic_write_csv()`.

---

## Module: `mention_detection/duplicates.py`  *(agent findings to be integrated)*

### `filter_exact_duplicates_with_report(name, df, output_dir) → tuple[DataFrame, DataFrame, Path, dict]`
Expected behavior (from notebook usage):
- Compares all rows for exact equality across all columns
- Keeps first occurrence
- Writes duplicate rows to `{output_dir}/{name}_duplicates.csv`
- Returns: `(deduplicated_df, duplicate_df, duplicate_path, stats_dict)`
- `stats_dict` contains: `raw_rows`, `kept_rows`, `duplicate_rows`

---

## Module: `mention_detection/publications.py`  *(agent findings to be integrated)*

### `extract_publication_rows_from_text(text) → list[dict]`
Parses `Publikation` blocks from a single episode text block.

### `build_publication_rows(episode_id, parsed_publications) → tuple[str, list[dict]]`
Assigns `episode_id`, `publication_index`, `is_primary` flags.

### `to_publication_dataframe(publication_rows) → DataFrame`
Converts to DataFrame with `PUBLIKATION_COLUMNS` schema.

### `save_publications(df, output_dir) → Path`
Writes `{output_dir}/publications.csv` via `atomic_write_csv()`.

---

## Module: `mention_detection/season.py`  *(agent findings to be integrated)*

### `extract_season_rows(episodes_df) → DataFrame`
Aggregates episodes by `season` column:
- Groups by season label
- Computes `start_time` (min date), `end_time` (max date), `episode_count`
- Assigns `season_id`

### `load_seasons_context()`, `build_seasons_lookup()`, `load_season_targets()`
Downstream helpers for candidate generation phase.

---

## Module: `mention_detection/topic.py`  *(agent findings to be integrated)*

### `extract_topic_mentions(episode_blocks, episodes_df) → DataFrame`
Extracts topic mentions from episode infos text.

### `save_topic_mentions(df, output_dir) → Path`
Writes `{output_dir}/topics.csv` via `atomic_write_csv()`.

---

## Output File Schemas (Complete)

### `data/10_mention_detection/episodes.csv`
14 columns. Sorted by `publikationsdatum` ascending, then `sendungstitel` for ties. `na_position="last"`. One row per episode block from the ZDF archive.

### `data/10_mention_detection/publications.csv`
11 columns. Sorted by episode order (matching episodes.csv), then by `publication_index` within each episode.

### `data/10_mention_detection/seasons.csv`
5 columns. One row per unique season label derived from episodes.

### `data/10_mention_detection/persons.csv`
9 columns. Sorted by `[_episode_order, name, beschreibung, mention_id]`. Deduplicated on `[episode_id, name, beschreibung]`. One row per distinct (episode, name, description) combination.

### `data/10_mention_detection/topics.csv`
8 columns. *(topic sorting to be confirmed by agent)*

### `data/10_mention_detection/*_duplicates.csv`
Mirror schema of their main table. Rows removed by exact-duplicate filtering.

### `data/10_mention_detection/episodes_without_person_mentions.csv`
Episodes that produced zero person rows. Used for TODO-008 triage. *(exact schema to be confirmed by agent)*

---

## Key Design Decisions

**1. Stable IDs via SHA1:** Episode IDs and mention IDs are SHA1 digests of content fields, not auto-increment. This ensures reproducibility across runs — the same input always produces the same ID.

**2. infos field as central hub:** The `infos` field (Sachinhalt→Jugendeignung span) is extracted once in `episode.py` and reused by `guest.py`. This means a failure to extract `infos` cascades to zero guest extraction for that episode.

**3. Precision-first confidence tiers:** Six distinct confidence levels encode how certain the extraction is. Downstream users can filter by confidence threshold. Confidence is stored as string to avoid float formatting issues in CSV.

**4. No gender, no category:** The notebook's TODO cell documents that mention categorization (guest vs topic-mention vs incidental) and gender inference are explicitly NOT implemented. The existing schema has no `mention_category` field (TODO-004).

**5. Deduplication is exact-match only:** `filter_exact_duplicates_with_report` removes only perfectly identical rows. Near-duplicate person mentions (same person, slightly different description phrasing) survive into downstream phases.

**6. Atomic writes everywhere:** All CSV writes go through `atomic_write_csv()` from `io_guardrails.py`, which writes to a temp file then renames — preventing partial-write corruption.

---

## Open Issues Affecting This Phase

| ID | Severity | Location | Description |
|----|----------|----------|-------------|
| TODO-009 | HIGH | `episode.py:_extract_info_block()` line 65 | EPISODE 363 loses `infos` — `Jugendeignung` marker may be missing from text |
| TODO-008 | HIGH | `guest.py` + triage list | 13 episodes produce no person rows after all fallbacks |
| TODO-001 | HIGH | `11_mention_detection.ipynb` cell 3 | Cross-archive duplicate episodes not caught by row-level dedup |
| TODO-004 | MEDIUM | `config.py`, `guest.py` | No `mention_category` field |
| TODO-010 | MEDIUM | `guest.py` | `Familie NAME (given1, given2)` not reconstructed to full names |
| TODO-002 | MEDIUM | Downstream (`person.py`) | Umlaut/ß normalization in matching path |
| TODO-003 | MEDIUM | `guest.py:_clean_name` | Abbreviation normalization not centralized |
