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
from .viz_universal import _PALETTE
from .viz_base import PALETTE, apply_font, save_fig


def _ensure_path(path: str | Path) -> Path:
    return Path(path)


def build_guest_frequency_pareto_outputs(
    guest_catalogue: pd.DataFrame,
    output_dir: str | Path,
    viz_dir: str | Path,
    *,
    top_n: int = 25,
    episode_appearances: pd.DataFrame | None = None,
) -> dict[str, pd.DataFrame | Path]:
    """Write guest frequency and Pareto outputs and return the generated tables.

    When *episode_appearances* is supplied the Pareto bar chart becomes a stacked
    bar where each segment represents one broadcasting show.  Each segment is
    labelled with its appearance count and percentage of that show's total
    appearances; the overall total + its percentage of all appearances is
    annotated above each full bar.
    """

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

    if episode_appearances is not None and not episode_appearances.empty and "show_id" in episode_appearances.columns:
        fig = _build_stacked_pareto(pareto_top, episode_appearances, guest_appearance_counts)
    else:
        fig = _build_simple_pareto(pareto_top, guest_appearance_counts)

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


def _build_simple_pareto(
    pareto_top: pd.DataFrame,
    guest_appearance_counts: pd.DataFrame,
) -> go.Figure:
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
                f"<sup>{len(guest_appearance_counts):,} unique guests · "
                f"{int(guest_appearance_counts['appearance_count'].sum()):,} total appearances</sup>"
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
    return fig


def _build_stacked_pareto(
    pareto_top: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    guest_appearance_counts: pd.DataFrame,
) -> go.Figure:
    guest_ep = episode_appearances[episode_appearances["role"] == "guest"].copy()

    # Per-show total appearances (denominator for segment percentages)
    show_totals = (
        guest_ep.groupby("show_id").size().reset_index(name="show_total")
    )
    # Use program_name if available, else show_id
    if "program_name" in guest_ep.columns:
        show_labels = (
            guest_ep[["show_id", "program_name"]]
            .drop_duplicates()
            .set_index("show_id")["program_name"]
            .to_dict()
        )
    else:
        show_labels = {}

    # Per-guest per-show appearances (for top-N guests only)
    top_ceids = set(pareto_top["canonical_entity_id"].dropna())
    guest_show = (
        guest_ep[guest_ep["canonical_entity_id"].isin(top_ceids)]
        .groupby(["canonical_entity_id", "show_id"])
        .size()
        .reset_index(name="show_appearances")
        .merge(show_totals, on="show_id", how="left")
    )
    guest_show["pct_of_show"] = (
        guest_show["show_appearances"] / guest_show["show_total"].clip(lower=1) * 100
    ).round(1)

    total_all = max(int(guest_ep.shape[0]), 1)
    label_order = pareto_top["canonical_label"].tolist()
    ceid_to_label = pareto_top.set_index("canonical_entity_id")["canonical_label"].to_dict()

    # Ordered list of shows (by total appearances desc, so dominant show is bottom)
    ordered_shows = (
        show_totals.sort_values("show_total", ascending=False)["show_id"].tolist()
    )
    show_color_map = {
        sid: _PALETTE[i % len(_PALETTE)]
        for i, sid in enumerate(ordered_shows)
    }

    fig = go.Figure()
    for show_id in ordered_shows:
        show_data = guest_show[guest_show["show_id"] == show_id].copy()
        # Build a row for every top guest (fill 0 if not on this show)
        merged = pd.DataFrame({"canonical_entity_id": list(top_ceids)})
        merged["canonical_label"] = merged["canonical_entity_id"].map(ceid_to_label)
        merged = merged.merge(
            show_data[["canonical_entity_id", "show_appearances", "pct_of_show"]],
            on="canonical_entity_id",
            how="left",
        )
        merged["show_appearances"] = merged["show_appearances"].fillna(0).astype(int)
        merged["pct_of_show"] = merged["pct_of_show"].fillna(0.0)
        # Restore pareto sort order
        merged = merged.set_index("canonical_label").reindex(label_order).reset_index()

        display_name = show_labels.get(show_id, show_id)
        text_labels = [
            f"{int(v)} ({p:.1f}%)" if v > 0 else ""
            for v, p in zip(merged["show_appearances"], merged["pct_of_show"])
        ]
        fig.add_trace(go.Bar(
            name=display_name,
            x=merged["canonical_label"],
            y=merged["show_appearances"],
            marker_color=show_color_map[show_id],
            text=text_labels,
            textposition="inside",
            insidetextanchor="middle",
            hovertemplate=(
                f"<b>{display_name}</b><br>"
                "%{x}: %{y:,} appearances (%{customdata:.1f}% of show)<extra></extra>"
            ),
            customdata=merged["pct_of_show"],
        ))

    # Annotations: total + % of all above each bar
    annotations = []
    for _, row in pareto_top.iterrows():
        total = int(row["appearance_count"])
        pct_all = total / total_all * 100
        annotations.append(dict(
            x=row["canonical_label"],
            y=total,
            text=f"<b>{total}</b> ({pct_all:.1f}%)",
            xanchor="center",
            yanchor="bottom",
            showarrow=False,
            font=dict(size=9),
            yshift=3,
        ))

    unique_guests = len(guest_appearance_counts)
    fig.update_layout(
        title=dict(
            text=(
                "Top Guests by Appearances — Stacked by Broadcasting Program<br>"
                f"<sup>{unique_guests:,} unique guests · {total_all:,} total guest appearances</sup>"
            ),
            x=0.5,
        ),
        barmode="stack",
        xaxis=dict(title="Guest", tickangle=-40, automargin=True),
        yaxis=dict(title="Appearances", rangemode="tozero"),
        template="plotly_white",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.06,
            xanchor="right",
            x=1,
            title_text="Show",
        ),
        annotations=annotations,
        height=max(560, 32 * len(pareto_top) + 240),
        margin=dict(t=160, b=120),
    )
    return fig


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