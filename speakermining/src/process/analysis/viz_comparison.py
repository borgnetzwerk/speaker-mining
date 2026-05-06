"""Cross-show comparison visualizations (TASK-F09).

For each property, answers: "Is the distribution of this property value
different between shows?"  Produces one grouped bar chart per property:
X = broadcasting show, Y = % of unique guests, bars grouped by property value.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig

_PALETTE = [
    "#E69F00", "#56B4E9", "#009E73", "#F0E442",
    "#0072B2", "#D55E00", "#CC79A7", "#44AA99",
    "#88CCEE", "#DDCC77", "#AA4499", "#332288",
]
_UNKNOWN_COLOR = "#999999"
_OTHER_COLOR = "#CCCCCC"


def build_cross_show_comparison(
    standard_frame: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    prop_id: str,
    prop_label: str,
    output_dir: Path,
    scope: str = "all",
    top_n_values: int = 10,
) -> None:
    """For each top value of a property, produce a grouped bar chart comparing
    unique-guest percentages across broadcasting shows.

    Args:
        standard_frame: property frame with canonical_entity_id, episode_id, value.
        episode_appearances: with canonical_entity_id, fernsehserien_de_id (=episode_id),
            show_id, program_name, role.
        prop_id: property PID (e.g. "P21")
        prop_label: human-readable label (e.g. "sex or gender")
        output_dir: scope output root
        scope: "all" or show ID — used in title only
        top_n_values: how many top values to include (rest grouped as "Other")
    """
    if standard_frame is None or standard_frame.empty:
        return
    if episode_appearances is None or episode_appearances.empty:
        return

    guest_ep = episode_appearances[episode_appearances["role"] == "guest"].copy()
    if guest_ep.empty:
        return

    # Show metadata
    show_meta = (
        guest_ep[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
    )

    # Total unique guests per show
    total_per_show = (
        guest_ep.groupby("show_id")["canonical_entity_id"].nunique()
        .reset_index(name="total_guests")
        .sort_values("total_guests", ascending=False)
    )
    show_order = total_per_show["show_id"].tolist()
    if not show_order:
        return

    # Episode → show mapping (episode_id in standard_frame = fernsehserien_de_id)
    ep_col = "episode_id" if "episode_id" in standard_frame.columns else "fernsehserien_de_id"
    ep_show = (
        guest_ep[["canonical_entity_id", "fernsehserien_de_id", "show_id"]]
        .drop_duplicates()
        .rename(columns={"fernsehserien_de_id": ep_col})
    )

    # Clean property frame
    frame = standard_frame.copy()
    frame = frame[
        frame["value"].fillna("").astype(str).str.strip().ne("")
        & ~frame["value"].astype(str).str.startswith("Unknown")
    ]
    if frame.empty:
        return

    merged = frame.merge(ep_show, on=["canonical_entity_id", ep_col], how="inner")
    if merged.empty:
        return

    # Top N values by total unique guests across all shows
    value_totals = (
        merged.groupby("value")["canonical_entity_id"].nunique()
        .sort_values(ascending=False)
    )
    top_values = value_totals.head(top_n_values).index.tolist()

    # Unique guests per (show, value)
    by_show_value = (
        merged[merged["value"].isin(top_values)]
        .groupby(["show_id", "value"])["canonical_entity_id"]
        .nunique()
        .reset_index(name="unique_guests")
    )

    # Pivot: rows = shows, cols = values
    pivot = by_show_value.pivot(index="show_id", columns="value", values="unique_guests").fillna(0)

    # Join totals and sort by show size
    pivot = pivot.join(total_per_show.set_index("show_id")["total_guests"], how="left").fillna(0)
    pivot = pivot.reindex(show_order).fillna(0)

    show_labels = [show_meta.get(s, s) for s in show_order]
    color_map = {v: _PALETTE[i % len(_PALETTE)] for i, v in enumerate(top_values)}

    fig = go.Figure()
    for i, val in enumerate(top_values):
        if val not in pivot.columns:
            continue
        counts = pivot[val].tolist()
        totals = pivot["total_guests"].tolist()
        pcts = [c / max(t, 1) * 100 for c, t in zip(counts, totals)]
        text = [f"{int(c):,} ({p:.0f}%)" for c, p in zip(counts, pcts)]

        fig.add_trace(go.Bar(
            name=str(val),
            x=show_labels,
            y=pcts,
            marker_color=color_map[val],
            text=text,
            textposition="auto",
            legendrank=i,
            hovertemplate=(
                f"<b>{val}</b><br>"
                "%{x}: %{y:.1f}% (%{customdata:,} unique guests)<extra></extra>"
            ),
            customdata=counts,
        ))

    fig.update_layout(
        title=dict(
            text=(
                f"{prop_label} — distribution across shows<br>"
                f"<sup>% of unique guests per show (top {len(top_values)} values)</sup>"
            ),
            x=0.5,
        ),
        barmode="group",
        xaxis_title="Show",
        yaxis=dict(title="% of unique guests", rangemode="tozero"),
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top", y=1.0,
            xanchor="left", x=1.02,
            title_text=prop_label,
        ),
        height=max(400, 60 * len(top_values) + 200),
        margin=dict(t=100, r=220, b=120),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    slug = prop_label.lower().replace(" ", "_").replace("/", "_")[:25]
    save_fig(fig, viz_dir / f"comparison_{prop_id}_{slug}")
    print(f"  Cross-show comparison [{prop_label}]: {len(show_order)} shows × {len(top_values)} values")


def build_all_cross_show_comparisons(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
    item_pids: list[str] | None = None,
    top_n_values: int = 10,
) -> None:
    """Run cross-show comparison for all item-type properties (or a specified subset).

    Args:
        property_frames: {pid: standard_frame} dict from the property loop.
        property_labels: {pid: label} mapping.
        episode_appearances: full episode_appearances frame.
        output_dir: scope output root.
        item_pids: optional explicit list of PIDs; if None, runs for all keys in property_frames.
        top_n_values: top N property values per chart.
    """
    pids = item_pids if item_pids is not None else list(property_frames.keys())
    print(f"Generating cross-show comparison charts for {len(pids)} properties...")
    for pid in pids:
        frame = property_frames.get(pid)
        label = property_labels.get(pid, pid)
        if frame is None or frame.empty:
            print(f"  [{pid}] {label} skipped — no data")
            continue
        build_cross_show_comparison(
            frame, episode_appearances, pid, label, output_dir,
            top_n_values=top_n_values,
        )
    print("Cross-show comparison charts complete.")
