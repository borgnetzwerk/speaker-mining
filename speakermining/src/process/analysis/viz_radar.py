"""Radar (spider) chart visualizations for cross-show property comparison (TASK-F08).

For each item-type property, one radar chart shows the percentage of unique
guests carrying the top-N values, with one polygon per show and a combined
average polygon overlaid.

This answers: "Does Markus Lanz have a different gender/occupation/party profile
than Caren Miosga?"
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig


_UNKNOWN_PREFIX = "Unknown"
_PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#56B4E9",
    "#D55E00", "#CC79A7", "#F0E442", "#44AA99",
    "#88CCEE", "#DDCC77", "#AA4499", "#332288",
]
_COMBINED_COLOR = "#000000"


def _scope_text(scope: str) -> str:
    return "Combined" if scope == "all" else f"Show: {scope}"


def _top_values(frame: pd.DataFrame, top_n: int) -> list[str]:
    """Return the top-N values by unique guest count, excluding unknowns."""
    mask = (
        frame["value"].fillna("").astype(str).str.strip().ne("")
        & ~frame["value"].astype(str).str.startswith(_UNKNOWN_PREFIX)
    )
    counts = (
        frame[mask]
        .groupby("value")["canonical_entity_id"]
        .nunique()
        .sort_values(ascending=False)
    )
    return counts.head(top_n).index.tolist()


def build_property_radar_chart(
    standard_frame: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    prop_label: str,
    prop_id: str,
    output_dir: Path,
    scope: str = "all",
    top_n_values: int = 8,
) -> None:
    """Build a radar chart for one property, comparing shows to combined.

    Each axis of the radar = one top property value (e.g. "female", "Journalist").
    Each polygon = one broadcasting show.
    The combined average is overlaid as a dashed black polygon.

    Args:
        standard_frame: Expanded property frame.
            Required columns: canonical_entity_id, value.
        episode_appearances: Full episode appearances frame.
            Required columns: canonical_entity_id, show_id, role, program_name.
        prop_label: Human-readable label for the property.
        prop_id: Property ID used in output file name.
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or show ID — used in chart titles only.
        top_n_values: Number of axes (top property values).
    """
    if standard_frame is None or standard_frame.empty:
        return
    if episode_appearances is None or episode_appearances.empty:
        return
    if not {"canonical_entity_id", "value"}.issubset(standard_frame.columns):
        return

    guest_ep = episode_appearances[episode_appearances.get("role", pd.Series(dtype=str)) == "guest"].copy() if "role" in episode_appearances.columns else episode_appearances.copy()
    if guest_ep.empty or "show_id" not in guest_ep.columns:
        return

    top_vals = _top_values(standard_frame, top_n_values)
    if not top_vals:
        return

    # Show metadata
    show_meta: dict = {}
    if "program_name" in guest_ep.columns:
        show_meta = (
            guest_ep[["show_id", "program_name"]]
            .drop_duplicates()
            .set_index("show_id")["program_name"]
            .to_dict()
        )

    # Unique guests per show
    show_unique_totals = (
        guest_ep.groupby("show_id")["canonical_entity_id"].nunique()
    )

    # Property frame: clean values
    df = standard_frame.copy()
    df = df[
        df["value"].fillna("").astype(str).str.strip().ne("")
        & ~df["value"].astype(str).str.startswith(_UNKNOWN_PREFIX)
        & df["value"].isin(top_vals)
    ]
    if df.empty:
        return

    # Join with episode_appearances to get show_id per (entity, value)
    entity_show = (
        guest_ep[["canonical_entity_id", "show_id"]]
        .drop_duplicates()
    )
    df_with_show = df[["canonical_entity_id", "value"]].drop_duplicates().merge(
        entity_show, on="canonical_entity_id", how="inner"
    )

    # % per show per value
    show_ids = sorted(show_unique_totals.index.tolist())

    rows_show: dict = {}
    for sid in show_ids:
        total = int(show_unique_totals.get(sid, 0))
        if total == 0:
            continue
        sid_data = df_with_show[df_with_show["show_id"] == sid]
        row = {}
        for val in top_vals:
            n = int(sid_data[sid_data["value"] == val]["canonical_entity_id"].nunique())
            row[val] = round(n / total * 100, 1)
        rows_show[sid] = row

    if not rows_show:
        return

    # Combined average (across all shows, weighted by show size)
    all_unique = int(show_unique_totals.sum())
    combined_row = {}
    for val in top_vals:
        n = int(df[df["value"] == val]["canonical_entity_id"].nunique())
        combined_row[val] = round(n / max(all_unique, 1) * 100, 1)

    # Build radar figure
    # Plotly radar requires the first and last theta to be identical to close the polygon
    theta = top_vals + [top_vals[0]]
    fig = go.Figure()

    for i, (sid, row) in enumerate(rows_show.items()):
        r_vals = [row.get(v, 0) for v in top_vals] + [row.get(top_vals[0], 0)]
        display = show_meta.get(sid, sid)
        fig.add_trace(go.Scatterpolar(
            r=r_vals,
            theta=theta,
            mode="lines+markers",
            name=display,
            line=dict(color=_PALETTE[i % len(_PALETTE)], width=2),
            marker=dict(size=5),
            hovertemplate=(
                f"<b>{display}</b><br>"
                "%{theta}: %{r:.1f}%<extra></extra>"
            ),
        ))

    # Combined overlay
    r_combined = [combined_row.get(v, 0) for v in top_vals] + [combined_row.get(top_vals[0], 0)]
    fig.add_trace(go.Scatterpolar(
        r=r_combined,
        theta=theta,
        mode="lines",
        name="Combined",
        line=dict(color=_COMBINED_COLOR, width=2, dash="dash"),
        hovertemplate="<b>Combined</b><br>%{theta}: %{r:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=(
                f"{prop_label} — Show Comparison (Radar)<br>"
                f"<sup>{_scope_text(scope)} · % of unique guests per show</sup>"
            ),
            x=0.5,
        ),
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, max(
                    max(v for row in rows_show.values() for v in row.values()),
                    max(r_combined),
                    1,
                ) * 1.1],
                ticksuffix="%",
            )
        ),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.05,
        ),
        template="plotly_white",
        height=600,
        margin=dict(t=120, b=60, r=200),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / f"radar_{prop_id}")
    print(f"  Radar [{prop_label}]: {len(top_vals)} axes × {len(rows_show)} shows → {viz_dir.name}/")


def build_all_radar_charts(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
    item_pids: list[str] | None = None,
    top_n_values: int = 8,
) -> None:
    """Build radar charts for all item-type properties.

    Args:
        property_frames: {pid: standard_frame} from the property loop.
        property_labels: {pid: human-readable label}.
        episode_appearances: Full episode appearances frame.
        output_dir: Scope output root.
        scope: "all" or a show ID.
        item_pids: Explicit list of PIDs to process. If None, all keys are used.
        top_n_values: Number of radar axes per chart.
    """
    pids = item_pids if item_pids is not None else list(property_frames.keys())
    for pid in pids:
        frame = property_frames.get(pid)
        if frame is None or frame.empty:
            continue
        label = property_labels.get(pid, pid)
        build_property_radar_chart(
            frame, episode_appearances, label, pid,
            output_dir, scope=scope, top_n_values=top_n_values,
        )
