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
Compute property distribution statistics over the full guest catalogue. Specified in `speaker_mining_code.md`:

> "The average page-rank for a person with property X is ..."
> "Make a list of all guests. Then make a list of all their properties. Then analyze all these properties and make a statistic of their values."

### Status
**Not implemented.** No analysis notebook or module exists. The `19_analysis.ipynb` is limited to Phase 1 confidence checks only.

### What Needs to Be Built

#### New Notebook: `41_analysis.ipynb` (or extend `40_link_prediction.ipynb`)

**Section 1: Guest Catalogue**

Build flat guest list from Phase 32 canonical persons with all Wikidata properties:
```python
# Merge canonical_persons with wikidata_persons.json
# Output: one row per guest with all properties
guests_catalogue = merge(canonical_persons, wikidata_instances)
```

**Section 2: Property Distribution**

For each key Wikidata property, compute statistics:

| Property | Wikidata PID | Analysis |
|----------|-------------|---------|
| Gender | P21 | % male / female / other across all guests and by occupation |
| Date of birth | P569 | Derive age at episode date; histogram |
| Party affiliation | P102 | Distribution of political parties |
| Employer / journalism house | P108 | Major media organizations |
| University / educated at | P69 | Academic institutions |
| Occupation | P106 | Role/occupation distribution |

**Key computation — Age at episode:**
```python
# For each guest-episode pair:
age_at_episode = episode_broadcast_date - person_birthdate
# Use publications.csv for broadcast dates
```

**Expected statistics format:**
```
"The average page-rank for a person with property P21=female is X"
"30% of invited researchers were female (by individual)"
"10% of researcher invitations were female (by occurrence)"
```

**Section 3: Per-Occupation Sub-Analysis**

For each major occupation branch:
- Count unique persons
- Count total appearances (occurrences)
- Gender breakdown (by individual AND by occurrence)
- Average age at first appearance

**Section 4: Page-Rank Statistics**

- Average page-rank by gender
- Average page-rank by occupation
- Average page-rank by party affiliation

---

## Visualization

### Purpose
Visualize all analysis results. Specified in detail in `speaker_mining_code.md`.

### Status
**Not implemented.** No visualization notebook or module exists.
`documentation/visualizations/` exists but only contains the workflow diagram PNG.

### What Needs to Be Built

#### Page-Rank Graph Visualization

**Class diagram:**
- All instances, organized by class
- Core classes (persons, episodes, organizations, etc.) have specific colors
- Other/unknown classes are grey

**Instance diagram:**
- No class labels shown
- Inherits color from class assignment
- Node size proportional to page-rank score
- Validation: ZDF and Markus Lanz nodes should be very large

**Implementation suggestion:**
- Use `networkx` + `pyvis` or `plotly` for interactive graph
- Or `graphviz` / `d3.js` for publication-quality output
- Input: `data/20_candidate_generation/wikidata/projections/triples.csv` (120,930 edges) — may need subsampling for visual clarity

#### Normalized Stacked Bar Charts

**Design specification (from `speaker_mining_code.md`):**

> "Every time there is a bar, make two: One 'by individual', one 'by occurrence'."
>
> "30% of the invited researchers were female. When a researcher was guest, 10% of them were female."
>
> Bar 1 (by individual): each unique person counted once regardless of appearance count.  
> Bar 2 (by occurrence): each guest appearance counted separately.

**Charts to produce:**

1. **Total gender distribution** — all guests, by individual and by occurrence
2. **Gender by occupation branch** — each major occupation category
3. **Age distribution** — histogram at time of episode
4. **Party affiliation distribution** — top N parties
5. **Media house affiliation** — top N journalism organizations
6. **University affiliation** — top N institutions

**Implementation suggestion:**
```python
import matplotlib.pyplot as plt
# or
import plotly.express as px

# Each chart: two bars side-by-side (by_individual, by_occurrence)
# Normalized to 100% (stacked within each bar)
# Color: gender-standard colors or custom palette
```

**Export:**
- Save all charts to `documentation/visualizations/`
- Include both PNG and HTML (interactive) versions

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

- Phase 4 requires Phase 32 canonical persons (not yet built)
- Analysis requires Phase 4 page-rank scores and Phase 2 Wikidata property data
- Visualization requires Analysis outputs
- Gender analysis uses **only Wikidata P21** — not description inference
- Age computation uses `publications.csv` broadcast dates from Phase 1
- Page-rank uses `triples.csv` from Phase 2 Wikidata (already available: 120,930 edges)

---

## Available Data for Analysis (Already Computed)

The following data is already available and can be used immediately:

| Data | Location | Rows | Notes |
|------|----------|------|-------|
| Wikidata persons | `projections/instances_core_persons.json` | 640 | 767 properties each |
| Wikidata triples | `projections/triples.csv` | 120,930 | Graph edges for page-rank |
| ZDF persons | `data/10_mention_detection/persons.csv` | 10,381 | With episode links |
| fernsehserien.de guests | `projections/episode_guests_normalized.csv` | 25,452 | With episode URLs |
| Aligned persons | `data/31_entity_disambiguation/aligned/aligned_persons.csv` | — | Cross-source links |
| Wikidata organizations | `projections/instances_core_organizations.json` | 51 | 881 properties |

Even without Phase 32 deduplication, a preliminary analysis can be conducted directly on `aligned_persons.csv` filtered to `match_tier != unresolved`.
