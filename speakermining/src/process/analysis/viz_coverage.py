"""Property coverage heatmap (TASK-F09).

Produces a heatmap where rows = properties, columns = shows,
cell = % of guest appearances that have a value for this property.
Answers: "Which properties are well-covered in which shows?"
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig


def build_property_coverage_dashboard(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    """Build a property × show coverage heatmap and write the backing CSV.

    Coverage is defined as: guest-episode pairs that have at least one non-Unknown
    value for this property, divided by total guest-episode pairs for that show.

    Args:
        property_frames: {pid: standard_frame} from the property loop.
            Each frame has columns: canonical_entity_id, episode_id, value.
        property_labels: {pid: human-readable label}.
        episode_appearances: full frame with canonical_entity_id,
            fernsehserien_de_id (=episode_id), show_id, program_name, role.
        output_dir: scope output root.

    Returns:
        DataFrame of coverage percentages (properties × shows).
    """
    if episode_appearances is None or episode_appearances.empty:
        return pd.DataFrame()

    guest_ep = episode_appearances[episode_appearances["role"] == "guest"].copy()
    if guest_ep.empty:
        return pd.DataFrame()

    # Show metadata + sort order
    show_meta = (
        guest_ep[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
    )
    total_per_show = (
        guest_ep.groupby("show_id").size()
        .reset_index(name="total_appearances")
        .sort_values("total_appearances", ascending=False)
    )
    show_order = total_per_show["show_id"].tolist()
    if not show_order:
        return pd.DataFrame()

    total_map = total_per_show.set_index("show_id")["total_appearances"].to_dict()

    coverage_rows = []
    for pid, frame in property_frames.items():
        if frame is None or frame.empty:
            continue
        label = property_labels.get(pid, pid)
        ep_col = "episode_id" if "episode_id" in frame.columns else "fernsehserien_de_id"

        ep_show = (
            guest_ep[["canonical_entity_id", "fernsehserien_de_id", "show_id"]]
            .drop_duplicates()
            .rename(columns={"fernsehserien_de_id": ep_col})
        )

        has_value = frame[
            frame["value"].fillna("").astype(str).str.strip().ne("")
            & ~frame["value"].astype(str).str.startswith("Unknown")
        ]
        if has_value.empty:
            with_value_per_show = pd.Series(dtype=int)
        else:
            merged = has_value.merge(ep_show, on=["canonical_entity_id", ep_col], how="inner")
            with_value_per_show = merged.groupby("show_id").size()

        row = {"property_id": pid, "property_label": label}
        for show_id in show_order:
            total = total_map.get(show_id, 0)
            with_val = int(with_value_per_show.get(show_id, 0))
            row[show_id] = round(with_val / max(total, 1) * 100, 1)
        coverage_rows.append(row)

    if not coverage_rows:
        return pd.DataFrame()

    coverage_df = pd.DataFrame(coverage_rows)

    # Write CSV
    csv_path = output_dir / "property_coverage_dashboard.csv"
    coverage_df.to_csv(csv_path, index=False)

    # Build heatmap
    y_labels = coverage_df["property_label"].tolist()
    x_labels = [show_meta.get(s, s) for s in show_order]
    z_vals = [
        [float(row.get(s, 0)) for s in show_order]
        for _, row in coverage_df.iterrows()
    ]
    text_vals = [[f"{v:.0f}%" for v in row] for row in z_vals]

    fig = go.Figure(data=go.Heatmap(
        z=z_vals,
        x=x_labels,
        y=y_labels,
        colorscale="Blues",
        zmin=0,
        zmax=100,
        text=text_vals,
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title="Coverage %", ticksuffix="%"),
        hovertemplate="%{y}<br>%{x}: %{z:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=(
                "Property Coverage by Show<br>"
                "<sup>% of guest appearances with at least one value for this property</sup>"
            ),
            x=0.5,
        ),
        xaxis=dict(title="Show", side="bottom", tickangle=-30),
        yaxis=dict(title="Property", autorange="reversed"),
        template="plotly_white",
        height=max(400, 45 * len(coverage_rows) + 180),
        margin=dict(t=110, b=120, l=200, r=60),
    )
    apply_font(fig)

    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)
    save_fig(fig, viz_dir / "property_coverage_heatmap")
    print(
        f"  Property coverage dashboard: {len(coverage_rows)} properties × "
        f"{len(show_order)} shows → {csv_path.name}"
    )

    return coverage_df
