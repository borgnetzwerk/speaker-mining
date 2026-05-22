# T15: Clean Up Statistical Analysis Scripts in src/process/analysis/

Three Python scripts were placed in `speakermining/src/process/analysis/` on 2026-05-21
without adequate content review. They contain genuine pipeline-quality analysis logic,
but carry paper/review framing that makes them misleading as repository modules.

## Current state of each file

### `statistical_tests.py` (982 lines)

**What it actually does:**
- Loads canonical persons from `dedup_persons.csv` and fetches P21/P569 via the live
  `entity_access` cache (same method as `50_analysis.ipynb`)
- Runs 6 analyses: age-by-gender (Mann-Whitney U + Welch's t), gender appearance bounds,
  Wikidata selection-bias quantification, Step 3.1.1 alignment precision, dedup strategy
  breakdown, unresolved person characterization
- Writes results to `Path(__file__).parent / "results.json"` → **currently points to src/**

**What is wrong:**
- Module docstring: "Reviewer-requested quantitative analyses for Speaker Mining paper"
- All analysis functions labeled "R1-1", "R1-2b", "R3-1" etc. (reviewer shorthand)
- `OUT_JSON = Path(__file__).parent / "results.json"` writes into `src/` (wrong)
- Usage path in docstring: `documentation/ToDo/2026-05-15_Speaker_Mining_Paper/review/code/...` (deleted)
- One comment says "PAPER CORRECTION REQUIRED" — no longer relevant

**What it should be:**
A module named `statistical_analysis.py` (or keep `statistical_tests.py`) with:
- Docstring: "Statistical analysis of Speaker Mining dataset: age distributions, gender
  trends, Wikidata coverage bias, and alignment precision"
- Functions renamed: `analysis_age_by_gender` → stays; "R1-1" section header → "Age Distribution by Gender"
- `OUT_JSON` → `DATA / "50_analysis/all/statistical_summary.json"` (or similar)
- All "paper" and "reviewer" references removed

---

### `gender_trend_analysis.py` (480 lines)

**What it actually does:**
- Long-running temporal analysis of male guest share over time
- Exhaustive Mann-Whitney split search to detect tipping point (data-driven, not hardcoded)
- Monthly-granularity CUSUM changepoint detection
- Per-show Spearman trend breakdown across 10 configured shows
- Imports `load_person_properties_from_cache`, `load_episode_premiere_years` from
  `statistical_tests` (same directory import)

**What is wrong:**
- Docstring: "R1-2 Gender Gap Trend Analysis — long-running component"
- Usage path in docstring: deleted location
- `OUT_JSON` writes to `Path(__file__).parent / "results_gender_trend.json"` → **src/**
- Depends on `statistical_tests.py` via directory-relative import — this coupling works
  only when both files are in the same directory

**What it should be:**
- Docstring: "Temporal analysis of gender representation in guest appearances over time"
- `OUT_JSON` → proper data output path
- Import from `statistical_tests` should be explicit relative import (`.statistical_tests`)
  once both are part of the analysis package

---

### `episode_date_range.py` (57 lines)

**What it actually does:**
- Calls `compute_meta_statistics(REPO)` (already in `meta_statistics.py`) and extracts
  the episode date range subset
- Writes result to `Path(__file__).parent / "results_episode_date_range.json"` → **src/**

**What is wrong:**
- This is largely redundant: `meta_statistics.py` already computes and returns these
  values as part of its full output
- Output path writes into `src/`
- Docstring usage path is stale

**What it should be:**
- Evaluate: is this standalone script needed, or is the date range already covered by
  `meta_statistics.py`? If redundant, deprecate and delete; if useful as a quick CLI
  summary, keep but fix output path and decouple from a specific file location.

---

### `results.json` / `results_episode_date_range.json` — RESOLVED

`results_episode_date_range.json` — deleted. Episode date range is already documented
in `documentation/data_reference.md` with source verification.

`results.json` — renamed to `documentation/statistical_analysis_results.json`. Kept as
a committed reference document: it contains p-values, medians, effect sizes, and bias
estimates from one pipeline run (2026-05-15) that cannot easily be re-derived without
running the pipeline. Until the scripts are cleaned up and can be re-run cleanly, this
file is the only accessible record of these computations.

---

## Precomputed results summary (from results.json)

Key values to preserve regardless of file location:
- Gender-age Mann-Whitney U: p < 10⁻¹⁸⁷, rank-biserial r = 0.268, male median age 54 vs female 49
- Gender trend tipping year: 2021, pre-mean 68.9% male, post-mean 62.3% male (p = 0.00044)
- Wikidata alignment Step 3.1.1 HIGH precision: see results.json R3_1_alignment_precision
- Unresolved characterization: see results.json R1_4_unresolved

---

## Actions (code scope — deferred)

1. Rewrite module docstrings in `statistical_tests.py` and `gender_trend_analysis.py`
2. Replace "R1-*" / "R3-*" section labels with descriptive names throughout
3. Fix `OUT_JSON` paths in all three scripts to write to `data/50_analysis/`
4. Evaluate `episode_date_range.py` — keep or fold into `meta_statistics.py`
5. Decide on committed reference copy of `results.json` (documentation vs. data)
6. Once cleaned up, update `__init__.py` for the analysis module to expose these functions
7. Create `51_statistical_analysis.ipynb` (or extend `50_analysis.ipynb`) to call them
