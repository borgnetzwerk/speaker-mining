"""Property coverage dashboards (TASK-F09).

Implements two distinct coverage concepts (2026-05-09 — previously merged incorrectly):

1. AVERAGE VALUES PER PROPERTY — decimal ≥ 0.
   For each (appearance/guest), how many values does it carry for this property?
   E.g. a guest with 3 occupations counts as 3 for P106 average.

2. BINARY PROPERTY COVERAGE — percentage 0–100 %.
   For each (appearance/guest), was at least one non-Unknown value found?
   It does not matter how many values — presence/absence only.

Each concept is produced in two variants:
  a) By guest:      the unit is a unique guest (canonical_entity_id).
  b) By appearance: the unit is a guest × episode pair.

That yields 4 CSV outputs + 4 charts, plus the heatmap summary.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .viz_base import apply_font, save_fig


def _guest_ep_from_appearances(
    episode_appearances: pd.DataFrame,
) -> tuple[pd.DataFrame, dict, dict, list]:
    """Extract guest-only rows, show metadata, total maps, and show order."""
    guest_ep = episode_appearances[episode_appearances["role"] == "guest"].copy()

    show_meta = (
        guest_ep[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
    )
    total_appearances_per_show = guest_ep.groupby("show_id").size().to_dict()
    total_guests_per_show = (
        guest_ep.groupby("show_id")["canonical_entity_id"].nunique().to_dict()
    )
    show_order = sorted(
        total_appearances_per_show.keys(),
        key=lambda s: -total_appearances_per_show.get(s, 0),
    )
    return guest_ep, show_meta, total_appearances_per_show, total_guests_per_show, show_order


def _merge_frame_with_episodes(
    frame: pd.DataFrame,
    guest_ep: pd.DataFrame,
) -> pd.DataFrame:
    """Join property frame with guest×episode rows, returning merged frame."""
    ep_col = next((c for c in ("episode_uid", "episode_id") if c in frame.columns), "episode_uid")
    ep_show = (
        guest_ep[["canonical_entity_id", "episode_uid", "show_id"]]
        .drop_duplicates()
        .rename(columns={"episode_uid": ep_col})
    )
    return frame.merge(ep_show, on=["canonical_entity_id", ep_col], how="inner")


def _has_value(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str).str.strip()
    return s.ne("") & ~s.str.startswith("Unknown")


def compute_property_coverage(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
) -> dict[str, pd.DataFrame]:
    """Compute and write all four coverage variants for every property.

    Outputs written:
      property_coverage_avg_by_appearance.csv
      property_coverage_avg_by_guest.csv
      property_coverage_binary_by_appearance.csv
      property_coverage_binary_by_guest.csv

    Returns:
      Dict with keys "avg_appearance", "avg_guest", "binary_appearance", "binary_guest".
    """
    if episode_appearances is None or episode_appearances.empty:
        return {}

    guest_ep, show_meta, total_app_map, total_guest_map, show_order = (
        _guest_ep_from_appearances(episode_appearances)
    )
    if guest_ep.empty:
        return {}

    avg_app_rows, avg_guest_rows, bin_app_rows, bin_guest_rows = [], [], [], []

    for pid, frame in property_frames.items():
        if frame is None or frame.empty:
            continue
        label = property_labels.get(pid, pid)
        merged = _merge_frame_with_episodes(frame, guest_ep)
        if merged.empty:
            continue

        merged = merged.copy()
        merged["_has_value"] = _has_value(merged["value"]).astype(int)
        ep_col = next((c for c in ("episode_uid", "episode_id") if c in frame.columns), "episode_uid")

        # --- AVG VALUES per appearance (guest × episode pair) ---
        # Count of non-Unknown values per (person, episode) pair, then average
        ep_pair_counts = (
            merged[merged["_has_value"] == 1]
            .groupby(["canonical_entity_id", ep_col, "show_id"])
            .size()
            .reset_index(name="_n_values")
        )
        # Include pairs with 0 values (missing in ep_pair_counts)
        all_pairs = (
            guest_ep[["canonical_entity_id", "episode_uid", "show_id"]]
            .drop_duplicates()
            .rename(columns={"episode_uid": ep_col})
        )
        pair_merged = all_pairs.merge(ep_pair_counts, on=["canonical_entity_id", ep_col, "show_id"], how="left")
        pair_merged["_n_values"] = pair_merged["_n_values"].fillna(0)

        row_avg_app = {"property_id": pid, "property_label": label}
        for show_id in show_order:
            show_pairs = pair_merged[pair_merged["show_id"] == show_id]
            row_avg_app[show_id] = round(show_pairs["_n_values"].mean(), 3) if not show_pairs.empty else 0.0
        avg_app_rows.append(row_avg_app)

        # --- AVG VALUES per guest ---
        # Count distinct values per (guest, show); standard_frame has one row per
        # (guest, episode, value), so .size() would inflate by episode count — use nunique.
        guest_counts = (
            merged[merged["_has_value"] == 1]
            .groupby(["canonical_entity_id", "show_id"])["value"]
            .nunique()
            .reset_index(name="_n_values")
        )
        all_guests = (
            guest_ep[["canonical_entity_id", "show_id"]].drop_duplicates()
        )
        guest_merged = all_guests.merge(guest_counts, on=["canonical_entity_id", "show_id"], how="left")
        guest_merged["_n_values"] = guest_merged["_n_values"].fillna(0)

        row_avg_guest = {"property_id": pid, "property_label": label}
        for show_id in show_order:
            sg = guest_merged[guest_merged["show_id"] == show_id]
            row_avg_guest[show_id] = round(sg["_n_values"].mean(), 3) if not sg.empty else 0.0
        avg_guest_rows.append(row_avg_guest)

        # --- BINARY coverage by appearance ---
        # For each (person, episode) pair: has at least one value? (1 or 0)
        pair_binary = (
            merged.groupby(["canonical_entity_id", ep_col, "show_id"])["_has_value"]
            .max()
            .reset_index(name="_has_val")
        )
        all_pairs_b = all_pairs.copy()
        pair_bin_merged = all_pairs_b.merge(pair_binary, on=["canonical_entity_id", ep_col, "show_id"], how="left")
        pair_bin_merged["_has_val"] = pair_bin_merged["_has_val"].fillna(0)

        row_bin_app = {"property_id": pid, "property_label": label}
        for show_id in show_order:
            sp = pair_bin_merged[pair_bin_merged["show_id"] == show_id]
            total = total_app_map.get(show_id, 0)
            if total > 0 and not sp.empty:
                covered = int(sp["_has_val"].sum())
                row_bin_app[show_id] = round(covered / total * 100, 1)
            else:
                row_bin_app[show_id] = 0.0
        bin_app_rows.append(row_bin_app)

        # --- BINARY coverage by guest ---
        guest_bin = (
            merged.groupby(["canonical_entity_id", "show_id"])["_has_value"]
            .max()
            .reset_index(name="_has_val")
        )
        all_guests_b = all_guests.copy()
        guest_bin_merged = all_guests_b.merge(guest_bin, on=["canonical_entity_id", "show_id"], how="left")
        guest_bin_merged["_has_val"] = guest_bin_merged["_has_val"].fillna(0)

        row_bin_guest = {"property_id": pid, "property_label": label}
        for show_id in show_order:
            sg = guest_bin_merged[guest_bin_merged["show_id"] == show_id]
            total = total_guest_map.get(show_id, 0)
            if total > 0 and not sg.empty:
                covered = int(sg["_has_val"].sum())
                row_bin_guest[show_id] = round(covered / total * 100, 1)
            else:
                row_bin_guest[show_id] = 0.0
        bin_guest_rows.append(row_bin_guest)

    results = {}
    for key, rows, fname in [
        ("avg_appearance",    avg_app_rows,   "property_coverage_avg_by_appearance.csv"),
        ("avg_guest",         avg_guest_rows,  "property_coverage_avg_by_guest.csv"),
        ("binary_appearance", bin_app_rows,    "property_coverage_binary_by_appearance.csv"),
        ("binary_guest",      bin_guest_rows,  "property_coverage_binary_by_guest.csv"),
    ]:
        if rows:
            df = pd.DataFrame(rows)
            df.to_csv(output_dir / fname, index=False)
            results[key] = df
        else:
            results[key] = pd.DataFrame()

    return results


def compute_global_property_coverage(
    property_frames: dict,
    episode_appearances: pd.DataFrame,
) -> tuple[int, dict[str, float]]:
    """Compute binary property coverage globally (cross-show deduplicated).

    Applies the same binary-by-guest logic as ``compute_property_coverage`` but
    without grouping by show, so each unique guest is counted once regardless of
    how many shows they appeared on.

    Args:
        property_frames: ``{pid: standard_frame}`` as produced by the notebook.
        episode_appearances: Full episode appearances table (all roles).

    Returns:
        ``(n_global_unique_guests, coverage_dict)`` where ``coverage_dict`` maps
        each ``pid`` to a percentage (0–100) and ``'__wikidata__'`` to the
        Wikidata reconciliation rate.
    """
    guest_ep = episode_appearances[episode_appearances["role"] == "guest"].copy()
    if guest_ep.empty:
        return 0, {}

    n_global = int(guest_ep["canonical_entity_id"].nunique())
    if n_global == 0:
        return 0, {}

    guest_ids = set(guest_ep["canonical_entity_id"].unique())
    result: dict[str, float] = {}

    # Wikidata: guests with a non-empty wikidata_id
    n_wd = int(
        guest_ep.drop_duplicates("canonical_entity_id")["wikidata_id"]
        .fillna("").str.strip().ne("").sum()
    )
    result["__wikidata__"] = round(n_wd / n_global * 100, 1)

    for pid, frame in property_frames.items():
        if frame is None or frame.empty or "value" not in frame.columns:
            continue
        fg = frame[frame["canonical_entity_id"].isin(guest_ids)]
        has_val = _has_value(fg["value"])
        covered = int(fg.loc[has_val, "canonical_entity_id"].nunique())
        result[pid] = round(covered / n_global * 100, 1)

    return n_global, result


def build_property_coverage_dashboard(
    property_frames: dict,
    property_labels: dict,
    episode_appearances: pd.DataFrame,
    output_dir: Path,
) -> pd.DataFrame:
    """Build coverage charts and write all CSVs.

    Produces:
      - property_coverage_heatmap_binary_appearance.png  (100% binary, by appearance)
      - property_coverage_heatmap_binary_guest.png       (100% binary, by guest)
      - property_coverage_heatmap_avg_appearance.png     (avg values, by appearance)
      - property_coverage_heatmap_avg_guest.png          (avg values, by guest)
      - property_coverage_heatmap_combined.png           (2×2 subplot summary)

    Returns the binary-by-appearance DataFrame for backward compatibility.
    """
    if episode_appearances is None or episode_appearances.empty:
        return pd.DataFrame()

    coverage = compute_property_coverage(
        property_frames, property_labels, episode_appearances, output_dir
    )
    if not coverage:
        return pd.DataFrame()

    guest_ep, show_meta, total_app_map, total_guest_map, show_order = (
        _guest_ep_from_appearances(episode_appearances)
    )
    x_labels = [show_meta.get(s, s) for s in show_order]
    viz_dir = output_dir / "visualizations"
    viz_dir.mkdir(parents=True, exist_ok=True)

    def _make_heatmap(
        df: pd.DataFrame, title: str, is_pct: bool, use_log: bool = False
    ) -> go.Figure:
        if df.empty:
            return go.Figure()
        y_labels = df["property_label"].tolist()
        z_vals = [
            [float(df.loc[i, s]) if s in df.columns else 0.0 for s in show_order]
            for i in range(len(df))
        ]
        if use_log:
            z_plot = [[np.log1p(v) for v in row] for row in z_vals]
            max_orig = max((max(row) for row in z_vals if row), default=1.0)
            tick_originals = [
                v for v in [0, 0.25, 0.5, 1, 2, 3, 5, 10, 20, 50, 100]
                if v <= max_orig * 1.1
            ]
            colorbar = dict(
                title="avg (log)",
                tickvals=[np.log1p(v) for v in tick_originals],
                ticktext=[f"{v:.3g}" for v in tick_originals],
            )
            text_vals = [[f"{v:.2f}" for v in row] for row in z_vals]
            colorscale = "Oranges"
        else:
            z_plot = z_vals
            colorbar = dict(
                title="%" if is_pct else "avg",
                ticksuffix="%" if is_pct else "",
            )
            text_vals = [
                [f"{v:.0f}%" if is_pct else f"{v:.2f}" for v in row]
                for row in z_vals
            ]
            colorscale = "Blues"

        fig = go.Figure(data=go.Heatmap(
            z=z_plot, x=x_labels, y=y_labels,
            colorscale=colorscale,
            zmin=0, zmax=(100 if (is_pct and not use_log) else None),
            text=text_vals, texttemplate="%{text}",
            textfont=dict(size=10),
            colorbar=colorbar,
            hovertemplate="%{y}<br>%{x}: %{z:.3g}<extra></extra>",
        ))
        fig.update_layout(
            title=dict(text=title, x=0.5),
            xaxis=dict(title="Show", side="bottom", tickangle=-30),
            yaxis=dict(title="Property", autorange="reversed"),
            template="plotly_white",
            height=max(400, 45 * len(df) + 180),
            margin=dict(t=80, b=120, l=200, r=60),
        )
        apply_font(fig)
        return fig

    specs = [
        ("binary_appearance", "Binary coverage by appearance (% with ≥1 value)", True,  False, "property_coverage_heatmap_binary_appearance"),
        ("binary_guest",      "Binary coverage by guest (% with ≥1 value)",      True,  False, "property_coverage_heatmap_binary_guest"),
        ("avg_appearance",    "Average values per appearance (log scale)",        False, True,  "property_coverage_heatmap_avg_appearance"),
        ("avg_guest",         "Average values per guest (log scale)",             False, True,  "property_coverage_heatmap_avg_guest"),
    ]
    for key, title, is_pct, use_log, fname in specs:
        df = coverage.get(key, pd.DataFrame())
        if df.empty:
            continue
        fig = _make_heatmap(df, title, is_pct, use_log=use_log)
        save_fig(fig, viz_dir / fname)

    print(
        f"  Property coverage dashboard: {len(property_frames)} properties × "
        f"{len(show_order)} shows → 4 variants"
    )
    return coverage.get("binary_appearance", pd.DataFrame())
