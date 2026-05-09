"""Cross-property stacked bar chart visualizations.

Two families:

1. Property × Property (build_cross_property_stacked_bars):
   For a pair of properties A and B, produces two horizontal stacked bar charts:
     - Unique guests: for each top value of A, how many unique guests also carry
       each value of B?  Segments sum to the total unique guests for that A value.
     - Appearances: same breakdown by total appearance count.

   This answers: "Of the female guests, what occupations do they have?" or
   "For each occupation, what gender distribution do we see?"

2. Property × Person (build_property_top_persons_chart):
   For each top value of a property, show the top individual guests who carry
   that value, with bar segments coloured by broadcasting show.  This answers:
   "Who are the most-invited female guests?" or "Which journalists appear most?"
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import plotly.graph_objects as go

from plotly.subplots import make_subplots

from .viz_base import apply_font, save_fig, wrap_labels
from .universal_stats import UNKNOWN_LABEL
from .color_registry import PALETTE as _PALETTE, UNKNOWN_COLOR as _UNKNOWN_COLOR, OTHER_COLOR as _OTHER_COLOR


def _top_values(counts_by_value: pd.Series, top_n: int) -> list[str]:
    """Return the top-N labels by count, excluding Unknown / no data."""
    mask = ~counts_by_value.index.astype(str).str.startswith("Unknown")
    ranked = counts_by_value[mask].sort_values(ascending=False)
    return ranked.head(top_n).index.tolist()


def _build_cross_fig(
    pivot: pd.DataFrame,
    a_order: list[str],
    b_order: list[str],
    prop_A_label: str,
    prop_B_label: str,
    metric_label: str,
    scope: str,
) -> go.Figure:
    """Build a horizontal stacked bar chart from a pivot table.

    Args:
        pivot: DataFrame with value_A as index, value_B as columns, cell = count.
        a_order: ordered list of A values for the Y axis (top to bottom).
        b_order: ordered list of B values to use as bar segments.
        metric_label: "Unique guests" or "Appearances".
    """
    # Restrict to known rows/cols; add Other column if tail exists
    pivot = pivot.reindex(index=a_order, columns=b_order, fill_value=0)

    # Row totals for percentage computation
    row_totals = pivot.sum(axis=1).clip(lower=1)

    # Assign colors: one per B value
    color_map: dict[str, str] = {}
    palette_idx = 0
    for b_val in b_order:
        b_str = str(b_val)
        if b_str == "Other":
            color_map[b_val] = _OTHER_COLOR
        elif b_str.startswith("Unknown"):
            color_map[b_val] = _UNKNOWN_COLOR
        else:
            color_map[b_val] = _PALETTE[palette_idx % len(_PALETTE)]
            palette_idx += 1

    # Collect per-A-value Other counts before restricting the trace list
    other_per_a: dict[str, int] = {}
    if "Other" in b_order and "Other" in pivot.columns:
        for a in a_order:
            if a in pivot.index:
                v = int(pivot.loc[a, "Other"])
                if v > 0:
                    other_per_a[a] = v

    y_reversed = list(reversed(a_order))
    y_base = wrap_labels(y_reversed)
    y_display = [
        f"{lbl}<br><sup>({other_per_a[a]:,} other)</sup>" if a in other_per_a else lbl
        for lbl, a in zip(y_base, y_reversed)
    ]
    has_wrapped = any("<br>" in lbl for lbl in y_display)

    fig = go.Figure()
    for i, b_val in enumerate(bv for bv in b_order if bv != "Other"):
        y_vals = [pivot.loc[a, b_val] for a in y_reversed]
        pct_vals = [
            pivot.loc[a, b_val] / row_totals[a] * 100
            for a in y_reversed
        ]
        text_labels = [
            f"{int(v):,} ({p:.0f}%)" if v > 0 else ""
            for v, p in zip(y_vals, pct_vals)
        ]
        fig.add_trace(go.Bar(
            name=str(b_val),
            y=y_display,
            x=y_vals,
            orientation="h",
            marker_color=color_map[b_val],
            text=text_labels,
            textposition="inside",
            insidetextanchor="middle",
            textangle=0,
            legendrank=i,
            hovertemplate=(
                f"<b>{b_val}</b><br>"
                "%{y}: %{x:,} " + metric_label.lower() +
                " (%{customdata:.1f}%)<extra></extra>"
            ),
            customdata=pct_vals,
        ))

    scope_text = "Combined" if scope == "all" else f"Show: {scope}"
    fig.update_layout(
        title=dict(
            text=(
                f"{metric_label} — {prop_B_label} distribution within {prop_A_label}<br>"
                f"<sup>{scope_text}</sup>"
            ),
            x=0.5,
        ),
        barmode="stack",
        xaxis=dict(title=metric_label, rangemode="tozero"),
        yaxis=dict(title=prop_A_label, automargin=True),
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.3,
            xanchor="center",
            x=0.5,
            title_text=prop_B_label,
        ),
        height=max(400, (40 if has_wrapped else 30) * len(a_order) + 200),
        margin=dict(t=100, r=80, b=150),
    )
    apply_font(fig)
    return fig


def _build_combined_cross_fig(
    unique_pivot: pd.DataFrame,
    app_pivot: pd.DataFrame,
    a_order: list[str],
    b_order: list[str],
    prop_A_label: str,
    prop_B_label: str,
    scope: str,
) -> go.Figure:
    """Single figure: unique-guests stacked bars (top) + appearances stacked bars (bottom).

    The two subplot panels share the same color scheme and legend so the reader
    can compare both metrics in one view without needing to open two files.
    """
    unique_pivot = unique_pivot.reindex(index=a_order, columns=b_order, fill_value=0)
    app_pivot = app_pivot.reindex(index=a_order, columns=b_order, fill_value=0)
    unique_totals = unique_pivot.sum(axis=1).clip(lower=1)
    app_totals = app_pivot.sum(axis=1).clip(lower=1)

    color_map: dict[str, str] = {}
    palette_idx = 0
    for b_val in b_order:
        b_str = str(b_val)
        if b_str == "Other":
            color_map[b_val] = _OTHER_COLOR
        elif b_str.startswith("Unknown"):
            color_map[b_val] = _UNKNOWN_COLOR
        else:
            color_map[b_val] = _PALETTE[palette_idx % len(_PALETTE)]
            palette_idx += 1

    # Collect Other counts per A-value from both pivots for Y-axis annotations
    other_per_a_unique: dict[str, int] = {}
    other_per_a_app: dict[str, int] = {}
    if "Other" in b_order:
        if "Other" in unique_pivot.columns:
            for a in a_order:
                if a in unique_pivot.index:
                    v = int(unique_pivot.loc[a, "Other"])
                    if v > 0:
                        other_per_a_unique[a] = v
        if "Other" in app_pivot.columns:
            for a in a_order:
                if a in app_pivot.index:
                    v = int(app_pivot.loc[a, "Other"])
                    if v > 0:
                        other_per_a_app[a] = v

    y_reversed = list(reversed(a_order))
    y_base = wrap_labels(y_reversed)

    def _annotate(lbl: str, a: str) -> str:
        u = other_per_a_unique.get(a, 0)
        ap = other_per_a_app.get(a, 0)
        if u == 0 and ap == 0:
            return lbl
        parts = []
        if u > 0:
            parts.append(f"{u:,} unique other")
        if ap > 0:
            parts.append(f"{ap:,} app other")
        return f"{lbl}<br><sup>({', '.join(parts)})</sup>"

    y_display = [_annotate(lbl, a) for lbl, a in zip(y_base, y_reversed)]
    n_a = len(a_order)
    has_wrapped = any("<br>" in lbl for lbl in y_display)
    row_h = max(180, (32 if has_wrapped else 28) * n_a + 60)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=False,
        vertical_spacing=0.10,
        subplot_titles=("Unique Guests", "Appearances"),
    )

    for i, b_val in enumerate(bv for bv in b_order if bv != "Other"):
        color = color_map[b_val]

        y_u = [unique_pivot.loc[a, b_val] for a in y_reversed]
        pct_u = [unique_pivot.loc[a, b_val] / unique_totals[a] * 100 for a in y_reversed]
        text_u = [f"{int(v):,} ({p:.0f}%)" if v > 0 else "" for v, p in zip(y_u, pct_u)]

        y_a = [app_pivot.loc[a, b_val] for a in y_reversed]
        pct_a = [app_pivot.loc[a, b_val] / app_totals[a] * 100 for a in y_reversed]
        text_a = [f"{int(v):,} ({p:.0f}%)" if v > 0 else "" for v, p in zip(y_a, pct_a)]

        fig.add_trace(go.Bar(
            name=str(b_val),
            y=y_display, x=y_u,
            orientation="h",
            marker_color=color,
            text=text_u, textposition="inside", insidetextanchor="middle",
            textangle=0, legendrank=i, legendgroup=str(b_val), showlegend=True,
            hovertemplate=(
                f"<b>{b_val}</b><br>"
                "%{y}: %{x:,} unique guests (%{customdata:.1f}%)<extra></extra>"
            ),
            customdata=pct_u,
        ), row=1, col=1)

        fig.add_trace(go.Bar(
            name=str(b_val),
            y=y_display, x=y_a,
            orientation="h",
            marker_color=color,
            text=text_a, textposition="inside", insidetextanchor="middle",
            textangle=0, legendrank=i, legendgroup=str(b_val), showlegend=False,
            hovertemplate=(
                f"<b>{b_val}</b><br>"
                "%{y}: %{x:,} appearances (%{customdata:.1f}%)<extra></extra>"
            ),
            customdata=pct_a,
        ), row=2, col=1)

    scope_text = "Combined" if scope == "all" else f"Show: {scope}"
    fig.update_layout(
        title=dict(
            text=(
                f"{prop_B_label} distribution within {prop_A_label}<br>"
                f"<sup>{scope_text}</sup>"
            ),
            x=0.5,
        ),
        barmode="stack",
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.2,
            xanchor="center", x=0.5,
            title_text=prop_B_label,
        ),
        height=row_h * 2 + 200,
        margin=dict(t=100, r=80, b=150),
    )
    fig.update_xaxes(rangemode="tozero")
    fig.update_yaxes(automargin=True)
    fig.update_yaxes(title_text=prop_A_label, row=1, col=1)
    fig.update_yaxes(title_text=prop_A_label, row=2, col=1)
    apply_font(fig)
    return fig


def build_cross_property_stacked_bars(
    frame_A: pd.DataFrame,
    frame_B: pd.DataFrame,
    prop_A_label: str,
    prop_B_label: str,
    prop_A_id: str,
    prop_B_id: str,
    output_dir: Path,
    scope: str = "all",
    top_n_A: int = 15,
    top_n_B: int = 8,
) -> None:
    """Generate cross-property stacked bar charts (unique guests + appearances).

    Two charts are produced for each (A, B) pair:
      - cross_{A_id}_{B_id}_unique.png  — unique-guest counts per (A value, B value)
      - cross_{A_id}_{B_id}_appearances.png — appearance counts per (A value, B value)

    Args:
        frame_A: Per-person-value frame for property A.
            Required columns: canonical_entity_id, value, appearance_count.
        frame_B: Per-person-value frame for property B.
            Required columns: canonical_entity_id, value.
        prop_A_label: Human-readable label for property A (Y axis).
        prop_B_label: Human-readable label for property B (bar segments).
        prop_A_id: Short identifier for A used in output file names (e.g. "P21").
        prop_B_id: Short identifier for B used in output file names (e.g. "P106").
        output_dir: Directory that contains the "visualizations/" sub-folder.
        scope: "all" or a show ID — used only in chart titles.
        top_n_A: How many top A values to include on the Y axis.
        top_n_B: How many top B value segments to show per bar (rest → "Other").
    """
    if frame_A is None or frame_A.empty or frame_B is None or frame_B.empty:
        return

    req_A = {"canonical_entity_id", "value"}
    req_B = {"canonical_entity_id", "value"}
    if not req_A.issubset(frame_A.columns) or not req_B.issubset(frame_B.columns):
        raise ValueError("Both frames must have columns: canonical_entity_id, value")

    # Strip unknowns and blanks from both frames
    def _clean(df: pd.DataFrame) -> pd.DataFrame:
        mask = (
            df["value"].fillna("").astype(str).str.strip().ne("")
            & ~df["value"].astype(str).str.startswith("Unknown")
        )
        return df[mask].copy()

    fa = _clean(frame_A)
    fb = _clean(frame_B)

    if fa.empty or fb.empty:
        return

    # Unique (entity, value) pairs for each property
    entities_A = fa[["canonical_entity_id", "value"]].drop_duplicates().rename(
        columns={"value": "value_A"}
    )
    entities_B = fb[["canonical_entity_id", "value"]].drop_duplicates().rename(
        columns={"value": "value_B"}
    )

    # Appearance count per entity (from frame_A — total appearances across episodes)
    if "appearance_count" in fa.columns:
        app_per_entity = (
            fa.groupby("canonical_entity_id")["appearance_count"]
            .sum()
            .reset_index()
        )
    else:
        app_per_entity = None

    # Cross-join: entities that have BOTH A and B values
    cross = entities_A.merge(entities_B, on="canonical_entity_id")
    if cross.empty:
        return

    # ---- Unique guests pivot ----
    unique_pivot = (
        cross.groupby(["value_A", "value_B"])["canonical_entity_id"]
        .nunique()
        .reset_index()
        .rename(columns={"canonical_entity_id": "unique_guests"})
    )
    unique_wide = unique_pivot.pivot(index="value_A", columns="value_B", values="unique_guests").fillna(0)

    # ---- Appearances pivot ----
    if app_per_entity is not None:
        cross_app = cross.merge(app_per_entity, on="canonical_entity_id", how="left")
        app_pivot = (
            cross_app.groupby(["value_A", "value_B"])["appearance_count"]
            .sum()
            .reset_index()
        )
        app_wide = app_pivot.pivot(index="value_A", columns="value_B", values="appearance_count").fillna(0)
    else:
        app_wide = unique_wide.copy()

    # Top-N A values (by unique guest total across all B values)
    a_totals = unique_wide.sum(axis=1)
    top_a = _top_values(a_totals, top_n_A)

    # Top-N B values (by total unique guests across all A values)
    b_totals = unique_wide.sum(axis=0)
    top_b = _top_values(b_totals, top_n_B)

    def _add_other_col(wide: pd.DataFrame, top_b_vals: list[str]) -> pd.DataFrame:
        all_b = [c for c in wide.columns if c not in top_b_vals]
        out = wide[top_b_vals].copy()
        if all_b:
            out["Other"] = wide[all_b].sum(axis=1)
        return out

    unique_plot = _add_other_col(unique_wide, top_b)
    app_plot = _add_other_col(app_wide, top_b)

    b_cols = top_b + (["Other"] if "Other" in unique_plot.columns else [])

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    a_slug = prop_A_label.lower().replace(" ", "_").replace("/", "_")[:15]
    b_slug = prop_B_label.lower().replace(" ", "_").replace("/", "_")[:15]
    prefix = f"cross_{prop_A_id}_{a_slug}_{prop_B_id}_{b_slug}"

    # Single combined chart: unique guests (top) + appearances (bottom)
    fig_combined = _build_combined_cross_fig(
        unique_plot, app_plot, top_a, b_cols,
        prop_A_label, prop_B_label, scope,
    )
    save_fig(fig_combined, viz_dir / prefix)

    print(
        f"  Cross-property [{prop_A_label} × {prop_B_label}]: "
        f"{len(top_a)} A-values × {len(b_cols)} B-values"
    )


def build_property_top_persons_chart(
    frame_A: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    prop_A_label: str,
    prop_A_id: str,
    output_dir: Path,
    scope: str = "all",
    top_n_values: int = 6,
    top_n_persons: int = 20,
) -> None:
    """For each top value of property A, show the top guests who carry that value.

    For each value (e.g., "female", "Journalist", "SPD"), produces a horizontal
    stacked bar chart: Y axis = top-N guests by appearance count, X axis =
    appearances, bar segments = broadcasting show (coloured by show).

    Args:
        frame_A: Per-person-value frame for property A.
            Required columns: canonical_entity_id, value, canonical_label.
        episode_appearances: Episode-level appearances frame.
            Required columns: canonical_entity_id, show_id, role.
            Optional: program_name.
        prop_A_label: Human-readable label for property A.
        prop_A_id: Short identifier used in output file names (e.g. "P21").
        output_dir: Directory containing the "visualizations/" sub-folder.
        scope: "all" or show ID — used in chart titles only.
        top_n_values: How many top property values get their own chart.
        top_n_persons: How many top persons to show per value chart.
    """
    if frame_A is None or frame_A.empty:
        return
    if episode_appearances is None or episode_appearances.empty:
        return

    req = {"canonical_entity_id", "value"}
    if not req.issubset(frame_A.columns):
        raise ValueError("frame_A must have columns: canonical_entity_id, value")
    if "canonical_entity_id" not in episode_appearances.columns or "show_id" not in episode_appearances.columns:
        raise ValueError("episode_appearances must have columns: canonical_entity_id, show_id")

    # Only guest-role appearances for counting
    guest_ep = episode_appearances[episode_appearances.get("role", pd.Series("guest", index=episode_appearances.index)) == "guest"].copy() if "role" in episode_appearances.columns else episode_appearances.copy()

    # Show label map
    show_labels: dict[str, str] = {}
    if "program_name" in guest_ep.columns:
        show_labels = (
            guest_ep[["show_id", "program_name"]]
            .drop_duplicates()
            .set_index("show_id")["program_name"]
            .to_dict()
        )

    # Per-guest per-show appearance counts (all guests, to use for filtering)
    guest_show = (
        guest_ep.groupby(["canonical_entity_id", "show_id"])
        .size()
        .reset_index(name="show_appearances")
    )
    guest_total = (
        guest_show.groupby("canonical_entity_id")["show_appearances"]
        .sum()
        .reset_index(name="total_appearances")
    )

    # Show ordering (largest show first, so it becomes the leftmost/bottom segment)
    show_totals = guest_ep.groupby("show_id").size().reset_index(name="show_total")
    ordered_shows = show_totals.sort_values("show_total", ascending=False)["show_id"].tolist()
    show_color_map = {
        sid: _PALETTE[i % len(_PALETTE)]
        for i, sid in enumerate(ordered_shows)
    }

    # Filter out unknowns from property frame
    clean_A = frame_A[
        frame_A["value"].fillna("").astype(str).str.strip().ne("")
        & ~frame_A["value"].astype(str).str.startswith("Unknown")
    ].copy()

    # Entity → label map
    label_col = "canonical_label" if "canonical_label" in frame_A.columns else None

    # Top-N property values by unique guest count
    value_counts = (
        clean_A.groupby("value")["canonical_entity_id"].nunique()
        .sort_values(ascending=False)
    )
    top_values = value_counts.head(top_n_values).index.tolist()

    viz_dir = output_dir / "visualizations" / f"by_value_{prop_A_id}"
    viz_dir.mkdir(parents=True, exist_ok=True)

    scope_text = "Combined" if scope == "all" else f"Show: {scope}"

    for val in top_values:
        val_entities = set(
            clean_A.loc[clean_A["value"] == val, "canonical_entity_id"].dropna().unique()
        )
        if not val_entities:
            continue

        # Merge with totals to get top persons for this value
        val_total = guest_total[guest_total["canonical_entity_id"].isin(val_entities)].copy()
        if val_total.empty:
            continue
        top_persons = val_total.nlargest(top_n_persons, "total_appearances")["canonical_entity_id"].tolist()

        # Build per-person per-show data
        val_show = guest_show[guest_show["canonical_entity_id"].isin(top_persons)].copy()

        # Labels for top persons
        if label_col:
            label_map = (
                frame_A[frame_A["canonical_entity_id"].isin(top_persons)]
                [["canonical_entity_id", label_col]]
                .drop_duplicates("canonical_entity_id")
                .set_index("canonical_entity_id")[label_col]
                .to_dict()
            )
        else:
            label_map = {p: p for p in top_persons}

        # Sort persons by total appearances descending, Y order (reversed for top-down)
        person_order_asc = [
            p for p in
            val_total[val_total["canonical_entity_id"].isin(top_persons)]
            .sort_values("total_appearances", ascending=True)["canonical_entity_id"]
            .tolist()
        ]
        y_labels = wrap_labels([label_map.get(p, p) for p in person_order_asc])
        has_wrapped = any("<br>" in lbl for lbl in y_labels)

        fig = go.Figure()
        for i, show_id in enumerate(ordered_shows):
            show_data = val_show[val_show["show_id"] == show_id]
            y_vals = []
            x_vals = []
            for p, lbl in zip(person_order_asc, y_labels):
                row = show_data[show_data["canonical_entity_id"] == p]
                n = int(row["show_appearances"].iloc[0]) if not row.empty else 0
                y_vals.append(lbl)
                x_vals.append(n)

            display_name = show_labels.get(show_id, show_id)
            text_labels = [str(v) if v > 0 else "" for v in x_vals]
            fig.add_trace(go.Bar(
                name=display_name,
                y=y_vals,
                x=x_vals,
                orientation="h",
                marker_color=show_color_map.get(show_id, _UNKNOWN_COLOR),
                text=text_labels,
                textposition="inside",
                insidetextanchor="middle",
                textangle=0,
                legendrank=i,
                hovertemplate=(
                    f"<b>{display_name}</b><br>"
                    "%{y}: %{x:,} appearances<extra></extra>"
                ),
            ))

        n_shown = len(top_persons)
        val_slug = str(val).lower().replace(" ", "_").replace("/", "_")[:30]
        fig.update_layout(
            title=dict(
                text=(
                    f"Top guests — {prop_A_label}: {val}<br>"
                    f"<sup>{scope_text} · top {n_shown} by appearances</sup>"
                ),
                x=0.5,
            ),
            barmode="stack",
            xaxis=dict(title="Appearances", rangemode="tozero"),
            yaxis=dict(title="Guest", automargin=True),
            template="plotly_white",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.3,
                xanchor="center",
                x=0.5,
                title_text="Show",
            ),
            height=max(400, (40 if has_wrapped else 30) * n_shown + 200),
            margin=dict(t=100, r=80, b=150),
        )
        apply_font(fig)
        a_short = prop_A_label.lower().replace(" ", "_").replace("/", "_")[:15]
        save_fig(fig, viz_dir / f"top_persons_{prop_A_id}_{a_short}_{val_slug}")

    print(f"  Property×Person [{prop_A_label}]: charts written to {viz_dir.name}/")
