# visualization-reference-library

* priority: medium
* scope: pipeline
* legacy-id: TODO-046

## Summary

No reference collection exists for Phase 5 visualization plot types with minimal runnable example code. Without it, each new visualization risks inconsistent implementation of axes, colors, legends, and accessibility.

## Evidence

Plot types identified: violin plot (age distribution), centered stacked bar chart (Likert scale). `documentation/tasks/visualization_references/Lanz-und-Precht/theme_detection.ipynb` shows a working example for reference.

## Definition of done

1. A reference notebook or module exists at `speakermining/src/process/notebooks/viz_reference.ipynb` (or `data/output/visualization/reference/`) with one cell per plot type.
2. Each cell: dummy data, correct implementation, exported PNG + PDF, documented principles (axis labels, color choices, legend, accessibility).
3. Subtypes are present where nuance exists (e.g. two ways to display grouped bar charts).
4. All Phase 5 visualizations are verifiably consistent with the reference implementations.

## Notes

Immediately relevant for Phase 5 — violin plot needed for age distribution (C8 in design spec), grouped bar chart for gender distributions (C1/C2). Should be created alongside or before the first Phase 5 visualization cell.
