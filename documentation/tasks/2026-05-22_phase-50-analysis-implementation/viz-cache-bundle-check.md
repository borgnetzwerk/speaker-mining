# viz-cache-bundle-check

* priority: medium
* scope: pipeline
* legacy-finding: F-06 (2026-05-11 review)

## Summary

The visualization cache validity check in `50_analysis.ipynb` only tests for the existence of a `.png` file. If a chart was previously generated but the `.pdf` or `.html` outputs were not produced (or were deleted), the cache hit suppresses re-generation and the full output bundle is silently incomplete.

## Evidence

Source: `documentation/archive/50_Analysis/2026-05-11_review/code_update_plan.md` (F-06) and `findings.md`.

The cache check reads: `if png_path.exists(): return`. It should verify the complete output bundle (PNG + PDF + HTML) before skipping regeneration.

## Definition of done

1. Cache validity check tests for all required output files in the bundle (PNG, PDF, HTML), not just PNG.
2. A missing PDF or HTML file triggers full chart regeneration regardless of PNG presence.
