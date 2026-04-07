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

## WDT-012 Countries are Organizations
First, we thought Nodes that should not expand are being expanded.
Cell 18 produced the following output during the node_integrity:expansion:

[node_integrity:expansion] heartbeat: processed=524/1045 expanded=524 network_queries_expansion=635
[node_integrity:expansion] example: expanded seed Q1446020: +1 qids, network_queries=8
[graph_seed:Q183] Network calls used: 50 / unlimited elapsed=58.9s rate=50.98/min
[graph_seed:Q183] Network calls used: 100 / unlimited elapsed=118.9s rate=50.45/min
[graph_seed:Q183] Network calls used: 150 / unlimited elapsed=179.0s rate=50.29/min
[graph_seed:Q183] Network calls used: 200 / unlimited elapsed=239.2s rate=50.16/min
[graph_seed:Q183] Network calls used: 250 / unlimited elapsed=299.3s rate=50.12/min
[graph_seed:Q183] Network calls used: 300 / unlimited elapsed=359.4s rate=50.09/min
[graph_seed:Q183] Network calls used: 350 / unlimited elapsed=419.5s rate=50.06/min
[node_integrity:expansion] heartbeat: processed=532/1045 expanded=532 network_queries_expansion=1016
[node_integrity:expansion] example: expanded seed Q183: +1 qids, network_queries=369
[node_integrity:expansion] heartbeat: processed=537/1045 expanded=537 network_queries_expansion=1071
[node_integrity:expansion] example: expanded seed Q203453: +1 qids, network_queries=16
[graph_seed:Q30] Network calls used: 50 / unlimited elapsed=58.9s rate=50.93/min
[graph_seed:Q30] Network calls used: 91 / unlimited elapsed=127.3s rate=42.90/min
[node_integrity:expansion] heartbeat: processed=550/1045 expanded=550 network_queries_expansion=1205
[node_integrity:expansion] example: expanded seed Q30: +1 qids, network_queries=92

Both Q183 and Q30 are countries (Germany and the USA). Both have connections to our broadcasting programmes, but are not instances of our core classes. They should not have been allowed to expand. There is likely something wrong with the expansion logic being applied here. Once again:
A node must meet all of the following requirements:
* Be an instance of a core class
* Have a direct link (direct neighbor) to an instance of a core class that has a direct link (is a direct neighbor) of a specified broadcasting programm
Thus, only instance of a core class that have a link of max length 2 to one of our broadcasting programmes should be allowed to expand.
* Q183 and Q30 are instances of country, which should not permit them to expand. 

I have checked the respective instance.csv and found the likely error:
Both are considered instances of core-classes:
* country (Q6256)
* political territorial entity (Q1048835)
* administrative territorial entity (Q56061)
* organization (Q43229)

id,class_id,class_filename,label_de,label_en,description_de,description_en,alias_de,alias_en,path_to_core_class,subclass_of_core_class,discovered_at_utc,expanded_at_utc
Q30,Q6256,,Vereinigte Staaten,United States,Staat in Nordamerika,country located primarily in North America,America|Amerika|Staaten|Staaten von Amerika|U. S.|U. S. A.|U.S.|U.S.-Amerika|U.S.A.|US|US-Amerika|USA|United States|United States of America|V. S.|V. S. A.|V.S.|V.S.A.|VS|VSA|Vereinigte Staaten von Amerika|die Staaten|us|usa,America|Merica|Murica|U. S.|U. S. A.|U.S.|U.S. of America|U.S.A.|US|US of A|US of America|USA|United States of America|the States|the U.S.|the U.S. of A|the U.S. of America|the U.S.A.|the US|the US of A|the US of America|the USA|the United States|the United States of America|us|usa,Q6256|Q1048835|Q56061|Q43229,True,2026-04-02T21:21:35Z,
Q183,Q6256,,Deutschland,Germany,Staat in Mitteleuropa,country in Central Europe,BR Deutschland|BRD|Bundesrepublik Deutschland|DE|DEU|FRG|GER|de,BRD|DE|DEU|FRG|Federal Republic of Germany|GER|de,Q6256|Q1048835|Q56061|Q43229,True,2026-04-02T21:06:36Z,

This is not an error, but a feature: countries are organizations. That makes sense and is thus valid.