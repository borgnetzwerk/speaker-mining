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

### 2a · Fix fernsehserien.de Guest Description Row 3 Bug · Hours 16–18

- **Hypothesis:** Lost in CSV write (step 2.1) or CSV-to-episode conversion (step 3.1)
- **Inspect:** `22_candidate_generation_fernsehserien_de.ipynb` + `fernsehserien_de/projection.py`
- **Fix:** Identify row drop, add validation cell

### 2b · OpenRefine Match Storage (disambiguation question) · Hours 18–22

- **Decision:** Add `open_refine_name` column (duplicate of existing name column, renamed)
- **Location:** Step 312 handoff tables in `data/31_entity_disambiguation/`
- **Document:** Update contracts.md + disambiguation specification

### 2c · Complete Step 311 Automated Disambiguation · Hours 20–26

- **Location:** `31_entity_disambiguation.ipynb` + `entity_disambiguation/orchestrator.py`
- **Check:** Person/episode/topic/org/role alignment implementations
- **Fix:** Any incomplete alignment logic per `entity_disambiguation/*.py`
- **Validation:** `quality_gates.py` checks pass

### 2d · Step 312 Manual Reconciliation Spec Review · Hours 24–28

- **Review:** `312_manual_reconciliation_specification.md`
- **Ensure:** Handoff tables are correctly shaped for OpenRefine import
- **Document:** Expected columns, confidence tiers, decision fields

---

## Stage 3 · Phase 32: Deduplication (Hours 28–36)

**Goal:** Implement automated deduplication recommendation notebook (Step 321).

### 3a · Design Deduplication Contract · Hours 28–30

- **Output schema:** What does `32_entity_deduplication.ipynb` produce?
- **Document:** Update `contracts.md` with Phase 32 schema

### 3b · Implement Step 321: Automated Deduplication Prep · Hours 30–35

- **Location:** `32_entity_deduplication.ipynb`
- **Logic:** Compare disambiguation output for near-duplicate persons/entities
- **Use:** Misspelling clusters from Stage 1h as input signal
- **Output:** Deduplication recommendation table with confidence + evidence

### 3c · Validate Against Known Cases · Hours 35–36

- **Check:** Wikidata QID-matched persons against multi-entry persons
- **Document:** Known duplicate examples in findings.md

---

## Stage 4 · Analysis (Hours 36–42)

**Goal:** Property distribution statistics over the full guest catalogue.

### 4a · Build Guest Catalogue · Hours 36–38

- **Input:** Phase 32 output (deduplicated persons)
- **Output:** Flat guest list with all Wikidata properties
- **Location:** `40_link_prediction.ipynb` or new `41_analysis.ipynb`

### 4b · Property Distribution Analysis · Hours 38–41

Per-property statistics (count, %, avg per occupation):
- Gender (from Wikidata P21)
- Age at episode release (birthdate P569 minus episode broadcast date)
- Party affiliation (P102)
- Journalism house affiliation (employer P108 + industry)
- University affiliation (educated at P69)

**Format:** "The average page-rank for a person with property X is …"

### 4c · Page-Rank Computation · Hours 40–42

- **Input:** Phase 2 Wikidata graph (triples)
- **Compute:** Page-rank per entity node
- **Validation:** ZDF and Markus Lanz should rank very high

---

## Stage 5 · Visualization (Hours 42–48)

**Goal:** Visualize analysis results.

### 5a · Page-Rank Graph Visualization · Hours 42–44

- **Class diagram:** All instances, core classes with specific colors, grey otherwise
- **Instance diagram:** No classes; inherit class diagram color logic
- **Page-rank diagram:** Node size proportional to page-rank score

### 5b · Normalized Stacked Bar Charts · Hours 44–47

For each major occupation branch:
- Bar 1 (by individual): unique persons, gender %
- Bar 2 (by occurrence): total guest appearances, gender %
- Caption: "30% of invited researchers were female (individual); 10% of researcher invitations were female (by occurrence)"

### 5c · Export & Documentation · Hours 47–48

- Export all charts to `documentation/visualizations/`
- Add notebook cell with interpretation notes

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
