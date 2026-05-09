"""Treemap visualizations for item-type properties (TASK-F08).

Each tile = one property value; tile area proportional to count.
Always produces a combined figure: left panel = by appearances, right = by unique guests.
PRINCIPLE-9: every guest visualization also has an appearances version.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .viz_base import apply_font, save_fig


_UNKNOWN_PREFIX = "Unknown"


def _make_treemap_counts(
    df: pd.DataFrame,
    count_col: str,
    count_label: str,
    top_n: int,
) -> tuple[list, list, list, list]:
    """Return (labels, parents, values, texts) for a go.Treemap trace."""
    counts = (
        df.groupby("value")[count_col]
        .sum()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    if counts.empty:
        return [], [], [], []

    total = counts["count"].sum()
    counts["pct"] = (counts["count"] / max(total, 1) * 100).round(1)
    counts["text"] = counts.apply(
        lambda r: f"{r['value']}<br>{int(r['count']):,} {count_label} ({r['pct']:.0f}%)", axis=1
    )
    return (
        counts["value"].tolist(),
        [""] * len(counts),
        counts["count"].tolist(),
        counts["text"].tolist(),
    )


def build_property_treemap(
    standard_frame: pd.DataFrame,
    prop_label: str,
    prop_id: str,
    output_dir: Path,
    scope: str = "all",
    top_n: int = 30,
) -> None:
    """Build a combined treemap (guests + appearances) for one item-type property.

    Left panel: tile area = unique guest count.
    Right panel: tile area = total appearance count (guest × episode pairs).

    Args:
        standard_frame: Expanded property frame.
            Required columns: canonical_entity_id, value, and optionally episode_id.
        prop_label: Human-readable property label.
        prop_id: Property ID (e.g. "P106"), included in the output file name.
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or show ID — used in chart titles only.
        top_n: Maximum number of values to display per panel.
    """
    if standard_frame is None or standard_frame.empty:
        return
    if not {"canonical_entity_id", "value"}.issubset(standard_frame.columns):
        return

    df = standard_frame.copy()
    mask = (
        df["value"].fillna("").astype(str).str.strip().ne("")
        & ~df["value"].astype(str).str.startswith(_UNKNOWN_PREFIX)
    )
    df = df[mask]
    if df.empty:
        return

    # By unique guest: one row per (guest, value) pair
    guest_df = df.drop_duplicates(subset=["canonical_entity_id", "value"]).copy()
    guest_df["_count"] = 1

    # By appearances: one row per (guest, episode, value) pair
    ep_col = "episode_id" if "episode_id" in df.columns else None
    if ep_col:
        appear_df = df.drop_duplicates(subset=["canonical_entity_id", ep_col, "value"]).copy()
    else:
        appear_df = df.copy()
    appear_df["_count"] = 1

    scope_text = "Combined" if scope == "all" else f"Show: {scope}"
    short_label = prop_label.lower().replace(" ", "_").replace("/", "_")[:25]

    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            f"{prop_label} — by appearances",
            f"{prop_label} — by unique guests",
        ],
        specs=[[{"type": "treemap"}, {"type": "treemap"}]],
        horizontal_spacing=0.04,
    )

    # Left panel: appearances
    a_labels, a_parents, a_values, a_texts = _make_treemap_counts(
        appear_df, "_count", "appearances", top_n
    )
    if a_labels:
        fig.add_trace(
            go.Treemap(
                labels=a_labels,
                parents=a_parents,
                values=a_values,
                text=a_texts,
                textinfo="text",
                hovertemplate="<b>%{label}</b><br>%{text}<extra></extra>",
            ),
            row=1, col=1,
        )

    # Right panel: unique guests
    g_labels, g_parents, g_values, g_texts = _make_treemap_counts(
        guest_df, "_count", "guests", top_n
    )
    if g_labels:
        fig.add_trace(
            go.Treemap(
                labels=g_labels,
                parents=g_parents,
                values=g_values,
                text=g_texts,
                textinfo="text",
                hovertemplate="<b>%{label}</b><br>%{text}<extra></extra>",
            ),
            row=1, col=2,
        )

    fig.update_layout(
        title=dict(
            text=(
                f"{prop_label} — Treemap ({scope_text})<br>"
                f"<sup>Left: appearances · Right: unique guests · top {top_n} values</sup>"
            ),
            x=0.5,
        ),
        template="plotly_white",
        height=max(500, min(900, 20 * top_n + 200)),
        margin=dict(t=100, b=40, l=10, r=10),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / f"treemap_{prop_id}_{short_label}")
    print(f"  Treemap [{prop_label}]: {len(a_labels)} appearance values, {len(g_labels)} guest values → {viz_dir.name}/")


def build_all_treemaps(
    property_frames: dict,
    property_labels: dict,
    output_dir: Path,
    scope: str = "all",
    item_pids: list[str] | None = None,
    top_n: int = 30,
) -> None:
    """Build combined treemaps for all item-type properties.

    Args:
        property_frames: {pid: standard_frame} from the property loop.
        property_labels: {pid: human-readable label}.
        output_dir: Scope output root.
        scope: "all" or a show ID.
        item_pids: Explicit list of PIDs to process; if None, processes all keys.
        top_n: Maximum tiles per panel.
    """
    pids = item_pids if item_pids is not None else list(property_frames.keys())
    for pid in pids:
        frame = property_frames.get(pid)
        if frame is None or frame.empty:
            continue
        label = property_labels.get(pid, pid)
        build_property_treemap(frame, label, pid, output_dir, scope=scope, top_n=top_n)
