# Analysis Initialization — Open Tasks

Tasks specific to the Phase 5 analysis design and implementation. For pipeline-wide tasks, see `documentation/ToDo/open-tasks.md`.

---

## TASK-A01 — Meta-level structure for analysis angles
**Priority:** Immediate — prerequisite for implementation  
**Status:** ✅ Resolved — see `04_analysis_angle_structure.md`

What was missing was a document that finds the right solution to: a) capture, b) document, and c) scale the full space of analysis angles properly. The current combinations in `03_design_spec.md` (C1–C8) are now structured through the property type taxonomy in `04_analysis_angle_structure.md`.

**Core insight (resolved):** Properties are classified into four types (A: categorical multi-value hierarchical, B: categorical single-value, C: continuous/numeric, D: temporal), each mapping to generic parameterized functions (F1–F5). Gender is treated as categorical (Type B) — the value set is enumerated from data, never hardcoded as binary. New analyses are added by identifying property type + function type, then calling the generic function with appropriate parameters.

---

## TASK-A02 — Hierarchy visualizations for occupation/role data
**Priority:** Immediate  
**Status:** Open  
**Links:** Builds on TODO-025 patterns; implements in `50_analysis.ipynb` (not `51_visualization.ipynb`)

The patterns developed in `21_wikidata_visualization.ipynb` (Sunburst, Sankey, hierarchy view) are exactly what Phase 5 needs for occupation and role data. These were prematurely deferred — they are required now.

**Required outputs:**
1. Sunburst diagram of occupations — one combined (all shows), one per talk show; 5% "other" cutoff for subclasses; innermost ring = top-level occupation classes
2. Sankey diagram of occupation hierarchy — same scope rules as sunburst
3. Hierarchy view of occupations and roles
4. All diagrams exported as PNG + PDF to `data/40_analysis/visualizations/`

**Reference:** `speakermining/src/process/notebooks/21_wikidata_visualization.ipynb` as learning set. Multi-parent strategy needed for subclasses with multiple superclasses (primary-parent assignment or proportional count split).

---

## TASK-A03 — Page rank node visualization for Phase 5
**Priority:** Immediate  
**Status:** Open  
**Links:** Builds on TODO-032 patterns; implements in `50_analysis.ipynb`

A node-graph visualization of page rank is needed for Phase 5 analysis outputs:
1. Node graph for all person instances (nodes sized/colored by rank score)
2. Node graph for all classes
3. Combined view

All exported as PNG + PDF to `data/40_analysis/visualizations/`.

---

## TASK-A04 — Property value statistics table (generic pattern)
**Priority:** Immediate  
**Status:** Open

A generic function that produces a per-value statistics table for any property:

| Property value | min/episode | max/episode | mean over episodes | std dev | median | episode % without | total appearances | unique persons |
|---|---|---|---|---|---|---|---|---|

This pattern applies to occupation, gender, age, party, and any other property. The same function parameterized by column name produces all variants.

**Interesting derived analyses:**
- Where is the gap between `unique` and `total` largest? (repeat-invite bias)
- How many episodes have zero women? Zero men? (representation gaps)
- Where is the median of "how many values does one person have" == 1, and what are the outlier multi-value cases? (e.g. singer+songwriter combinations)

---

## TASK-A05 — Additional analysis angles (time-permitting)
**Priority:** Time-permitting  
**Status:** Open

Additional analysis types to implement after the core C1–C8 set:

**Subset dominance analysis:**  
Which values of property A explain the over-presence of a value from property B? Example: if removing politicians from the guest list drops the journalist share from 80% to 5%, that subset is load-bearing for the journalist statistic. Also: identify individuals who over-represent their group (one female scientist invited 100× while others are invited 5×).

**Cross-show guest presence:**  
Which guests appear across multiple shows vs. only one? Which are over-concentrated in one show relative to others? Which are balanced?

**Career arc patterns:**  
Identify guest trajectory types (provisional terminology):
- "Shooting star": many invitations in quick succession, rarely before or after
- "Evergreen": frequently invited over a long time span

**Property co-occurrence:**  
Which property value combinations are most common (e.g. journalist+politician, singer+songwriter)? Predictive analysis: does having property value X predict property value Y?
