"""Layer 3a: Universal bar chart visualizations for all properties.

Implements TASK-B09: appearances + unique-individuals charts for every property.
A single function drives all charts; no property-specific code lives here.

Requirements: REQ-U07, REQ-V05, REQ-V09, REQ-V10, REQ-V11, REQ-U08, REQ-V07
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig
from .universal_stats import UNKNOWN_LABEL


_PALETTE = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
    "#0072B2", "#D55E00", "#CC79A7", "#44AA99",
    "#88CCEE", "#DDCC77", "#AA4499", "#332288",
]
UNKNOWN_COLOR = "#999999"
OTHER_COLOR = "#CCCCCC"


def _hex_to_rgba(color: str, alpha: float) -> str:
    hex_color = str(color).lstrip("#")
    if len(hex_color) != 6:
        return str(color)
    red = int(hex_color[0:2], 16)
    green = int(hex_color[2:4], 16)
    blue = int(hex_color[4:6], 16)
    return f"rgba({red}, {green}, {blue}, {alpha})"


def _assign_colors(labels: list) -> list[str]:
    """Cycle through palette; gray for Unknown rows, light-gray for Other."""
    colors: list[str] = []
    palette_idx = 0
    for label in labels:
        s = str(label)
        if s.startswith("Unknown"):
            colors.append(UNKNOWN_COLOR)
        elif s == "Other":
            colors.append(OTHER_COLOR)
        else:
            colors.append(_PALETTE[palette_idx % len(_PALETTE)])
            palette_idx += 1
    return colors


def _prepare_plot_df(stats: pd.DataFrame, top_n: int) -> pd.DataFrame:
    """
    Sort by appearance_count descending; group tail beyond top_n as 'Other';
    always place Unknown row last (REQ-V05, REQ-V11, REQ-U08).
    """
    if stats is None or stats.empty:
        return pd.DataFrame()

    unknown_mask = stats["value"].astype(str).str.startswith("Unknown")
    unknown_rows = stats[unknown_mask].copy()
    value_rows = (
        stats[~unknown_mask]
        .sort_values("appearance_count", ascending=False)
        .copy()
    )

    if len(value_rows) > top_n:
        tail = value_rows.iloc[top_n:]
        other_row = pd.DataFrame([{
            "value": "Other",
            "person_count": int(tail["person_count"].sum()),
            "appearance_count": int(tail["appearance_count"].sum()),
        }])
        value_rows = pd.concat([value_rows.head(top_n), other_row], ignore_index=True)

    frames = [value_rows]
    if not unknown_rows.empty:
        frames.append(unknown_rows.reset_index(drop=True))
    return pd.concat(frames, ignore_index=True)


def make_universal_chart(
    stats: pd.DataFrame,
    property_label: str,
    scope: str = "all",
    top_n: int = 20,
) -> go.Figure:
    """
    Build a grouped horizontal bar chart: appearances + unique persons side by side.

    Design rules applied:
    - REQ-V05: bars sorted descending by appearance count
    - REQ-V09: bar labels shown (plotly handles inside/outside automatically)
    - REQ-V11: tail values grouped as 'Other' (light gray)
    - REQ-U08: 'Unknown / no data' row always last (medium gray)
    - REQ-V07: scope label in chart title
    - REQ-V10: context stats (n_unique, n_appearances, n_empty) in subtitle
    """
    plot_df = _prepare_plot_df(stats, top_n)
    if plot_df.empty:
        return go.Figure()

    scope_text = "Combined" if scope == "all" else f"Show: {scope}"
    colors = _assign_colors(plot_df["value"].tolist())

    unknown_mask = stats["value"].astype(str).str.startswith("Unknown")
    n_unique = int(stats[~unknown_mask]["person_count"].sum())
    n_appearances = int(stats[~unknown_mask]["appearance_count"].sum())
    n_empty = int(stats[unknown_mask]["person_count"].sum()) if unknown_mask.any() else 0

    fig = go.Figure()

    # Appearances bars (slightly transparent to distinguish from unique-persons bars)
    fig.add_trace(go.Bar(
        name="Appearances",
        y=plot_df["value"],
        x=plot_df["appearance_count"],
        orientation="h",
        marker_color=[_hex_to_rgba(c, 0.6) for c in colors],
        text=plot_df["appearance_count"].apply(lambda v: f"{int(v):,}"),
        textposition="auto",
        hovertemplate="%{y}: %{x:,} appearances<extra></extra>",
    ))

    # Unique-persons bars (opaque)
    fig.add_trace(go.Bar(
        name="Unique Persons",
        y=plot_df["value"],
        x=plot_df["person_count"],
        orientation="h",
        marker_color=colors,
        text=plot_df["person_count"].apply(lambda v: f"{int(v):,}"),
        textposition="auto",
        hovertemplate="%{y}: %{x:,} unique persons<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=(
                f"{property_label} Distribution — {scope_text}<br>"
                f"<sup>n={n_unique:,} unique persons · {n_appearances:,} appearances"
                f" · {n_empty:,} no data</sup>"
            ),
            x=0.5,
        ),
        xaxis_title="Count",
        yaxis=dict(autorange="reversed", title=property_label),
        barmode="group",
        hovermode="y unified",
        height=max(400, 35 * len(plot_df) + 150),
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_font(fig)
    return fig


def universal_visualizations(
    property_stats: Dict[str, Tuple[str, pd.DataFrame]],
    output_dir: Path,
    scope: str = "all",
    top_n: int = 20,
) -> None:
    """
    Generate universal bar charts for every active property.

    The function is fully data-driven: adding a new entry to property_stats
    automatically produces a new visualization with no code changes needed.

    Args:
        property_stats: {pid: (label, stats_df)} — one entry per active property.
            stats_df must have columns: value, person_count, appearance_count.
        output_dir: scope output root (e.g. data/50_analysis/all/)
        scope: scope label used in chart titles and file names
        top_n: maximum values shown per chart before tail is grouped as 'Other'
    """
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    for pid, (label, stats_df) in property_stats.items():
        print(f"  [{pid}] {label} ...", end=" ", flush=True)
        if stats_df is None or (hasattr(stats_df, "empty") and stats_df.empty):
            print("no data, skipped")
            continue

        fig = make_universal_chart(stats_df, label, scope=scope, top_n=top_n)
        slug = label.lower().replace(" ", "_").replace("/", "_")
        save_fig(fig, viz_dir / f"universal_{pid}_{slug}")
        processed += 1
        print("saved")

    print(f"Universal visualizations complete: {processed}/{len(property_stats)} properties saved")
