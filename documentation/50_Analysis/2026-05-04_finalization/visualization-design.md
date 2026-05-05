# Visualization Boundary Design

This note captures the expected design for analysis visualizations in Phase 5.

## Core Rule

The notebook orchestrates the analysis flow, but it does not build figures inline.
Plot construction, layout decisions, exports, and chart-specific table shaping live in `speakermining/src/process/analysis/` modules.

## Why This Matters

These dashboard outputs are reused under multiple configurations. When the notebook owns chart logic, it becomes harder to rerun the same analysis with different scopes, filters, or output directories without duplicating code.

Moving the visualization logic into modules gives us:

1. Reusable entry points for repeated notebook runs.
2. A single place to change chart styling and export rules.
3. Clear separation between data preparation and presentation.
4. Easier validation of chart generation outside the notebook.

## Current Module Contract

The notebook should call module functions such as:

- `build_guest_frequency_pareto_outputs(...)`
- `build_source_coverage_dashboards(...)`

Those helpers are responsible for:

- building the figures,
- writing the CSV/PNG/PDF/HTML artifacts,
- returning the generated tables for downstream notebook steps.

The notebook should only:

- provide the already-prepared analysis frames,
- choose the output directories,
- display summary text,
- pass outputs into later analysis steps.

## Reuse Expectations

The dashboard helpers should remain safe to call more than once in the same session, and they should accept different output roots or scope labels without needing notebook edits. That keeps the design aligned with the repository coding principles and the phase output contract.