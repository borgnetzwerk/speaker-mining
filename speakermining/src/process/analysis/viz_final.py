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
# Bilingual label tables  (lang="en" | lang="de")
# ──────────────────────────────────────────────────────────────────────────────

_TR: dict[str, dict[str, str]] = {
    "en": {
        "broadcasting_program": "Broadcasting Program",
        "episodes": "Episodes",
        "span": "Span",
        "unique": "Unique",
        "unresolved": "Unresolved",
        "guests": "Guests",
        "appearances": "Appearances",
        "with_wikidata": "w/ Wikidata",
        "guest_gender": "Guest Gender",
        "male": "Male",
        "female": "Female",
        "other": "Other",
        "eps_without_gender": "Eps w/o Gender",
        "guest_age": "Guest Age",
        "min": "Min",
        "median": "Median",
        "max": "Max",
        "00_title": "Talk Shows \u00b7 Sample &amp; Demographics",
        "00_sub": "Sorted by total appearances \u00b7 German shows + StarTalk reference \u00b7 2003\u20132025",
        "01_title": "Age at Appearance \u00b7 by Show",
        "01_sub": "Sorted by median age \u00b7 box = IQR \u00b7 centre line = median",
        "01_xaxis": "Age at time of appearance",
        "02_title": "Male Guest Share over Time",
        "02_sub": "{w}-yr rolling mean \u00b7 known gender only \u00b7 colour = show",
        "02_50pct": "50 % parity",
        "02_yaxis": "Male share of appearances (%)",
        "03a_title": "Party Affiliation Share \u00b7 by Show",
        "03a_sub": "% of unique guests with known party \u00b7 ordered by total appearances \u00b7 top {n} parties",
        "03a_total": "Total guests",
        "03b_title": "Male Share \u00b7 {prop}",
        "03b_sub": "Dot = % male (of known gender) \u00b7 size = total guests \u00b7 top {n} \u00b7 50 % parity line",
        "03b_xaxis": "% male (of known gender)",
    },
    "de": {
        "broadcasting_program": "Sendung",
        "episodes": "Folgen",
        "span": "Zeitraum",
        "unique": "Unique",
        "unresolved": "Unaufgelöst",
        "guests": "Gäste",
        "appearances": "Auftritte",
        "with_wikidata": "m. Wikidata",
        "guest_gender": "Geschlecht",
        "male": "Männlich",
        "female": "Weiblich",
        "other": "Andere",
        "eps_without_gender": "Folgen o. Geschlecht",
        "guest_age": "Alter",
        "min": "Min",
        "median": "Median",
        "max": "Max",
        "00_title": "Talkshows \u00b7 Stichprobe &amp; Demografie",
        "00_sub": "Sortiert nach Auftritten \u00b7 Deutsche Sendungen + StarTalk \u00b7 2003\u20132025",
        "01_title": "Alter bei Auftritt \u00b7 nach Sendung",
        "01_sub": "Sortiert nach Median \u00b7 Box = IQR \u00b7 Mittellinie = Median",
        "01_xaxis": "Alter bei Auftritt",
        "02_title": "Anteil männlicher Gäste im Zeitverlauf",
        "02_sub": "{w}-j. gleitender Mittel \u00b7 nur bekanntes Geschlecht \u00b7 Farbe = Sendung",
        "02_50pct": "50 % Parität",
        "02_yaxis": "Anteil männlicher Auftritte (%)",
        "03a_title": "Parteizugehörigkeit \u00b7 nach Sendung",
        "03a_sub": "% Gäste m. bekannter Partei \u00b7 nach Gesamtauftritten \u00b7 Top {n} Parteien",
        "03a_total": "Gäste gesamt",
        "03b_title": "Männeranteil \u00b7 {prop}",
        "03b_sub": "Punkt = % männlich (bekanntes Geschlecht) \u00b7 Größe = Gäste \u00b7 Top {n} \u00b7 50%-Linie",
        "03b_xaxis": "% männlich (bekanntes Geschlecht)",
    },
}


def _t(lang: str, key: str, **fmt) -> str:
    """Return translated string, falling back to English."""
    s = _TR.get(lang, _TR["en"]).get(key, _TR["en"].get(key, key))
    return s.format(**fmt) if fmt else s



# ──────────────────────────────────────────────────────────────────────────────
# Registry builders  (call once at session start; pass results to all charts)
# ──────────────────────────────────────────────────────────────────────────────

def build_show_color_registry(
    per_show_stats: pd.DataFrame,
    *,
    party_colors_path: str | Path | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Assign palette colors to shows ordered by total appearances descending."""
    sentinel_ids = {"NONE"}

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
        if sid and sid.upper() not in sentinel_ids:
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
    unresolved_by_show: pd.DataFrame | None = None,
    lang: str = "en",
) -> None:
    """Viz 0: Show statistics table with grouped column headers and colour-bar cells.

    Column groups: Broadcasting Program | Episodes (Span/Unique/Unresolved) |
    Guests (Appearances/Unique/w/ Wikidata) | Guest Gender (M/F/Other %) |
    Eps w/o Gender (M/F/Other) | Guest Age (Min/Median/Max)
    """
    df = per_show_stats.drop_duplicates(subset=["show_id"]).copy()
    ordered_ids = _sort_by_order(df["show_id"].tolist(), show_order)
    order_map = {sid: i for i, sid in enumerate(ordered_ids)}
    df = df[df["show_id"].isin(set(ordered_ids))].copy()
    df["_order"] = df["show_id"].map(order_map)
    df = df.sort_values("_order").drop(columns=["_order"]).reset_index(drop=True)

    for extra, cols in [
        (gender_by_show,             ["male_pct", "female_pct", "other_pct"]),
        (gender_by_show,             ["male_count", "female_count", "other_count"]),
        (age_by_show,                ["min_age", "median_age", "max_age"]),
        (span_by_show,               ["span_label"]),
        (wikidata_pct_by_show,       ["wikidata_pct", "has_wd"]),
        (eps_without_gender_by_show, ["eps_without_male", "eps_without_female", "eps_without_other"]),
        (unresolved_by_show,         ["unresolved"]),
    ]:
        if extra is not None and not extra.empty:
            present = [c for c in cols if c in extra.columns]
            if present:
                df = df.merge(extra[["show_id"] + present], on="show_id", how="left")
        for c in cols:
            if c not in df.columns:
                df[c] = float("nan") if c != "span_label" else "—"

    def _pct(v):
        try:
            fv = float(v)
            return f"{fv:.0f}%" if not pd.isna(fv) else "—"
        except (TypeError, ValueError):
            return "—"

    def _int(v):
        try:
            return f"{int(float(v)):,}" if pd.notna(v) and float(v) >= 0 else "—"
        except (TypeError, ValueError):
            return "—"

    def _age(v):
        try:
            return f"{float(v):.0f}" if pd.notna(v) else "—"
        except (TypeError, ValueError):
            return "—"

    def _bar_cell(count_val, pct_val, show_hex: str) -> str:
        """Format '{count} ({pct}%)' with pct available for fill_color logic."""
        try:
            c = int(float(count_val)) if pd.notna(count_val) else None
            p = float(pct_val) if pd.notna(pct_val) else None
        except (TypeError, ValueError):
            return "—"
        if c is None or p is None:
            return "—"
        return f"{c:,}\n({p:.0f}%)"

    def _eps_bar_cell(count_val, total_eps) -> str:
        try:
            c = int(float(count_val)) if pd.notna(count_val) else None
            t = int(float(total_eps)) if pd.notna(total_eps) else None
        except (TypeError, ValueError):
            return "—"
        if c is None or t is None or t == 0:
            return "—" if c is None else f"{c:,}"
        p = c / t * 100
        return f"{c:,}\n({p:.0f}%)"

    def _blend(hex_color: str, pct: float, opacity: float = 0.85) -> str:
        """Blend hex_color toward white, scaled by pct/100 × opacity."""
        try:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            t = min(pct / 100, 1.0) * opacity
            r2 = int(r * t + 255 * (1 - t))
            g2 = int(g * t + 255 * (1 - t))
            b2 = int(b * t + 255 * (1 - t))
            return f"#{r2:02X}{g2:02X}{b2:02X}"
        except Exception:
            return "#f5f5f5"

    n = len(df)
    row_fills_base = ["#f7f7f7" if i % 2 == 0 else "#ffffff" for i in range(n)]

    T = lambda k, **fmt: _t(lang, k, **fmt)

    # ── column definitions ────────────────────────────────────────────────────
    # Each entry: (header, cell_values_list, col_width, fill_list_or_None)
    cols_def = []

    # Broadcasting Program
    cols_def.append((
        f"<b>{T('broadcasting_program')}</b>",
        df["program_name"].tolist(),
        190, None,
    ))
    # Episodes · Span
    cols_def.append((
        f"<b>{T('episodes')}<br>{T('span')}</b>",
        df["span_label"].fillna("—").tolist(),
        85, None,
    ))
    # Episodes · Unique
    cols_def.append((
        f"<b>{T('episodes')}<br>{T('unique')}</b>",
        df["episode_count"].apply(_int).tolist(),
        60, None,
    ))
    # Episodes · Unresolved
    cols_def.append((
        f"<b>{T('episodes')}<br>{T('unresolved')}</b>",
        df["unresolved"].apply(_int).tolist(),
        70, None,
    ))
    # Guests · Appearances
    cols_def.append((
        f"<b>{T('guests')}<br>{T('appearances')}</b>",
        df["guest_appearances"].apply(_int).tolist(),
        70, None,
    ))
    # Guests · Unique
    cols_def.append((
        f"<b>{T('guests')}<br>{T('unique')}</b>",
        df["unique_guests"].apply(_int).tolist(),
        60, None,
    ))
    # Guests · w/ Wikidata
    cols_def.append((
        f"<b>{T('guests')}<br>{T('with_wikidata')}</b>",
        df["has_wd"].apply(_int).tolist(),
        70, None,
    ))

    # Gender columns — colour bars
    for gender_key, cnt_col, pct_col in [
        ("male",   "male_count",   "male_pct"),
        ("female", "female_count", "female_pct"),
        ("other",  "other_count",  "other_pct"),
    ]:
        texts = []
        fills = []
        fcolors = []
        for _, row in df.iterrows():
            sid = str(row.get("show_id", ""))
            shex = show_colors.get(sid, "#999999")
            t = _bar_cell(row.get(cnt_col), row.get(pct_col), shex)
            try:
                pv = float(row.get(pct_col, 0)) if pd.notna(row.get(pct_col)) else 0.0
            except (TypeError, ValueError):
                pv = 0.0
            fc = _blend(shex, pv)
            texts.append(t)
            fills.append(fc)
            fcolors.append("white" if pv >= 50 else "#333333")
        cols_def.append((
            f"<b>{T('guest_gender')}<br>{T(gender_key)}</b>",
            texts, 80, (fills, fcolors),
        ))

    # Eps w/o gender — percentage of total episodes
    for gender_key, col in [("male", "eps_without_male"), ("female", "eps_without_female"), ("other", "eps_without_other")]:
        texts = []
        fills = []
        fcolors = []
        for _, row in df.iterrows():
            sid = str(row.get("show_id", ""))
            shex = show_colors.get(sid, "#999999")
            total_eps = row.get("episode_count", 0)
            t = _eps_bar_cell(row.get(col), total_eps)
            try:
                c = float(row.get(col, 0)) if pd.notna(row.get(col)) else 0.0
                te = float(total_eps) if pd.notna(total_eps) and float(total_eps) > 0 else 1.0
                pv = c / te * 100
            except (TypeError, ValueError, ZeroDivisionError):
                pv = 0.0
            fc = _blend(shex, pv)
            texts.append(t)
            fills.append(fc)
            fcolors.append("white" if pv >= 50 else "#333333")
        cols_def.append((
            f"<b>{T('eps_without_gender')}<br>{T(gender_key)}</b>",
            texts, 80, (fills, fcolors),
        ))

    # Age
    for age_key, col in [("min", "min_age"), ("median", "median_age"), ("max", "max_age")]:
        cols_def.append((
            f"<b>{T('guest_age')}<br>{T(age_key)}</b>",
            df[col].apply(_age).tolist(),
            48, None,
        ))

    # ── assemble table ────────────────────────────────────────────────────────
    header_vals = [c[0] for c in cols_def]
    cell_vals   = [c[1] for c in cols_def]
    col_widths  = [c[2] for c in cols_def]
    n_cols = len(cols_def)

    # fill_color: 2-D list [col][row]
    fill_color_matrix = []
    font_color_matrix = []
    for c in cols_def:
        if c[3] is not None:
            fills_col, fc_col = c[3]
            fill_color_matrix.append(fills_col)
            font_color_matrix.append(fc_col)
        else:
            fill_color_matrix.append(row_fills_base)
            font_color_matrix.append(["#333333"] * n)

    # Header fill: alternate light bands to indicate column groups
    hdr_fills = ["#d0d8e4", "#dce8d0", "#dce8d0", "#dce8d0",
                 "#e8dcd0", "#e8dcd0", "#e8dcd0",
                 "#d4e8e8", "#d4e8e8", "#d4e8e8",
                 "#e8d4e0", "#e8d4e0", "#e8d4e0",
                 "#e8e4d0", "#e8e4d0", "#e8e4d0"]
    hdr_fills = (hdr_fills + ["#e8e8e8"] * n_cols)[:n_cols]

    fig = go.Figure(go.Table(
        columnwidth=col_widths,
        header=dict(
            values=header_vals,
            align=["left"] + ["center"] * (n_cols - 1),
            font=dict(size=9, color="#333333"),
            fill_color=hdr_fills,
            line_color="#cccccc",
            height=46,
        ),
        cells=dict(
            values=cell_vals,
            align=["left"] + ["center"] * (n_cols - 1),
            font=dict(size=9, color=font_color_matrix),
            fill_color=fill_color_matrix,
            line_color="#e0e0e0",
            height=30,
        ),
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>{T('00_title')}</b><br><sup>{T('00_sub')}</sup>",
            x=0.02, font=dict(size=14), pad=dict(l=0, t=10),
        ),
        margin=dict(l=20, r=20, t=90, b=20),
        height=90 + 46 + n * 30 + 20,
        width=sum(col_widths) + 60,
    )
    stem = f"00_show_stats_table_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 0 [{lang}]: show stats table ({n} shows) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 1: Age at appearance — density ridge
# ──────────────────────────────────────────────────────────────────────────────

def build_age_ridge_plot(
    age_with_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    lang: str = "en",
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

    T = lambda k, **fmt: _t(lang, k, **fmt)

    tick_vals = list(range(x_min - x_min % 5, x_max + 6, 5))

    # Add median annotations (right side of plot)
    for sid in show_ids_sorted:
        sub = df[df["show_id"] == sid]["age"]
        if sub.empty:
            continue
        med = float(sub.median())
        fig.add_annotation(
            x=med, y=prog.get(sid, sid),
            text=f"  {med:.0f}",
            showarrow=False,
            font=dict(size=9, color=show_colors.get(sid, UNKNOWN_COLOR)),
            xanchor="left",
        )

    fig.update_layout(
        title=dict(
            text=f"<b>{T('01_title')}</b><br><sup>{T('01_sub')}</sup>",
            x=0.02, font=dict(size=15),
        ),
        xaxis=dict(
            title=T("01_xaxis"),
            range=[x_min, x_max],
            tickvals=tick_vals,
            tickfont=dict(size=11),
            title_font=dict(size=12),
            mirror=True,
            showline=True,
            side="bottom",
        ),
        xaxis2=dict(
            overlaying="x",
            side="top",
            range=[x_min, x_max],
            tickvals=tick_vals,
            tickfont=dict(size=9),
            showticklabels=True,
            showgrid=False,
            zeroline=False,
        ),
        yaxis=dict(title="", tickfont=dict(size=12)),
        template="plotly_white",
        height=120 + len(show_ids_sorted) * 75,
        width=900,
        margin=dict(l=60, r=200, t=130, b=60),
        showlegend=True,
        legend=dict(
            orientation="v", x=1.01, y=1.0, xanchor="left",
            font=dict(size=11),
            title=dict(text="Show"),
        ),
        violingap=0.05,
        violingroupgap=0,
    )
    stem = f"01_age_ridge_plot_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 1 [{lang}]: age ridge ({len(show_ids_sorted)} shows) → {output_dir.name}/")


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
    lang: str = "en",
) -> None:
    """Viz 2: Male guest share over time — one line per show.

    Only männlich (male) gender is plotted. 50 % parity reference line included.
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
    _MALE_KEY = _nfc("männlich")
    genders_to_plot = [
        g for g in gender_order
        if g in meaningful and g != UNKNOWN_LABEL and _nfc(g) == _MALE_KEY
    ]
    if not genders_to_plot:
        # Fallback: if NFC match fails, take first non-unknown gender
        genders_to_plot = [g for g in gender_order if g in meaningful and g != UNKNOWN_LABEL][:1]
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
                  annotation_text=_t(lang, "02_50pct"), annotation_position="right")

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

    T = lambda k, **fmt: _t(lang, k, **fmt)
    fig.update_layout(
        title=dict(
            text=(
                f"<b>{T('02_title')}</b><br>"
                f"<sup>{T('02_sub', w=rolling_window)}</sup>"
            ),
            x=0.02, font=dict(size=15),
        ),
        xaxis=dict(title="Year", tickangle=-45, dtick=2, tickfont=dict(size=11)),
        yaxis=dict(title=T("02_yaxis"), range=[0, 100], ticksuffix="%"),
        template="plotly_white",
        height=520,
        width=1300,
        margin=dict(l=70, r=260, t=120, b=80),
        legend=dict(
            orientation="v", x=1.01, y=1.0, xanchor="left",
            font=dict(size=11),
            title=dict(text="Show"),
        ),
    )
    stem = f"02_gender_over_time_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 2 [{lang}]: male share over time ({len(show_ids)} shows) → {output_dir.name}/")


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
    top_n: int = 10,
    lang: str = "en",
) -> None:
    """Viz 3a: Heatmap-table — party share by show.

    Shows top_n parties ordered by total appearances across all shows.
    Adds a totals row at the top showing total guest count per party.
    Party colors loaded from party_colors.csv when not explicitly provided.

    Args:
        party_by_show: show_id, program_name, party_label, unique_guests.
        top_n: Keep only the N parties with the most total appearances.
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

    # Keep top_n parties by total guest count across all shows
    _party_totals_all = df.groupby("party_label")["unique_guests"].sum()
    _top_parties = set(_party_totals_all.nlargest(top_n).index)
    df = df[df["party_label"].isin(_top_parties)]
    if df.empty:
        print(f"  Viz 3a: no parties in top {top_n} — skipping")
        return

    # Order parties by total appearances (most common → rightmost)
    present_parties = set(df["party_label"].unique())
    party_totals_all = df.groupby("party_label")["unique_guests"].sum()
    ordered_parties = party_totals_all.sort_values(ascending=True).index.tolist()
    ordered_parties = [p for p in ordered_parties if p in present_parties]

    # Auto-load party colors from CSV when not explicitly provided
    pcolors: dict[str, str] = dict(party_colors or {})
    if not pcolors:
        try:
            pc_df = load_party_colors()
            # Prefer P465 hex; fall back to hex_color column
            for _, row in pc_df.iterrows():
                lbl = str(row.get("label", "")).strip()
                hex_c = str(row.get("hex_color", "")).strip()
                if lbl and hex_c and hex_c.startswith("#"):
                    pcolors[lbl] = hex_c
        except Exception:
            pass

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

    T = lambda k, **fmt: _t(lang, k, **fmt)
    show_names = [prog.get(s, s) for s in show_ids]
    header_row = ["<b>Show</b>"] + [f"<b>{p}</b>" for p in ordered_parties]

    # Row 0: totals row (total appearances per party across all shows)
    party_totals_row = []
    for party in ordered_parties:
        tot = int(party_totals_all.get(party, 0))
        party_totals_row.append(f"<b>{tot:,}</b>")

    n_shows = len(show_ids)
    n_parties = len(ordered_parties)
    n_data_rows = n_shows + 1  # +1 for totals

    # Build cell column lists: first entry = totals row, then per-show rows
    fill_colors: list[list[str]] = [["#d8e4f0"] + ["#e8e8e8"] * n_shows]
    text_colors: list[list[str]] = [["#333333"] * n_data_rows]
    cell_texts: list[list[str]] = [[T("03a_total")] + show_names]

    for party in ordered_parties:
        party_hex = pcolors.get(party, "#4a90c4")
        col_fills = ["#d8e4f0"]  # totals row
        col_texts_val = [f"<b>{int(party_totals_all.get(party, 0)):,}</b>"]
        col_font_colors = ["#333333"]
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

    col_widths = [180] + [72] * n_parties
    fig = go.Figure(go.Table(
        columnwidth=col_widths,
        header=dict(
            values=header_row,
            align=["left"] + ["center"] * n_parties,
            font=dict(size=11, color="#333333"),
            fill_color="#e0e0e0",
            line_color="#cccccc",
            height=38,
        ),
        cells=dict(
            values=cell_texts,
            align=["left"] + ["center"] * n_parties,
            font=dict(size=11, color=text_colors),
            fill_color=fill_colors,
            line_color="#e8e8e8",
            height=28,
        ),
    ))
    fig.update_layout(
        title=dict(
            text=(
                f"<b>{T('03a_title')}</b><br>"
                f"<sup>{T('03a_sub', n=n_parties)}</sup>"
            ),
            x=0.02, font=dict(size=15),
        ),
        margin=dict(l=20, r=20, t=100, b=40),
        height=100 + 38 + n_data_rows * 28 + 40,
        width=sum(col_widths) + 40,
    )
    stem = f"03a_party_by_show_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 3a [{lang}]: party heatmap ({n_shows} shows × {n_parties} parties) → {output_dir.name}/")


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
    lang: str = "en",
) -> None:
    """Viz 3b: One dot plot per property — male share, dot size = total guests.

    Each property is saved as an individual file (03b_{slug}_{lang}).
    Age group panel sorted youngest-at-top; others sorted by male share.
    """
    props = {k: v for k, v in property_gender_frames.items() if v is not None and not v.empty}
    if not props:
        print("  Viz 3b: no property-gender data — skipping")
        return

    T = lambda k, **fmt: _t(lang, k, **fmt)
    male_color = gender_colors.get(_nfc("männlich"), PALETTE[0])

    for prop_label, df_raw in props.items():
        df = df_raw.copy()
        df["total_count"] = pd.to_numeric(df["total_count"], errors="coerce").fillna(0)
        df["male_count"]   = pd.to_numeric(df["male_count"],  errors="coerce").fillna(0)
        df["female_count"] = pd.to_numeric(df["female_count"],errors="coerce").fillna(0)
        df["value"] = df["value"].astype(str).str.strip()
        df = df[df["value"].ne("") & df["value"].ne("nan")]

        known = df["male_count"] + df["female_count"]
        df = df[known > 0].copy()
        df["known"] = known
        df["male_pct"] = df["male_count"] / df["known"] * 100
        df = df[df["total_count"] > 0].nlargest(top_n, "total_count")
        if df.empty:
            continue

        is_age = "age" in prop_label.lower()
        if is_age:
            df["_age_start"] = df["value"].apply(_parse_age_bin_start)
            df = df.sort_values("_age_start", ascending=False).reset_index(drop=True)
        else:
            df = df.sort_values("male_pct", ascending=True).reset_index(drop=True)

        labels = df["value"].astype(str).tolist()
        max_total = float(df["total_count"].max()) or 1.0
        max_size = 40
        sizes = (df["total_count"] / max_total * max_size ** 2).apply(lambda x: max(4, x ** 0.5))

        fig = go.Figure()
        fig.add_vline(x=50, line_dash="dot", line_color="#c0392b", line_width=1.2)
        fig.add_trace(go.Scatter(
            x=df["male_pct"].tolist(),
            y=labels,
            mode="markers",
            showlegend=False,
            marker=dict(
                size=sizes.tolist(),
                color=male_color,
                opacity=0.82,
                line=dict(color="white", width=1),
                sizemode="diameter",
            ),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Male: %{x:.1f} %<br>"
                "Total guests: %{customdata:,}<extra></extra>"
            ),
            customdata=df["total_count"].astype(int).tolist(),
        ))
        fig.update_xaxes(range=[0, 100], ticksuffix=" %", title_text=T("03b_xaxis"),
                         title_font=dict(size=10), tickfont=dict(size=10))
        if is_age:
            fig.update_yaxes(tickfont=dict(size=10))
        else:
            fig.update_yaxes(tickfont=dict(size=10))

        actual_n = len(df)
        fig.update_layout(
            title=dict(
                text=(
                    f"<b>{T('03b_title', prop=prop_label)}</b><br>"
                    f"<sup>{T('03b_sub', n=actual_n)}</sup>"
                ),
                x=0.02, font=dict(size=14),
            ),
            template="plotly_white",
            height=120 + actual_n * 30,
            width=500,
            margin=dict(l=160, r=20, t=100, b=60),
        )
        slug = "".join(c if c.isalnum() else "_" for c in prop_label.lower()).strip("_")
        stem = f"03b_{slug}_{lang}"
        _save(fig, output_dir, stem)
        print(f"  Viz 3b [{lang}]: {prop_label} ({actual_n} values) → {output_dir.name}/")


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
