"""Person-level visualizations (TASK-F10).

- Co-occurrence encounter matrix heatmap (top-N guests × top-N guests).
- Relevance score bar chart (top-N guests by computed relevance).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig


_PALETTE = [
    "#0072B2", "#E69F00", "#009E73", "#56B4E9",
    "#D55E00", "#CC79A7", "#F0E442",
]


def _scope_text(scope: str) -> str:
    return "Combined" if scope == "all" else f"Show: {scope}"


# ──────────────────────────────────────────────────────────────────────────────
# Co-occurrence heatmap
# ──────────────────────────────────────────────────────────────────────────────

def build_cooccurrence_heatmap(
    co_occurrence_pairs: pd.DataFrame,
    catalogue: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
    top_n: int = 40,
) -> None:
    """Heatmap of top-N guests × top-N guests, colored by co-appearance count.

    Only the top-N guests (by total appearances) are shown. Cell value = number
    of episodes in which both guests appeared simultaneously.

    Args:
        co_occurrence_pairs: DataFrame with columns [guest_a, guest_b, co_occurrence_count].
            Each row represents an unordered pair of guests who shared at least one episode.
        catalogue: Person catalogue. Used for canonical_entity_id → canonical_label mapping.
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or a show ID — used in chart titles only.
        top_n: Number of top guests (by appearances) to include on each axis.
    """
    if co_occurrence_pairs is None or co_occurrence_pairs.empty:
        return
    if catalogue is None or catalogue.empty:
        return

    # Top-N guests by appearance count
    top_guests = (
        catalogue[catalogue["role"] == "guest"]
        .sort_values("appearance_count", ascending=False)
        .head(top_n)
    )
    if top_guests.empty:
        return

    top_ceids = top_guests["canonical_entity_id"].tolist()
    label_map = top_guests.set_index("canonical_entity_id")["canonical_label"].to_dict()

    # Build a square matrix of co-occurrence counts
    n = len(top_ceids)
    matrix: dict[tuple, int] = {}
    for _, row in co_occurrence_pairs.iterrows():
        a, b = str(row["guest_a"]), str(row["guest_b"])
        count = int(row["co_occurrence_count"])
        if a in label_map and b in label_map:
            matrix[(a, b)] = count
            matrix[(b, a)] = count

    z_vals = [
        [matrix.get((a, b), 0) if a != b else 0 for b in top_ceids]
        for a in top_ceids
    ]
    labels = [label_map.get(c, c) for c in top_ceids]
    max_val = max((max(row) for row in z_vals if row), default=1)

    fig = go.Figure(go.Heatmap(
        z=z_vals,
        x=labels,
        y=labels,
        colorscale="Blues",
        zmin=0,
        zmax=max_val,
        colorbar=dict(title="Co-appearances"),
        hovertemplate="%{y} & %{x}: %{z} shared episodes<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=(
                f"Guest Co-occurrence Matrix<br>"
                f"<sup>{_scope_text(scope)} · top {n} guests by appearance count</sup>"
            ),
            x=0.5,
        ),
        xaxis=dict(tickangle=-45, side="bottom", automargin=True),
        yaxis=dict(autorange="reversed", automargin=True),
        template="plotly_white",
        height=max(500, 12 * n + 200),
        width=max(600, 12 * n + 300),
        margin=dict(t=110, b=130, l=160, r=60),
    )
    apply_font(fig, font_size=9)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / "cooccurrence_heatmap")
    print(f"  Co-occurrence heatmap: {n}×{n} matrix → {viz_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Relevance score bar chart
# ──────────────────────────────────────────────────────────────────────────────

def build_relevance_chart(
    relevance_df: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
    top_n: int = 30,
) -> None:
    """Horizontal bar chart of top-N guests by relevance score.

    Args:
        relevance_df: DataFrame produced by `compute_person_relevance`.
            Must have columns: canonical_label, relevance_score, appearance_count,
            claim_count, show_diversity.
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or show ID.
        top_n: Number of guests to display.
    """
    if relevance_df is None or relevance_df.empty:
        return
    if "relevance_score" not in relevance_df.columns:
        return

    df = (
        relevance_df
        .sort_values("relevance_score", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    if df.empty:
        return

    # Sort ascending so top rank appears at the top of horizontal bar
    df = df.iloc[::-1].reset_index(drop=True)
    label_col = "canonical_label" if "canonical_label" in df.columns else df.columns[0]
    labels = df[label_col].astype(str).tolist()
    scores = df["relevance_score"].tolist()

    hover_parts = ["<b>%{y}</b>"]
    if "appearance_count" in df.columns:
        hover_parts.append("Appearances: " + df["appearance_count"].astype(str))
    if "claim_count" in df.columns:
        hover_parts.append("Wikidata claims: " + df["claim_count"].astype(str))
    if "show_diversity" in df.columns:
        hover_parts.append("Show diversity: " + df["show_diversity"].round(2).astype(str))

    fig = go.Figure(go.Bar(
        x=scores,
        y=labels,
        orientation="h",
        marker_color=_PALETTE[0],
        text=[f"{s:.1f}" for s in scores],
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Relevance: %{x:.2f}<extra></extra>"
        ),
    ))
    fig.update_layout(
        title=dict(
            text=(
                f"Top Guests by Relevance Score<br>"
                f"<sup>{_scope_text(scope)} · "
                "score = appearances × log(1 + claims) × show_diversity</sup>"
            ),
            x=0.5,
        ),
        xaxis=dict(title="Relevance Score", rangemode="tozero"),
        yaxis=dict(title="Guest", automargin=True),
        template="plotly_white",
        height=max(400, 22 * len(df) + 180),
        margin=dict(t=110, r=100),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / "guest_relevance_ranking")
    print(f"  Relevance chart: top {len(df)} guests → {viz_dir.name}/")
