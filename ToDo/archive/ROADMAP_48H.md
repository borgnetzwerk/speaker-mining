# 48-Hour Roadmap: Speaker Mining

> Generated: 2026-04-18  
> Scope: All open items from `speaker_mining_code.md` and `documentation/open-tasks.md`  
> Reference: [speaker_mining_code.md](speaker_mining_code.md) | [open-tasks.md](../documentation/open-tasks.md)

---

## Interdependency Map

```
Pre-Phase (Text) ──► Phase 1 (Mention Detection) ──► Phase 2 (Candidate Gen.)
                            │                                  │
                     [BUG FIXES]                       [already complete]
                            │                                  │
                            └──────────────────────────────────┘
                                                               │
                                                      Phase 31 (Disambiguation)
                                                          [311 automated]
                                                          [312 manual/OpenRefine]
                                                               │
                                                      Phase 32 (Deduplication)
                                                          [misspelling clusters]
                                                          [family name reconstruction]
                                                               │
                                                      Analysis + Visualization
```

**Critical path:** Phase 1 quality → Phase 31 → Phase 32 → Analysis → Visualization

**Parallelizable:** Documentation cleanup can run throughout any stage.

---

## Stage 0 · Documentation & Analysis Pass (Hours 0–4)

**Goal:** Understand the current state of every file before touching code.

| Task | File(s) | Output |
|------|---------|--------|
| Phase-by-phase summary of all .md, .py, .ipynb files | All | `ToDo/PHASE_ANALYSIS_*.md` |
| Index all open issues per phase | `open-tasks.md`, `findings.md` | This roadmap |

**Deliverables:**
- `ToDo/PHASE_ANALYSIS_PRE_P1.md` — Pre-Phase + Phase 1
- `ToDo/PHASE_ANALYSIS_P2.md` — Phase 2 (Wikidata + fernsehserien.de)
- `ToDo/PHASE_ANALYSIS_P31_P32.md` — Disambiguation + Deduplication
- `ToDo/PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md` — Phase 4 + Analysis + Visualization stubs

---

## Stage 1 · Phase 1 Bug Fixes (Hours 4–16)

**Goal:** Fix all known parsing and data quality issues upstream of disambiguation.

### 1a · Critical Bug: EPISODE 363 Parsing Gap (TODO-009) · ✅ DONE 2026-04-22

- **Root cause:** `_extract_info_block()` in `mention_detection/episode.py` only matched up to `Jugendeignung`. EPISODE 363 uses a different section terminator, so `infos` returned empty.
- **Fix applied:** Extended regex terminator set to `(Jugendeignung|Bearbeiter|Autor/|Kategorie|Schlagwörter|$)`. All 2,036 episodes now produce non-empty `infos` in notebook output.
- **Validation:** Notebook output confirms 2,036 episodes with `infos` content; persons: 10,390 rows across 2,025 episodes.

### 1b · Guest Extraction Misses — 13 Episodes (TODO-008) · ✅ TRIAGED 2026-04-22 — all accepted as not_extractable

Triage of `episodes_without_person_mentions_diagnostics.csv`:

| Bucket | Count | Verdict |
|--------|-------|---------|
| `infos_missing` | 3 | Source PDF had no parseable Sachinhalt block. Accept. |
| `section_without_parenthetical_pairs` | 1 | Anchor matched, but infos lists only topics — no names present. Accept. |
| Documentary/travel specials (Kuba!, Russland!, Amerika!, Heiliges Land, Südtirol) | 5 | Prose narration, not studio-interview format. Names exist but in title-case without ALL-CAPS surname. Adding a rule risks false positives across the entire corpus. Accept. |
| Special broadcast events (Das Jahr 2020, Ukraine Abend) | 2 | Collective "Studiogästen" cue, no individual names. Accept. |
| Retrospective interview format (Wieder vereint!, Genscher) | 2 | Title-case names after mid-sentence LANZ anchor — no opening pattern match. Could theoretically extract but ROI is near zero (0.1% of corpus, fernsehserien.de covers these). Accept. |

**No code change. All 13 episodes are genuinely not extractable from the current infos field.** The diagnostics file remains as-is for reference.

### 1c · Archive-Level Episode Dedup (TODO-001) · ✅ ALREADY RESOLVED — verified 2026-04-22

The stable `episode_id = SHA1(title|date|block[:200])` design means identical cross-archive episodes produce identical rows → caught by `filter_exact_duplicates_with_report` (all-column `df.duplicated`). Validation: `ep_f9b9ff6dab61` and `ep_7b029db7a145` both appear in `duplicates_episodes.csv`; notebook shows `raw=2038 → kept=2036`. No code change needed.

### 1d · Umlaut / Eszett Normalization (TODO-002) · ✅ DONE 2026-04-22

- **Added:** `normalize_name_for_matching(name)` in `candidate_generation/person.py` — applies `clean_mixed_uppercase_name` then substitutes ä→ae, ö→oe, ü→ue, ß→ss, then lowercases. Returns a key suitable for comparing ZDF names against Wikidata labels.
- **Tests:** 12 tests in `speakermining/test/process/candidate_generation/test_person.py` — all pass. Covers THEVEßEN/THEVESSEN → same key, GRÖßER handling, all umlaut pairs, NaN/empty edge cases.
- **Note:** The function is exported but not yet wired into the Wikidata matching path (Phase 2b). That wiring is a Phase 31 concern.

### 1e · Abbreviation Normalization (TODO-003) · ✅ DONE 2026-04-22

- **Added:** `_expand_abbreviations(text)` in `mention_detection/guest.py` — applied to `desc` in `_rule_rows_for_block` before storing in `beschreibung`.
- **Rules:** `ehem.`→`ehemalig` (case-insensitive), `stellv.`→`stellvertretend`, `Vors.`→`Vorsitzende(r)`, `Vizepräs.`→`Vizepräsident`, `Präs.`→`Präsident`.
- **Coverage:** 650 `ehem.`, 83 `Vors.`, 69 `stellv.` occurrences in existing persons.csv (notebook re-run will normalize these).
- **Note:** `Prof.`, `MdB`, `MPr` left unexpanded — these are common German titles/initialisms that downstream processes recognise without expansion.

### 1f · Explicit Person Mention Categories (TODO-004) · ✅ DONE 2026-04-22

- **Added:** `mention_category` column to `PERSON_MENTION_COLUMNS` in `config.py` (position 3, after `name`).
- **Logic in `guest.py`:** `"incidental"` when the inter-name segment (text between the previous name's end and the current name's start) contains a relation cue word (`ehemann`, `ehefrau`, `mutter`, `vater`, `tochter`, `ihre`, `ihrem`, etc.); `"guest"` otherwise. Scoped to inter-segment to prevent spill-over from earlier names in a chain.
- **Coverage:** All three code paths updated: `_rule_rows_for_block`, `_extract_surname_fallback_rows`, legacy fallback.
- **Known limitation:** If the relation word (`Tochter`, `Sohn`) is consumed into the name match by `_NAME_PATTERN`, the inter-segment before the match may only contain a pronoun (`seiner`) not in the cue list. These rare cases fall back to `"guest"` conservatively.
- **topic_person deferred:** Requires separate topic-section detection; not yet implemented.

### 1g · Split Family Name Reconstruction (TODO-010) · ✅ TRIAGED 2026-04-22 — deferred (minimal ROI)

Data check: only **2** occurrences of `Familie SURNAME (given1, given2, ...)` in current corpus:
- `Familie LECCE (10-köpfige Familie)` — description gives count, not names → not reconstructable
- `Familie EWERDWALBESLOH (Walter, Corinna und Sohn Leon, ...)` — names present but this is a one-off edge case

With 2 occurrences in 10,390 person rows (0.02%), implementing a dedicated parsing rule is not justified. Accept as `not_extractable` for now. Revisit if new archive files add more Familie entries.

### 1h · Misspelling Cluster Identification (open) · ✅ DONE 2026-04-22

- **Cluster key:** `normalize_name_for_matching()` (added Stage 1d) collapses umlaut variants — `SÖDER`/`SOEDER`, `THEVEßEN`/`THEVESSEN`, `FAßBENDER`/`FASSBENDER` etc. all map to the same key.
- **Scale:** 394 unique match-keys with 2+ raw name forms, covering 2,499 mention rows (24% of corpus). The majority are all-caps vs title-case variants of the same person (see Stage 1f / mention_category discussion) rather than true misspellings.
- **`name_cleaned` column:** provided by `clean_mixed_uppercase_name()` in `candidate_generation/person.py` — already used in the `append_persons_to_episodes` pipeline.
- **No further action needed:** the normalization utilities are in place; cluster-level deduplication belongs in Phase 32 (deduplication notebook), not Phase 1.

---

## Stage 2 · Phase 31: Entity Disambiguation (Hours 16–28)

**Goal:** Complete the automated Step 311 and establish the OpenRefine handoff contract.

### 2a · Fix fernsehserien.de Guest Description Row 3 Bug · ✅ CLOSED 2026-04-22 — Non-Issue

- **Finding:** Both discovered and normalized CSVs have exactly 25,452 rows with zero per-episode discrepancy. Descriptions are correctly split from `<dd><p>ROLE<br>DESCRIPTION</p></dd>` by `_line_parts_from_html()`. Ute Teichert's description confirmed present in Phase 31 aligned output. The 28.3% of rows with empty descriptions genuinely have no description line in source HTML.
- **No code change needed.**

### 2b · OpenRefine Match Storage · ✅ DONE 2026-04-22

- **Added:** `open_refine_name` column to `SHARED_COLUMNS` in `entity_disambiguation/contracts.py` (position after `canonical_label`)
- **Populated in `person_alignment.py`** for all three person row types (ZDF mention rows, fernsehserien-only rows, Wikidata-only rows) — value is `canonical_label.strip().strip("-").strip()` (cleans leading-dash parse artifacts)
- **Effect:** Next notebook re-run will include `open_refine_name` in all aligned CSV outputs; OpenRefine users can use this column directly as the reconciliation query field

### 2c · Complete Step 311 Automated Disambiguation · ✅ DONE 2026-04-23

- **Reviewed:** All five alignment modules (`person_alignment.py`, `episode_alignment.py`, `topic_alignment.py`, `role_org_alignment.py`, `season_alignment.py`)
- **Finding:** All modules are structurally complete. High unresolved rates for topics (10,714/10,714), roles (9,616/9,616), and organizations (51/51) are data-source limitations — Wikidata expansion produced 0 role entities and 1 topic entity — not code gaps.
- **Person alignment:** Produces 31,811 rows across three path types (ZDF mention, fernsehserien-only, Wikidata-only).
- **Episode alignment:** Uses date-backbone matching against fernsehserien.de + Wikidata unique-label fallback.
- **No code changes needed.** Existing unresolved rows carry correct reason codes via `match_strategy="topic_context_only_best_effort"` etc.

### 2d · Step 312 Manual Reconciliation Spec Review · ✅ DONE 2026-04-23

- **Reviewed:** `312_manual_reconciliation_specification.md` (Draft v0.1)
- **`open_refine_name` reference:** Section 4, item 3 already updated to reference the new column as the reconciliation query field.
- **Spec is complete** for the current stage: input files, workflow steps, required human decision columns, and Phase 32 boundary are all defined.
- **Pending:** Sections 5–7 are sufficient; no structural gaps found.

---

## Stage 3 · Phase 32: Deduplication (Hours 28–36)

**Goal:** Implement automated deduplication recommendation notebook (Step 321).

### 3a · Design Deduplication Contract · ✅ DONE 2026-04-23

- **Designed schema:** `dedup_persons.csv` (one row per canonical entity) + `dedup_cluster_members.csv` (membership mapping) + `dedup_summary.json`
- **Documented in `contracts.md`** under new "Phase 32" section
- **Three cluster strategies:** `wikidata_qid_match` (high confidence), `normalized_name_match` (medium), `singleton` (low)
- **Normalization:** `normalize_name_for_matching` applied symmetrically to both sides — compliant with TODO-016

### 3b · Implement Step 321: Automated Deduplication Prep · ✅ DONE 2026-04-23

- **Module:** `speakermining/src/process/entity_deduplication/` (new)
  - `contracts.py` — paths and schema constants
  - `person_deduplication.py` — `build_person_clusters()` — strategy 1 (wikidata_id grouping) + strategy 2 (normalized name grouping) + singletons
  - `orchestrator.py` — `run_phase32()` — loads aligned_persons.csv, runs clustering, writes outputs via atomic_write helpers
  - `__init__.py`
- **Notebook:** `32_entity_deduplication.ipynb` — 10 cells: setup, orchestrator call, summary display, cluster distribution, largest clusters, Wikidata cluster inspection
- **Representative selection:** Prefers rows with non-empty wikidata_id; within ties, prefers best `match_tier` (exact > high > medium > unresolved)

### 3c · Validate Against Known Cases · ✅ DONE 2026-04-23

- **Input:** 31,811 aligned_persons rows → 8,976 canonical entities (71.8% reduction)
- **Wikidata clusters:** 640 — exactly 640 distinct Wikidata persons, avg ~8.6 alignment units/entity. Top: Elmar THEVEßEN (83), Robin Alexander (66), Karl Lauterbach (56)
- **Normalized-name clusters:** 2,968 — persons without Wikidata match grouped by `normalize_name_for_matching` key. Top: Markus Lanz (1,199), Sandra Maischberger (615)
- **Singletons:** 5,368 — persons with no cluster partner
- **Integrity:** all 31,811 alignment_unit_ids covered, no duplicates, 8,976 representatives
- **Note:** `open_refine_name` is empty in current output because Phase 31 notebook has not been re-run yet to include the new column

---

## Stage 4 · Analysis (Hours 36–42)

**Goal:** Property distribution statistics over the full guest catalogue.

### 4a · Build Guest Catalogue · ✅ DONE 2026-04-23

- **Notebook:** `41_analysis.ipynb` (new)
- **Output:** `data/40_analysis/guest_catalogue.csv` — 640 rows (one per Wikidata-matched canonical entity)
- **Columns:** `canonical_entity_id`, `wikidata_id`, `cluster_size`, `label_de/en`, `gender`, `occupations`, `party`, `employer`, `birthyear`
- **Property extraction:** gender from P21 (QID-to-label hardcoded), occupations from P106 (label via instances.csv), party from P102, employer from P108, birthyear from P569

### 4b · Property Distribution Analysis · ✅ DONE 2026-04-23

**Gender (unique persons):** 64.1% male, 35.6% female, 0.3% unknown

**Gender by appearance (cluster_size weighted):** 71.6% male, 28.4% female

→ Male guests are invited ~2.5× more frequently than female guests on average

**Top occupations:** Journalist (258), Politiker (151), Fernsehmoderator (76), Schriftsteller (70), Hochschullehrer (61)

**Top parties:** CDU (51), SPD (51), FDP (21)

### 4c · Page-Rank Computation · ✅ DONE 2026-04-23

- **Input:** 62,179 triples (of 120,930 total; excluded P31/P279/taxonomy predicates that inflate class-hub scores)
- **Graph:** 37,072 nodes, 59,295 edges
- **Output:** `data/40_analysis/pagerank_persons.csv` — 640 person-node scores
- **Top 5:** Markus Lanz (0.000844), Sandra Maischberger (0.000528), Maybrit Illner (0.000434), Frank Plasberg (0.000320), Susan Link (0.000252)
- **Validation:** Markus Lanz ranks #1 as expected (host of the show)

---

## Stage 5 · Visualization (Hours 42–48)

**Goal:** Visualize analysis results.

### 5a · Page-Rank Visualization · ✅ DONE 2026-04-23

- **Chart:** `pagerank_top20.html/.png` — horizontal bar chart with colorscale, top 20 persons
- **Libraries:** plotly + kaleido (installed) for interactive HTML + static PNG output
- **Note:** Full network graph (37k nodes) deferred — pyvis/graphviz not yet installed; bar chart is more readable

### 5b · Normalized Stacked Bar Charts · ✅ DONE 2026-04-23

- **`gender_by_occupation.html/.png`** — gender % by occupation, unique persons (sorted by female %)
- **`gender_by_occurrence.html/.png`** — same, weighted by cluster_size (appearance count)
- **Key finding:** The gap widens with appearances — e.g. Journalist: 37% female persons but fewer female slots
- **Occupations shown:** those with ≥ 20 Wikidata-matched persons

### 5c · Age and Appearance Analysis · ✅ DONE 2026-04-23 (extended scope)

- **`age_distribution.html/.png`** — histogram of age at first appearance, split by gender. Mean ≈ 49 years.
- **`age_by_occupation.html/.png`** — box plots of age by occupation (sorted by median age)
- **`appearance_count_distribution.html/.png`** — how many episodes each guest appears in (median = 3, max = 83)
- **Age data:** 381 of 640 persons have Wikidata P569 birthdate; age computed as `first_appearance_year - birth_year`
- **All charts exported** to `documentation/visualizations/` as interactive HTML (self-contained) + PNG (scale=2x)

---

## Deferred / Future Work (out of 48h scope)

| Item | Reason for deferral |
|------|---------------------|
| Einschaltquoten PDF integration | Requires separate data source work |
| Gender inference from description text | Risk of false inference — documented as inadvisable |
| Description Semantification | Experimental, noisy input |
| Forbidden Features Catalogue | Governance/legal process, not code |
| Institution extraction (TODO-005) | Intentionally deferred; needs architecture decision first |
| Gender-framing analysis methodology (TODO-006) | Depends on analysis results |
| Role/occupation merge strategy (TODO-007) | Depends on deduplication design |

---

## Risk Register

| Risk | Affected Stage | Mitigation |
|------|----------------|------------|
| EPISODE 363 root cause unclear | Stage 1a | Inspect both CSV write and conversion paths independently |
| 13 remaining guest misses may be truly unextractable | Stage 1b | Triage first; accept `not_extractable_from_infos` as valid outcome |
| fernsehserien.de row 3 loss may be in HTML parsing | Stage 2a | Add roundtrip assertion in projection output |
| OpenRefine column naming conflicts existing schema | Stage 2b | Prefix new column `open_refine_*` to avoid collision |
| Deduplication may produce false positives | Stage 3b | Confidence-tiered output; no auto-merge without human sign-off |
| Page-rank computation may be slow on full graph | Stage 4c | Use sparse matrix or NetworkX with budget cap |

---

## Files Created By This Roadmap

| File | Purpose |
|------|---------|
| `ToDo/ROADMAP_48H.md` | This document |
| `ToDo/PHASE_ANALYSIS_PRE_P1.md` | Pre-Phase + Phase 1 detailed analysis |
| `ToDo/PHASE_ANALYSIS_P2.md` | Phase 2 detailed analysis |
| `ToDo/PHASE_ANALYSIS_P31_P32.md` | Phase 31/32 detailed analysis |
| `ToDo/PHASE_ANALYSIS_P4_ANALYSIS_VIZ.md` | Phase 4 + analysis + visualization analysis |
| `ToDo/PHASE_ANALYSIS_INDEX.md` | Index + cross-cutting findings |
