"""Dashboard visualizations for the analysis notebooks.

The notebook layer should call these helpers and persist the returned tables,
but the chart construction and export logic belongs here so the same outputs
can be generated repeatedly under different configurations.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from process.io_guardrails import atomic_write_csv

from .meta_analysis import (
    compute_coverage_statistics,
    compute_per_show_coverage,
)
from .universal_stats import (
    build_frequency_distribution,
    build_pareto_table,
)
from .viz_base import PALETTE, apply_font, save_fig


def _ensure_path(path: str | Path) -> Path:
    return Path(path)


def build_guest_frequency_pareto_outputs(
    guest_catalogue: pd.DataFrame,
    output_dir: str | Path,
    viz_dir: str | Path,
    *,
    top_n: int = 25,
) -> dict[str, pd.DataFrame | Path]:
    """Write guest frequency and Pareto outputs and return the generated tables."""

    all_dir = _ensure_path(output_dir)
    viz_dir = _ensure_path(viz_dir)
    viz_dir.mkdir(parents=True, exist_ok=True)

    guest_appearance_counts = guest_catalogue[["canonical_entity_id", "appearance_count"]].drop_duplicates().copy()
    frequency_distribution = build_frequency_distribution(
        guest_appearance_counts,
        carrier_column="canonical_entity_id",
        appearance_column="appearance_count",
    ).rename(columns={"guest_count": "number_of_guests"})
    frequency_distribution = frequency_distribution.sort_values("frequency").reset_index(drop=True)
    frequency_distribution["appearances"] = frequency_distribution["frequency"] * frequency_distribution["number_of_guests"]
    frequency_distribution["cumulative_appearances"] = frequency_distribution["appearances"].cumsum()
    total_appearances = max(int(frequency_distribution["appearances"].sum()), 1)
    frequency_distribution["pct_cumulative_appearances"] = (
        frequency_distribution["cumulative_appearances"] / total_appearances * 100
    ).round(2)

    pareto_table = build_pareto_table(
        guest_appearance_counts,
        carrier_column="canonical_entity_id",
        appearance_column="appearance_count",
    )
    label_lookup = guest_catalogue[["canonical_entity_id", "canonical_label"]].drop_duplicates()
    pareto_table = pareto_table.merge(
        label_lookup,
        left_on="carrier",
        right_on="canonical_entity_id",
        how="left",
    )
    pareto_table["canonical_label"] = pareto_table["canonical_label"].fillna(pareto_table["carrier"])
    pareto_top = pareto_table.head(top_n).copy()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=pareto_top["canonical_label"],
        y=pareto_top["appearance_count"],
        name="Appearances",
        marker_color=PALETTE["blue"],
        text=pareto_top["appearance_count"],
        textposition="outside",
        hovertemplate="%{x}: %{y:,} appearances<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=pareto_top["canonical_label"],
        y=pareto_top["pct_cumulative_appearances"],
        name="Cumulative %",
        yaxis="y2",
        mode="lines+markers",
        line=dict(color=PALETTE["orange"], width=3),
        marker=dict(size=6),
        hovertemplate="%{x}: %{y:.2f}% cumulative appearances<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=(
                "Guest Appearance Frequency and Pareto Distribution<br>"
                f"<sup>{len(guest_appearance_counts):,} unique guests · {int(guest_appearance_counts['appearance_count'].sum()):,} total appearances</sup>"
            ),
            x=0.5,
        ),
        xaxis=dict(title="Guest", tickangle=-35),
        yaxis=dict(title="Appearances", rangemode="tozero"),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", rangemode="tozero", range=[0, 100]),
        barmode="overlay",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=max(500, 28 * len(pareto_top) + 180),
    )
    apply_font(fig)
    save_fig(fig, viz_dir / "guest_frequency_pareto")

    atomic_write_csv(all_dir / "guest_frequency_distribution.csv", frequency_distribution)
    atomic_write_csv(all_dir / "guest_frequency_pareto.csv", pareto_table)

    return {
        "frequency_distribution": frequency_distribution,
        "pareto_table": pareto_table,
        "pareto_top": pareto_top,
        "figure_path": viz_dir / "guest_frequency_pareto",
    }


def build_source_coverage_dashboards(
    reconciled_df: pd.DataFrame,
    episode_meta_df: pd.DataFrame,
    output_dir: str | Path,
    viz_dir: str | Path,
    *,
    overall_stats: pd.DataFrame | None = None,
    per_show_stats: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Write source-coverage dashboards and return the show-level coverage table."""

    all_dir = _ensure_path(output_dir)
    viz_dir = _ensure_path(viz_dir)
    source_viz_dir = viz_dir / "source_coverage"
    source_viz_dir.mkdir(parents=True, exist_ok=True)

    if overall_stats is None:
        overall_stats = compute_coverage_statistics(reconciled_df)
    if per_show_stats is None:
        per_show_stats = compute_per_show_coverage(reconciled_df, episode_meta_df)

    coverage_by_show = per_show_stats.copy()
    if coverage_by_show.empty:
        atomic_write_csv(all_dir / "source_coverage_dashboard.csv", coverage_by_show)
        return coverage_by_show

    coverage_by_show["matched_mentions"] = pd.to_numeric(coverage_by_show.get("matched_mentions", 0), errors="coerce").fillna(0).astype(int)
    coverage_by_show["total_mentions"] = pd.to_numeric(coverage_by_show.get("total_mentions", 0), errors="coerce").fillna(0).astype(int)
    coverage_by_show["unmatched_mentions"] = (coverage_by_show["total_mentions"] - coverage_by_show["matched_mentions"]).clip(lower=0)

    unique_coverage = (
        reconciled_df.copy()
        .assign(has_wikidata=lambda df: df["wikidata_id"].astype(str).str.strip().ne(""))
        .drop_duplicates(subset=["fernsehserien_de_id", "canonical_entity_id"])
        .groupby("fernsehserien_de_id")
        .agg(
            total_unique_people=("canonical_entity_id", "nunique"),
            matched_unique_people=("has_wikidata", "sum"),
        )
        .reset_index()
        .rename(columns={"fernsehserien_de_id": "show_id"})
    )
    unique_coverage["unique_coverage_pct"] = (
        unique_coverage["matched_unique_people"] / unique_coverage["total_unique_people"].clip(lower=1) * 100
    ).round(1)

    coverage_by_show = coverage_by_show.merge(unique_coverage, on="show_id", how="left")
    coverage_by_show["unique_coverage_pct"] = coverage_by_show["unique_coverage_pct"].fillna(0).round(1)
    coverage_by_show = coverage_by_show.sort_values(["coverage_pct", "total_mentions"], ascending=[False, False]).reset_index(drop=True)

    atomic_write_csv(all_dir / "source_coverage_dashboard.csv", coverage_by_show)

    overall_total = int(overall_stats.loc[overall_stats["metric"] == "Total Mentions Processed", "count"].iloc[0]) if not overall_stats.empty else 0
    overall_matched = int(overall_stats.loc[overall_stats["metric"] == "Matched to Wikidata", "count"].iloc[0]) if not overall_stats.empty else 0
    overall_unmatched = max(overall_total - overall_matched, 0)

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=["Matched to Wikidata", "Unmatched"],
        values=[overall_matched, overall_unmatched],
        hole=0.45,
        marker=dict(colors=[PALETTE["green"], PALETTE["gray"]]),
        textinfo="label+percent",
        sort=False,
        hovertemplate="%{label}: %{value:,} mentions<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=(
                "Overall Wikidata Reconciliation Coverage<br>"
                f"<sup>{overall_total:,} total mentions</sup>"
            ),
            x=0.5,
        ),
        template="plotly_white",
        height=420,
    )
    apply_font(fig)
    save_fig(fig, source_viz_dir / "coverage_overall")

    show_stack = coverage_by_show.sort_values("coverage_pct", ascending=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=show_stack["show_id"],
        x=show_stack["matched_mentions"],
        name="Matched mentions",
        orientation="h",
        marker_color=PALETTE["blue"],
        hovertemplate="%{y}: %{x:,} matched mentions<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=show_stack["show_id"],
        x=show_stack["unmatched_mentions"],
        name="Unmatched mentions",
        orientation="h",
        marker_color=PALETTE["gray"],
        hovertemplate="%{y}: %{x:,} unmatched mentions<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=(
                "Wikidata Coverage by Show<br>"
                f"<sup>{len(show_stack):,} shows · stacked matched vs unmatched mentions</sup>"
            ),
            x=0.5,
        ),
        barmode="stack",
        xaxis_title="Mentions",
        yaxis_title="Show ID",
        template="plotly_white",
        height=max(420, 26 * len(show_stack) + 180),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_font(fig)
    save_fig(fig, source_viz_dir / "coverage_by_show_stacked")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=show_stack["show_id"],
        y=show_stack["coverage_pct"],
        name="Mention coverage %",
        marker_color=PALETTE["green"],
        hovertemplate="%{x}: %{y:.1f}% mention coverage<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=show_stack["show_id"],
        y=show_stack["unique_coverage_pct"],
        name="Unique-person coverage %",
        marker_color=PALETTE["orange"],
        hovertemplate="%{x}: %{y:.1f}% unique-person coverage<extra></extra>",
    ))
    fig.update_layout(
        title=dict(
            text=(
                "Cross-Show Coverage Comparison<br>"
                f"<sup>mention-based vs unique-person coverage by show</sup>"
            ),
            x=0.5,
        ),
        barmode="group",
        xaxis_title="Show ID",
        yaxis_title="Coverage %",
        yaxis=dict(range=[0, 100]),
        template="plotly_white",
        height=max(420, 26 * len(show_stack) + 180),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    apply_font(fig)
    save_fig(fig, source_viz_dir / "coverage_comparison_by_show")

    return coverage_by_show