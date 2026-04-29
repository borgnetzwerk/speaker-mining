# Analysis Angle Structure
> Created: 2026-04-29  
> Status: Active — governs implementation of `50_analysis.ipynb`  
> Resolves: TASK-A01

This document defines the property type taxonomy and the generic function architecture that flows from it. The goal: a small number of parameterized functions that cover all current and future analyses, rather than bespoke code per analysis.

---

## 1. Property Type Taxonomy

Every person attribute falls into one of four types. The type determines which functions apply.

### Type A — Categorical (multi-value, optionally hierarchical)
A person can have **multiple values** simultaneously. Values may be organized into a hierarchy navigable via P279 class walk (Phase 2 output).

**Examples:** occupation (P106), party (P102), employer (P108)  
**Visualization functions:** distribution bar chart, over-time line, cross-tabulation, Sunburst (hierarchy), Sankey (hierarchy), tree view  
**Notes:** Analysis can be run at any level of the P279 hierarchy — top-level aggregate, raw class, or a meaningful intermediate grouping (e.g. "Wissenschaftler" rather than every sub-discipline).

### Type B — Categorical (single-value)
A person typically has **one value**. Treat as categorical — do not assume a fixed set of possible values.

**Examples:** gender (P21), place of birth (P19), nationality  
**Visualization functions:** distribution bar chart, stacked bar, over-time line, cross-tabulation  
**Notes:** Gender specifically must NOT be assumed binary. It is a categorical property whose observed value set happens to be small — but the implementation must enumerate values from data, not hardcode `["male", "female"]`.

### Type C — Continuous / numeric (derived)
Value is a **number on an integer or real scale**, derived from primary data.

**Examples:** age (derived: `premiere_year − birth_year`), cluster_size, appearance_count  
**Visualization functions:** violin plot, histogram buckets (bin width configurable), box plot  
**Notes:** Binning strategy must be explicit and configurable. Year-of-birth precision caveat must be documented in output.

### Type D — Temporal
Value is a **date or year**, used as the analysis axis rather than as a property.

**Examples:** premiere_date, broadcast year  
**Usage:** Always the X-axis in over-time analyses; never analyzed as a property distribution directly.

---

## 2. Analysis Function Type Taxonomy

Five generic function types cover all current Step C analyses and most future extensions.

### F1 — Property distribution
**Question:** How is property X distributed across the guest population?  
**Output:** Table of (value, person_count, appearance_count, pct_by_person, pct_by_appearance)  
**Modes:** all shows combined; per show  
**Applies to types:** A, B  
**Current analyses using F1:** C1 (gender), C3 (occupation), C5 (party)

### F2 — Property distribution over time
**Question:** How does the distribution of property X change year by year?  
**Output:** Table of (year, value, person_count, appearance_count)  
**Modes:** all shows combined; per show  
**Applies to types:** A, B (X-axis is always Type D)  
**Current analyses using F2:** C2 (gender over time)

### F3 — Property cross-tabulation
**Question:** For a given combination of property X and property Y, what are the person counts?  
**Output:** Matrix of (value_X, value_Y, person_count); filtered to top-N values of each  
**Modes:** all shows combined; per show  
**Applies to types:** A × A, A × B, B × B  
**Current analyses using F3:** C4 (gender × occupation), C6 (gender × party), C7 (occupation × party)

### F4 — Continuous distribution
**Question:** What is the distribution of numeric property X?  
**Output:** Histogram buckets or statistical summary (min, max, mean, std, median, per-bucket count)  
**Modes:** all shows combined; per show  
**Applies to types:** C  
**Current analyses using F4:** C8 (age distribution)

### F5 — Hierarchy visualization
**Question:** How do values of a hierarchical property nest within their class tree?  
**Output:** Sunburst diagram, Sankey diagram, or tree view; exportable as PNG + PDF  
**Input:** F1 output + P279 class hierarchy from Phase 2  
**Applies to types:** A (hierarchical only)  
**Current analyses using F5:** C3 extended (occupation Sunburst/Sankey — TASK-A02)

---

## 3. Mapping: Current Analyses → Function Types

| Step | Property | Prop. Type | Function(s) | Notes |
|------|----------|-----------|-------------|-------|
| C1 | gender | B | F1 | Include "unknown" row |
| C2 | gender × time | B × D | F2 | Per year |
| C3 | occupation | A (hierarchical) | F1 + F5 | P279 subclustering required |
| C4 | occupation × gender | A × B | F3 | Top 20 occupations |
| C5 | party | A (hierarchical) | F1 | Snapshot caveat (TODO-041) |
| C6 | party × gender | A × B | F3 | Top 15 parties |
| C7 | party × occupation | A × A | F3 | Top 15 occ × top 10 parties |
| C8 | age | C | F4 | 10-year bins; year-of-birth caveat |

---

## 4. Generic Function Signatures

```python
def analyze_distribution(
    catalogue_df,           # guest_catalogue.csv merged with episode data
    property_col: str,      # column name in catalogue_df (e.g. "gender", "occupations")
    multi_value: bool,      # True for Type A (multiple values per person)
    population: str = "guest",   # filter on role column
    by_show: bool = True,   # also produce per-show breakdown
    top_n: int | None = None,    # limit to top N values; None = all
) -> pd.DataFrame           # (value, person_count, appearance_count, pct_by_person, pct_by_appearance)


def analyze_over_time(
    catalogue_df,
    property_col: str,
    multi_value: bool,
    time_col: str = "premiere_year",
    population: str = "guest",
    by_show: bool = True,
) -> pd.DataFrame           # (year, value, person_count, appearance_count)


def analyze_cross_tab(
    catalogue_df,
    prop_a: str,
    prop_b: str,
    multi_a: bool,
    multi_b: bool,
    population: str = "guest",
    top_n_a: int = 20,
    top_n_b: int = 20,
) -> pd.DataFrame           # pivot: prop_a values × prop_b values → person_count


def analyze_continuous(
    catalogue_df,
    numeric_col: str,       # e.g. "appearance_age"
    bins: int = 10,
    population: str = "guest",
    by_show: bool = True,
) -> pd.DataFrame           # (bin_label, bin_min, bin_max, person_count, appearance_count)


def visualize_hierarchy(
    distribution_df,        # output of analyze_distribution
    hierarchy: dict,        # {child_qid: parent_qid} from Phase 2 class walk
    output_type: str,       # "sunburst" | "sankey" | "tree"
    output_path: Path,
    per_show: bool = True,
) -> None                   # writes PNG + PDF
```

---

## 5. Property Value Statistics Table (TASK-A04)

A generic statistics table applicable to any property, capturing per-value episode-level statistics:

| Property value | min/episode | max/episode | mean | std dev | median | episodes without (%) | total appearances | unique persons |
|---|---|---|---|---|---|---|---|---|

```python
def analyze_property_episode_stats(
    appearances_df,         # occurrence matrix or raw joined data
    property_col: str,
    episode_col: str = "episode_url",
    population: str = "guest",
) -> pd.DataFrame
```

Derived insights from this table:
- `total / unique` gap — measures repeat-invite concentration
- `episodes_without_pct` — measures representation gaps (e.g. share of episodes with no women)
- Rows where median of "values per person" > 1 — multi-value outliers (e.g. singer+songwriter)

---

## 6. Extension Guide

To add a new analysis:
1. Identify the property type (A / B / C / D) for each axis
2. Select the matching function type (F1–F5) or combine two
3. Call the generic function with the appropriate parameters
4. Document in §3 mapping table above
5. Add output file to `03_design_spec.md` §4 output files table

New property types or visualization types that do not fit F1–F5 should be added to §2 of this document before implementation.
