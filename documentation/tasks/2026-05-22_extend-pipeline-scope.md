# extend-pipeline-scope

* priority: low
* scope: pipeline
* legacy-id: TODO-035

## Summary

The current pipeline is scoped to Markus Lanz archive files only; `DEFAULT_PDF_TXT_INPUTS` and `ZDF_ARCHIVE_DIR` hardcode that path. Extending to other shows requires parameterized input discovery and show-specific parsing configuration.

## Evidence

`speakermining/src/process/notebooks/11_mention_detection.ipynb` cell `d4f55fab`, `speakermining/src/process/mention_detection/config.py`.

## Definition of done

1. Input discovery is parameterized so that a different show can be processed by changing a config value, not code.
2. At least one additional show archive is processed successfully end-to-end through Phase 1.
3. Show identity is propagated as a column in all Phase 1 output CSVs.
