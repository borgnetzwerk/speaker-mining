"""Treemap visualizations for item-type properties (TASK-F08).

Each tile = one property value; tile area proportional to unique guest count.
Produced per-scope (combined "all" and per-show).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig


_UNKNOWN_PREFIX = "Unknown"
_OTHER_COLOR = "#CCCCCC"
_PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#56B4E9",
    "#D55E00", "#CC79A7", "#F0E442", "#44AA99",
    "#88CCEE", "#DDCC77", "#AA4499", "#332288",
]


def _scope_text(scope: str) -> str:
    return "Combined" if scope == "all" else f"Show: {scope}"


def build_property_treemap(
    standard_frame: pd.DataFrame,
    prop_label: str,
    prop_id: str,
    output_dir: Path,
    scope: str = "all",
    top_n: int = 30,
) -> None:
    """Build a treemap for one item-type property.

    Each leaf tile is a property value; tile area = unique guest count.
    Values beyond top_n are omitted to keep the chart readable.

    Args:
        standard_frame: Expanded property frame.
            Required columns: canonical_entity_id, value.
        prop_label: Human-readable property label (used in title).
        prop_id: Property ID used in output file name (e.g. "P106").
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or show ID — used in chart titles only.
        top_n: Maximum number of values to display.
    """
    if standard_frame is None or standard_frame.empty:
        return
    if not {"canonical_entity_id", "value"}.issubset(standard_frame.columns):
        return

    df = standard_frame.copy()
    # Remove unknown / empty values
    mask = (
        df["value"].fillna("").astype(str).str.strip().ne("")
        & ~df["value"].astype(str).str.startswith(_UNKNOWN_PREFIX)
    )
    df = df[mask]
    if df.empty:
        return

    counts = (
        df.groupby("value")["canonical_entity_id"]
        .nunique()
        .reset_index(name="unique_guests")
        .sort_values("unique_guests", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    if counts.empty:
        return

    total = counts["unique_guests"].sum()
    counts["pct"] = (counts["unique_guests"] / max(total, 1) * 100).round(1)
    counts["text"] = counts.apply(
        lambda r: f"{r['value']}<br>{r['unique_guests']:,} ({r['pct']:.0f}%)", axis=1
    )

    # Assign colors cycling through the palette
    colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(counts))]

    fig = go.Figure(go.Treemap(
        labels=counts["value"].tolist(),
        parents=[""] * len(counts),
        values=counts["unique_guests"].tolist(),
        text=counts["text"].tolist(),
        textinfo="text",
        hovertemplate=(
            "<b>%{label}</b><br>"
            "Unique guests: %{value:,}<br>"
            "%{text}<extra></extra>"
        ),
        marker=dict(colors=colors),
    ))
    fig.update_layout(
        title=dict(
            text=(
                f"{prop_label} — Treemap<br>"
                f"<sup>{_scope_text(scope)} · top {top_n} values by unique guest count</sup>"
            ),
            x=0.5,
        ),
        template="plotly_white",
        height=max(500, min(900, 20 * len(counts) + 200)),
        margin=dict(t=100, b=40, l=10, r=10),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / f"treemap_{prop_id}")
    print(f"  Treemap [{prop_label}]: {len(counts)} values → {viz_dir.name}/")


def build_all_treemaps(
    property_frames: dict,
    property_labels: dict,
    output_dir: Path,
    scope: str = "all",
    item_pids: list[str] | None = None,
    top_n: int = 30,
) -> None:
    """Build treemaps for all item-type properties.

    Args:
        property_frames: {pid: standard_frame} from the property loop.
        property_labels: {pid: human-readable label}.
        output_dir: Scope output root.
        scope: "all" or a show ID.
        item_pids: Explicit list of PIDs to process. If None, processes all
            keys in property_frames.
        top_n: Maximum tiles per treemap.
    """
    pids = item_pids if item_pids is not None else list(property_frames.keys())
    for pid in pids:
        frame = property_frames.get(pid)
        if frame is None or frame.empty:
            continue
        label = property_labels.get(pid, pid)
        build_property_treemap(frame, label, pid, output_dir, scope=scope, top_n=top_n)
