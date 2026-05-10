"""Final publication-quality visualizations — 2026-05-04 finalization.

Design principles (see documentation/50_Analysis/2026-05-04_finalization/):
  * No hardcoded colors, orderings, or category mappings.
  * Same QID always keeps the same color (ColorRegistry principle).
  * Show/gender/category ordering is always derived from appearance counts.
  * Occupation categories are resolved via the P279 class hierarchy
    (class_resolution_map.csv + midlevel_classes.csv), not hardcoded labels.

All build_* functions accept pre-computed colors and orderings as parameters
so that every chart in a single report shares exactly one registry built once
at notebook setup time.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .color_registry import PALETTE, UNKNOWN_COLOR, OTHER_COLOR
from .config import load_party_colors, load_midlevel_classes, load_loop_resolution
from .viz_base import apply_font, save_fig


# ──────────────────────────────────────────────────────────────────────────────
# Registry builders  (call once at session start; pass results to all charts)
# ──────────────────────────────────────────────────────────────────────────────

def build_show_color_registry(
    per_show_stats: pd.DataFrame,
    *,
    party_colors_path: str | Path | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Assign palette colors to shows ordered by total appearances descending."""
    if party_colors_path is not None:
        try:
            party_df = pd.read_csv(party_colors_path, dtype=str).fillna("")
        except Exception:
            party_df = load_party_colors()
    else:
        party_df = load_party_colors()

    reserved: set[str] = {
        str(row.get("hex_color", "")).strip().upper()
        for _, row in party_df.iterrows()
        if str(row.get("hex_color", "")).strip()
    } | {UNKNOWN_COLOR.upper(), OTHER_COLOR.upper()}

    available = [c for c in PALETTE if c.upper() not in reserved]
    if not available:
        available = list(PALETTE)

    ordered = (
        per_show_stats
        .sort_values("guest_appearances", ascending=False)
        .reset_index(drop=True)
    )

    show_colors: dict[str, str] = {}
    show_order: list[str] = []
    for i, row in ordered.iterrows():
        sid = str(row.get("show_id", "")).strip()
        if sid:
            show_colors[sid] = available[len(show_order) % len(available)]
            show_order.append(sid)

    return show_colors, show_order


def build_gender_color_registry(
    gender_counts: pd.Series | dict[str, int],
) -> tuple[dict[str, str], list[str]]:
    """Assign palette colors to gender labels ordered by frequency descending."""
    if isinstance(gender_counts, dict):
        counts = pd.Series(gender_counts, dtype=float)
    else:
        counts = gender_counts.copy().astype(float)

    unknown_key = "Unknown / no data"
    known = counts.drop(index=unknown_key, errors="ignore").sort_values(ascending=False)
    order = known.index.tolist()
    if unknown_key in counts.index:
        order.append(unknown_key)

    gender_colors: dict[str, str] = {}
    palette_idx = 0
    for label in order:
        if label == unknown_key:
            gender_colors[label] = UNKNOWN_COLOR
        else:
            gender_colors[label] = PALETTE[palette_idx % len(PALETTE)]
            palette_idx += 1

    return gender_colors, order


def build_occupation_category_map(
    occ_value_qids: list[str],
    class_resolution_map: pd.DataFrame,
    qid_label: dict[str, str],
    *,
    midlevel_classes: pd.DataFrame | None = None,
    loop_resolution: pd.DataFrame | None = None,
) -> dict[str, tuple[str, str]]:
    """Map occupation QIDs to their nearest midlevel class ancestor via P279."""
    if midlevel_classes is None:
        midlevel_classes = load_midlevel_classes()
    if loop_resolution is None:
        loop_resolution = load_loop_resolution()

    midlevel_qids: set[str] = set(
        midlevel_classes["wikidata_id"].astype(str).str.strip()
    ) if not midlevel_classes.empty else set()
    midlevel_labels: dict[str, str] = {}
    if not midlevel_classes.empty:
        midlevel_labels = dict(zip(
            midlevel_classes["wikidata_id"].astype(str).str.strip(),
            midlevel_classes["label"].astype(str).str.strip(),
        ))

    loop_map: dict[str, str] = {}
    if not loop_resolution.empty and "loop_member_qid" in loop_resolution.columns:
        loop_map = dict(zip(
            loop_resolution["loop_member_qid"].astype(str).str.strip(),
            loop_resolution["designated_top_level_qid"].astype(str).str.strip(),
        ))

    parent_map: dict[str, list[str]] = {}
    core_map: dict[str, str] = {}
    if not class_resolution_map.empty:
        for _, row in class_resolution_map.iterrows():
            qid = str(row.get("class_qid", "")).strip()
            parents_raw = str(row.get("parent_qids", "")).strip()
            parents = [p.strip() for p in parents_raw.split("|") if p.strip()]
            if qid:
                parent_map[qid] = parents
            core = str(row.get("core_class_qid", "")).strip()
            if qid and core:
                core_map[qid] = core

    def _resolve(occ_qid: str) -> tuple[str, str]:
        current = loop_map.get(occ_qid, occ_qid)
        if current in midlevel_qids:
            lbl = midlevel_labels.get(current) or qid_label.get(current, current)
            return current, lbl
        visited: set[str] = set()
        queue: list[str] = [current]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            for parent in parent_map.get(node, []):
                if parent in midlevel_qids:
                    lbl = midlevel_labels.get(parent) or qid_label.get(parent, parent)
                    return parent, lbl
                if parent not in visited:
                    queue.append(parent)
        core = core_map.get(occ_qid, "")
        if core:
            lbl = midlevel_labels.get(core) or qid_label.get(core, core)
            return core, lbl
        return "", "Sonstiges"

    return {
        qid: _resolve(qid)
        for qid in occ_value_qids
        if qid and str(qid).strip()
    }


def build_category_color_registry(
    category_counts: pd.Series | dict[str, int],
    *,
    reserved_colors: set[str] | None = None,
) -> dict[str, str]:
    """Assign palette colors to category QIDs ordered by total count descending."""
    reserved = (reserved_colors or set()) | {UNKNOWN_COLOR.upper(), OTHER_COLOR.upper()}
    available = [c for c in PALETTE if c.upper() not in {r.upper() for r in reserved}]
    if not available:
        available = list(PALETTE)

    if isinstance(category_counts, dict):
        counts = pd.Series(category_counts, dtype=float).sort_values(ascending=False)
    else:
        counts = category_counts.sort_values(ascending=False)

    cat_colors: dict[str, str] = {}
    for i, (qid, _) in enumerate(counts.items()):
        cat_colors[str(qid)] = available[i % len(available)]

    return cat_colors


# ──────────────────────────────────────────────────────────────────────────────
# Shared internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _sort_by_order(ids: list[str], order: list[str]) -> list[str]:
    present = set(ids)
    return [s for s in order if s in present] + sorted(s for s in present if s not in order)


def _save(fig: go.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    apply_font(fig)
    save_fig(fig, output_dir / stem)


def _nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return first column name matching any candidate (NFC-normalized, case-insensitive)."""
    lower_map = {_nfc(c).lower(): c for c in df.columns}
    for cand in candidates:
        key = _nfc(cand).lower()
        if key in lower_map:
            return lower_map[key]
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Viz 0: Show statistics table
# ──────────────────────────────────────────────────────────────────────────────

def _mini_bar(value: float, max_val: float = 100.0, width: int = 8) -> str:
    """Return a simple Unicode block bar for a percentage value."""
    if pd.isna(value) or max_val <= 0:
        return ""
    filled = round(min(value / max_val, 1.0) * width)
    return "█" * filled + "░" * (width - filled)


def build_show_stats_table(
    per_show_stats: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    gender_by_show: pd.DataFrame | None = None,
    age_by_show: pd.DataFrame | None = None,
    span_by_show: pd.DataFrame | None = None,
    wikidata_pct_by_show: pd.DataFrame | None = None,
    eps_without_gender_by_show: pd.DataFrame | None = None,
) -> None:
    """Viz 0: Show statistics overview table.

    Columns: Broadcasting Program · Episodes · Appearances · Unique Guests ·
             Wikidata % · Male % · Female % · Other % ·
             Eps w/o Male · Eps w/o Female · Eps w/o Other ·
             Age Min/Med/Max · Span

    Args:
        eps_without_gender_by_show: show_id, eps_without_male, eps_without_female,
            eps_without_other.
    """
    df = per_show_stats.drop_duplicates(subset=["show_id"]).copy()
    ordered_ids = _sort_by_order(df["show_id"].tolist(), show_order)
    order_map = {sid: i for i, sid in enumerate(ordered_ids)}
    df = df[df["show_id"].isin(set(ordered_ids))].copy()
    df["_order"] = df["show_id"].map(order_map)
    df = df.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)

    extra_cols_map = [
        (gender_by_show,           ["male_pct", "female_pct", "other_pct"]),
        (age_by_show,              ["min_age", "median_age", "max_age"]),
        (span_by_show,             ["span_label"]),
        (wikidata_pct_by_show,     ["wikidata_pct"]),
        (eps_without_gender_by_show, ["eps_without_male", "eps_without_female", "eps_without_other"]),
    ]
    for extra, cols in extra_cols_map:
        if extra is not None and not extra.empty:
            present = [c for c in cols if c in extra.columns]
            df = df.merge(extra[["show_id"] + present], on="show_id", how="left")
        for c in cols:
            if c not in df.columns:
                df[c] = float("nan") if c != "span_label" else "—"

    def _pct(v: object) -> str:
        try:
            fv = float(v)
            if pd.isna(fv):
                return "—"
            return f"{fv:.0f} % {_mini_bar(fv)}"
        except (TypeError, ValueError):
            return "—"

    def _age(v: object) -> str:
        try:
            return f"{float(v):.0f}" if pd.notna(v) else "—"
        except (TypeError, ValueError):
            return "—"

    def _int(v: object) -> str:
        try:
            return f"{int(float(v)):,}" if pd.notna(v) else "—"
        except (TypeError, ValueError):
            return "—"

    n = len(df)
    row_fills = ["#f7f7f7" if i % 2 == 0 else "#ffffff" for i in range(n)]

    # Two-level header: use <br> to group Age and Gender subcolumns
    header_vals = [
        "<b>Broadcasting<br>Program</b>",
        "<b>Episodes</b>",
        "<b>Appear-<br>ances</b>",
        "<b>Unique<br>Guests</b>",
        "<b>Wikidata<br>%</b>",
        # Gender group
        "<b>Gender ·<br>Male %</b>",
        "<b>Gender ·<br>Female %</b>",
        "<b>Gender ·<br>Other %</b>",
        "<b>Eps<br>w/o ♂</b>",
        "<b>Eps<br>w/o ♀</b>",
        "<b>Eps<br>w/o other</b>",
        # Age group
        "<b>Age ·<br>Min</b>",
        "<b>Age ·<br>Median</b>",
        "<b>Age ·<br>Max</b>",
        "<b>Span</b>",
    ]

    cell_vals = [
        df["program_name"].tolist(),
        df["episode_count"].apply(_int).tolist(),
        df["guest_appearances"].apply(_int).tolist(),
        df["unique_guests"].apply(_int).tolist(),
        df["wikidata_pct"].apply(_pct).tolist(),
        df["male_pct"].apply(_pct).tolist(),
        df["female_pct"].apply(_pct).tolist(),
        df["other_pct"].apply(_pct).tolist(),
        df["eps_without_male"].apply(_int).tolist(),
        df["eps_without_female"].apply(_int).tolist(),
        df["eps_without_other"].apply(_int).tolist(),
        df["min_age"].apply(_age).tolist(),
        df["median_age"].apply(_age).tolist(),
        df["max_age"].apply(_age).tolist(),
        df["span_label"].fillna("—").tolist(),
    ]
    n_cols = len(header_vals)
    col_widths = [200, 65, 70, 65, 80, 95, 95, 80, 70, 70, 85, 50, 60, 50, 85]

    fig = go.Figure(go.Table(
        columnwidth=col_widths,
        header=dict(
            values=header_vals,
            align=["left"] + ["right"] * (n_cols - 1),
            font=dict(size=10, color="#333333"),
            fill_color="#e8e8e8",
            line_color="#cccccc",
            height=44,
        ),
        cells=dict(
            values=cell_vals,
            align=["left"] + ["right"] * (n_cols - 1),
            font=dict(size=10, color="#333333"),
            fill_color=[row_fills] * n_cols,
            line_color="#e0e0e0",
            height=28,
        ),
    ))
    fig.update_layout(
        title=dict(
            text=(
                "<b>Talk Shows · Sample &amp; Demographics</b><br>"
                "<sup>Sorted by total appearances · German shows + StarTalk reference · 2003–2025</sup>"
            ),
            x=0.02,
            font=dict(size=15),
            pad=dict(l=0, t=10),
        ),
        margin=dict(l=20, r=20, t=90, b=20),
        height=90 + 44 + n * 28 + 20,
        width=sum(col_widths) + 60,
    )
    _save(fig, output_dir, "00_show_stats_table")
    print(f"  Viz 0: show stats table ({n} shows) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 1: Age at appearance — density ridge
# ──────────────────────────────────────────────────────────────────────────────

def build_age_ridge_plot(
    age_with_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
) -> None:
    """Viz 1: Horizontal violin per show, sorted by median age desc.

    Stats (median, IQR) are encoded visually via the violin's embedded box plot.
    Labels show only the show name.
    """
    df = age_with_show.dropna(subset=["age", "show_id"]).copy()
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df = df[(df["age"] >= 15) & (df["age"] < 105)].dropna(subset=["age"])
    if df.empty:
        print("  Viz 1: no age data — skipping")
        return

    prog = (
        df[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
        if "program_name" in df.columns else {}
    )

    medians = df.groupby("show_id")["age"].median().sort_values(ascending=False)
    show_ids_sorted = medians.index.tolist()

    x_min = max(15, int(df["age"].min()) - 1)
    x_max = min(104, int(df["age"].max()) + 1)

    fig = go.Figure()
    for sid in show_ids_sorted:
        sub = df[df["show_id"] == sid]["age"].tolist()
        if not sub:
            continue
        label = prog.get(sid, sid)
        color = show_colors.get(sid, UNKNOWN_COLOR)

        fig.add_trace(go.Violin(
            x=sub,
            name=label,
            orientation="h",
            side="positive",
            box_visible=True,
            meanline_visible=True,
            fillcolor=color,
            line_color=color,
            opacity=0.78,
            bandwidth=2,
            points=False,
        ))

    fig.update_layout(
        title=dict(
            text="<b>Age at Appearance · by Show</b><br><sup>Sorted by median age · box = IQR · centre line = median</sup>",
            x=0.02,
            font=dict(size=15),
        ),
        xaxis=dict(
            title="Age at time of appearance",
            range=[x_min, x_max],
            tickvals=list(range(x_min - x_min % 5, x_max + 5, 5)),
            tickfont=dict(size=11),
            title_font=dict(size=12),
        ),
        yaxis=dict(title="", tickfont=dict(size=12)),
        template="plotly_white",
        height=80 + len(show_ids_sorted) * 75,
        width=900,
        margin=dict(l=60, r=180, t=100, b=60),
        showlegend=True,
        legend=dict(
            orientation="v", x=1.01, y=1.0, xanchor="left",
            font=dict(size=11),
            title=dict(text="Show"),
        ),
        violingap=0.05,
        violingroupgap=0,
    )
    _save(fig, output_dir, "01_age_ridge_plot")
    print(f"  Viz 1: age ridge ({len(show_ids_sorted)} shows) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 2: Gender share over time — multi-gender line chart
# ──────────────────────────────────────────────────────────────────────────────

def build_gender_over_time(
    gender_by_year_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    gender_colors: dict[str, str],
    gender_order: list[str],
    output_dir: Path,
    *,
    rolling_window: int = 3,
    min_year: int = 2003,
    max_year: int = 2025,
) -> None:
    """Viz 2: One line per (show × gender), dash by gender, color by show.

    Unknown gender is excluded so all visible lines sum to 100 % at each point.
    Legend is outside the plot area with sufficient right margin.
    """
    UNKNOWN_LABEL = "Unknown / no data"
    DASHES = ["solid", "dash", "dot", "dashdot"]

    df = gender_by_year_show.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df = df.dropna(subset=["year", "show_id", "gender"])
    df = df[(df["year"] >= min_year) & (df["year"] <= max_year)]
    df = df[df["gender"] != UNKNOWN_LABEL]
    if df.empty:
        print("  Viz 2: no gender-over-time data — skipping")
        return

    prog = (
        df[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
        if "program_name" in df.columns else {}
    )

    pivot = df.groupby(["year", "show_id", "gender"])["n_appearances"].sum().reset_index()
    totals = pivot.groupby(["year", "show_id"])["n_appearances"].transform("sum")
    pivot["share"] = pivot["n_appearances"] / totals.replace(0, float("nan"))

    meaningful = (
        pivot.groupby("gender")["n_appearances"].sum()
        .pipe(lambda s: s[s > 20]).index.tolist()
    )
    genders_to_plot = [
        g for g in gender_order if g in meaningful and g != UNKNOWN_LABEL
    ]
    if not genders_to_plot:
        print("  Viz 2: no meaningful gender categories — skipping")
        return

    dash_map: dict[str, str] = {
        g: DASHES[i % len(DASHES)] for i, g in enumerate(genders_to_plot)
    }

    all_years = sorted(df["year"].unique())
    show_ids = _sort_by_order(df["show_id"].unique().tolist(), show_order)

    fig = go.Figure()

    fig.add_hline(y=50, line_dash="dot", line_color="#c0392b", line_width=1.2,
                  annotation_text="50 % parity", annotation_position="right")

    for sid in show_ids:
        for i_g, gender in enumerate(genders_to_plot):
            sub = pivot[(pivot["show_id"] == sid) & (pivot["gender"] == gender)].sort_values("year")
            if sub.empty or sub["n_appearances"].sum() < 5:
                continue
            if len(sub) >= rolling_window:
                roll = (
                    sub.set_index("year")["share"]
                    .reindex(all_years)
                    .rolling(rolling_window, center=True, min_periods=1)
                    .mean()
                    .reset_index()
                )
                show_name = prog.get(sid, sid)
                fig.add_trace(go.Scatter(
                    x=roll["year"],
                    y=roll["share"] * 100,
                    mode="lines",
                    name=show_name if i_g == 0 else None,
                    showlegend=(i_g == 0),
                    legendgroup=sid,
                    line=dict(
                        color=show_colors.get(sid, UNKNOWN_COLOR),
                        width=1.8,
                        dash=dash_map.get(gender, "solid"),
                    ),
                    hovertemplate=(
                        f"{show_name} · {gender} · %{{x}}<br>Share: %{{y:.1f}}%<extra></extra>"
                    ),
                ))

    for gender in genders_to_plot:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="lines",
            name=f"── {gender}",
            line=dict(color="#666666", width=2, dash=dash_map.get(gender, "solid")),
            showlegend=True,
            legendgroup=f"gender_{gender}",
        ))

    fig.update_layout(
        title=dict(
            text=(
                "<b>Gender Share of Appearances over Time</b><br>"
                f"<sup>{rolling_window}-yr rolling mean · known gender only (sums to 100 %) · "
                "colour = show · dash = gender</sup>"
            ),
            x=0.02,
            font=dict(size=15),
        ),
        xaxis=dict(title="Year", tickangle=-45, dtick=2, tickfont=dict(size=11)),
        yaxis=dict(title="Share of appearances (%)", range=[0, 100], ticksuffix="%"),
        template="plotly_white",
        height=520,
        width=1300,
        margin=dict(l=70, r=260, t=120, b=80),
        legend=dict(
            orientation="v", x=1.01, y=1.0, xanchor="left",
            font=dict(size=11),
            title=dict(text="Show · gender pattern"),
        ),
    )
    _save(fig, output_dir, "02_gender_over_time")
    print(f"  Viz 2: gender over time ({len(genders_to_plot)} genders, {len(show_ids)} shows) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 3a: Party affiliation share by show
# ──────────────────────────────────────────────────────────────────────────────

def _hex_blend(hex1: str, hex2: str, t: float) -> str:
    """Blend hex1 (t=0) to hex2 (t=1) in RGB space."""
    h1 = hex1.lstrip("#")
    h2 = hex2.lstrip("#")
    r1, g1, b1 = int(h1[0:2], 16), int(h1[2:4], 16), int(h1[4:6], 16)
    r2, g2, b2 = int(h2[0:2], 16), int(h2[2:4], 16), int(h2[4:6], 16)
    t = max(0.0, min(1.0, t))
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def build_party_by_show(
    party_by_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    party_colors: dict[str, str] | None = None,
    party_order: list[str] | None = None,
    min_pct: float = 1.0,
    min_guests: int = 0,
) -> None:
    """Viz 3a: Heatmap-table — party share by show.

    Parties filtered to those that reach at least min_pct % in ANY show.
    Cell color = sequential from #f5f5f5 (0 %) to party hex (column max).

    Args:
        party_by_show: show_id, program_name, party_label, unique_guests.
        min_pct: Minimum % share in any single show to be included (default 1 %).
        min_guests: Minimum total guests across all shows (secondary filter).
    """
    df = party_by_show.copy()
    df = df[df["party_label"].astype(str).str.strip().ne("Unknown / no data")]
    df = df[df["party_label"].astype(str).str.strip().ne("")]
    if df.empty:
        print("  Viz 3a: no party-by-show data — skipping")
        return

    # Compute per-show totals for denominator (all guests in the show, not just partisan)
    # We use the total unique guests across all parties per show as denominator.
    show_totals_partisan = df.groupby("show_id")["unique_guests"].sum()

    # Pivot: show × party (guest counts)
    pivot_raw = (
        df.groupby(["show_id", "party_label"])["unique_guests"].sum()
        .unstack(fill_value=0)
    )

    # % per party per show (partisan denominator: guests with ANY party affiliation)
    pct_pivot = pivot_raw.div(
        pivot_raw.sum(axis=1).replace(0, float("nan")), axis=0
    ) * 100

    # Keep parties that reach min_pct in at least one show
    max_pct_per_party = pct_pivot.max(axis=0)
    keep_pct = set(max_pct_per_party[max_pct_per_party >= min_pct].index)

    # Secondary: absolute guest threshold
    if min_guests > 0:
        party_totals = pivot_raw.sum(axis=0)
        keep_abs = set(party_totals[party_totals >= min_guests].index)
        keep = keep_pct & keep_abs
    else:
        keep = keep_pct

    df = df[df["party_label"].isin(keep)]
    if df.empty:
        print(f"  Viz 3a: no parties above {min_pct:.0f}% threshold — skipping")
        return

    # Political spectrum ordering
    if party_order is None:
        try:
            pc_df = load_party_colors()
            if "spectrum_position" in pc_df.columns:
                spec = (
                    pc_df[pc_df["spectrum_position"].notna()]
                    .assign(_pos=lambda d: pd.to_numeric(d["spectrum_position"], errors="coerce"))
                    .dropna(subset=["_pos"])
                    .sort_values("_pos")["label"]
                    .tolist()
                )
                party_order = spec
        except Exception:
            party_order = None

    present_parties = set(df["party_label"].unique())
    if party_order:
        ordered_parties = [p for p in party_order if p in present_parties]
        ordered_parties += sorted(p for p in present_parties if p not in party_order)
    else:
        party_totals_all = df.groupby("party_label")["unique_guests"].sum()
        ordered_parties = party_totals_all.sort_values(ascending=False).index.tolist()

    pcolors: dict[str, str] = dict(party_colors or {})

    show_ids = _sort_by_order(df["show_id"].unique().tolist(), show_order)
    prog = (
        df[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
    )

    pivot = (
        df.groupby(["show_id", "party_label"])["unique_guests"].sum()
        .unstack(fill_value=0)
        .reindex(index=show_ids, columns=ordered_parties, fill_value=0)
    )

    totals_per_show = pivot.sum(axis=1).replace(0, float("nan"))
    pct_matrix = pivot.div(totals_per_show, axis=0) * 100

    col_max = pct_matrix.max(axis=0).replace(0, 1.0)
    norm_matrix = pct_matrix.div(col_max, axis=1).fillna(0)

    show_names = [prog.get(s, s) for s in show_ids]
    header_row = ["<b>Show</b>"] + [f"<b>{p}</b>" for p in ordered_parties]

    fill_colors: list[list[str]] = [["#e8e8e8"] * len(show_ids)]
    text_colors: list[list[str]] = [["#333333"] * len(show_ids)]
    cell_texts: list[list[str]] = [show_names]

    for party in ordered_parties:
        party_hex = pcolors.get(party, "#4a90c4")
        col_fills = []
        col_texts_val = []
        col_font_colors = []
        for sid in show_ids:
            pct_val = float(pct_matrix.loc[sid, party]) if sid in pct_matrix.index else 0.0
            norm_val = float(norm_matrix.loc[sid, party]) if sid in norm_matrix.index else 0.0
            t = min(norm_val ** 0.6, 1.0)
            fill = _hex_blend("#f5f5f5", party_hex, t)
            col_fills.append(fill)
            col_texts_val.append(f"{pct_val:.1f} %" if pct_val >= 0.1 else "")
            col_font_colors.append("#333333" if norm_val < 0.45 else "white")
        fill_colors.append(col_fills)
        text_colors.append(col_font_colors)
        cell_texts.append(col_texts_val)

    col_widths = [180] + [72] * len(ordered_parties)
    fig = go.Figure(go.Table(
        columnwidth=col_widths,
        header=dict(
            values=header_row,
            align=["left"] + ["center"] * len(ordered_parties),
            font=dict(size=11, color="#333333"),
            fill_color="#e0e0e0",
            line_color="#cccccc",
            height=38,
        ),
        cells=dict(
            values=cell_texts,
            align=["left"] + ["center"] * len(ordered_parties),
            font=dict(size=11, color=text_colors),
            fill_color=fill_colors,
            line_color="#e8e8e8",
            height=28,
        ),
    ))
    n_shows = len(show_ids)
    n_parties = len(ordered_parties)
    fig.update_layout(
        title=dict(
            text=(
                "<b>Party Affiliation Share · by Show</b><br>"
                "<sup>% of unique guests with known party affiliation · "
                "parties ordered left → right by political spectrum · darker = higher share · "
                f"parties ≥{min_pct:.0f}% share in at least one show</sup>"
            ),
            x=0.02,
            font=dict(size=15),
        ),
        margin=dict(l=20, r=20, t=100, b=20),
        height=100 + 38 + n_shows * 28 + 20,
        width=sum(col_widths) + 40,
    )
    _save(fig, output_dir, "03a_party_by_show")
    print(f"  Viz 3a: party heatmap ({n_shows} shows × {n_parties} parties) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 3b: Gender breakdown by property value (modular dot plot)
# ──────────────────────────────────────────────────────────────────────────────

def _parse_age_bin_start(label: str) -> float:
    """Return the numeric start of an age bin like '30-39' or '30–39'."""
    try:
        return float(str(label).split("-")[0].split("–")[0].strip())
    except (ValueError, IndexError):
        return float("inf")


def build_gender_breakdown_by_property(
    property_gender_frames: dict[str, pd.DataFrame],
    gender_colors: dict[str, str],
    output_dir: Path,
    *,
    top_n: int = 15,
) -> None:
    """Viz 3b: Dot plot — female share per property value, dot size = total guests.

    Age group panel sorted by numeric age (youngest at top).
    Empty string values excluded (they represent missing/unknown labels).
    Label area is wider; x-axis (plot area) narrower.
    """
    props = {k: v for k, v in property_gender_frames.items() if v is not None and not v.empty}
    if not props:
        print("  Viz 3b: no property-gender data — skipping")
        return

    female_color = gender_colors.get("weiblich", PALETTE[1] if len(PALETTE) > 1 else PALETTE[0])
    n_props = len(props)

    fig = make_subplots(
        rows=1, cols=n_props,
        subplot_titles=[f"<b>{k}</b>" for k in props.keys()],
        shared_yaxes=False,
        horizontal_spacing=0.06,
    )

    max_total = max(
        (float(df["total_count"].max()) for df in props.values()
         if not df.empty and "total_count" in df.columns),
        default=1.0,
    )

    for col_idx, (prop_label, df) in enumerate(props.items(), start=1):
        df = df.copy()
        df["total_count"] = pd.to_numeric(df["total_count"], errors="coerce").fillna(0)
        df["male_count"]   = pd.to_numeric(df["male_count"],   errors="coerce").fillna(0)
        df["female_count"] = pd.to_numeric(df["female_count"], errors="coerce").fillna(0)

        # Exclude empty string / NaN values (unknown labels)
        df["value"] = df["value"].astype(str).str.strip()
        df = df[df["value"].ne("") & df["value"].ne("nan")]

        known = df["male_count"] + df["female_count"]
        df = df[known > 0].copy()
        df["known"] = known
        df["female_pct"] = df["female_count"] / df["known"] * 100
        df = df[df["total_count"] > 0].nlargest(top_n, "total_count")
        if df.empty:
            continue

        # Sort age groups by numeric value (youngest at top = reversed axis)
        is_age = "age" in prop_label.lower()
        if is_age:
            df["_age_start"] = df["value"].apply(_parse_age_bin_start)
            df = df.sort_values("_age_start", ascending=True).reset_index(drop=True)
        else:
            df = df.sort_values("female_pct", ascending=True).reset_index(drop=True)

        labels = df["value"].astype(str).tolist()

        max_size = 40
        sizes = (df["total_count"] / max_total * max_size ** 2).apply(lambda x: max(4, x ** 0.5))

        fig.add_vline(x=50, line_dash="dot", line_color="#c0392b", line_width=1.2,
                      row=1, col=col_idx)

        fig.add_trace(go.Scatter(
            x=df["female_pct"].tolist(),
            y=labels,
            mode="markers",
            name=prop_label if col_idx == 1 else None,
            showlegend=False,
            marker=dict(
                size=sizes.tolist(),
                color=female_color,
                opacity=0.82,
                line=dict(color="white", width=1),
                sizemode="diameter",
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Female: %{x:.1f} %<br>"
                "Total guests: %{customdata:,}<extra></extra>"
            ),
            customdata=df["total_count"].astype(int).tolist(),
        ), row=1, col=col_idx)

        fig.update_xaxes(
            range=[0, 100], ticksuffix=" %",
            title_text="% female (of known)",
            title_font=dict(size=10),
            tickfont=dict(size=10),
            row=1, col=col_idx,
        )
        # Age: youngest at top (reversed), others: ascending female_pct (lowest at bottom)
        if is_age:
            fig.update_yaxes(
                tickfont=dict(size=10),
                autorange="reversed",
                row=1, col=col_idx,
            )
        else:
            fig.update_yaxes(
                tickfont=dict(size=10),
                row=1, col=col_idx,
            )

    # Wider label area: use domain to allocate more space to y-axis labels
    # Achieved by increasing left margin and using a wider overall figure
    panel_width = 340  # wider x-axis (plot) + label area
    label_pad = 60     # extra left pad per panel for long labels
    total_width = max(panel_width * n_props + label_pad * (n_props - 1) + 80, 700)

    fig.update_layout(
        title=dict(
            text=(
                "<b>Gender Breakdown by Property Value</b><br>"
                f"<sup>Dot = % female (of known gender) · size = total guests · "
                f"top {top_n} per property · 50% parity line</sup>"
            ),
            x=0.02,
            font=dict(size=15),
        ),
        template="plotly_white",
        height=140 + top_n * 28,
        width=total_width,
        margin=dict(l=50, r=20, t=110, b=60),
    )
    _save(fig, output_dir, "03b_gender_breakdown_by_property")
    print(f"  Viz 3b: gender breakdown dot plot ({n_props} panels) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 4: Guest co-appearance network — PageRank
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_NET_CONFIG = {
    "min_cooccurrences": 3,
    "top_n_nodes": 80,
    "seed": 42,
}

_NET_CONFIG_PATH = Path("data/50_analysis/all/final_visualizations/network_config.json")


def _load_net_config(config_path: Path | None = None) -> dict:
    """Load network layout config from JSON file, falling back to defaults."""
    path = config_path or _NET_CONFIG_PATH
    cfg = dict(_DEFAULT_NET_CONFIG)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            cfg.update({k: v for k, v in loaded.items() if k in cfg})
        except Exception:
            pass
    return cfg


def build_coappearance_network(
    co_occurrence_pairs: pd.DataFrame,
    guest_labels: dict[str, str],
    output_dir: Path,
    *,
    guest_attrs: pd.DataFrame | None = None,
    color_by: str = "occupation_meta",
    node_colors: dict[str, str] | None = None,
    min_cooccurrences: int | None = None,
    top_n_nodes: int | None = None,
    seed: int | None = None,
    config_path: Path | None = None,
) -> None:
    """Viz 4: Force-directed co-appearance network sized by PageRank.

    Parameters min_cooccurrences, top_n_nodes, and seed can be set via
    data/50_analysis/all/final_visualizations/network_config.json.
    Explicit keyword arguments override the config file.
    """
    try:
        import networkx as nx
    except ImportError:
        print("  Viz 4: networkx not installed — skipping")
        return

    cfg = _load_net_config(config_path)
    if min_cooccurrences is None:
        min_cooccurrences = cfg["min_cooccurrences"]
    if top_n_nodes is None:
        top_n_nodes = cfg["top_n_nodes"]
    if seed is None:
        seed = cfg["seed"]

    df = co_occurrence_pairs.copy()
    df["co_occurrence_count"] = pd.to_numeric(df["co_occurrence_count"], errors="coerce").fillna(0)
    df = df[df["co_occurrence_count"] >= min_cooccurrences]
    if df.empty:
        print(f"  Viz 4: no pairs with ≥{min_cooccurrences} co-occurrences — skipping")
        return

    G = nx.from_pandas_edgelist(df, "guest_a", "guest_b", edge_attr="co_occurrence_count")
    pr = nx.pagerank(G, alpha=0.85, weight="co_occurrence_count")

    top_nodes = sorted(pr, key=lambda n: -pr[n])[:top_n_nodes]
    G = G.subgraph(top_nodes).copy()
    try:
        pos = nx.kamada_kawai_layout(G, weight="co_occurrence_count")
    except Exception:
        pos = nx.spring_layout(G, seed=seed, k=4.0 / max(len(G.nodes) ** 0.5, 1))

    attr_map: dict[str, str] = {}
    if guest_attrs is not None and not guest_attrs.empty and color_by in guest_attrs.columns:
        attr_map = (
            guest_attrs.set_index("canonical_entity_id")[color_by]
            .fillna("Unknown").to_dict()
        )

    if node_colors is None:
        attr_counts: dict[str, int] = {}
        for node in G.nodes():
            attr = attr_map.get(node, "Unknown")
            attr_counts[attr] = attr_counts.get(attr, 0) + 1
        node_colors = build_category_color_registry(
            pd.Series(attr_counts).sort_values(ascending=False)
        )

    pr_values = list(pr.values())
    pr_p80 = np.percentile(pr_values, 80) if pr_values else 0

    groups: dict[str, list[str]] = {}
    for node in G.nodes():
        attr = attr_map.get(node, "Unknown")
        groups.setdefault(attr, []).append(node)

    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        w = data.get("co_occurrence_count", 1)
        edge_traces.append(go.Scatter(
            x=[x0, x1, None], y=[y0, y1, None],
            mode="lines",
            line=dict(color="#EBEBEB", width=0.3 + w * 0.08),
            hoverinfo="none", showlegend=False,
        ))

    node_traces = []
    for attr, nodes_in_group in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        xs = [pos[n][0] for n in nodes_in_group]
        ys = [pos[n][1] for n in nodes_in_group]
        sizes = [8 + pr[n] * 1200 for n in nodes_in_group]
        labels = [guest_labels.get(n, n) for n in nodes_in_group]
        color = node_colors.get(attr, UNKNOWN_COLOR)
        # Only label the top-ranked nodes (80th pct); text is centered in the node
        node_traces.append(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            name=attr,
            marker=dict(
                size=sizes,
                color=color,
                line=dict(color="white", width=1.2),
                sizemode="diameter",
            ),
            text=[lbl if pr.get(n, 0) >= pr_p80 else "" for n, lbl in zip(nodes_in_group, labels)],
            textposition="middle center",
            textfont=dict(size=8, color="white"),
            hovertext=[f"{lbl}<br>PageRank: {pr[n]:.4f}" for n, lbl in zip(nodes_in_group, labels)],
            hoverinfo="text",
        ))

    fig = go.Figure(data=edge_traces + node_traces)
    fig.update_layout(
        title=dict(
            text=(
                f"<b>Co-Appearance Network · Top {len(G.nodes)} Guests by PageRank</b><br>"
                f"<sup>Edge = ≥{min_cooccurrences} shared episodes · node area ∝ PageRank · colour = {color_by}</sup>"
            ),
            x=0.0,
        ),
        template="plotly_white",
        height=750, width=1100,
        margin=dict(l=20, r=20, t=100, b=20),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        legend=dict(orientation="v", x=1.01, y=1.0, xanchor="left", font=dict(size=11),
                    title=dict(text=color_by)),
    )
    _save(fig, output_dir, f"04_coappearance_network_{color_by}")
    print(f"  Viz 4: network colour={color_by} ({len(G.nodes)} nodes, {len(G.edges)} edges) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 5: Property coverage table (heatmap)
# ──────────────────────────────────────────────────────────────────────────────

def build_property_coverage_table(
    coverage_by_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    exclude_labels: list[str] | None = None,
    show_labels: dict[str, str] | None = None,
) -> None:
    """Viz 5: Heatmap of property coverage per show (linear scale).

    Properties sorted by mean coverage (highest first).
    Shows sorted by mean coverage (highest first).
    X-axis uses program names (via show_labels) with unique-guest count if provided.

    Args:
        coverage_by_show: property_id, property_label, then one column per
            show_id with coverage %.
        show_labels: {show_id → "Program Name (N guests)"} for x-axis labels.
            Show IDs are used if not provided.
        exclude_labels: Property labels to exclude.
    """
    df = coverage_by_show.copy()
    if df.empty:
        print("  Viz 5: no coverage data — skipping")
        return

    id_col = "property_id" if "property_id" in df.columns else df.columns[0]
    lbl_col = "property_label" if "property_label" in df.columns else df.columns[1]
    show_cols_raw = [c for c in df.columns if c not in (id_col, lbl_col)]

    if exclude_labels:
        df = df[~df[lbl_col].isin(exclude_labels)].copy()

    if df.empty or not show_cols_raw:
        print("  Viz 5: no data after filtering — skipping")
        return

    show_means = df[show_cols_raw].mean(axis=0).sort_values(ascending=False)
    show_cols_sorted = show_means.index.tolist()

    df["_mean_cov"] = df[show_cols_raw].mean(axis=1)
    df = df.sort_values("_mean_cov", ascending=False).reset_index(drop=True)

    labels = df[lbl_col].tolist()
    z = df[show_cols_sorted].values.astype(float)
    n_props, n_shows = len(labels), len(show_cols_sorted)

    # Map show IDs to display labels (program name + unique guests)
    x_labels = [
        show_labels.get(sid, sid) if show_labels else sid
        for sid in show_cols_sorted
    ]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=x_labels,
        y=labels,
        colorscale=[[0, "#f5f5f5"], [0.25, "#b3cde3"], [0.55, "#4393c3"], [1, "#0d4f8b"]],
        zmin=0, zmax=100,
        text=[[f"{v:.0f} %" if not np.isnan(v) else "—" for v in row] for row in z],
        texttemplate="%{text}",
        textfont=dict(size=10),
        colorbar=dict(title=dict(text="Coverage %", side="right"), ticksuffix="%", len=0.7),
        hovertemplate="Property: %{y}<br>Show: %{x}<br>Coverage: %{z:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text=(
                "<b>Property Coverage · by Show</b><br>"
                "<sup>% of unique guests with ≥1 value · properties sorted by mean coverage · "
                "shows sorted by mean coverage</sup>"
            ),
            x=0.02,
            font=dict(size=15),
        ),
        xaxis=dict(title="", side="top", tickangle=-40, tickfont=dict(size=11)),
        yaxis=dict(title="", autorange="reversed", tickfont=dict(size=11)),
        template="plotly_white",
        height=120 + n_props * 34,
        width=160 + n_shows * 100,
        margin=dict(l=220, r=80, t=130, b=20),
    )
    _save(fig, output_dir, "05_property_coverage_table")
    print(f"  Viz 5: coverage table ({n_props}×{n_shows}) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 6: Occupation hierarchy — sunburst
# ──────────────────────────────────────────────────────────────────────────────

def build_occupation_sunburst(
    occ_with_categories: pd.DataFrame,
    category_colors: dict[str, str],
    output_dir: Path,
    *,
    top_per_category: int = 8,
) -> None:
    """Viz 6: Two-ring sunburst using P279-resolved occupation categories.

    Inner ring: category (midlevel class label).
    Outer ring: individual occupation label, sized by unique guests.
    """
    df = occ_with_categories.copy()
    df = df[df["occ_label"].notna() & df["occ_label"].ne("Unknown / no data")]
    df["person_count"] = pd.to_numeric(df["person_count"], errors="coerce").fillna(0)
    df = df[df["person_count"] > 0]
    if df.empty:
        print("  Viz 6: no occupation data — skipping")
        return

    agg = (
        df.groupby(["cat_qid", "cat_label", "occ_label"])["person_count"]
        .sum().reset_index()
    )

    cat_totals = agg.groupby(["cat_qid", "cat_label"])["person_count"].sum().reset_index()
    cat_totals = cat_totals.sort_values("person_count", ascending=False)

    ids, labels, parents, values, colors = [], [], [], [], []

    for _, cat_row in cat_totals.iterrows():
        cqid = str(cat_row["cat_qid"])
        clbl = str(cat_row["cat_label"])
        ctot = int(cat_row["person_count"])
        color = category_colors.get(cqid, OTHER_COLOR)

        ids.append(cqid)
        labels.append(clbl)
        parents.append("")
        values.append(ctot)
        colors.append(color)

        leaves = (
            agg[agg["cat_qid"] == cqid]
            .sort_values("person_count", ascending=False)
            .reset_index(drop=True)
        )
        top_leaves = leaves.head(top_per_category)
        remainder = int(leaves["person_count"].sum()) - int(top_leaves["person_count"].sum())

        for rank, (_, lrow) in enumerate(top_leaves.iterrows()):
            uid = f"{cqid}::{lrow['occ_label']}"
            leaf_color = color + "BB"
            ids.append(uid)
            labels.append(str(lrow["occ_label"]))
            parents.append(cqid)
            values.append(int(lrow["person_count"]))
            colors.append(leaf_color)

        if remainder > 0:
            ids.append(f"{cqid}::__other__")
            labels.append("Weitere…")
            parents.append(cqid)
            values.append(remainder)
            colors.append(OTHER_COLOR)

    fig = go.Figure(go.Sunburst(
        ids=ids,
        labels=labels,
        parents=parents,
        values=values,
        marker=dict(colors=colors),
        branchvalues="total",
        insidetextorientation="radial",
        hovertemplate=(
            "<b>%{label}</b><br>%{value:,} unique guests<br>"
            "%{percentRoot:.1%} of total<extra></extra>"
        ),
    ))
    fig.update_layout(
        title=dict(
            text=(
                "<b>Guest Occupations · Hierarchy</b><br>"
                "<sup>Inner ring: P279-resolved category · Outer ring: Wikidata occupation · sized by unique guests</sup>"
            ),
            x=0.0,
        ),
        margin=dict(t=100, b=20, l=20, r=20),
        height=700, width=900,
    )
    _save(fig, output_dir, "06_occupation_sunburst")
    print(f"  Viz 6: occupation sunburst ({len(cat_totals)} categories) → {output_dir.name}/")
