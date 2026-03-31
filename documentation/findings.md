# Findings

Aggregated findings for this repository.

## Scope

This file consolidates analysis notes that were previously scattered across multiple markdown files.

For open or solved work tracking, use `open-tasks.md`.

## F-001: Episode Overlap Across Archive Files

- Observation: same episode titles can appear in multiple archive text files (notably across 2011-2015 and 2016-2020 source boundaries).
- Example: `ep_f9b9ff6dab61` was observed as cross-file overlap.
- Impact: inflated extraction volume and potential downstream skew unless deduplicated before final write.
- Related tracker item: `TODO-001`.

## F-002: Acronym/Abbreviation Normalization Gap

- Observation: person descriptions include abbreviation variants that should be normalized.
- Examples:
  - `ehem.` / `ehem` -> `ehemalige(r)`
  - `Vors.` / `Vors` -> `Vorsitzende(r)`
- Impact: weaker matching and noisier description fields.
- Related tracker item: `TODO-003`.

## F-003: Umlaut/Eszett Variant Explosion

- Observation: names with umlauts and `ß` can appear in many transliterated forms (`ö -> o/oe/drop`, `ß -> ss/s/drop`).
- Example family: `Peter GRÖßER` variants include `GROSSER`, `GROESSER`, reduced forms, and mixed forms.
- Known concrete case: `Elmar THEVEßEN` vs `Elmar THEVESSEN`.
- Recommendation: deterministic variant generation and/or normalization with explicit test coverage.
- Related tracker item: `TODO-002`.

## F-004: Institution Extraction Design (Deferred/Optional)

- Multi-source strategy documented:
  1. publication program direct match (highest confidence)
  2. episode infos keyword/context matches
  3. person description affiliation extraction
  4. optional topic-derived extraction
- Reported volume uplift vs legacy approach: substantial increase in candidate institution mentions.
- Known limitation: higher false-positive risk for role descriptors and ambiguous mentions without semantic validation.
- Current repository state: institutions are not part of active default Phase 1 output contracts.
- Related tracker item: `TODO-005`.

## F-005: Topic Extraction Ambiguity and Confidence

- Core issue: German comma usage is ambiguous between true list separation and relative clause structure.
- Current extraction design uses confidence tiers by parsing rule and ambiguity heuristics.
- Semicolon-separated explicit labels are highest confidence; cue-based inference is lower confidence.
- Recommendation: continue precision-first defaults and validate comma-splitting classes on samples.

## F-006: Orphan Research Notes (Archived Into Tracker)

The following former one-line notes were represented in the tracker and then archived into this aggregate:

- Gender-framing analysis question around women invitees by role framing.
  - Related tracker item: `TODO-006`.
- Merge identification concept for role/occupation/position/institution.
  - Related tracker item: `TODO-007`.

## F-007: Guest Detection Miss Patterns In Episode Infos

- Observation: episodes without extracted guests cluster into a small set of parser miss patterns.
- Root causes identified on the exported miss list (`episodes_without_person_mentions.csv`):
  - no anchor/cue hit
  - anchor hit but no parenthetical guest pairs
  - missing infos text
  - mononym or quoted-name edge cases
- Primary identifier convention confirmed: guest names are first and foremost identified via uppercase surname patterns (including umlaut and eszett forms).
- Impact: rows with valid guest names can be dropped when host-anchor phrasing differs (`Interview LANZ mit`, `Interview <guest list>`) or when descriptor parentheses are absent.
- Resolution implemented:
  - broader opening section extraction for `Interview ...` and `Studiogast` starts
  - surname-primary fallback extraction when no parenthetical block is present
  - support for mononym/artist-name parenthetical rows and quoted nickname normalization
- Post-change quick validation against the same 31-row miss list: 18 episodes now produce person rows; 13 remain unresolved (mostly documentary summaries or missing infos).
- Context snapshot: `documentation/context/mention-detection-guest-diagnostics-2026-03-27.md`.

## F-008: Wikidata v2 Migration Contract Deviations (Closed)

- Observation: migration evaluation identified contract deviations in raw-event semantics, direct-link tracking, source-step taxonomy, and budget-boundary behavior.
- Resolution implemented:
  - cache-hit/fallback reads no longer emit raw event files,
  - source-step usage aligns with frozen canonical taxonomy,
  - direct-link marking is symmetric for seed-touching edges,
  - seed filtering and materialization path resolution are cache-only (no unbounded network calls).
- Validation: `python -m pytest speakermining/test/process/wikidata -q` passes.
