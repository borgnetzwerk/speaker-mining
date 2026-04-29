# Open Tasks Triage — Phase 5 Focus
> Created: 2026-04-29  
> Principle: if it does not benefit Phase 5 analysis before 2026-05-03, it is deferred.

---

## Available Data Sources

Before triaging tasks, a map of what exists on disk and is immediately usable.

### Primary source of truth
| File | What it is |
|------|-----------|
| `data/31_entity_disambiguation/manual/reconciled_data_summary.csv` | Authoritative person records: alignment_unit_id, wikidata_id, fernsehserien_de_id, mention_id, canonical_label, match_confidence, match_tier, etc. Produced by manual OpenRefine reconciliation. |

### Rich raw data (from v3 Wikidata pipeline — unaffected by v4 issues)
| File | What it is |
|------|-----------|
| `data/31_entity_disambiguation/raw_import/episodes.csv` | Episode list with metadata |
| `data/31_entity_disambiguation/raw_import/persons.csv` | Person records from all sources |
| `data/31_entity_disambiguation/raw_import/broadcasting_programs.csv` | Show/programme records |
| `data/31_entity_disambiguation/raw_import/triples.csv` | Wikidata triple graph (subject, predicate, object) |
| `data/31_entity_disambiguation/raw_import/episode_guests_normalized.csv` | Normalized guest-episode links |
| `data/31_entity_disambiguation/raw_import/episode_metadata_normalized.csv` | Episode dates, titles |
| `data/31_entity_disambiguation/raw_import/episode_broadcasts_normalized.csv` | Episode broadcast/publication dates |
| `data/31_entity_disambiguation/raw_import/wikidata_persons_normalized.csv` | Wikidata properties for persons (v3) |
| `data/31_entity_disambiguation/raw_import/wikidata_roles_normalized.csv` (via normalized/) | Role-class hierarchy (v3) |
| `data/31_entity_disambiguation/aligned/aligned_persons.csv` | Merged person records across sources |
| `data/31_entity_disambiguation/aligned/aligned_episodes.csv` | Merged episode records |

### v4 Wikidata output (current state — may be incomplete due to v4 issues)
| File | What it is |
|------|-----------|
| `data/20_candidate_generation/wikidata/projections/core_persons.json` | `{QID: raw_wikidata_entity_doc}` — full claims (P21 gender, P106 occupation, P102 party, etc.) |
| `data/20_candidate_generation/wikidata/projections/core_episodes.json` | Episodes with Wikidata claims (currently sparse — v4 run incomplete) |
| `data/20_candidate_generation/wikidata/projections/core_series.json` | Series with claims |
| `data/20_candidate_generation/wikidata/projections/core_organizations.json` | Organizations with claims |
| `data/20_candidate_generation/wikidata/projections/core_broadcasting_programs.json` | Broadcasting programs with claims |

**Note:** v4 output files (`core_*.json`) may be incomplete. Where v4 data is missing, fall back to the v3 raw_import files via `data/31_entity_disambiguation/raw_import/`. The F25 entity access API (`entity_access.py`) can supplement with network calls for specific QIDs when needed.

---

## Open Tasks Triage

### Immediately needed for Phase 5 ✅

#### TODO-019 — Complete guest catalogue (add unmatched canonical entities)
- **Why now:** The current `guest_catalogue.csv` has only 640 rows; 8,976 canonical entities exist. Phase 5 analysis over guests must include all canonical persons, not just Wikidata-matched ones.
- **Action:** Build the catalogue from `reconciled_data_summary.csv` (authoritative). Wikidata properties come from `core_persons.json` where available, via `entity_access.get_cached_entity_doc(wikidata_id)` otherwise. Persons without a Wikidata match still appear with `canonical_label` and `cluster_size` only.

#### TODO-039 — Role-based classification (replaces "moderator exclusion")
- **Why now:** Persons in non-guest roles (moderators, production staff, editorial staff) will skew all guest statistics if not separated. Must be classified before any result is produced.
- **Action:** Implement data-driven role detection via `guest_role` field in `episode_guests_normalized.csv`. Survey all distinct `guest_role` values; map each to `guest`, `moderator`, `staff`, or `incidental`. A person is a moderator for a show if they appear in that show's episodes with role "Moderation" — not globally excluded. When Markus Lanz appears as a guest in another show, he is classified `guest` for that episode. `MODERATOR_QIDS` is an override for edge cases only. See `03_design_spec.md` §2.1 for the full role separation spec.

#### TODO-040 — Audit guest classification (Elon Musk case)
- **Why now:** If topic-mentioned persons are systematically in the guest catalogue, every distribution chart is wrong. This must be checked before publishing any result.
- **Action:** Trace Elon Musk (check for his QID in catalogue), trace back to Phase 1 source row. Take a random sample of 20 entries and verify. Document verdict. If systematic misclassification is found, raise a blocker before proceeding with analysis.

#### TODO-027 — Propagate mention_category (guest vs. incidental)
- **Why now:** Phase 5 analysis should operate only on guests, not on incidentally mentioned persons. The analysis design in `00_immutable_input.md` explicitly distinguishes guest instances from other mentions.
- **Action:** Verify that `mention_category` flows from `episode_guests_normalized.csv` into the final catalogue. If it does not, derive it from the episode-guest link table: any person linked as a guest to a relevant episode is a guest; others are incidental.

#### TODO-020 — Occupation subclustering via P279 + grouped bar charts
- **Why now:** The design spec (`03_design_spec.md` C3) specifies P279 subclustering as **required**, not optional. Flat occupation lists are the fallback only if hierarchy data is unavailable. The `04_analysis_angle_structure.md` defines the hierarchy as function type F5.
- **Action:** Use Phase 2 class walk output to group occupation QIDs under their top-level classes. Implement F5 (Sunburst + Sankey) for occupation hierarchy. See TASK-A02 in `open-tasks.md`.

#### TODO-025 — Hierarchy visualizations for Phase 5 (re-scoped from Wikidata notebook)
- **Why now:** The patterns from `21_wikidata_visualization.ipynb` (Sunburst, Sankey, tree view) are exactly what Phase 5 occupation analysis requires. Previously marked as "Notebook 21 work" — reassessed: these diagrams are required Phase 5 outputs.
- **Action:** Implement in `50_analysis.ipynb`, not `51_visualization.ipynb`. See TASK-A02 in `open-tasks.md` for scope and outputs.

#### TODO-032 — Page rank node visualization (re-scoped from notebook 51)
- **Why now:** Node-graph page rank visualization is needed as a Phase 5 output. Previously marked as "not blocking first results" — reassessed: required.
- **Action:** Implement node-graph visualization in `50_analysis.ipynb`. See TASK-A03 in `open-tasks.md`.

#### TODO-033 — Document gender scope limitation (sample vs. population)
- **Why now:** Must accompany every published gender distribution chart. The design spec (C1) already references it as a required caveat. Cannot publish any gender output without this documentation.
- **Action:** Add a documented caveat section to the analysis output (or `analysis_summary.json`) stating that results describe the sample of invited guests, not the population; self-selection and booking biases are not controlled for.

---

### Deferred — post-deadline (2026-05-03) ⏳

| TODO | Title | Reason for deferral |
|------|-------|-------------------|
| TODO-036 | Fix Phase 31/32 orchestration drift | Phase 31/32 refactoring; no Phase 5 analysis blocked |
| TODO-037 | Create CLAUDE.md / AGENT.md | Workflow quality; does not affect analysis output |
| TODO-018 | Integrate authoritative reconciliation CSV | Depends on externally produced CSV not yet received; integration logic already implemented — drop file and re-run when received |
| TODO-017 | Reduce aligned_*.csv column footprint | Requires re-running Phase 31; no Phase 5 analysis blocked |
| TODO-034 | Fix instances.csv dual-write | Phase 2/31 architecture; Phase 5 can use raw_import files directly |
| TODO-038 | Wikidata Node Integrity Pass performance | Phase 21 investigation; no notebook re-run planned before deadline |
| TODO-041 | Respect time-sensitive Wikidata claims (start/end dates) | Correctness improvement; current analysis can use snapshot properties with documented caveat (see TODO-033) |
| TODO-043 | Align hydration config with relevancy config | Phase 2 architecture |
| TODO-044 | Wikidata v4 conceptual rework | Already deferred; v4 fixes tracked in Wikidata investigation docs |
| TODO-035 | Extend pipeline to other shows | Phase 1 scope change |
| TODO-021 | Predictive analytics (frequent set / association rule mining) | Requires stable guest catalogue first |
| TODO-005 | Clarify institution extraction responsibility | Architecture documentation |
| TODO-006 | Define reproducible gender-framing analysis methodology | Requires stable analysis first |
| TODO-007 | Define merge strategy for role/occupation/position | Modeling decision; not blocking |
| TODO-042 | Fix roles projection (P279 vs P31) | Requires Phase 2 re-run |

---

### Medium-priority — include if time permits 🕐

| TODO | Title | Dependency |
|------|-------|-----------|
| TODO-022 | Compare to prior work (Arrrrrmin, Spiegel, Omar) | Requires stable guest catalogue |
| TODO-023 | Dataset overview and pipeline statistics | Any time; mostly counting |
| TODO-030 | Compile pipeline findings for paper | Documentation task; any time |

---

## Data Access Strategy

For Phase 5, data is loaded in priority order:

1. **`reconciled_data_summary.csv`** — authoritative person-episode-source links (canonical IDs, wikidata_id, fernsehserien_de_id, match confidence)
2. **`core_persons.json`** — raw Wikidata claims for Wikidata-matched persons (gender, occupation, party, birthdate, etc.)
3. **`data/31_entity_disambiguation/raw_import/`** — episode metadata, broadcast dates, guest-episode links (v3 data, stable, unaffected by v4 issues)
4. **`entity_access.get_cached_entity_doc(qid, repo_root)`** — runtime supplementation for QIDs not covered by the above

When `core_persons.json` is missing a QID that appears in `reconciled_data_summary.csv`, call `entity_access.ensure_basic_fetch(qid, repo_root)` to retrieve at minimum labels and P31/P106/P21 claims.
