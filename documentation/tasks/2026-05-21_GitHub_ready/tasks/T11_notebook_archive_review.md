# T11: Review Archived Notebooks and Test Coverage of Archive Code

## Archived notebooks (4 tracked files)

```
speakermining/src/process/notebooks/archive/
├── 21_candidate_generation_wikidata_v3_archive.ipynb  ← v3 runtime (paired with _v3_archive/)
├── 50_analysis_v0_5.ipynb                             ← analysis v0.5
├── 50_analysis_v0_archive.ipynb                       ← analysis v0
└── 51_visualization_v0_archive.ipynb                  ← visualization notebook v0
```

### Questions

1. **21_candidate_generation_wikidata_v3_archive.ipynb**: This is the v3 notebook. If T02 (_v3_archive Python code) proceeds with removal, this notebook should be removed at the same time.

2. **50_analysis_v0_5.ipynb and 50_analysis_v0_archive.ipynb**: Two old versions of the analysis notebook. Are these needed for reference or can they be removed once `50_analysis.ipynb` (current) is stable?

3. **51_visualization_v0_archive.ipynb**: The visualization notebook that became `21_wikidata_vizualization.ipynb`. The compliance gaps table in `visualization-principles.md` was originally titled "Compliance Gaps in 51_visualization.ipynb" — this archive notebook is what it referred to.

### Action plan

- Remove `21_candidate_generation_wikidata_v3_archive.ipynb` as part of T02 (coordinate)
- Review if `50_analysis_v0*` notebooks contain anything not in the current `50_analysis.ipynb`; if not, remove
- Remove `51_visualization_v0_archive.ipynb` once compliance gaps from it are verified as addressed or tracked

```bash
git rm speakermining/src/process/notebooks/archive/21_candidate_generation_wikidata_v3_archive.ipynb
git rm speakermining/src/process/notebooks/archive/50_analysis_v0_5.ipynb
git rm speakermining/src/process/notebooks/archive/50_analysis_v0_archive.ipynb
git rm speakermining/src/process/notebooks/archive/51_visualization_v0_archive.ipynb
# Only if the archive/ directory becomes empty:
# git rm -r speakermining/src/process/notebooks/archive/
```

---

## Test files that reference _v3_archive

Before T02 removes the archive code, audit the test suite:

| Test file | Likely dependency |
|---|---|
| `test_migration_v3.py` | v3 migration code — remove with _v3_archive |
| `test_handler_benchmark.py` | `handler_benchmark.py` exists in _v3_archive |
| `test_bootstrap_outputs.py` | check which bootstrap (v3 or v4) |
| `test_notebook_orchestrator_profiles.py` | check if testing v3 or v4 orchestrator |

### Audit command
```powershell
Select-String -Path speakermining/test/ -Pattern "_v3_archive|_v3_|v3_archive" -Recurse
```

## Acceptance criteria

- All archive notebooks either removed or carry a clear "historical reference only" header cell
- No test file imports from `_v3_archive` after T02 executes
