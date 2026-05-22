# T01: Extract Visualization Principles from visualization_references/

`documentation/ToDo/visualization_references/` contains three reference collections
that inform `documentation/visualizations/visualization-principles.md`. Some extraction
has already happened. This task is to complete the extraction and document what was learned.

All folders are gitignored (`documentation/ToDo/*/*`) — no git impact.

---

## What each sub-folder contains and why it's here

### `2025-scicom-ki-survey/` — Stakeholder cluster visualization reference
Survey analysis for the SciCom Wiki stakeholder study. Contains:
- Cluster PDFs: `Cluster_0–3_n_*_scale.pdf`, `Stakeholder_Clusters_Side_by_Side.pdf`,
  `Merged_Stakeholder_Clusters_Analysis.pdf`, `Merged_Stakeholder_Clusters_by_Role.pdf`
- UEQ (User Experience Questionnaire) analysis: `ueq.pdf`
- Platform ranking: `platformRanking.pdf`

**Visualization reference value:**
- How to visualize stakeholder clusters in a 2D space (scale PDFs)
- Side-by-side cluster comparison layouts
- UEQ score presentation (benchmark comparison format)
- These inform how Speaker Mining's analysis results could be presented to different audiences

**What to extract:**
- Open the cluster PDFs and note: color encoding, layout choices, label placement
- Add to visualization-principles.md under "Audience-Oriented Visualization" or a new
  "Layout and Comparison" section if applicable

---

### `Lanz-und-Precht/` — Predecessor project: episode analysis and visualization
Exploratory NLP + episode matching project for the Lanz & Precht podcast. Contains:
- Analysis notebooks: `analysis.ipynb`, `analysis_advanced.ipynb`, `theme_detection.ipynb`
- Word statistics outputs: `word_statistics.csv`, `word_statistics_no_stopwords.csv`
- YouTube matching data in `01_manual/`

**Visualization reference value:**
- `analysis.ipynb` and `analysis_advanced.ipynb` contain charts (wordclouds, word
  frequency plots, episode statistics) that show how the domain was visualized before
  the current pipeline existed
- These show what kinds of questions were asked first (word frequency, phrase occurrence,
  speaker identification) and how results were presented
- The approach here (Whisper transcripts + NLP) is different from the current pipeline
  (structured metadata + Wikidata) — the contrast is itself informative

**What to extract:**
- Open `analysis_advanced.ipynb` and note any visualization patterns worth preserving
  (chart types used, color choices, how results were labeled)
- Add any relevant principles to visualization-principles.md
- Consider one paragraph in `documentation/background.md` explaining the precursor
  approach and why the pipeline evolved toward structured metadata instead

---

### `Scientific knowledge fit for society Evaluation/` — Likert scale visualization reference
User evaluation study with Likert-scale charts. Contains:
- Likert charts as PNG/PDF pairs for 5 questions
- Python scripts: `likertA1-A5.py`, `_evaluation.py`, `example.py`
- Survey results: `results-survey325837.csv`

**Visualization reference value:**
- The Likert chart style (diverging stacked bars or similar) is a direct reference for
  how Speaker Mining could present property coverage, reconciliation rates, or quality
  tier distributions
- The Python scripts show how to generate this style programmatically

**What to extract:**
- Open one of the PNG files and note: chart style, color palette, label format
- If the Likert style is relevant for Speaker Mining's quality tier visualization, add
  a principle or example reference to visualization-principles.md

---

## Process

1. Open each reference collection and note what visualization patterns are present
2. Compare against current `documentation/visualizations/visualization-principles.md`
3. For each pattern not yet captured: add a principle, example reference, or design note
4. For `Lanz-und-Precht/`: decide if a background note is warranted
5. After extraction is complete: the folders can be archived or deleted (all gitignored)

## Acceptance criteria

- `visualization-principles.md` updated with any patterns found in these references
  that are not yet captured
- `documentation/background.md` updated if Lanz-und-Precht yields a worthy context note
- Decision documented: which folders were found useful and which were not, and why

## Outcome (2026-05-22)

**Scientific knowledge fit for society Evaluation**: Likert-scale diverging stacked bar chart pattern extracted → added as "Diverging Stacked Bar Charts — Likert / Quality-Tier Style" section to `documentation/visualizations/visualization-principles.md`.

**Lanz-und-Precht**: Notebooks (`theme_detection.ipynb`, `analysis_advanced.ipynb`) read in full. This is NOT a background.md predecessor — it is a parallel NLP exploration project using a different source (the Lanz & Precht podcast, not a talk show). However the analysis techniques it demonstrates are directly applicable to Speaker Mining if transcripts are available. Five future tasks raised: TODO-052 through TODO-056 in `documentation/open-tasks.md`.

**2025-scicom-ki-survey**: Cluster PDFs unviewable (PDF-only format). Low priority: stakeholder clustering is not a current Speaker Mining visualization need.

**Disposition**: Extracted / Partial. `visualization_references/` can be deleted (gitignored).
