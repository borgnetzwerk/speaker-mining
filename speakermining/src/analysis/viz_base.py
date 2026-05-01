"""Shared visualization helpers for the analysis redesign."""

from __future__ import annotations

from pathlib import Path


PALETTE = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "sky": "#56B4E9",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "yellow": "#F0E442",
    "black": "#000000",
    "gray": "#999999",
    "other": "#CCCCCC",
}

FONT_FAMILY = None
FONT_SIZE_BASE = 12


def apply_font(fig, font_family: str | None = None, font_size: int = FONT_SIZE_BASE):
    """Apply the shared font configuration to a Plotly figure."""

    fig.update_layout(font=dict(family=font_family if font_family is not None else FONT_FAMILY, size=font_size))
    return fig


def save_fig(fig, path: str | Path, html: bool = True) -> None:
    """Export a Plotly figure as PNG and PDF, with optional HTML."""

    base = Path(path)
    base.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(base) + ".png", scale=3)
    fig.write_image(str(base) + ".pdf")
    if html:
        fig.write_html(str(base) + ".html")
    print(f"  Saved: {base.name}.png / .pdf" + (" / .html" if html else ""))


def sort_bars_descending(frame, value_column: str):
    """Return a copy of a frame sorted by a value column descending."""

    return frame.sort_values(value_column, ascending=False).copy()


def add_unknown_row(frame, unknown_label: str = "(unknown)"):
    """Append an unknown row when the frame looks like a category table."""

    if frame is None or getattr(frame, "empty", True):
        return frame
    if "value" not in frame.columns:
        return frame
    if (frame["value"] == unknown_label).any():
        return frame

    unknown_row = {column: 0 for column in frame.columns}
    unknown_row["value"] = unknown_label
    return frame.__class__(list(frame.to_dict(orient="records")) + [unknown_row])


def add_scope_label(ax, scope: str) -> None:
    """Add a scope label to a matplotlib axis (REQ-V07)."""
    scope_text = "Combined" if scope == "all" else f"Show: {scope}"
    ax.text(0.98, 0.98, scope_text, transform=ax.transAxes,
            ha='right', va='top', fontsize=10, style='italic', color='#666666')


def add_context_stats(ax, n_appearances: int, n_unique: int, n_empty: int) -> None:
    """Add context statistics to axis (REQ-V10)."""
    stats_text = f"Appearances: {n_appearances:,} | Unique: {n_unique:,} | No data: {n_empty:,}"
    ax.text(0.02, -0.12, stats_text, transform=ax.transAxes,
            ha='left', va='top', fontsize=9, color='#666666')


def stacked_bar_from_zero(data, categories_col: str, values_dict: dict, label_col: str = None):
    """Create stacked bar data from zero (REQ-V06)."""
    import pandas as pd
    result = data[[categories_col]].copy()
    for key, val_col in values_dict.items():
        result[key] = data[val_col].fillna(0)
    return result.set_index(categories_col)


def place_bar_labels(ax, bars, value_format: str = "{:.0f}") -> None:
    """Place labels on top of bars (REQ-V09)."""
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   value_format.format(height),
                   ha='center', va='bottom', fontsize=9)


def apply_other_grouping(data, top_x: int, value_column: str = "person_count",
                         label_column: str = "value"):
    """Group data keeping top X and aggregating rest as 'other' (REQ-V11)."""
    import pandas as pd
    top_data = data.nlargest(top_x, value_column).copy()
    other_sum = data.iloc[top_x:][value_column].sum() if len(data) > top_x else 0
    
    if other_sum > 0:
        other_row = {label_column: "other", value_column: other_sum}
        for col in data.columns:
            if col not in [label_column, value_column]:
                other_row[col] = 0
        top_data = pd.concat([top_data, pd.DataFrame([other_row])], ignore_index=True)
    
    return top_data
