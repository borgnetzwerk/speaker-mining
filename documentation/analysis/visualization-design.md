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

## Visualization Layout Rules

### Layout

- Bars must dominate the chart area. Labels go on the left, legends go at the bottom (horizontal, up to two rows if needed). No right-side legends that compress bar space.
- Default to horizontal stacked bar charts wherever applicable. Vertical stacked bar charts with inline labels force readers to rotate their view. Exception: timelines (left-to-right expected) and any chart where the X axis is inherently temporal.
- For cross-show comparisons, use 100%-stacked horizontal bar charts: each bar = one show, segments = property values summing to 100%.
- For cross-property comparisons (Appearances vs. Unique Guests), use dual-subplot layout: Appearances LEFT, Unique Guests RIGHT.

### Color

- Every visualization module must load colors from `ColorRegistry`. No module may define its own `_PALETTE`, `_UNKNOWN_COLOR`, or `_OTHER_COLOR` constants. `ColorRegistry` is the only source of color assignments across the entire pipeline.
- Legend sort order: highest-count item on top.

### Labels

- File naming convention: every output file must include BOTH the property PID and a shortened property label (≤25 chars, spaces → underscores). Pattern: `{chart_type}_{pid}_{short_label}.png`.
- Long axis labels and legend labels must be broken at word boundaries. Enforce a maximum character count per line.
- Section numbering in the notebook should reflect logical sequence, not organic growth.

### Unknown / Other Treatment

- Unknown and Other must NOT share bar space with meaningful values. The highest meaningful bar gets 100% of bar width. Unknown/Other appear as a separate annotation, footnote, or visually distinct section — never as a competing segment.
- Three-line "no data" breakdown:
  - `N guest appearances of N unique persons` (total)
  - `no property data on N appearances of N unique persons` (Tier 1+2 guests with no claim for this property)
  - `no Wikidata entry on N appearances of N unique persons` (Tier 3+4 guests)

### Export

- Dual export contract: PNG + PDF. PNG is the preferred format for GitHub rendering.
- Caching: checksum-based skip logic via `.viz_cache.json` sidecar. Skip only when input checksum is unchanged, the output exists, AND the output checksum matches. Validate the full output bundle (PNG + PDF), not just the PNG.
