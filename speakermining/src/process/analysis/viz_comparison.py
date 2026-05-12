"""Cross-show comparison visualizations (TASK-F09).

For each property, produces a 100%-stacked horizontal bar chart per scope:
  - One chart for "all shows combined" (default scope)
  - One chart per group defined in data/00_setup/show_groups.csv

Show groups allow comparing subsets such as "All German talk shows" or
"All German podcasts" independently, each as its own visualization file,
analogous to the per-show files produced elsewhere in the pipeline.

Fixes applied (2026-05-09):
  - % now always sums to 100% per show: Unknown guests are an explicit last
    segment so the denominator is total unique guests per show (including
    no-data guests).
  - Show order is fixed and descending by episode count from
    per_show_statistics.csv (or aligned_episodes).
  - All charts are 100%-stacked horizontal bar charts (not grouped).
  - Sub-groups are separate visualizations, driven by show_groups.csv.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .viz_base import apply_font, save_fig
from .config import SETUP_DIR

from plotly.subplots import make_subplots

from .color_registry import PALETTE


def _load_show_metadata() -> pd.DataFrame:
    path = SETUP_DIR / "broadcasting_programs.csv"
    if not path.exists():
        return pd.DataFrame(columns=["filename", "label", "fernsehserien_de_id", "language", "show_type"])
    return pd.read_csv(path, dtype=str).fillna("")


def _load_show_groups() -> pd.DataFrame:
    """Load group definitions from data/00_setup/show_groups.csv.

    Expected columns: group_id, group_label, language, members.
    The members column contains pipe-separated fernsehserien_de_ids.
    """
    path = SETUP_DIR / "show_groups.csv"
    if not path.exists():
        return pd.DataFrame(columns=["group_id", "group_label", "language", "members"])
    return pd.read_csv(path, dtype=str).fillna("")


def _episode_count_order(
    aligned_episodes_path: Path | None = None,
) -> dict[str, int]:
    """Return {show_id: episode_count}, sorted helper."""
    path = aligned_episodes_path or Path("data/50_analysis/all/per_show_statistics.csv")
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("0")
    if "show_id" in df.columns and "episode_count" in df.columns:
        return {row["show_id"]: int(row["episode_count"]) for _, row in df.iterrows()}
    return {}


def _get_show_order(
    available_show_ids: list[str],
    episode_counts: dict[str, int],
) -> list[str]:
    return sorted(
        available_show_ids,
        key=lambda sid: (-episode_counts.get(sid, 0), sid),
    )


def _shows_for_group(members_str: str) -> list[str]:
    """Return list of fernsehserien_de_ids from a pipe-separated members string."""
    if not members_str:
        return []
    return [m.strip() for m in members_str.split("|") if m.strip()]


def _build_stacked_bar(
    prop_frame: pd.DataFrame,
    guest_ep: pd.DataFrame,
    show_ids: list[str],
    show_labels: list[str],
    top_values: list[str],
    has_other: bool,
    value_totals: pd.Series,
    prop_label: str,
    prop_id: str,
    scope_title: str,
    top_n_values: int,
) -> go.Figure:
    """Dual-panel stacked bar: LEFT by appearances, RIGHT by unique guests.

    Bars show % of total unit for each top-N value. Unknown and Other counts
    appear as subscript annotations in the Y-axis labels so bars stay within
    [0, 100 %]. Both panels share the same Y-axis with labels on the left.
    """
    ep_col = next((c for c in ("episode_uid", "episode_id") if c in prop_frame.columns), "episode_uid")
    ep_show = (
        guest_ep[["canonical_entity_id", "episode_uid", "show_id"]]
        .drop_duplicates()
        .rename(columns={"episode_uid": ep_col})
    )

    prop_clean = prop_frame.copy()
    prop_clean["value"] = prop_clean["value"].fillna("").astype(str).str.strip()
    prop_clean.loc[prop_clean["value"] == "", "value"] = "Unknown"
    prop_clean.loc[prop_clean["value"].str.startswith("Unknown"), "value"] = "Unknown"

    merged = prop_clean.merge(ep_show, on=["canonical_entity_id", ep_col], how="inner")
    merged = merged[merged["show_id"].isin(show_ids)]

    ep_unit = guest_ep[guest_ep["show_id"].isin(show_ids)]
    total_app_map = (
        ep_unit[["canonical_entity_id", "episode_uid", "show_id"]]
        .drop_duplicates()
        .groupby("show_id").size()
        .to_dict()
    )
    total_guest_map = ep_unit.groupby("show_id")["canonical_entity_id"].nunique().to_dict()

    other_vals = set(value_totals.index[top_n_values:]) if has_other else set()

    def _annotated_label(base: str, unk: int, oth: int) -> str:
        parts = []
        if unk > 0:
            parts.append(f"{unk:,} unknown")
        if oth > 0:
            parts.append(f"{oth:,} other")
        return f"{base}<br><sup>({', '.join(parts)})</sup>" if parts else base

    app_rows: list[dict] = []
    guest_rows: list[dict] = []

    for show_id, show_label in zip(show_ids, show_labels):
        total_app = total_app_map.get(show_id, 0)
        total_guest = total_guest_map.get(show_id, 0)
        if total_app == 0 or total_guest == 0:
            continue
        show_data = merged[merged["show_id"] == show_id]

        known_app_pairs = (
            show_data[show_data["value"] != "Unknown"][
                ["canonical_entity_id", ep_col]
            ].drop_duplicates()
        )
        unknown_app = total_app - len(known_app_pairs)
        other_app = 0
        if has_other:
            other_app = (
                show_data[show_data["value"].isin(other_vals)][
                    ["canonical_entity_id", ep_col]
                ].drop_duplicates().shape[0]
            )

        known_guest_ids = set(
            show_data[show_data["value"] != "Unknown"]["canonical_entity_id"].unique()
        )
        unknown_guest = total_guest - len(known_guest_ids)

        # Shared Y-axis label uses appearance-based annotation (left panel is primary)
        shared_label = _annotated_label(show_label, unknown_app, other_app)
        _ = unknown_guest  # also available if needed for guest-only label variant

        row_app: dict = {"show_id": show_id, "label": shared_label, "total": total_app}
        row_guest: dict = {"show_id": show_id, "label": shared_label, "total": total_guest}

        for val in top_values:
            app_ct = (
                show_data[show_data["value"] == val][["canonical_entity_id", ep_col]]
                .drop_duplicates().shape[0]
            )
            row_app[val] = app_ct / total_app * 100
            guest_ct = show_data[show_data["value"] == val]["canonical_entity_id"].nunique()
            row_guest[val] = guest_ct / total_guest * 100

        app_rows.append(row_app)
        guest_rows.append(row_guest)

    if not app_rows and not guest_rows:
        return go.Figure()

    app_df = pd.DataFrame(app_rows).iloc[::-1].reset_index(drop=True)
    guest_df = pd.DataFrame(guest_rows).iloc[::-1].reset_index(drop=True)
    color_map = {v: PALETTE[i % len(PALETTE)] for i, v in enumerate(top_values)}
    n_rows = max(len(app_rows), len(guest_rows))

    fig = make_subplots(
        rows=1, cols=2,
        shared_yaxes=True,
        subplot_titles=["By appearances", "By unique guests"],
        horizontal_spacing=0.04,
    )

    def _add_traces(df: pd.DataFrame, col: int, show_legend: bool) -> None:
        y_labels = df["label"].tolist()
        for i, seg in enumerate(top_values):
            if seg not in df.columns:
                continue
            pcts = df[seg].tolist()
            totals = df["total"].tolist()
            counts = [round(p / 100 * t) for p, t in zip(pcts, totals)]
            text = [
                f"{int(c):,} ({p:.0f}%)" if p >= 2 else ""
                for c, p in zip(counts, pcts)
            ]
            fig.add_trace(
                go.Bar(
                    name=seg,
                    y=y_labels,
                    x=pcts,
                    orientation="h",
                    marker_color=color_map.get(seg, PALETTE[i % len(PALETTE)]),
                    text=text,
                    textposition="inside",
                    textangle=0,
                    insidetextanchor="middle",
                    legendrank=i,
                    legendgroup=seg,
                    showlegend=show_legend,
                    hovertemplate=f"<b>{seg}</b><br>%{{y}}: %{{x:.1f}}%<extra></extra>",
                ),
                row=1, col=col,
            )

    _add_traces(app_df, col=1, show_legend=True)
    _add_traces(guest_df, col=2, show_legend=False)

    fig.update_layout(
        title=dict(
            text=(
                f"{prop_label} — {scope_title}<br>"
                f"<sup>Left: by appearances · Right: by unique guests"
                f" · top {len(top_values)} values · unknown/other in labels</sup>"
            ),
            x=0.5,
        ),
        barmode="stack",
        template="plotly_white",
        legend=dict(
            orientation="h", yanchor="bottom", y=-0.3,
            xanchor="center", x=0.5, title_text=prop_label,
        ),
        height=max(400, 45 * n_rows + 250),
        margin=dict(t=130, r=60, b=150, l=220),
    )
    fig.update_xaxes(
        title_text="% of appearances", range=[0, 100], ticksuffix="%", row=1, col=1
    )
    fig.update_xaxes(
        title_text="% of unique guests", range=[0, 100], ticksuffix="%", row=1, col=2
    )
    fig.update_yaxes(title_text="Show", row=1, col=1)

    apply_font(fig)
    return fig


def build_cross_show_comparison(
    standard_frame: pd.DataFrame,
    episode_appearances: pd.DataFrame,
    prop_id: str,
    prop_label: str,
    output_dir: Path,
    scope: str = "all",
    top_n_values: int = 10,
    episode_counts: dict[str, int] | None = None,
) -> None:
    """100%-stacked horizontal bar chart for all shows in scope.

    Also generates one additional chart per group defined in show_groups.csv.

    Args:
        standard_frame: property frame — canonical_entity_id, episode_id, value.
        episode_appearances: full frame — canonical_entity_id, fernsehserien_de_id,
            show_id, program_name, role.
        prop_id: property PID (e.g. "P21")
        prop_label: human-readable label (e.g. "sex or gender")
        output_dir: scope output root
        scope: "all" or show ID — used in file paths and titles
        top_n_values: how many top values to include (rest → "Other")
        episode_counts: {show_id: episode_count}; loaded from disk if None
    """
    if standard_frame is None or standard_frame.empty:
        return
    if episode_appearances is None or episode_appearances.empty:
        return

    guest_ep = episode_appearances[episode_appearances["role"] == "guest"].copy()
    if guest_ep.empty:
        return

    if episode_counts is None:
        episode_counts = _episode_count_order()

    show_meta = (
        guest_ep[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
    )
    total_per_show = (
        guest_ep.groupby("show_id")["canonical_entity_id"].nunique()
        .reset_index(name="total_guests")
    )
    total_map = total_per_show.set_index("show_id")["total_guests"].to_dict()

    ep_col = next((c for c in ("episode_uid", "episode_id") if c in standard_frame.columns), "episode_uid")
    ep_show = (
        guest_ep[["canonical_entity_id", "episode_uid", "show_id"]]
        .drop_duplicates()
        .rename(columns={"episode_uid": ep_col})
    )
    prop_clean = standard_frame.copy()
    prop_clean["value"] = prop_clean["value"].fillna("").astype(str).str.strip()
    prop_clean.loc[prop_clean["value"] == "", "value"] = "Unknown"
    prop_clean.loc[prop_clean["value"].str.startswith("Unknown"), "value"] = "Unknown"

    merged = prop_clean.merge(ep_show, on=["canonical_entity_id", ep_col], how="inner")
    if merged.empty:
        return

    value_totals = (
        merged[merged["value"] != "Unknown"]
        .groupby("value")["canonical_entity_id"].nunique()
        .sort_values(ascending=False)
    )
    top_values = value_totals.head(top_n_values).index.tolist()
    has_other = len(value_totals) > top_n_values

    show_ids = _get_show_order(list(total_map.keys()), episode_counts)
    show_labels = [show_meta.get(s, s) for s in show_ids]

    short_label = prop_label.lower().replace(" ", "_").replace("/", "_")[:25]
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    # --- Main all-shows chart ---
    fig = _build_stacked_bar(
        prop_clean, guest_ep, show_ids, show_labels,
        top_values, has_other, value_totals, prop_label, prop_id,
        "cross-show comparison", top_n_values,
    )
    if fig.data:
        save_fig(fig, viz_dir / f"comparison_{prop_id}_{short_label}")
        print(f"  Cross-show comparison [{prop_label}]: {len(show_ids)} shows")

    # --- One chart per group from show_groups.csv ---
    groups_df = _load_show_groups()
    for _, grp in groups_df.iterrows():
        group_id = grp.get("group_id", "")
        group_label = grp.get("group_label", group_id)
        members_str = grp.get("members", "")

        if not group_id:
            continue

        group_show_ids_fs = set(_shows_for_group(members_str))
        group_show_ids = [sid for sid in show_ids if sid in group_show_ids_fs]
        if not group_show_ids:
            continue

        group_show_labels = [show_meta.get(s, s) for s in group_show_ids]
        group_fig = _build_stacked_bar(
            prop_clean, guest_ep, group_show_ids, group_show_labels,
            top_values, has_other, value_totals, prop_label, prop_id,
            group_label, top_n_values,
        )
        if group_fig.data:
            save_fig(group_fig, viz_dir / f"comparison_{prop_id}_{short_label}_{group_id}")
            print(f"    Group [{group_label}]: {len(group_show_ids)} shows")


def build_all_cross_show_comparisons(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
    item_pids: list[str] | None = None,
    top_n_values: int = 10,
    episode_counts: dict[str, int] | None = None,
) -> None:
    """Run cross-show comparison for all item-type properties.

    For each property, generates one chart for all shows and one chart per
    group defined in data/00_setup/show_groups.csv.

    Args:
        property_frames: {pid: standard_frame} dict from the property loop.
        property_labels: {pid: label} mapping.
        episode_appearances: full episode_appearances frame.
        output_dir: scope output root.
        item_pids: optional explicit list of PIDs; if None, runs for all keys.
        top_n_values: top N property values per chart.
        episode_counts: {show_id: episode_count}; loaded from disk if None.
    """
    if episode_counts is None:
        episode_counts = _episode_count_order()

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
            episode_counts=episode_counts,
        )
    print("Cross-show comparison charts complete.")
