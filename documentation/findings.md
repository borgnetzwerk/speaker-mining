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

## F-009: Wikidata Language-Default Metadata Fallback Gap (Closed)

- Observation: some Wikidata entities provide labels, descriptions, and aliases only under language-default buckets (for example `mul`) rather than explicit `de`/`en` fields.
- Example: `Bernd Saur (Q133025759)` can miss `de`/`en` metadata while still carrying usable default-language metadata.
- Impact before fix: rows could lose meaningful text metadata when strict language-key lookup returned empty values.
- Resolution implemented:
  - labels/descriptions now fall back to first available language/default value when requested language fields are empty,
  - alias extraction now also includes language-default/global alias buckets in addition to language-specific buckets.
- Validation: `pytest speakermining/test/process/wikidata/test_materializer_language_fallback.py -q` passes.
- Related tracker item: `TODO-012`.

## F-010: Notebook 21 Lacked Run-Spanning Network Decision Log

- Observation: runtime heartbeat output in notebook 21 improved short-term visibility, but there was no append-only event stream across runs for major network-related decisions.
- Impact: difficult to analyze long-run behavior patterns (budget pressure, cache-hit ratio drift, backoff frequency, call-rate changes) and to compare behavior between notebooks.
- Requirement: add one append-only notebook event log that records all major network decisions and calls with timestamp, phase, rate-limit/budget context, and outcome.
- Design reference: `documentation/notebook-observability.md`.
- Related tracker item: `TODO-013`.

## F-011: JSONL Migration Potential Beyond Notebook Events (Historical Assessment)

- Historical status: this section captures pre-migration analysis context from 2026-04-01 and is retained for traceability.
- Non-normative notice: this section is not the active runtime contract for Wikidata v3.
- Current source of truth: use `documentation/Wikidata.md`, `documentation/contracts.md`, and `documentation/workflow.md` for active runtime policy.

- Observation: JSONL is attractive for append-only, event-like artifacts (for example `raw_queries` event records and checkpoint timelines), but replacing all JSON/CSV artifacts with JSONL would introduce mismatches for snapshot/state and tabular-contract outputs.
- Evidence snapshot (2026-04-01): repository currently contains `csv=335`, `json=16061`, `jsonl=1`; `data/20_candidate_generation/wikidata/raw_queries` alone has `3755` JSON files (~`181 MB` total).
- Primary opportunity: reduce file-count overhead and improve stream-style analysis for append-only event families.
- Primary risk: monolithic JSONL append files can become large hot spots during runtime and need corruption handling and rotation/indexing policy to remain operationally safe.
- Preliminary direction: keep CSV for stable tabular contracts, keep JSON objects/lists for mutable state snapshots, and evaluate JSONL selectively for append-only event flows (starting with `raw_queries` as a candidate) with staged rollout and validation.
- Dedicated analysis artifact: `documentation/context/jsonl_potential.md`.
- Related tracker item: `TODO-014`.

## F-012 Countries are Organizations (Resolved)

Observation:
- Countries such as Germany and the United States can legitimately resolve through the `organization` core-class branch in this registry.
- That does not indicate a broken expansion rule by itself; it is an expected consequence of the configured core-class chain and the class-lineage policy.

Resolution:
- Keep `organization` as a core class.
- Treat country rows that resolve via valid subclass chains as expected, not as an error condition.
- Use the node-integrity and class-resolution contracts to decide eligibility, not the English label alone.

## F-013 Even Fernsehserien.de has houndreds of episodes without guests.
Among the first episodes of Markus Lanz, there are episodes which have no guests listed on fernsehserien.de. Some examples:
* https://www.fernsehserien.de/hart-aber-fair/folgen/1-folge-1-653676
* https://www.fernsehserien.de/hart-aber-fair/folgen/10-folge-10-653957
* https://www.fernsehserien.de/hart-aber-fair/folgen/100-folge-100-654047
* https://www.fernsehserien.de/hart-aber-fair/folgen/101-folge-101-654048
* https://www.fernsehserien.de/hart-aber-fair/folgen/102-folge-102-654049
* https://www.fernsehserien.de/hart-aber-fair/folgen/103-folge-103-654050
* https://www.fernsehserien.de/hart-aber-fair/folgen/104-folge-104-654051
* https://www.fernsehserien.de/hart-aber-fair/folgen/105-folge-105-654052
* https://www.fernsehserien.de/hart-aber-fair/folgen/106-folge-106-654053
* https://www.fernsehserien.de/hart-aber-fair/folgen/107-folge-107-654054
* https://www.fernsehserien.de/hart-aber-fair/folgen/108-folge-108-654055
* https://www.fernsehserien.de/hart-aber-fair/folgen/109-folge-109-654056
* https://www.fernsehserien.de/hart-aber-fair/folgen/11-folge-11-653958
* https://www.fernsehserien.de/hart-aber-fair/folgen/110-folge-110-654057
* https://www.fernsehserien.de/hart-aber-fair/folgen/111-folge-111-654058
* https://www.fernsehserien.de/hart-aber-fair/folgen/112-folge-112-654059
* https://www.fernsehserien.de/hart-aber-fair/folgen/113-folge-113-654060
* https://www.fernsehserien.de/hart-aber-fair/folgen/114-folge-114-654061
* https://www.fernsehserien.de/hart-aber-fair/folgen/115-folge-115-654062
* https://www.fernsehserien.de/hart-aber-fair/folgen/116-folge-116-654063
* https://www.fernsehserien.de/hart-aber-fair/folgen/117-folge-117-654064
* https://www.fernsehserien.de/hart-aber-fair/folgen/118-folge-118-654065
* https://www.fernsehserien.de/hart-aber-fair/folgen/119-folge-119-654066
* https://www.fernsehserien.de/hart-aber-fair/folgen/12-folge-12-653959
* https://www.fernsehserien.de/hart-aber-fair/folgen/120-folge-120-654067