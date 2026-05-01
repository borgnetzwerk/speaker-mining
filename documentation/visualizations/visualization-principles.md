# Visualization Principles

> Related tracker item: TODO-024  
> All charts in `51_visualization.ipynb` and `21_wikidata_vizualization.ipynb` must comply with these rules.

---

## Universal Rules (apply to every chart)

### 1. Color Palette

Use the **Okabe-Ito colorblind-safe palette** (Okabe & Ito 2008). It is safe for all major forms of color vision deficiency including deuteranopia and protanopia.

**Named constants — define these once per notebook, never hardcode hex values inline:**

```python
# Paste at the top of every visualization notebook
PALETTE = {
    "blue":      "#0072B2",  # primary categorical color 1
    "orange":    "#E69F00",  # primary categorical color 2
    "green":     "#009E73",  # primary categorical color 3
    "sky":       "#56B4E9",  # primary categorical color 4
    "vermillion":"#D55E00",  # primary categorical color 5
    "purple":    "#CC79A7",  # primary categorical color 6
    "yellow":    "#F0E442",  # primary categorical color 7
    "black":     "#000000",  # primary categorical color 8
    "gray":      "#999999",  # reserved for "Unknown"
    "other":     "#CCCCCC",  # reserved for "Other"
}
```

**Extended palette**: for analysis notebooks that need more than the 8 Okabe-Ito seed colors, extend the dynamic assignment palette to 12–16 total colorblind-safe colors by appending additional distinct hues after the seed set. The current project palette uses these additional colors: `#44AA99`, `#88CCEE`, `#DDCC77`, `#AA4499`.

**Universal assignment order**: assign palette colors by categorical sequence — `blue` first, `orange` second, `green` third, and so on. `gray` is always reserved for "Unknown" / missing data and `other` is reserved for aggregated "Other" buckets. Never assign semantic meanings inline; put any semantic mappings in the [Use-Case-Specific Mappings](#use-case-specific-mappings) section at the bottom of this document. When a seeded semantic color collides with the dynamic palette, remove the colliding palette entry before assigning colors to unseeded QIDs.

**Rule**: never use `red` and `green` as a contrasting pair.

**Existing gap (as of 2026-04-23):** `51_visualization.ipynb` cells 8 and 11 still use hardcoded `#4878cf` / `#e8534a`. Replace with `PALETTE["blue"]` / `PALETTE["vermillion"]` when next updating those cells.

---

### 2. Font Family

The font family must be **configurable** via a single constant at the top of each notebook. Never set a font inline.

```python
# Set to match the target document's font. Default: None (system font).
# For paper publication: "Linux Libertine" (LinLibertine_Rah.ttf)
FONT_FAMILY = None  # or "Linux Libertine"
FONT_SIZE_BASE = 12

# Apply to Plotly figures:
def apply_font(fig):
    fig.update_layout(font=dict(family=FONT_FAMILY, size=FONT_SIZE_BASE))
    return fig
```

For matplotlib charts (reference code):
```python
from matplotlib import rcParams, font_manager
if FONT_FAMILY:
    font_path = "..."  # absolute path to .ttf
    font_manager.fontManager.addfont(font_path)
    prop = font_manager.FontProperties(fname=font_path)
    rcParams["font.family"] = prop.get_name()
rcParams["font.size"] = FONT_SIZE_BASE
```

---

### 3. Export Formats

Every chart **must** be exported as both PDF and PNG. HTML export is additionally optional but not a substitute.

```python
OUTPUT_DIR = pathlib.Path("data/output/visualization")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def save_fig(fig, name: str, html: bool = True) -> None:
    """Export a Plotly figure as PDF, PNG, and optionally HTML."""
    base = OUTPUT_DIR / name
    fig.write_image(str(base) + ".pdf")               # vector PDF
    fig.write_image(str(base) + ".png", scale=3)      # 3x scale → ~300 DPI equivalent
    if html:
        fig.write_html(str(base) + ".html")
```

For matplotlib:
```python
fig.savefig(str(OUTPUT_DIR / name) + ".pdf", bbox_inches="tight")
fig.savefig(str(OUTPUT_DIR / name) + ".png", dpi=300, bbox_inches="tight")
```

**Existing gap (as of 2026-04-23):** `51_visualization.ipynb` has no `write_image` calls — it only exports HTML. All charts need PDF+PNG export added (follow-up item, tracked under TODO-024 item 3).

---

### 4. Figure Dimensions

- **Default Plotly figure**: `width=1000, height=600`. Adjust for content.
- **Horizontal bar charts**: height scales with number of bars — allow ~30px per bar, minimum 400px.
- **Node graphs**: `width=1400, height=1000` (labels need space).
- Never rely on Plotly's default auto-size for exported artifacts.

---

### 5. Titles and Subtitles

Every exported chart must have:
- A descriptive **main title** (what the chart shows)
- A **subtitle** (`<sub>...</sub>` in Plotly HTML titles) containing at minimum: sample size (n=...) and data source

Example:
```
Gender distribution by occupation
<sub>640 Wikidata-matched guests · Markus Lanz 2008–2024 · Wikidata P21</sub>
```

---

### 6. Axis Labels

- Always set explicit axis labels. Never leave axes as the raw column name.
- Percentage axes: label as `"Percentage (%)"`, not `"pct"` or `"value"`.
- Sort categorical axes by value (descending) unless the category order is meaningful.

---

## Chart-Type-Specific Rules

### Bar Charts (horizontal preferred for long labels)

- Use horizontal bars when category name length > ~15 characters.
- Annotate bar values: show `n=` inside bars when the bar is wide enough (≥5% of total axis range); outside otherwise.
- Sort bars descending by value unless a meaningful order exists.
- "Unknown"/"Other" always last, always in `PALETTE["gray"]`.
- **Do not use bar charts for page rank.** Page rank must be visualized as a node graph (see below). See TODO-032.

### Grouped Bar Charts

- When showing "by individual" and "by occurrence" side-by-side, use `barmode="group"`.
- Keep the same color for the same category across both bar groups — only vary pattern or opacity to distinguish the two series if needed.

### Centered Stacked Bar Charts

Used to compare two opposed sub-groups (e.g., left-leaning vs. right-leaning, young vs. old) symmetrically about a zero axis. Key rules:

- Left/negative side uses `PALETTE["blue"]`; right/positive side uses `PALETTE["orange"]`. A neutral/midpoint category uses `PALETTE["gray"]` and straddles the zero line.
- Axis is percentage-based (range −100 % to +100 %). Label the axis `"← Group A  |  Group B →"` to make polarity explicit.
- Always annotate bars with the percentage value inside (centered on the bar segment) when the segment width ≥ 5 %; outside otherwise.
- Add a bold vertical line at x=0.
- Sort categories by the dominant side (e.g., by Group A share descending) unless a meaningful order exists.
- If multiple centered stacked bar charts appear **in the same row**, the second and subsequent charts may omit category-axis labels (the shared y-axis label from the first chart is sufficient). They **must** keep the bar value annotations.
- Example layout (for gender × occupation):
  ```python
  fig = make_subplots(rows=1, cols=2, shared_yaxes=True)
  # col 1: by individual; col 2: by occurrence
  # Only col 1 gets yaxis labels; col 2 reuses them via shared_yaxes=True
  ```

### Histograms / Distribution Plots

- Overlapping histograms: set `opacity=0.75` for all traces.
- Minimum 15 bins for continuous data; use `nbinsx=20` as default.
- Always set `barmode="overlay"` when comparing two distributions.

### Box / Violin Plots

- Show mean (`boxmean=True` in Plotly) in addition to median.
- Order categories by median value for readability.

### Nested Subgraphs (multi-panel figures)

When placing several related charts side-by-side in a single figure (e.g., a panel of bar charts, one per occupation):

- **Space scaling**: allocate column widths proportionally to the number of bars each subgraph contains. Use `column_widths` in `make_subplots`. Minimum column width: 80 px per bar.
- **Label reuse**: if all subgraphs share the same categories on one axis, only the **first** subgraph in each row carries the axis tick labels; subsequent subgraphs in that row use `showticklabels=False` on that axis. This prevents label repetition and saves space.
- **Shared axes**: use `shared_yaxes=True` (horizontal panels) or `shared_xaxes=True` (vertical stack) so that the scale is consistent and only printed once.
- **Per-panel titles**: use `fig.update_annotations` or the `subplot_titles` parameter — never place a title inside a cell as a manual `add_annotation` unless it cannot be expressed as a subplot title.
- **Consistent color mapping**: the same category must always use the same `PALETTE` color across all subgraphs in the figure.
- **Figure height scaling**: `height = max(400, 30 * max_bars_in_any_panel + 150)`. Adjust `150` for title/legend headroom.

### Hierarchical / Tree Layouts

- **Minimize edge overlap**: co-locate subclasses that share the same superclass set. Nodes whose edges do not interact with a dense cluster belong at the cluster perimeter, not its interior.
- Place all root/core-class nodes in consistent positions (e.g. always leftmost for horizontal layouts, always innermost ring for radial layouts).
- Apply this principle to: horizontal hierarchical, radial hierarchical, and any other directed graph layout.

### Sunburst / Sankey Diagrams

- Multi-parent nodes (subclasses with more than one superclass) require an explicit strategy before implementation: either assign a primary parent or split counts fractionally. Document the chosen strategy in the notebook cell.
- Combined diagram (all core classes): innermost ring = core classes only; subclasses < 5% of total instances grouped as "Other".
- Per-core-class diagram: exhaustive (no cutoff).

### Node Graphs (page rank, entity graphs)

- Node size proportional to rank/importance score.
- Label only the top-N nodes (configurable constant, default `LABEL_TOP_N = 20`).
- Edges: show only when edge weight exceeds a configurable threshold.
- Export at `scale=4` (PNG) to keep labels readable.

---

## Compliance Gaps in `51_visualization.ipynb` (as of 2026-04-23)

| Chart | Gap | Fix |
|-------|-----|-----|
| All charts | No PDF/PNG export — HTML only | Add `save_fig()` calls after each figure |
| Page rank (cell 3) | Bar chart — wrong chart type | Replace with node graph (TODO-032) |
| Age histogram (cell 8) | Hardcoded `#4878cf` / `#e8534a` | Use `PALETTE["blue"]` / `PALETTE["vermillion"]` |
| Episode count (cell 11) | Hardcoded colors in `color_discrete_map` | Use `COLORS` dict |
| All charts | No `apply_font()` call | Add font constant + `apply_font(fig)` |
| All charts | VIZ_DIR points to `documentation/visualizations/` | Change to `data/output/visualization/` |

---

## Use-Case-Specific Mappings

> These mappings apply only within the speaker-mining project. Universal rules above always take precedence. If a universal rule and a local mapping conflict, fix the mapping, not the rule.

### Gender (speaker-mining)

| Value | Color key | Rationale |
|-------|-----------|-----------|
| female | `PALETTE["blue"]` | first categorical color by sequence |
| male | `PALETTE["orange"]` | second categorical color by sequence |
| unknown / other | `PALETTE["gray"]` | reserved neutral color |

Use these assignments in centered stacked bar charts and grouped bar charts that break down by gender. Do not introduce a dedicated `COLORS` dict — derive from `PALETTE` directly:

```python
GENDER_COLOR = {
    "female": PALETTE["blue"],
    "male":   PALETTE["orange"],
    "":       PALETTE["gray"],
}
```

### Age groups (if used)

Assign palette colors by ascending age: youngest group = `PALETTE["blue"]`, next = `PALETTE["orange"]`, oldest = `PALETTE["green"]`, unknown = `PALETTE["gray"]`.
