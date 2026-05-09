"""Scalar and quantity visualizations (TASK-F08).

Covers:
- Birth year grouped bar chart (by year or decade).
- Age-at-appearance distribution: violin + box + strip.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig
from .color_registry import PALETTE


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _scope_text(scope: str) -> str:
    return "Combined" if scope == "all" else f"Show: {scope}"


# ──────────────────────────────────────────────────────────────────────────────
# Birth-year bar chart
# ──────────────────────────────────────────────────────────────────────────────

def build_birth_year_chart(
    standard_frame: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
    decade_mode: bool = False,
    min_year: int = 1900,
    max_year: int = 2010,
) -> None:
    """Grouped bar chart: X = birth year (or decade), Y = unique guest count.

    Args:
        standard_frame: Expanded property frame for P569 (birth date).
            Must contain columns: canonical_entity_id, value (year string).
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or a show ID — used in chart titles.
        decade_mode: If True, group years into decades (e.g. 1970–1979 → "1970s").
        min_year: Exclude values below this year (noise filter).
        max_year: Exclude values above this year (noise filter).
    """
    if standard_frame is None or standard_frame.empty:
        return
    if "canonical_entity_id" not in standard_frame.columns or "value" not in standard_frame.columns:
        return

    df = standard_frame.copy()
    df["_year"] = pd.to_numeric(df["value"].astype(str).str[:4], errors="coerce")
    df = df.dropna(subset=["_year"])
    df["_year"] = df["_year"].astype(int)
    df = df[(df["_year"] >= min_year) & (df["_year"] <= max_year)]
    if df.empty:
        return

    if decade_mode:
        df["_group"] = (df["_year"] // 10 * 10).astype(str) + "s"
    else:
        df["_group"] = df["_year"].astype(str)

    counts = (
        df.groupby("_group")["canonical_entity_id"]
        .nunique()
        .reset_index(name="unique_guests")
        .sort_values("_group")
    )

    fig = go.Figure(go.Bar(
        x=counts["_group"],
        y=counts["unique_guests"],
        marker_color=PALETTE[0],
        text=counts["unique_guests"].astype(str),
        textposition="outside",
    ))
    group_label = "Decade" if decade_mode else "Birth Year"
    title_suffix = " (by decade)" if decade_mode else ""
    fig.update_layout(
        title=dict(
            text=(
                f"Guest Birth Year Distribution{title_suffix}<br>"
                f"<sup>{_scope_text(scope)}</sup>"
            ),
            x=0.5,
        ),
        xaxis=dict(title=group_label, tickangle=-45, type="category"),
        yaxis=dict(title="Unique Guests", rangemode="tozero"),
        template="plotly_white",
        height=480,
        margin=dict(t=100, b=100),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_by_decade" if decade_mode else ""
    save_fig(fig, viz_dir / f"birth_year_distribution{suffix}")
    print(f"  Birth year chart ({group_label}): {len(counts)} bars → {viz_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Age-at-appearance violin + box
# ──────────────────────────────────────────────────────────────────────────────

def build_age_distribution_chart(
    standard_frame: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
    per_show: bool = False,
    show_labels: dict | None = None,
) -> None:
    """Violin + box chart for appearance age distribution.

    Args:
        standard_frame: AGE derived property frame.
            Must contain: canonical_entity_id, value (integer age), and
            optionally show_id / program_name columns when per_show=True.
        output_dir: Scope output root.
        scope: "all" or show ID.
        per_show: If True and show_id is available, produce one violin per show.
        show_labels: {show_id: program_name} for axis labels.
    """
    if standard_frame is None or standard_frame.empty:
        return
    if "value" not in standard_frame.columns:
        return

    df = standard_frame.copy()
    df["_age"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["_age"])
    df["_age"] = df["_age"].astype(int)
    df = df[(df["_age"] >= 15) & (df["_age"] < 100)]
    if df.empty:
        return

    fig = go.Figure()

    if per_show and "show_id" in df.columns:
        show_ids = df["show_id"].dropna().unique().tolist()
        for i, sid in enumerate(sorted(show_ids)):
            ages = df[df["show_id"] == sid]["_age"].tolist()
            if not ages:
                continue
            label = (show_labels or {}).get(sid, sid) if show_labels else sid
            fig.add_trace(go.Violin(
                y=ages,
                name=label,
                box_visible=True,
                meanline_visible=True,
                points="outliers",
                marker_color=PALETTE[i % len(PALETTE)],
            ))
        title_text = f"Age at Appearance by Show<br><sup>{_scope_text(scope)}</sup>"
    else:
        ages = df["_age"].tolist()
        fig.add_trace(go.Violin(
            y=ages,
            name="All guests",
            box_visible=True,
            meanline_visible=True,
            points="outliers",
            marker_color=PALETTE[0],
        ))
        title_text = f"Age at Appearance Distribution<br><sup>{_scope_text(scope)}</sup>"

    median_age = df["_age"].median()
    fig.add_hline(
        y=median_age,
        line_dash="dot",
        line_color="#666666",
        annotation_text=f"Median: {median_age:.0f}",
        annotation_position="right",
    )

    fig.update_layout(
        title=dict(text=title_text, x=0.5),
        yaxis=dict(title="Age at Appearance"),
        template="plotly_white",
        height=520,
        margin=dict(t=100, r=100),
        showlegend=per_show,
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_by_show" if per_show else ""
    save_fig(fig, viz_dir / f"age_distribution{suffix}")
    print(f"  Age distribution violin{' (by show)' if per_show else ''} → {viz_dir.name}/")


def build_age_vs_appearances_scatter(
    catalogue: "pd.DataFrame",
    episode_appearances: "pd.DataFrame",
    output_dir: Path,
    scope: str = "all",
) -> None:
    """Scatter plot: age-at-first-appearance vs total appearance count.

    Each dot is one guest.  X = age at first appearance (derived from birthyear
    and earliest episode premiere date), Y = total appearance count.  Colored
    by show with the most appearances.

    Args:
        catalogue: Person catalogue with birthyear and appearance_count.
        episode_appearances: Episode appearances frame with premiere_date and show_id.
        output_dir: Scope output root.
        scope: "all" or show ID.
    """
    if catalogue is None or catalogue.empty:
        return
    if episode_appearances is None or episode_appearances.empty:
        return

    guest_cat = catalogue[catalogue["role"] == "guest"].copy()
    guest_cat["birthyear_num"] = pd.to_numeric(
        guest_cat["birthyear"].astype(str).str[:4], errors="coerce"
    )
    guest_cat = guest_cat.dropna(subset=["birthyear_num"])
    if guest_cat.empty:
        return

    guest_ep = episode_appearances[episode_appearances.get("role", pd.Series(dtype=str)) == "guest"].copy() if "role" in episode_appearances.columns else episode_appearances.copy()

    # Earliest episode year per guest
    if "premiere_date" in guest_ep.columns:
        guest_ep["_year"] = pd.to_numeric(guest_ep["premiere_date"].astype(str).str[:4], errors="coerce")
        first_year = guest_ep.groupby("canonical_entity_id")["_year"].min().reset_index(name="first_year")
        guest_cat = guest_cat.merge(first_year, on="canonical_entity_id", how="left")
        guest_cat["first_age"] = guest_cat["first_year"] - guest_cat["birthyear_num"]
        guest_cat = guest_cat[(guest_cat["first_age"] >= 15) & (guest_cat["first_age"] < 100)]
    else:
        return

    if guest_cat.empty:
        return

    # Dominant show per guest for color
    show_labels: dict = {}
    if "show_id" in guest_ep.columns:
        if "program_name" in guest_ep.columns:
            show_labels = (
                guest_ep[["show_id", "program_name"]]
                .drop_duplicates()
                .set_index("show_id")["program_name"]
                .to_dict()
            )
        dominant = (
            guest_ep.groupby(["canonical_entity_id", "show_id"])
            .size()
            .reset_index(name="n")
            .sort_values("n", ascending=False)
            .drop_duplicates("canonical_entity_id")
            [["canonical_entity_id", "show_id"]]
        )
        guest_cat = guest_cat.merge(dominant, on="canonical_entity_id", how="left")
        show_ids = sorted(guest_cat["show_id"].dropna().unique().tolist())
    else:
        show_ids = []

    fig = go.Figure()
    if show_ids:
        for i, sid in enumerate(show_ids):
            sub = guest_cat[guest_cat["show_id"] == sid]
            if sub.empty:
                continue
            label = show_labels.get(sid, sid)
            fig.add_trace(go.Scatter(
                x=sub["first_age"].tolist(),
                y=sub["appearance_count"].tolist(),
                mode="markers",
                name=label,
                marker=dict(color=PALETTE[i % len(PALETTE)], size=5, opacity=0.6),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Age at debut: %{x:.0f}<br>"
                    "Appearances: %{y}<extra></extra>"
                ),
                text=sub["canonical_label"].astype(str).tolist() if "canonical_label" in sub.columns else None,
            ))
    else:
        fig.add_trace(go.Scatter(
            x=guest_cat["first_age"].tolist(),
            y=guest_cat["appearance_count"].tolist(),
            mode="markers",
            name="Guests",
            marker=dict(color=PALETTE[0], size=5, opacity=0.6),
        ))

    fig.update_layout(
        title=dict(
            text=(
                f"Age at Debut vs Total Appearances<br>"
                f"<sup>{_scope_text(scope)}</sup>"
            ),
            x=0.5,
        ),
        xaxis=dict(title="Age at First Appearance"),
        yaxis=dict(title="Total Appearances", rangemode="tozero"),
        template="plotly_white",
        legend=dict(orientation="v", x=1.02, y=1.0, xanchor="left"),
        height=520,
        margin=dict(t=100, r=200),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / "scatter_age_vs_appearances")
    print(f"  Scatter (age vs appearances): {len(guest_cat)} guests → {viz_dir.name}/")


def build_all_scalar_charts(
    property_frames: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
) -> None:
    """Convenience wrapper: build all scalar charts from property_frames.

    Looks for P569 (birth date / year) and AGE (derived age) frames.

    Args:
        property_frames: {pid: standard_frame} from the property loop.
        episode_appearances: Full episode appearances frame (for show labels).
        output_dir: Scope output root.
        scope: "all" or a show ID.
    """
    # Birth year chart
    birth_frame = property_frames.get("P569")
    if birth_frame is not None and not birth_frame.empty:
        build_birth_year_chart(birth_frame, output_dir, scope=scope, decade_mode=False)
        build_birth_year_chart(birth_frame, output_dir, scope=scope, decade_mode=True)

    # Age distribution
    age_frame = property_frames.get("AGE")
    if age_frame is not None and not age_frame.empty:
        show_labels: dict = {}
        if episode_appearances is not None and not episode_appearances.empty:
            if "show_id" in episode_appearances.columns and "program_name" in episode_appearances.columns:
                show_labels = (
                    episode_appearances[["show_id", "program_name"]]
                    .drop_duplicates()
                    .set_index("show_id")["program_name"]
                    .to_dict()
                )
        # Merge show_id into age_frame if available
        age_with_show = age_frame.copy()
        if (
            "canonical_entity_id" in age_with_show.columns
            and "episode_id" in age_with_show.columns
            and episode_appearances is not None
            and not episode_appearances.empty
            and "fernsehserien_de_id" in episode_appearances.columns
            and "show_id" in episode_appearances.columns
        ):
            ep_show = (
                episode_appearances[["fernsehserien_de_id", "show_id"]]
                .drop_duplicates()
                .rename(columns={"fernsehserien_de_id": "episode_id"})
            )
            age_with_show = age_with_show.merge(ep_show, on="episode_id", how="left")

        build_age_distribution_chart(age_with_show, output_dir, scope=scope, per_show=False)
        build_age_distribution_chart(age_with_show, output_dir, scope=scope, per_show=True, show_labels=show_labels)
