# Phase Analysis: Pre-Phase & Phase 1

> Part of the phase-by-phase analysis pass.  
> See [PHASE_ANALYSIS_INDEX.md](PHASE_ANALYSIS_INDEX.md) for the full index.

---

## Pre-Phase: Text Extraction

### Purpose
Converts raw ZDF archive PDFs into canonical `*.pdf_episodes.txt` text dump files stored in `data/01_input/zdf_archive/`.

### Status
**Complete / Skippable.** Pre-exported `.pdf_episodes.txt` files already exist for all four time ranges. This phase only needs to run if new PDFs are added.

### Files

#### [10_text_extraction.ipynb](../speakermining/src/process/notebooks/10_text_extraction.ipynb)
Entry-point notebook. 4 sections:
1. Project setup
2. Input discovery (which PDFs exist)
3. PDF-to-text conversion via `pdfplumber`
4. Roundtrip validation

#### [text_extraction/text.py](../speakermining/src/process/text_extraction/text.py)
- `split_episode_text_dump(raw_text)` — splits a pre-exported dump into raw episode blocks using `--- EPISODE N ---` markers and `=` * 50 separators.
- `load_episode_blocks_from_txt(path)` — reads one `.pdf_episodes.txt` file.
- `load_episode_blocks_from_many(paths)` — loads episodes from all four archive files preserving order.
- `extract_text_from_pdf(pdf_path)` — uses pdfplumber for per-page text extraction. Optional.
- `assemble_episode_blocks_from_pdf(pdf_path)` — assembles full episode blocks from raw PDF using page counters (`Seite N von M`). Optional fallback.
- `write_episode_text_dump(episode_blocks, path)` — writes canonical text dump format.
- `convert_pdf_to_episode_text_dump(pdf_path, output_path)` — end-to-end PDF → text dump pipeline.

### Known Issues / Open Tasks
- None. This phase is complete and stable.

### Input Files
```
data/01_input/zdf_archive/Markus Lanz_2008-2010.pdf_episodes.txt
data/01_input/zdf_archive/Markus Lanz_2011-2015.pdf_episodes.txt
data/01_input/zdf_archive/Markus Lanz_2016-2020.pdf_episodes.txt
data/01_input/zdf_archive/Markus Lanz_2021-2024.pdf_episodes.txt
```

### Output Files
Same as inputs (created by PDF conversion, already exist).

---

## Phase 1: Mention Detection

### Purpose
Parses archive text into structured mention tables covering:
- Episodes (episode_id, metadata, infos block)
- Publications (broadcast dates, programs)
- Seasons (aggregated from episodes)
- Persons / Guests (name, description, confidence, parsing_rule)
- Topics

Writes all outputs to `data/10_mention_detection/`.

### Status
**Actively running but has known bugs.** Phase 1 is the most critical upstream phase — its quality directly determines everything downstream.

### Files

#### [11_mention_detection.ipynb](../speakermining/src/process/notebooks/11_mention_detection.ipynb)
The primary runtime entry point for Phase 1. 5 sections:

**Section 1 — Project Setup:** Repo root discovery, sys.path wiring.

**Section 2 — Input Discovery:** Loads the four `.pdf_episodes.txt` paths from `DEFAULT_PDF_TXT_INPUTS`.

**Section 3 — Episode and Season Extraction:**
- `load_episode_blocks_from_many()` → all episode text blocks
- `extract_episode_and_publication_rows()` → episodes_raw_df + publications_raw_df
- `extract_season_rows()` → seasons_raw_df
- `filter_exact_duplicates_with_report()` applied to all three
- Saves `episodes.csv`, `publications.csv`, `seasons.csv`

**Section 4 — Mention Extraction:**
- `extract_person_mentions()` → persons
- `extract_topic_mentions()` → topics
- `filter_exact_duplicates_with_report()` on both
- Saves `persons.csv`, `topics.csv`
- **ToDo cell present** in notebook (TODO-004 gender inference; TODO-004 mention categories)

**Section 5 — Quantitative Validation:**
Comprehensive validation cells for all five tables covering row counts, confidence distributions, top persons, top topics, rule distributions, and date coverage.

#### [mention_detection/config.py](../speakermining/src/process/mention_detection/config.py)
Defines all phase paths and output contract column names:
- `EPISODE_COLUMNS` (14 columns including `infos`)
- `PERSON_MENTION_COLUMNS` (9 columns including `parsing_rule`, `confidence`, `confidence_note`)
- `PUBLIKATION_COLUMNS` (11 columns)
- `TOPIC_MENTION_COLUMNS` (8 columns)
- `SEASON_COLUMNS` (5 columns)
- `DEFAULT_PDF_TXT_INPUTS` (4 file names)

#### [mention_detection/episode.py](../speakermining/src/process/mention_detection/episode.py)
Episode extraction logic:
- `_stable_episode_id(title, date_value, fallback_text)` — SHA1-based stable ID
- `_extract_title(text)` — `Sendetitel` line extraction
- `_extract_date(text)` — prefers publication date row, fallback regex
- `_extract_archivnummer(text)` — Archivnummer extraction
- `_extract_prod_nr_beitrag(text)` — Prod-Nr format `NNNNN/NNNNN`
- `_extract_tc_range(text)` — TC timecode extraction
- `_extract_info_block(text)` — **KEY FUNCTION**: extracts `Sachinhalt ... Jugendeignung` span. The `infos` field is the primary input to guest extraction.
- `_season_string(staffel, title, date_value)` — derives season string from year
- `extract_episode_and_publication_rows(episode_blocks)` — main extraction loop; returns `(episodes_df, publications_df)`

**~~Bug site for TODO-009 (EPISODE 363):~~ RESOLVED (2026-04-22):** `_extract_info_block()` now uses a multi-terminator regex `Sachinhalt(.*?)(Jugendeignung|Bearbeiter|Autor/|Kategorie|Schlagwörter|$)` so episodes whose text ends with a different section delimiter (or none) still yield a populated `infos` field. All 2,036 episodes now have non-empty `infos` in notebook output.

#### [mention_detection/guest.py](../speakermining/src/process/mention_detection/guest.py)
Guest/person extraction — the most complex module in Phase 1.

**Extraction Pipeline:**
1. `_extract_infos_sections(infos)` — primary path using `Mark\w*\s+LANZ ... mit` anchor
2. `_extract_studiogast_sections(text)` — conservative fallback for `Studiogast/Studiogästen` cues (requires parenthetical pairs)
3. `_extract_opening_guest_sections(text)` — handles opening patterns like `Interview LANZ mit`, `Studiogäste`, `O-Ton ...`
4. `_extract_surname_fallback_rows(episode_id, section)` — last-resort extraction without parenthetical descriptors

**Name Matching Patterns:**
- `_NAME_PATTERN` — TitleCase firstname + UPPERCASE surname
- `_MONONYM_PATTERN` — all-caps single token (artist names)
- `_SURNAME_PRIMARY_NAME_PATTERN` — broader, allows non-parenthetical context

**Confidence Tiers:**
| Rule | Confidence |
|------|-----------|
| `single_parenthetical` | 0.95 |
| `last_name_parenthetical` | 0.82 |
| `surname_primary_no_parenthetical` | 0.68 |
| `group_parenthetical` | 0.70 |
| `name_without_local_parenthetical` | 0.45–0.55 |
| `single_parenthetical_mononym` | 0.62 |
| `legacy_sachinhalt_fallback` | 0.50 |

**Key gap for TODO-008 (13 unresolved episodes):** Episodes without a LANZ anchor and without Studiogast cues, or episodes missing a parenthetical block entirely, produce no rows. The `_extract_opening_guest_sections` fallback covers many of these but requires uppercase surname pattern + parenthetical.

**Key gap for TODO-010 (split family names):** The module currently has no logic to detect `Familie NAME (given1, given2, ...)` group patterns and reconstruct full names. The `_is_group_description` check only guards against attaching group-level descriptions.

**Key gap for TODO-002 (umlaut normalization):** `_is_plausible_person_name` checks for uppercase chars in each part, which correctly accepts `THEVEßEN`, but the _matching_ against Wikidata names downstream does not have normalization. The normalization gap is in `candidate_generation/person.py` not here.

#### [mention_detection/season.py](../speakermining/src/process/mention_detection/season.py)
- `extract_season_rows(episodes_df)` — derives season rows from aggregated episode data
- `load_seasons_context()`, `build_seasons_lookup()`, `load_season_targets()` — for downstream use

#### [mention_detection/topic.py](../speakermining/src/process/mention_detection/topic.py)
- `extract_topic_mentions()`, `save_topic_mentions()` — extracts and persists topic mentions

#### [mention_detection/publications.py](../speakermining/src/process/mention_detection/publications.py)
- `extract_publication_rows_from_text()`, `build_publication_rows()`, `to_publication_dataframe()`, `save_publications()` — extract and standardize publication metadata

#### [mention_detection/duplicates.py](../speakermining/src/process/mention_detection/duplicates.py)
- `filter_exact_duplicates_with_report()` — detects exact duplicates, saves duplicate report, returns deduplicated df + stats

#### [19_analysis.ipynb](../speakermining/src/process/notebooks/19_analysis.ipynb)
Optional lightweight inspection notebook over Phase 1 outputs. Provides confidence-aware checks.

### Output Contract (data/10_mention_detection/)

| File | Columns | Purpose |
|------|---------|---------|
| `episodes.csv` | 14 cols (episode_id, sendungstitel, infos, ...) | One row per episode |
| `publications.csv` | 11 cols (publikation_id, date, program, ...) | One row per broadcast publication |
| `seasons.csv` | 5 cols (season_id, season_label, ...) | One row per season |
| `persons.csv` | 9 cols (mention_id, name, beschreibung, confidence, ...) | One row per person mention |
| `topics.csv` | 8 cols (mention_id, topic, confidence, ...) | One row per topic mention |
| `*_duplicates.csv` | mirror of main schema | Exact duplicates removed before write |
| `episodes_without_person_mentions.csv` | episodes with no person rows | For TODO-008 triage |

### Current Scale (from notebook output)
- Seasons: 17
- Episodes: ~2,036
- Publications: ~2,542
- Persons: ~10,381 (mention rows, not unique persons)
- Topics: ~10,713

### Open Tasks for Phase 1

| ID | Priority | Description |
|----|----------|-------------|
| ~~TODO-009~~ | ~~HIGH~~ | ~~EPISODE 363 infos parsing gap~~ — **RESOLVED 2026-04-22**: multi-terminator regex fix in `_extract_info_block` |
| TODO-008 | HIGH | 13 episodes still produce no guest rows — triage `episodes_without_person_mentions.csv` |
| TODO-001 | HIGH | Cross-archive duplicate episodes (same episode in multiple txt files) not deduplicated before write — `filter_exact_duplicates_with_report` only catches row-level exact dups, not content-hash dups |
| TODO-004 | MEDIUM | No `mention_category` field distinguishing guest/topic-person/incidental mentions |
| TODO-002 | MEDIUM | Umlaut/ß normalization in candidate matching path |
| TODO-003 | MEDIUM | Abbreviation normalization in descriptions |
| TODO-010 | MEDIUM | Split family names (Familie NAME) not reconstructed |
| (open) | MEDIUM | Misspelling cluster identification; add `name_cleaned` column |

### Key Interdependencies
- Phase 1 `persons.csv` feeds Phase 2 candidate generation (person matching)
- Phase 1 `episodes.csv` `infos` field is the primary guest extraction source
- Phase 1 `episodes.csv` feeds Phase 31 alignment (`zdf_episodes`)
- Phase 1 `persons.csv` feeds Phase 31 alignment (`zdf_persons` — 10,381 rows)
- Fixing TODO-001 (dedup) will change row counts in all downstream phases
- Fixing TODO-009 (EPISODE 363) will add previously missing person rows
