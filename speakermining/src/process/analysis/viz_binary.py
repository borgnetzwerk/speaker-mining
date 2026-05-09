"""Binary presence analysis for string-type properties (TASK-F08).

For string properties (e.g. IMDB ID P345, Wikimedia Commons P18, Twitter/X P2002),
the meaningful question is not "what is the value?" but "does this guest have a value
at all?".  This module:

1. Computes per-guest binary presence (has_value: True/False) for each string property.
2. Writes `{pid}_binary_presence.csv` with has_value rate per show and combined.
3. Produces a grouped bar chart: X = shows, Y = % of guests with a value,
   bars grouped by string property.  This answers "which shows have guests with
   better external profile coverage (IMDB, Wikipedia photo, social media)?"
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig
from .color_registry import PALETTE as _PALETTE


_UNKNOWN_PREFIX = "Unknown"


def _scope_text(scope: str) -> str:
    return "Combined" if scope == "all" else f"Show: {scope}"


def _has_value(frame: pd.DataFrame) -> pd.Series:
    """Return a boolean Series: True if the row has a non-empty, non-Unknown value."""
    return (
        frame["value"].fillna("").astype(str).str.strip().ne("")
        & ~frame["value"].astype(str).str.startswith(_UNKNOWN_PREFIX)
    )


def compute_binary_presence(
    standard_frame: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    prop_id: str,
    prop_label: str,
    output_dir: Path,
) -> pd.DataFrame:
    """Compute and write binary presence stats for one string property.

    Coverage = % of unique guests (in this show's guest population) that have at
    least one non-Unknown value for this property.

    Args:
        standard_frame: Expanded property frame.
            Required columns: canonical_entity_id, value.
        episode_appearances: Full episode appearances frame.
            Required columns: canonical_entity_id, show_id, role.
        prop_id: Property ID for output file naming.
        prop_label: Human-readable property label.
        output_dir: Property output directory (e.g. all/{property_slug}/).

    Returns:
        DataFrame with columns [scope, total_guests, guests_with_value, coverage_pct].
    """
    if standard_frame is None or standard_frame.empty:
        return pd.DataFrame()
    if episode_appearances is None or episode_appearances.empty:
        return pd.DataFrame()
    if "canonical_entity_id" not in standard_frame.columns:
        return pd.DataFrame()

    guest_ep = (
        episode_appearances[episode_appearances["role"] == "guest"].copy()
        if "role" in episode_appearances.columns
        else episode_appearances.copy()
    )
    if guest_ep.empty:
        return pd.DataFrame()

    # Entities that have a value for this property
    has_val_entities = set(
        standard_frame[_has_value(standard_frame)]["canonical_entity_id"].dropna().unique()
    )

    rows = []

    # Combined
    total_all = int(guest_ep["canonical_entity_id"].nunique())
    with_val_all = int(len(has_val_entities & set(guest_ep["canonical_entity_id"].unique())))
    rows.append({
        "scope": "all",
        "total_guests": total_all,
        "guests_with_value": with_val_all,
        "coverage_pct": round(with_val_all / max(total_all, 1) * 100, 1),
    })

    # Per show
    if "show_id" in guest_ep.columns:
        for show_id, show_group in guest_ep.groupby("show_id"):
            total = int(show_group["canonical_entity_id"].nunique())
            with_val = int(len(has_val_entities & set(show_group["canonical_entity_id"].unique())))
            rows.append({
                "scope": str(show_id),
                "total_guests": total,
                "guests_with_value": with_val,
                "coverage_pct": round(with_val / max(total, 1) * 100, 1),
            })

    result = pd.DataFrame(rows)
    out_path = output_dir / f"{prop_id}_binary_presence.csv"
    output_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(out_path, index=False)
    return result


def build_binary_presence_chart(
    presence_frames: dict,
    show_labels: dict,
    output_dir: Path,
    scope: str = "all",
) -> None:
    """Grouped bar chart comparing string property coverage across shows.

    X axis = shows (+ combined), Y axis = % of unique guests with a value,
    bars grouped by string property.

    Args:
        presence_frames: {prop_label: presence_df} as returned by
            `compute_binary_presence`. Each presence_df must have columns
            [scope, coverage_pct].
        show_labels: {show_id: program_name} for axis labels.
        output_dir: Scope output root; chart written to visualizations/.
        scope: "all" or a show ID — used in chart titles only.
    """
    if not presence_frames:
        return

    # Collect all scopes that appear in any frame
    all_scopes: list[str] = []
    for df in presence_frames.values():
        if df is not None and not df.empty:
            for s in df["scope"].tolist():
                if s not in all_scopes:
                    all_scopes.append(s)

    # Sort: "all" first, then show IDs
    all_scopes = ["all"] + [s for s in all_scopes if s != "all"]
    x_labels = [show_labels.get(s, s) if s != "all" else "Combined" for s in all_scopes]

    fig = go.Figure()
    for i, (prop_label, df) in enumerate(presence_frames.items()):
        if df is None or df.empty:
            continue
        pct_map = df.set_index("scope")["coverage_pct"].to_dict()
        y_vals = [float(pct_map.get(s, 0)) for s in all_scopes]
        text_labels = [f"{v:.0f}%" for v in y_vals]
        fig.add_trace(go.Bar(
            name=prop_label,
            x=x_labels,
            y=y_vals,
            text=text_labels,
            textposition="outside",
            marker_color=_PALETTE[i % len(_PALETTE)],
            hovertemplate=f"<b>{prop_label}</b><br>%{{x}}: %{{y:.1f}}%<extra></extra>",
        ))

    fig.update_layout(
        title=dict(
            text=(
                "String Property Coverage by Show<br>"
                "<sup>% of unique guests with at least one value per property</sup>"
            ),
            x=0.5,
        ),
        barmode="group",
        xaxis=dict(title="Show", tickangle=-30),
        yaxis=dict(title="Coverage (%)", rangemode="tozero", range=[0, 110]),
        template="plotly_white",
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0,
            xanchor="left",
            x=1.02,
            title_text="Property",
        ),
        height=500,
        margin=dict(t=110, r=220),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / "string_property_coverage")
    print(f"  String binary presence chart: {len(presence_frames)} properties → {viz_dir.name}/")


def build_all_binary_presence(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    analysis_properties: pd.DataFrame,
    output_dir: Path,
    scope: str = "all",
) -> None:
    """Build binary presence CSVs and combined chart for all string-type properties.

    Args:
        property_frames: {pid: standard_frame} from the property loop.
        property_labels: {pid: human-readable label}.
        episode_appearances: Full episode appearances frame.
        analysis_properties: analysis_properties DataFrame; used to identify
            string-type properties.
        output_dir: Scope output root.
        scope: "all" or show ID.
    """
    if analysis_properties is None or analysis_properties.empty:
        return

    string_pids = [
        str(row["wikidata_id"]).strip()
        for _, row in analysis_properties.iterrows()
        if str(row.get("type", "")).strip().lower() == "string"
        and str(row.get("enabled", "1")).strip() != "0"
        and str(row.get("wikidata_id", "")).strip() in property_frames
    ]
    if not string_pids:
        return

    # Build show_labels from episode_appearances
    show_labels: dict = {}
    if episode_appearances is not None and "show_id" in episode_appearances.columns and "program_name" in episode_appearances.columns:
        show_labels = (
            episode_appearances[["show_id", "program_name"]]
            .drop_duplicates()
            .set_index("show_id")["program_name"]
            .to_dict()
        )

    presence_frames: dict = {}
    for pid in string_pids:
        frame = property_frames.get(pid)
        if frame is None or frame.empty:
            continue
        label = property_labels.get(pid, pid)

        # Derive property output directory from label slug
        slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in label.strip())
        slug = "_".join(p for p in slug.split("_") if p)
        prop_dir = output_dir / slug

        pres_df = compute_binary_presence(frame, episode_appearances, pid, label, prop_dir)
        if not pres_df.empty:
            presence_frames[label] = pres_df
            print(f"  [{pid}] {label}: binary presence computed")

    if presence_frames:
        build_binary_presence_chart(presence_frames, show_labels, output_dir, scope=scope)
