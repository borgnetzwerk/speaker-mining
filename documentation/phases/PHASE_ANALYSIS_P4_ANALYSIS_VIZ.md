# Phase Analysis: Phase 4, Analysis & Visualization

> Part of the phase-by-phase analysis pass.  
> See [PHASE_ANALYSIS_INDEX.md](PHASE_ANALYSIS_INDEX.md) for the full index.

---

## Phase 4: Link Prediction

### Purpose
Derive relation-level outputs connecting entities after deduplication is complete. This is the final automated pipeline phase, consuming Phase 32 outputs to produce a knowledge graph with links.

### Status
**Not implemented. Placeholder only.**

### Files

#### [40_link_prediction.ipynb](../speakermining/src/process/notebooks/40_link_prediction.ipynb)
Contains only:
```
# Placeholder Notebook: 40 Link Prediction
This notebook is a temporary placeholder and is not implemented yet.
Intended future task: derive relation-level outputs for data/40_link_prediction from finalized upstream manual decisions.
```

No Python modules exist for Phase 4.

### What Needs to Be Built

The core purpose of Phase 4 is to answer: **which guests appeared in which episodes, with what roles?**

After Phase 32 deduplication produces `canonical_persons.csv` and after Phase 31 provides aligned episodes, Phase 4 should:

1. **Guest-Episode links:** For each episode, list canonical person entities as guests
2. **Person-Role links:** Map ZDF descriptions to canonical role/occupation terms
3. **Person-Organization links:** Extract affiliated organizations from descriptions
4. **Page-rank computation:** Compute a page-rank score over the entity graph (episodes → persons, persons → organizations, organizations → roles)

**Inputs from upstream:**
- `data/32_entity_deduplication/canonical_persons.csv`
- `data/31_entity_disambiguation/aligned/aligned_episodes.csv`
- `data/31_entity_disambiguation/aligned/aligned_persons.csv`
- `data/20_candidate_generation/wikidata/projections/triples.csv` (120,930 edges)

**Proposed outputs:**
```
data/40_link_prediction/
    guest_episode_links.csv    # canonical_person_id, episode_id, confidence
    person_properties.csv      # all Wikidata properties per canonical person
    page_rank_scores.csv       # entity_id, entity_class, page_rank_score
```

### Page-Rank Validation
Per the `speaker_mining_code.md` specification: "Validation: Instances such as 'ZDF' or 'Markus Lanz' should be very big."

This provides a clear ground-truth check — if these entities don't rank high, something is wrong with the graph wiring.

---

## Analysis

### Purpose
Compute property distribution statistics over the full guest catalogue.

### Status
**✓ IMPLEMENTED 2026-04-23** — `41_analysis.ipynb` is complete and producing outputs.

### Files

#### [41_analysis.ipynb](../speakermining/src/process/notebooks/41_analysis.ipynb)

Three-section notebook:

| Section | Description |
|---------|-------------|
| 4a | Guest catalogue build — merge Phase 32 canonical entities with Wikidata properties → `data/40_analysis/guest_catalogue.csv` |
| 4b | Property distribution — gender/occupation/party/age statistics over 640 Wikidata-matched persons |
| 4c | Page-rank computation — 37,072 nodes / 59,295 edges (taxonomy predicates excluded); → `data/40_analysis/pagerank_persons.csv` |

### Actual Output (2026-04-23)

**`data/40_analysis/guest_catalogue.csv`** — 640 rows (Wikidata-matched canonical entities only)

Key columns: `canonical_entity_id`, `wikidata_id`, `cluster_size`, `label_de`, `gender`, `occupations`, `party`, `birthyear`, `first_appearance_year`, `last_appearance_year`, `median_appearance_year`, `episode_count`, `age_at_first_appearance`, `age_at_median_appearance`

**`data/40_analysis/pagerank_persons.csv`** — 640 rows

Top results: Markus Lanz (0.000844), Sandra Maischberger (0.000528), Maybrit Illner (0.000434) — validates graph wiring.

### Design Notes

- Page-rank predicate filter: `EXCLUDE_PREDICATES = {P31, P279, P1889, P460, ...}` — prevents class-hub dominance by ontology concepts
- Guest catalogue has 640 rows, not 8,976: the join with Wikidata is the limiting factor; unmatched entities lack property data. See **TODO-019** for the complementary unmatched-persons list.

### Open Tasks

| ID | Priority | Description |
|----|----------|-------------|
| TODO-019 | high | Complete guest catalogue: add ~8,336 unmatched canonical entities to a separate list |
| TODO-020 | medium | Extended gender distribution: grouped bars + occupation subclustering |
| TODO-021 | low | Predictive analytics: identify what predicts other properties (gender, age) |
| TODO-022 | medium | Compare to prior work: Arrrrrmin, Spiegel, Omar datasets |

---

## Visualization

### Purpose
Visualize all analysis results.

### Status
**✓ IMPLEMENTED 2026-04-23** — `51_visualization.ipynb` is complete and producing outputs.

### Files

#### [51_visualization.ipynb](../speakermining/src/process/notebooks/51_visualization.ipynb)

Plotly-based visualization notebook; 5 chart types:

| Chart | Description |
|-------|-------------|
| Page-rank bar | Top 20 persons by page-rank score |
| Gender stacked bars (by individual) | Gender breakdown per occupation, each unique person counted once |
| Gender stacked bars (by occurrence) | Gender breakdown per occupation, each appearance counted separately |
| Age histogram | Age at first appearance |
| Appearance count histogram | Episodes per canonical person |

All charts exported to `documentation/visualizations/` as **HTML** (interactive) and **PNG** (scale=2x via kaleido).

**Implementation stack:** Plotly Express + kaleido for export; colorblind-friendly palette; Windows path handling for kaleido.

### Open Tasks

| ID | Priority | Description |
|----|----------|-------------|
| TODO-020 | medium | Extended gender distribution: grouped (side-by-side) bars combining unique and occurrence views |
| TODO-023 | medium | Dataset overview: dashboard-like visualizations per core class |
| TODO-024 | medium | Visualization principles document: formalize from existing work, review `ToDo/visualization_references` |
| TODO-025 | medium | Ingest `21_wikidata_vizualization.ipynb` visualizations + 5 targeted improvements |

---

## Deferred Items (from speaker_mining_code.md)

These are explicitly documented as potentially out of scope or advised against:

### Einschaltquoten (Viewing Figures)
- Have some PDFs on Einschaltquoten
- Requires separate data source pipeline
- **Deferred:** requires significant new data extraction work

### Gender Inference from Description Text
**Advised against** in `speaker_mining_code.md`:
> "infering gender from a description is dangerous"
> "We can identify female gender from '-in' ending, as well as from terms like 'Ehefrau' — but the inverse, a word not ending on '-in', is not automatically clear."
> "It is advised not to conduct this kind of mining."

**Status:** Do not implement. Use Wikidata P21 only.

### Description Semantification
- Match free-text descriptions to canonical Wikidata concepts
- Example: "Gärtner" in description → occupation = "Gärtner" in Wikidata
- **Deferred:** High noise, requires NLP/semantic matching; complex with abbreviation variants

### Forbidden Features Catalogue / Data Privacy Catalogue
- A governance catalogue for sensitive properties (P.o.C., age, gender)
- Internally accessible only, with institution backing + contract requirement
- References: Wikidata P8274, Q44601380, Q44597997
- **Future Work:** Governance/legal, not code

---

## Key Interdependencies (Phase 4 + Analysis + Visualization)

- Phase 4 (link prediction) still placeholder — not yet needed for current analysis outputs
- `41_analysis.ipynb` reads Phase 32 `dedup_persons.csv` + `dedup_cluster_members.csv` ✓ (flowing)
- `51_visualization.ipynb` reads `data/40_analysis/guest_catalogue.csv` ✓ (flowing)
- Gender analysis uses **only Wikidata P21** — not description inference (confirmed policy)
- Age computation uses episode `publikationsdatum` via `persons.csv` → `episodes.csv` join chain
- Page-rank uses `triples.csv` from Phase 2 Wikidata (120,930 edges; 37,072 usable after predicate filter)

---

## Current Data State (2026-04-23)

| Data | Location | Rows | Notes |
|------|----------|------|-------|
| Wikidata persons | `projections/instances_core_persons.json` | 640 | 767 properties each |
| Wikidata triples | `projections/triples.csv` | 120,930 | 59,295 usable after predicate filter |
| Phase 32 canonical entities | `data/32_entity_deduplication/dedup_persons.csv` | 8,976 | 640 Wikidata-matched; 8,336 unmatched |
| Guest catalogue | `data/40_analysis/guest_catalogue.csv` | 640 | Wikidata-matched only — see TODO-019 |
| Page-rank scores | `data/40_analysis/pagerank_persons.csv` | 640 | Top: Markus Lanz, Maischberger, Illner |
| Visualizations | `documentation/visualizations/` | 5 chart types | HTML + PNG |
