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
        "male": "Male Guest",
        "female": "Female Guest",
        "other": "Other",
        "eps_without_gender": "Episodes without ...",
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
        "02_coverage_yaxis": "Coverage",
        "03a_title": "Party Affiliation Share \u00b7 by Show",
        "03a_sub": "% of unique guests with known party \u00b7 ordered by total appearances \u00b7 top {n} parties",
        "03a_total": "Total guests",
        "03b_title": "Male Share \u00b7 {prop}",
        "03b_sub": "Dot = % male (of known gender) \u00b7 size = total guests \u00b7 top {n} \u00b7 50 % parity line",
        "03b_xaxis": "% male (of known gender)",
        "total": "Total",
        "02_trend": "Overall trend",
        "05_col_avg": "Avg.",
        "wikidata_entry": "Wikidata entry",
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
        "male": "männlichen Gast",
        "female": "weiblichen Gast",
        "other": "Andere",
        "eps_without_gender": "Folgen ohne ...",
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
        "02_coverage_yaxis": "Abdeckung",
        "03a_title": "Parteizugehörigkeit \u00b7 nach Sendung",
        "03a_sub": "% Gäste m. bekannter Partei \u00b7 nach Gesamtauftritten \u00b7 Top {n} Parteien",
        "03a_total": "Gäste gesamt",
        "03b_title": "Männeranteil \u00b7 {prop}",
        "03b_sub": "Punkt = % männlich (bekanntes Geschlecht) \u00b7 Größe = Gäste \u00b7 Top {n} \u00b7 50%-Linie",
        "03b_xaxis": "% männlich (bekanntes Geschlecht)",
        "total": "Gesamt",
        "02_trend": "Gesamttrend",
        "05_col_avg": "Ø",
        "wikidata_entry": "Wikidata-Eintrag",
    },
}


def _t(lang: str, key: str, **fmt) -> str:
    """Return translated string, falling back to English."""
    s = _TR.get(lang, _TR["en"]).get(key, _TR["en"].get(key, key))
    return s.format(**fmt) if fmt else s


def _wrap_label_html(text: str, max_chars: int = 10) -> str:
    """Insert <br> at word boundaries so no line exceeds max_chars (for HTML tables)."""
    if len(text) <= max_chars:
        return text
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return "<br>".join(lines)


def _wrap_label_plotly(text: str, max_chars: int = 30) -> str:
    """Insert \\n at word boundaries so no line exceeds max_chars (for Plotly tick labels)."""
    if len(text) <= max_chars:
        return text
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        if current and len(current) + 1 + len(word) > max_chars:
            lines.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
    if current:
        lines.append(current)
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Short-label support
# short_labels.csv: entity_id, wikidata_id, entity_type, label_en, label_de,
#                   short_label_en, short_label_de
# entity_id = show slug for shows; wikidata QID for parties.
# Indexed by both entity_id and wikidata_id so QID-based lookups work.
# Party entries are populated from Wikidata P1813 (short name) at notebook run time.
# ──────────────────────────────────────────────────────────────────────────────

SHORT_LABELS_PATH = Path("data/00_setup/short_labels.csv")


def load_short_labels(path: str | Path | None = None) -> dict[tuple[str, str], str]:
    """Load {(entity_id, lang): short_label} from CSV, silently returns {} on missing file.

    Also indexes by wikidata_id when present, enabling (QID, lang) lookups for parties.
    """
    p = Path(path) if path else SHORT_LABELS_PATH
    if not p.exists():
        return {}
    try:
        df = pd.read_csv(p, dtype=str).fillna("")
        out: dict[tuple[str, str], str] = {}
        for _, row in df.iterrows():
            eid = str(row.get("entity_id", "")).strip()
            wid = str(row.get("wikidata_id", "")).strip()
            for lang in ("en", "de"):
                short = str(row.get(f"short_label_{lang}", "")).strip()
                if short:
                    if eid:
                        out[(eid, lang)] = short
                    if wid and wid != eid:
                        out[(wid, lang)] = short
        return out
    except Exception:
        return {}


def _short(entity_id: str, fallback: str, lang: str, labels: dict) -> str:
    """Return the short label for entity_id/lang, or fallback if not found."""
    return labels.get((entity_id, lang), fallback)


# ──────────────────────────────────────────────────────────────────────────────
# Registry builders  (call once at session start; pass results to all charts)
# ──────────────────────────────────────────────────────────────────────────────

def build_show_color_registry(
    per_show_stats: pd.DataFrame,
    *,
    party_colors_path: str | Path | None = None,
) -> tuple[dict[str, str], list[str]]:
    """Assign palette colors to shows ordered by episode count descending."""
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

    sort_col = "episode_count" if "episode_count" in per_show_stats.columns else "guest_appearances"
    ordered = (
        per_show_stats
        .assign(_sort=lambda d: pd.to_numeric(d[sort_col], errors="coerce").fillna(0))
        .sort_values("_sort", ascending=False)
        .drop(columns=["_sort"])
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
    seen: set[str] = set()
    result: list[str] = []
    for s in order:
        if s in present and s not in seen:
            seen.add(s)
            result.append(s)
    for s in sorted(s for s in present if s not in seen):
        result.append(s)
    return result


def _save(fig: go.Figure, output_dir: Path, stem: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    apply_font(fig)
    save_fig(fig, output_dir / stem)


def _render_html_table(html_path: Path, png_path: Path, pdf_path: Path, *, dpr: int = 3) -> None:
    """Render the <table> in html_path to PNG and PDF via playwright (headless Chromium).

    Spawns a subprocess so the sync playwright API doesn't conflict with
    Jupyter's running asyncio event loop.
    dpr sets the device pixel ratio for the screenshot (3 → roughly 300 dpi).
    """
    import os, sys, subprocess, tempfile

    _html_uri = html_path.resolve().as_uri()
    _png_str  = str(png_path.resolve())
    _pdf_str  = str(pdf_path.resolve())

    script = "\n".join([
        "from playwright.sync_api import sync_playwright",
        f"html_uri = {_html_uri!r}",
        f"png_path = {_png_str!r}",
        f"pdf_path = {_pdf_str!r}",
        f"dpr = {dpr}",
        "with sync_playwright() as pw:",
        "    browser = pw.chromium.launch()",
        "    ctx = browser.new_context(",
        "        viewport={'width': 1800, 'height': 900},",
        "        device_scale_factor=dpr,",
        "    )",
        "    page = ctx.new_page()",
        "    page.goto(html_uri, wait_until='domcontentloaded')",
        "    table = page.locator('table')",
        "    table.screenshot(path=png_path, scale='device')",
        "    bbox = table.bounding_box()",
        "    if bbox:",
        "        mm = lambda px: f'{px * 0.2646:.1f}mm'",
        "        page.pdf(",
        "            path=pdf_path,",
        "            width=mm(bbox['width'] + 32),",
        "            height=mm(bbox['height'] + 32),",
        "            print_background=True,",
        "            margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'},",
        "        )",
        "    browser.close()",
    ])

    try:
        fd, script_path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(script)
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                err = (result.stderr or "").strip()
                print(f"  ! playwright render failed ({png_path.name}): {err}")
            else:
                print(f"  → {png_path.name} / {pdf_path.name} ({dpr}x DPR)")
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass
    except Exception as exc:
        print(f"  ! playwright render failed ({png_path.name}): {exc}")


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
# Viz 0: Show statistics table  (pure HTML/CSS — supports colspan headers + bars)
# ──────────────────────────────────────────────────────────────────────────────

_TABLE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #fff; padding: 16px; }
table { border-collapse: collapse; font-size: 11px; width: max-content; }

/* ── group header row ─────────────────────────────────────── */
thead tr:first-child th {
  padding: 5px 10px; font-weight: bold; font-size: 11px;
  border: 1px solid #bbb; text-align: center;
}
th.th-program  { background: #d0d8e4; text-align: left !important; }
th.th-episodes { background: #dce8d0; }
th.th-guests   { background: #e8dcd0; }
th.th-epswo    { background: #d4e8e8; }

/* ── leaf header row ──────────────────────────────────────── */
thead tr:last-child th {
  padding: 3px 8px; font-weight: normal; font-size: 10px;
  border: 1px solid #bbb; text-align: center;
}
thead tr:last-child th.th-episodes { background: #eaf0e4; }
thead tr:last-child th.th-guests   { background: #f0e8e0; }
thead tr:last-child th.th-epswo    { background: #e0efef; }

/* ── data cells ───────────────────────────────────────────── */
td { border: 1px solid #e0e0e0; height: 28px; vertical-align: middle; }
tbody tr:nth-child(odd)  td { background: #fff; }
tbody tr:nth-child(even) td { background: #f7f7f7; }

/* ── total row ────────────────────────────────────────────── */
tr.total-row td {
  background: #c8d4e4 !important;
  font-weight: bold;
  border-color: #b0c2d4 !important;
}

/* ── program name column ──────────────────────────────────── */
td.td-program {
  padding: 3px 8px 3px 7px;
  text-align: left; white-space: nowrap;
  border-left-width: 4px !important;
}

/* ── plain numeric column ─────────────────────────────────── */
td.td-number { padding: 3px 10px; text-align: right; white-space: nowrap; }

/* ── bar cells (padding managed by inner div) ─────────────── */
td.td-bar { padding: 0 !important; overflow: visible; }
.bar-wrap {
  display: flex; align-items: center;
  height: 28px; min-width: 85px;
}
.bar-label {
  position: relative; z-index: 1;
  font-size: 10px; white-space: nowrap; padding: 0 5px;
}
"""


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
    global_unique_guests: int | None = None,
    lang: str = "en",
    short_labels: dict | None = None,
) -> None:
    """Viz 0: Compact show statistics table — pure HTML/CSS, academic-paper ready.

    Two-level colspan header: Broadcasting Program | Episodes |
    Guests (Appearances / Unique) | Episodes without (Male / Female).
    Bar cells show a CSS linear-gradient in the show's colour; text is placed
    inside the bar when ≥50 %, to the right when <50 %.
    Outputs a self-contained .html file; PNG attempted via playwright if installed.
    """
    _sl = short_labels if short_labels is not None else load_short_labels()
    T = lambda k, **fmt: _t(lang, k, **fmt)

    SENTINEL = {"NONE", "none", ""}
    df = per_show_stats.copy()
    df = df[~df["show_id"].astype(str).str.strip().isin(SENTINEL)]
    df = df.drop_duplicates(subset=["show_id"]).copy()

    df["_epc"] = pd.to_numeric(df.get("episode_count", 0), errors="coerce").fillna(0)
    df = df.sort_values("_epc", ascending=False).drop(columns=["_epc"]).reset_index(drop=True)

    for extra, cols in [
        (eps_without_gender_by_show, ["eps_without_male", "eps_without_female"]),
    ]:
        if extra is not None and not extra.empty:
            present = [c for c in cols if c in extra.columns]
            if present:
                extra_deduped = extra.drop_duplicates(subset=["show_id"])
                df = df.merge(extra_deduped[["show_id"] + present], on="show_id", how="left")
        for c in cols:
            if c not in df.columns:
                df[c] = float("nan")

    def _int(v) -> str:
        try:
            return f"{int(float(v)):,}" if pd.notna(v) and float(v) >= 0 else "—"
        except (TypeError, ValueError):
            return "—"

    def _num_td(v, row_bg: str = "") -> str:
        return f'<td class="td-number">{_int(v)}</td>'

    def _bar_td(count_val, total_eps, hex_color: str, row_bg: str) -> str:
        """CSS gradient bar cell: fill proportional to count/total_eps."""
        try:
            c = int(float(count_val)) if pd.notna(count_val) else None
            t = int(float(total_eps)) if pd.notna(total_eps) and float(total_eps) > 0 else None
        except (TypeError, ValueError):
            return f'<td class="td-number">—</td>'
        if c is None:
            return f'<td class="td-number">—</td>'
        pct = (c / t * 100) if t else 0.0
        text = f"{c:,} ({pct:.0f} %)"
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        # Gradient: show-colour → row background at the pct boundary
        grad = (
            f"linear-gradient(to right,"
            f"rgba({r},{g},{b},0.82) {pct:.1f}%,"
            f"{row_bg} {pct:.1f}%)"
        )
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        if pct >= 50:
            # Label sits inside the bar — use white only for very dark bars.
            txt_color = "white" if lum < 60 else "#333"
            space = 55 - int(pct) if pct < 55 else 5
            label_style = f"color:{txt_color}; padding-left:{space}px;"
        else:
            # Label sits to the right of the bar — always dark.
            space = int(pct) - 45 if pct > 45 else 5
            label_style = f"color:#333; padding-left:calc({pct:.1f}% + {space}px);"
        return (
            f'<td class="td-bar">'
            f'<div class="bar-wrap" style="background:{grad};">'
            f'<span class="bar-label" style="{label_style}">{text}</span>'
            f'</div></td>'
        )

    # ── totals ────────────────────────────────────────────────────────────────
    def _tot_sum(col) -> float:
        try:
            return float(pd.to_numeric(df[col], errors="coerce").fillna(0).sum())
        except Exception:
            return 0.0

    tot_eps_sum  = _tot_sum("episode_count")
    tot_app_sum  = _tot_sum("guest_appearances")
    tot_uniq_sum = _tot_sum("unique_guests")
    tot_m_sum    = _tot_sum("eps_without_male")
    tot_f_sum    = _tot_sum("eps_without_female")

    def _tot_bar_td(count_sum: float, eps_sum: float) -> str:
        pct = (count_sum / eps_sum * 100) if eps_sum > 0 else 0.0
        text = f"{int(count_sum):,} ({pct:.0f} %)" if eps_sum > 0 else f"{int(count_sum):,}"
        return f'<td class="td-number"><b>{text}</b></td>'

    # ── header rows ───────────────────────────────────────────────────────────
    bp  = T("broadcasting_program").replace(" ", "<br>", 1)
    eps = T("episodes")
    gst = T("guests")
    app = T("appearances")
    unq = T("unique")
    ewo = T("eps_without_gender")
    mal = T("male")
    fem = T("female")

    header_html = (
        f'<tr>'
        f'<th class="th-program"  rowspan="2">{bp}</th>'
        f'<th class="th-episodes" rowspan="2">{eps}</th>'
        f'<th class="th-guests"   colspan="2">{gst}</th>'
        f'<th class="th-epswo"    colspan="2">{ewo}</th>'
        f'</tr>'
        f'<tr>'
        f'<th class="th-guests">{app}</th>'
        f'<th class="th-guests">{unq}</th>'
        f'<th class="th-epswo">{mal}</th>'
        f'<th class="th-epswo">{fem}</th>'
        f'</tr>'
    )

    # ── total row ─────────────────────────────────────────────────────────────
    # global_unique_guests: cross-show deduplicated person count from notebook.
    # Summing per-show unique counts overcounts guests appearing on multiple shows,
    # so we show the true value when provided, or "—" to signal it's unavailable.
    if global_unique_guests is not None:
        _uniq_cell = f'<td class="td-number"><b>{int(global_unique_guests):,}</b></td>'
    else:
        _uniq_cell = '<td class="td-number" title="Cross-show unique count not available; per-show sum overcounts shared guests."><b>—</b></td>'
    total_row = (
        '<tr class="total-row">'
        + f'<td class="td-program" style="border-left-color:#888;"><b>{T("total")}</b></td>'
        + f'<td class="td-number"><b>{int(tot_eps_sum):,}</b></td>'
        + f'<td class="td-number"><b>{int(tot_app_sum):,}</b></td>'
        + _uniq_cell
        + _tot_bar_td(tot_m_sum, tot_eps_sum)
        + _tot_bar_td(tot_f_sum, tot_eps_sum)
        + '</tr>'
    )

    # ── data rows ─────────────────────────────────────────────────────────────
    rows_html = [total_row]
    for i, (_, row) in enumerate(df.iterrows()):
        sid    = str(row.get("show_id", ""))
        shex   = show_colors.get(sid, "#999999")
        name   = _short(sid, str(row.get("program_name", sid)), lang, _sl)
        te     = row.get("episode_count", 0)
        # alternating: total row is child-1 (odd), first data row is child-2 (even)
        row_bg = "#f7f7f7" if (i % 2 == 0) else "#ffffff"
        rows_html.append(
            f'<tr>'
            f'<td class="td-program" style="border-left-color:{shex};">{name}</td>'
            + _num_td(te)
            + _num_td(row.get("guest_appearances"))
            + _num_td(row.get("unique_guests"))
            + _bar_td(row.get("eps_without_male"),   te, shex, row_bg)
            + _bar_td(row.get("eps_without_female"),  te, shex, row_bg)
            + '</tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="utf-8">
<style>{_TABLE_CSS}</style>
</head>
<body>
<table>
<colgroup>
  <col>
  <col>
  <col>
  <col>
  <col>
  <col>
</colgroup>
<thead>{header_html}</thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
</body>
</html>"""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"00_show_stats_table_{lang}"
    html_path = output_dir / f"{stem}.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"  Viz 0 [{lang}]: show stats table ({len(df)} shows) → {output_dir.name}/")

    _render_html_table(
        html_path,
        output_dir / f"{stem}.png",
        output_dir / f"{stem}.pdf",
    )


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
    short_labels: dict | None = None,
    bandwidth: float = 3.5,
) -> None:
    """Viz 1: Ridge-density plot per show, sorted by median age desc.

    Each row (bottom → top = lowest → highest median):
      • Smooth Gaussian KDE density silhouette, filled with the show colour.
      • Semi-transparent grey rectangle behind the density marking the IQR (Q1–Q3).
      • Solid vertical bar at the Median crossing the full row height.

    X-axis tick labels appear on both bottom (xaxis) and top (xaxis2 overlay).
    No legend. No title. Compact rows (~52 px / show).
    """
    _sl = short_labels if short_labels is not None else load_short_labels()

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
    short_prog: dict[str, str] = {
        sid: _short(sid, name, lang, _sl) for sid, name in prog.items()
    }

    medians = df.groupby("show_id")["age"].median().sort_values(ascending=False)
    show_ids_sorted = medians.index.tolist()   # highest median first
    n = len(show_ids_sorted)

    x_min = max(15, int(df["age"].min()) - 2)
    x_max = min(104, int(df["age"].max()) + 2)
    tick_vals = list(range(x_min - x_min % 10, x_max + 11, 10))
    x_grid = np.linspace(x_min, x_max, 300)

    T = lambda k, **fmt: _t(lang, k, **fmt)

    def _kde_norm(data: np.ndarray, bw: float) -> np.ndarray:
        """Vectorised Gaussian KDE, peak-normalised to [0, 1]. No scipy needed."""
        diff = data[:, None] - x_grid[None, :]
        raw = np.exp(-0.5 * (diff / bw) ** 2).sum(axis=0)
        peak = raw.max()
        return raw / peak if peak > 0 else raw

    def _rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    RIDGE_H = 0.82   # fraction of row height used by the density silhouette

    fig = go.Figure()

    # Iterate lowest-median-first → rank 0 is at the bottom of the chart.
    for rank, sid in enumerate(reversed(show_ids_sorted)):
        sub = df[df["show_id"] == sid]["age"].values.astype(float)
        if len(sub) == 0:
            continue
        label = short_prog.get(sid, sid)
        color = show_colors.get(sid, UNKNOWN_COLOR)
        y_base = float(rank)

        density = _kde_norm(sub, bandwidth)
        q1  = float(np.percentile(sub, 25))
        q3  = float(np.percentile(sub, 75))
        med = float(np.median(sub))

        # Grey IQR rectangle, rendered below the density fill
        fig.add_shape(
            type="rect",
            x0=q1, y0=y_base, x1=q3, y1=y_base + RIDGE_H,
            fillcolor="rgba(150,150,150,0.18)",
            line=dict(width=0),
            layer="below",
        )

        # Density silhouette — closed polygon: density outline + flat baseline
        x_fill = np.concatenate([x_grid, x_grid[::-1]])
        y_fill = np.concatenate(
            [y_base + density * RIDGE_H, np.full(len(x_grid), y_base)]
        )
        fig.add_trace(go.Scatter(
            x=x_fill,
            y=y_fill,
            fill="toself",
            fillcolor=_rgba(color, 0.62),
            line=dict(color=color, width=1.1),
            mode="lines",
            name=label,
            showlegend=False,
            hovertemplate=(
                f"<b>{label}</b><br>"
                f"Median {med:.0f} · IQR {q1:.0f}–{q3:.0f}<extra></extra>"
            ),
        ))

        # Median bar — solid black vertical line crossing the full row height
        fig.add_shape(
            type="line",
            x0=med, y0=y_base, x1=med, y1=y_base + RIDGE_H,
            line=dict(color="#000000", width=2.0),
            layer="above",
        )

    # Minimal dummy trace to activate xaxis2 (top tick labels)
    fig.add_trace(go.Scatter(
        x=[x_min, x_max], y=[0, 0],
        mode="markers", marker=dict(size=0.001, opacity=0),
        showlegend=False, xaxis="x2", hoverinfo="skip",
    ))

    # Y-axis tick labels at row centres (show names)
    ytick_vals = [rank + RIDGE_H / 2 for rank in range(n)]
    ytick_text = [short_prog.get(sid, sid) for sid in reversed(show_ids_sorted)]

    fig.update_layout(
        xaxis=dict(
            title=T("01_xaxis"),
            range=[x_min, x_max],
            tickvals=tick_vals,
            tickangle=0,
            tickfont=dict(size=11),
            title_font=dict(size=12),
            showline=True,
            side="bottom",
            mirror=True,
        ),
        xaxis2=dict(
            overlaying="x",
            side="top",
            range=[x_min, x_max],
            tickvals=tick_vals,
            tickangle=0,
            tickfont=dict(size=11),
            showgrid=False,
            zeroline=False,
            showticklabels=True,
            showline=True,
        ),
        yaxis=dict(
            title="",
            tickvals=ytick_vals,
            ticktext=ytick_text,
            tickfont=dict(size=12),
            range=[-0.12, n - 1 + RIDGE_H + 0.18],
            showgrid=False,
            zeroline=False,
            automargin=True,
        ),
        template="plotly_white",
        height=40 + n * 52,
        width=350,
        margin=dict(l=0, r=10, t=28, b=36),
        showlegend=False,
    )
    stem = f"01_age_ridge_plot_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 1 [{lang}]: age ridge ({n} shows) → {output_dir.name}/")


def build_age_box_plot(
    age_with_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    lang: str = "en",
    short_labels: dict | None = None,
) -> None:
    """Viz 1 (box variant): Horizontal box-and-whisker per show.

    Whiskers = true Min/Max · Box = IQR · Centre line = Median · Dashed = Mean.
    Saved alongside the ridge plot as ``01_age_box_plot_{lang}``.
    """
    _sl = short_labels if short_labels is not None else load_short_labels()

    df = age_with_show.dropna(subset=["age", "show_id"]).copy()
    df["age"] = pd.to_numeric(df["age"], errors="coerce")
    df = df[(df["age"] >= 15) & (df["age"] < 105)].dropna(subset=["age"])
    if df.empty:
        print("  Viz 1b: no age data — skipping")
        return

    prog = (
        df[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
        if "program_name" in df.columns else {}
    )
    short_prog = {sid: _short(sid, name, lang, _sl) for sid, name in prog.items()}

    medians = df.groupby("show_id")["age"].median().sort_values(ascending=False)
    show_ids_sorted = medians.index.tolist()

    x_min = max(15, int(df["age"].min()) - 2)
    x_max = min(104, int(df["age"].max()) + 2)
    tick_vals = list(range(x_min - x_min % 5, x_max + 6, 5))
    T = lambda k, **fmt: _t(lang, k, **fmt)

    def _rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    fig = go.Figure()
    for sid in reversed(show_ids_sorted):
        sub = df[df["show_id"] == sid]["age"]
        if sub.empty:
            continue
        label = short_prog.get(sid, sid)
        color = show_colors.get(sid, UNKNOWN_COLOR)
        fig.add_trace(go.Box(
            q1=[float(sub.quantile(0.25))],
            median=[float(sub.median())],
            q3=[float(sub.quantile(0.75))],
            mean=[float(sub.mean())],
            lowerfence=[float(sub.min())],
            upperfence=[float(sub.max())],
            y=[label], name=label,
            orientation="h", boxmean=True, boxpoints=False,
            fillcolor=_rgba(show_colors.get(sid, UNKNOWN_COLOR), 0.35),
            line=dict(color=color, width=1.5),
            marker_color=color, whiskerwidth=0.5,
        ))

    fig.add_trace(go.Scatter(
        x=[x_min, x_max], y=[show_ids_sorted[-1], show_ids_sorted[-1]],
        mode="markers", marker=dict(size=0.001, opacity=0),
        showlegend=False, xaxis="x2", hoverinfo="skip",
    ))

    fig.update_layout(
        xaxis=dict(title=T("01_xaxis"), range=[x_min, x_max], tickvals=tick_vals,
                   tickfont=dict(size=11), showline=True, side="bottom", mirror=True),
        xaxis2=dict(overlaying="x", side="top", range=[x_min, x_max], tickvals=tick_vals,
                    tickfont=dict(size=11), showgrid=False, zeroline=False,
                    showticklabels=True, showline=True),
        yaxis=dict(title="", tickfont=dict(size=12), automargin=True),
        template="plotly_white",
        height=90 + len(show_ids_sorted) * 50,
        width=860,
        margin=dict(l=20, r=30, t=50, b=55),
        showlegend=False, boxgap=0.35,
    )
    stem = f"01_age_box_plot_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 1b [{lang}]: age box plot ({len(show_ids_sorted)} shows) → {output_dir.name}/")


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
    start_year: int = 2004,
    lang: str = "en",
    short_labels: dict | None = None,
    episode_coverage: pd.DataFrame | None = None,
    episode_counts_by_show: dict[str, int] | None = None,
) -> None:
    """Viz 2: Male guest share over time — one line per show, academic-paper ready.

    No title. Legend placed above the plot (horizontal). X-axis ticks are horizontal.
    An overall-trend line (aggregate across all shows) is added as a thick dark line.
    The redundant gender-type legend entry ("── männlich") is suppressed.

    episode_coverage: optional DataFrame with columns [year, show_id, pct_covered].
    When provided, a compact sub-panel (1/5 the main height) is added below the main
    chart sharing the same x-axis, showing per-show Wikidata episode coverage.  This
    helps readers interpret data gaps in the main chart.  The legend is NOT duplicated
    in the sub-panel.
    """
    UNKNOWN_LABEL = "Unknown / no data"
    _sl = short_labels if short_labels is not None else load_short_labels()

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
        genders_to_plot = [g for g in gender_order if g in meaningful and g != UNKNOWN_LABEL][:1]
    if not genders_to_plot:
        print("  Viz 2: no meaningful gender categories — skipping")
        return

    # Reindex over the full declared range so that years with zero Phase-32
    # coverage (e.g. 2011) appear as explicit NaN breaks rather than being
    # silently skipped. If only df["year"].unique() were used, absent years
    # would be omitted from all_years and Plotly would draw through the gap
    # at the wrong x position.
    all_years = list(range(min_year, max_year + 1))
    x_start = max(min_year, start_year)
    show_ids = _sort_by_order(df["show_id"].unique().tolist(), show_order)
    # Sort show_ids by episode count desc for legend ordering
    if episode_counts_by_show:
        show_ids_legend_order = sorted(
            show_ids, key=lambda s: episode_counts_by_show.get(s, 0), reverse=True
        )
    else:
        show_ids_legend_order = list(show_ids)
    _show_legend_rank = {sid: i for i, sid in enumerate(show_ids_legend_order)}

    T = lambda k, **fmt: _t(lang, k, **fmt)

    _cov = (
        episode_coverage is not None
        and isinstance(episode_coverage, pd.DataFrame)
        and not episode_coverage.empty
    )

    if _cov:
        # 5:1 height ratio — sub-panel is exactly 1/5th the main panel height.
        # shared_xaxes=False so tick labels are rendered at the bottom of the
        # top subplot (between the two panels), not at the bottom of the page.
        MAIN_H, SUB_H = 468, 104
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=False,
            vertical_spacing=0.12,
            row_heights=[MAIN_H, SUB_H],
        )
        _r1 = {"row": 1, "col": 1}
        _r2 = {"row": 2, "col": 1}
    else:
        MAIN_H, SUB_H = 468, 0
        fig = go.Figure()
        _r1 = {}
        _r2 = {}

    def _add(trace, *, row=1):
        if _cov:
            fig.add_trace(trace, **(_r1 if row == 1 else _r2))
        else:
            fig.add_trace(trace)

    _n_shows = len(show_ids)
    # 50 % parity reference as a Scatter trace so it appears in the legend (last).
    _parity_trace = go.Scatter(
        x=all_years,
        y=[50] * len(all_years),
        mode="lines",
        name=_t(lang, "02_50pct"),
        showlegend=True,
        legendgroup="__parity__",
        legendrank=_n_shows + 20,
        line=dict(color="#c0392b", width=1.2, dash="dot"),
        hoverinfo="skip",
    )
    _add(_parity_trace, row=1)

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
                show_name = _short(sid, prog.get(sid, sid), lang, _sl)
                _add(go.Scatter(
                    x=roll["year"],
                    y=roll["share"] * 100,
                    mode="lines",
                    name=show_name if i_g == 0 else None,
                    showlegend=(i_g == 0),
                    legendgroup=sid,
                    legendrank=_show_legend_rank.get(sid, 999),
                    line=dict(
                        color=show_colors.get(sid, UNKNOWN_COLOR),
                        width=1.8,
                        dash="solid",
                    ),
                    hovertemplate=(
                        f"{show_name} · %{{x}}<br>Share: %{{y:.1f}}%<extra></extra>"
                    ),
                ), row=1)

    # Overall trend line across all shows
    for gender in genders_to_plot:
        all_male_n  = pivot[pivot["gender"] == gender].groupby("year")["n_appearances"].sum()
        all_total_n = pivot.groupby("year")["n_appearances"].sum()
        year_share  = (all_male_n / all_total_n.replace(0, float("nan")) * 100).reset_index()
        year_share.columns = ["year", "share"]
        if len(year_share) >= rolling_window:
            trend = (
                year_share.set_index("year")["share"]
                .reindex(all_years)
                .rolling(rolling_window, center=True, min_periods=1)
                .mean()
                .reset_index()
            )
            _add(go.Scatter(
                x=trend["year"],
                y=trend["share"],
                mode="lines",
                name=T("02_trend"),
                showlegend=True,
                legendgroup="__trend__",
                legendrank=_n_shows + 10,
                line=dict(color="#222222", width=2.8, dash="dot"),
                hovertemplate=f"{T('02_trend')} · %{{x}}<br>%{{y:.1f}}%<extra></extra>",
            ), row=1)

    # Coverage sub-panel
    if _cov:
        cov_df = episode_coverage.copy()
        cov_df["year"] = pd.to_numeric(cov_df["year"], errors="coerce")
        cov_df = cov_df.dropna(subset=["year", "show_id", "pct_covered"])
        cov_df["year"] = cov_df["year"].astype(int)
        for sid in show_ids:
            sub_cov = cov_df[cov_df["show_id"] == sid].set_index("year")["pct_covered"]
            if sub_cov.empty:
                continue
            sub_cov = sub_cov.reindex(all_years)
            show_name = _short(sid, prog.get(sid, sid), lang, _sl)
            _add(go.Scatter(
                x=list(all_years),
                y=sub_cov.tolist(),
                mode="lines",
                name=show_name,
                showlegend=False,
                legendgroup=sid,
                line=dict(color=show_colors.get(sid, UNKNOWN_COLOR), width=1.0),
                hovertemplate=f"{show_name} · %{{x}}<br>Coverage: %{{y:.0f}}%<extra></extra>",
            ), row=2)

    # Layout
    total_height = MAIN_H + SUB_H + (20 if _cov else 0)
    _x_range = [x_start - 0.5, max_year + 0.5]
    xaxis_upper = dict(title="", tickangle=0, dtick=2, tickfont=dict(size=12),
                       range=_x_range, showgrid=True)
    xaxis_lower = dict(showticklabels=False, dtick=2, range=_x_range, showgrid=True)
    fig.update_layout(
        template="plotly_white",
        height=total_height,
        width=840,
        margin=dict(l=70, r=40, t=90, b=50),
        legend=dict(
            orientation="h",
            x=0.5, xanchor="center",
            y=1.02, yanchor="bottom",
            font=dict(size=11),
        ),
    )
    if _cov:
        fig.update_xaxes(xaxis_upper, row=1, col=1)
        fig.update_xaxes(xaxis_lower, row=2, col=1)
        fig.update_yaxes(
            title_text=T("02_yaxis"), range=[0, 100], 
            tickfont=dict(size=12), row=1, col=1,
        )
        fig.update_yaxes(
            title_text=T("02_coverage_yaxis") + " (%)",
            range=[0, 100], tickvals=[0, 50, 100], ticksuffix="%",
            tickfont=dict(size=12), title_font=dict(size=12),
            row=2, col=1,
        )
    else:
        fig.update_layout(
            xaxis=xaxis_upper,
            yaxis=dict(title=T("02_yaxis"), range=[0, 100], ticksuffix="%", tickfont=dict(size=12)),
        )

    stem = f"02_gender_over_time_{lang}"
    _save(fig, output_dir, stem)
    print(f"  Viz 2 [{lang}]: male share over time ({len(show_ids)} shows) → {output_dir.name}/")


# ──────────────────────────────────────────────────────────────────────────────
# Viz 3a: Party affiliation share by show  (pure HTML/CSS, two output modes)
# ──────────────────────────────────────────────────────────────────────────────

_PARTY_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #fff; padding: 16px; }
table { border-collapse: collapse; font-size: 11px; width: max-content; }
thead tr.hdr-party th {
  background: #e0e0e0; font-weight: bold; padding: 5px 4px;
  border: 1px solid #ccc; text-align: center; white-space: nowrap;
}
thead tr.hdr-party th.th-show { text-align: left; background: #d0d8e4; padding: 5px 8px; }
thead tr.hdr-totals td {
  background: #d8e4f0; font-weight: bold; font-size: 10px;
  padding: 3px 4px; border: 1px solid #c0d0e0; text-align: center; white-space: nowrap;
}
thead tr.hdr-totals td.td-show { text-align: left; font-style: italic; }
tbody td { border: 1px solid #e8e8e8; height: 26px; vertical-align: middle; }
tbody tr:nth-child(odd)  td.td-show { background: #fff; }
tbody tr:nth-child(even) td.td-show { background: #f7f7f7; }
td.td-show {
  padding: 3px 8px 3px 7px; text-align: left; white-space: nowrap;
  border-left-width: 4px !important;
}
td.td-pct { padding: 3px 4px; text-align: center; font-size: 10px; white-space: nowrap; }
td.td-bar { padding: 0 !important; }
.bar-wrap  { display: flex; align-items: center; height: 26px; min-width: 0; }
.bar-label { position: relative; z-index: 1; font-size: 10px; white-space: nowrap; padding: 0 3px; }
"""

_PARTY_BLUE = (0x43, 0x93, 0xC3)   # #4393c3


def _party_grad_td(pct_val: float, norm_val: float) -> str:
    """Blue-gradient cell: intensity = column-normalised share."""
    t = min(norm_val ** 0.6, 1.0)
    r2, g2, b2 = _PARTY_BLUE
    bg = f"#{int(0xf5 + (r2 - 0xf5) * t):02X}{int(0xf5 + (g2 - 0xf5) * t):02X}{int(0xf5 + (b2 - 0xf5) * t):02X}"
    fc = "white" if norm_val > 0.45 else "#333"
    text = f"{pct_val:.1f}&thinsp;%" if pct_val >= 0.1 else ""
    return f'<td class="td-pct" style="background:{bg};color:{fc};">{text}</td>'


def _party_bar_td(pct_val: float, row_bg: str) -> str:
    """CSS gradient bar cell: bar width = raw percentage (comparable across parties)."""
    r, g, b = _PARTY_BLUE
    if pct_val < 0.1:
        return (
            f'<td class="td-bar">'
            f'<div class="bar-wrap" style="background:{row_bg};"></div></td>'
        )
    grad = (
        f"linear-gradient(to right,"
        f"rgba({r},{g},{b},0.82) {pct_val:.1f}%,"
        f"{row_bg} {pct_val:.1f}%)"
    )
    text = f"{pct_val:.1f}&thinsp;%"
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if pct_val >= 50:
        txt_color = "white" if lum < 60 else "#333"
        ls = f"color:{txt_color}; padding-left:4px;"
    else:
        ls = f"color:#333; padding-left:calc({pct_val:.1f}% + 4px);"
    return (
        f'<td class="td-bar">'
        f'<div class="bar-wrap" style="background:{grad};">'
        f'<span class="bar-label" style="{ls}">{text}</span>'
        f'</div></td>'
    )


def _build_party_html(
    show_ids: list[str],
    ordered_parties: list[str],
    abbrev_parties: list[str],
    show_names: list[str],
    show_colors: dict[str, str],
    pct_matrix: pd.DataFrame,
    norm_matrix: pd.DataFrame,
    party_totals_all: pd.Series,
    party_app_totals: pd.Series,
    show_col_label: str,
    lang: str,
    mode: str,
) -> str:
    """Assemble the full HTML string for mode='gradient' or mode='bars'.

    Two totals rows below the party-name header:
      • row 1 "Appearances" — total episode-appearances per party
      • row 2 "Unique"      — unique persons per party (may equal row 1 if the
        source dataframe only carries unique_guests)
    """
    col_w_show = "min-width:140px;"

    hdr_th = "".join(
        f'<th>{a}</th>' for a in abbrev_parties
    )
    hdr_total_tds = "".join(
        f'<td class="td-pct"><b>{int(party_totals_all.get(p, 0)):,}</b></td>'
        for p in ordered_parties
    )
    hdr_app_tds = "".join(
        f'<td class="td-pct"><b>{int(party_app_totals.get(p, 0)):,}</b></td>'
        for p in ordered_parties
    )
    header_html = (
        f'<tr class="hdr-party">'
        f'<th class="th-show" style="{col_w_show}">{show_col_label}</th>'
        + hdr_th
        + '</tr>'
        f'<tr class="hdr-totals">'
        f'<td class="td-show">{_t(lang, "appearances")}</td>'
        + hdr_app_tds
        + '</tr>'
        f'<tr class="hdr-totals">'
        f'<td class="td-show">{_t(lang, "unique")}</td>'
        + hdr_total_tds
        + '</tr>'
    )

    rows = []
    for i, sid in enumerate(show_ids):
        shex   = show_colors.get(sid, "#999")
        sname  = show_names[i]
        row_bg = "#fff" if (i % 2 == 0) else "#f7f7f7"
        if mode == "gradient":
            cells = "".join(
                _party_grad_td(
                    float(pct_matrix.loc[sid, p]) if sid in pct_matrix.index else 0.0,
                    float(norm_matrix.loc[sid, p]) if sid in norm_matrix.index else 0.0,
                )
                for p in ordered_parties
            )
        else:
            cells = "".join(
                _party_bar_td(
                    float(pct_matrix.loc[sid, p]) if sid in pct_matrix.index else 0.0,
                    row_bg,
                )
                for p in ordered_parties
            )
        rows.append(
            f'<tr>'
            f'<td class="td-show" style="border-left-color:{shex};">{sname}</td>'
            + cells
            + '</tr>'
        )

    colgroup = f'<col style="{col_w_show}">' + "".join("<col>" for _ in ordered_parties)
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><style>{_PARTY_CSS}</style></head>
<body>
<table>
<colgroup>{colgroup}</colgroup>
<thead>{header_html}</thead>
<tbody>{"".join(rows)}</tbody>
</table>
</body>
</html>"""


def build_party_by_show(
    party_by_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    party_qids: dict[str, str] | None = None,
    party_order: list[str] | None = None,
    min_pct: float = 1.0,
    min_guests: int = 0,
    top_n: int = 10,
    lang: str = "en",
    short_labels: dict | None = None,
    party_abbrev: dict[str, str] | None = None,
) -> None:
    """Viz 3a: Party share heatmap — pure HTML/CSS, two output files.

    Writes:
      03a_party_by_show_{lang}.html      — blue-gradient heatmap (main)
      03a_party_by_show_{lang}_bars.html — proportional bar cells (alt)
    Each is also rendered to PNG + PDF via playwright.

    party_qids: {full_party_label: wikidata_qid} extracted from P102 value_qid column.
    Used to look up P1813 short names from short_labels.csv.

    Parties are ordered highest-total-appearances → left.
    """
    _sl = short_labels if short_labels is not None else load_short_labels()
    T = lambda k, **fmt: _t(lang, k, **fmt)

    party_qid_map: dict[str, str] = dict(party_qids) if party_qids else {}

    df = party_by_show.copy()
    df = df[df["party_label"].astype(str).str.strip().ne("Unknown / no data")]
    df = df[df["party_label"].astype(str).str.strip().ne("")]
    if df.empty:
        print("  Viz 3a: no party-by-show data — skipping")
        return

    # Restrict to top_n parties
    _party_totals_all = df.groupby("party_label")["unique_guests"].sum()
    _top_parties = set(_party_totals_all.nlargest(top_n).index)
    df = df[df["party_label"].isin(_top_parties)]
    if df.empty:
        print(f"  Viz 3a: no parties in top {top_n} — skipping")
        return

    # Sort: highest total appearances → leftmost column
    present_parties = set(df["party_label"].unique())
    party_totals_all = df.groupby("party_label")["unique_guests"].sum()
    ordered_parties = (
        party_totals_all.sort_values(ascending=False).index.tolist()
    )
    ordered_parties = [p for p in ordered_parties if p in present_parties]

    show_ids = _sort_by_order(df["show_id"].unique().tolist(), show_order)
    prog = (
        df[["show_id", "program_name"]].drop_duplicates()
        .set_index("show_id")["program_name"].to_dict()
    )

    # Deduplicate list inputs — duplicate labels in a reindexed pivot cause
    # .loc[row, col] to return a Series instead of a scalar.
    show_ids       = list(dict.fromkeys(show_ids))
    ordered_parties = list(dict.fromkeys(ordered_parties))

    pivot = (
        df.groupby(["show_id", "party_label"])["unique_guests"].sum()
        .unstack(fill_value=0)
        .reindex(index=show_ids, columns=ordered_parties, fill_value=0)
    )
    pct_matrix  = pivot.div(pivot.sum(axis=1).replace(0, float("nan")), axis=0) * 100
    norm_matrix = pct_matrix.div(pct_matrix.max(axis=0).replace(0, 1.0), axis=1).fillna(0)

    show_names = [_short(s, prog.get(s, s), lang, _sl) for s in show_ids]

    def _abbrev(label: str) -> str:
        if party_abbrev and label in party_abbrev:
            return party_abbrev[label]
        qid = party_qid_map.get(label, "")
        if qid:
            short = _sl.get((qid, lang), "")
            if short:
                return short
        return _short(label, label, lang, _sl)

    abbrev_parties = [_abbrev(p) for p in ordered_parties]

    # Appearances = total episode-appearances; fall back to unique_guests if absent
    app_col = "appearances" if "appearances" in df.columns else "unique_guests"
    party_app_totals = df.groupby("party_label")[app_col].sum()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    shared = dict(
        show_ids=show_ids,
        ordered_parties=ordered_parties,
        abbrev_parties=abbrev_parties,
        show_names=show_names,
        show_colors=show_colors,
        pct_matrix=pct_matrix,
        norm_matrix=norm_matrix,
        party_totals_all=party_totals_all,
        party_app_totals=party_app_totals,
        show_col_label="Show",
        lang=lang,
    )

    for mode, suffix in [("gradient", ""), ("bars", "_bars")]:
        stem      = f"03a_party_by_show_{lang}{suffix}"
        html_path = output_dir / f"{stem}.html"
        html_path.write_text(_build_party_html(**shared, mode=mode), encoding="utf-8")
        _render_html_table(
            html_path,
            output_dir / f"{stem}.png",
            output_dir / f"{stem}.pdf",
        )

    n_shows, n_parties = len(show_ids), len(ordered_parties)
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
    short_labels: dict | None = None,
) -> None:
    """Viz 3b: One dot plot per property — male share, dot size = total guests.

    Each property is saved as an individual file (03b_{slug}_{lang}).
    Age group panel sorted youngest-at-top; others sorted by male share.
    """
    props = {k: v for k, v in property_gender_frames.items() if v is not None and not v.empty}
    if not props:
        print("  Viz 3b: no property-gender data — skipping")
        return

    _sl = short_labels if short_labels is not None else load_short_labels()
    T = lambda k, **fmt: _t(lang, k, **fmt)
    male_color = "#4393c3"

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

        raw_labels = df["value"].astype(str).tolist()
        # Apply short label lookup; use value_qid if available for party/occupation lookups
        if "value_qid" in df.columns:
            resolved = [
                _sl.get((str(qid).strip(), lang), "") or _short(val, val, lang, _sl)
                for val, qid in zip(raw_labels, df["value_qid"].tolist())
            ]
        else:
            resolved = [_short(val, val, lang, _sl) for val in raw_labels]
        # Wrap long labels with \n (Plotly multi-line tick support)
        labels = [_wrap_label_plotly(lbl, max_chars=30) for lbl in resolved]
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
        fig.update_yaxes(tickfont=dict(size=10), automargin=True)

        actual_n = len(df)
        fig.update_layout(
            template="plotly_white",
            height=120 + actual_n * 30,
            width=250,
            margin=dict(l=8, r=20, t=20, b=50),
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
# Viz 5: Property coverage table — HTML/CSS, rows=shows, columns=properties
# ──────────────────────────────────────────────────────────────────────────────

_COVERAGE_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; background: #fff; padding: 16px; }
table { border-collapse: collapse; font-size: 11px; width: max-content; }
thead th {
  background: #e0e0e0; font-weight: bold; padding: 5px 4px;
  border: 1px solid #ccc; text-align: center; white-space: nowrap;
}
thead th.th-show { text-align: left; background: #d0d8e4; padding: 5px 8px; white-space: nowrap; }
thead th.th-prop {
  writing-mode: vertical-rl; transform: rotate(180deg);
  text-align: left; vertical-align: bottom; white-space: nowrap;
  padding: 8px 4px 4px 4px; height: 90px;
  background: #e0e0e0;
}
tbody td { border: 1px solid #e8e8e8; height: 26px; vertical-align: middle; }
tbody tr:nth-child(odd)  td.td-show { background: #fff; }
tbody tr:nth-child(even) td.td-show { background: #f7f7f7; }
tfoot td { border: 1px solid #ccc; height: 26px; vertical-align: middle;
           background: #d8e4f0; font-weight: bold; font-size: 10px; }
tfoot td.td-show { text-align: left; font-style: italic; padding: 3px 8px 3px 7px;
                   border-left-width: 4px !important; }
td.td-show {
  padding: 3px 8px 3px 7px; text-align: left; white-space: nowrap;
  border-left-width: 4px !important;
}
td.td-pct { padding: 3px 4px; text-align: center; font-size: 10px; white-space: nowrap; min-width: 40px; }
td.td-bar { padding: 0 !important; min-width: 40px; }
.bar-wrap  { display: flex; align-items: center; height: 26px; min-width: 40px; }
.bar-label { position: relative; z-index: 1; font-size: 10px; white-space: nowrap; padding: 0 3px; }
"""


def _cov_grad_td(pct: float) -> str:
    """Blue-gradient cell: intensity proportional to raw percentage."""
    if np.isnan(pct):
        return '<td class="td-pct" style="background:#f5f5f5;color:#aaa;">—</td>'
    t = min((pct / 100) ** 0.6, 1.0)
    r2, g2, b2 = _PARTY_BLUE
    bg = f"#{int(0xf5 + (r2 - 0xf5) * t):02X}{int(0xf5 + (g2 - 0xf5) * t):02X}{int(0xf5 + (b2 - 0xf5) * t):02X}"
    fc = "white" if t > 0.45 else "#333"
    text = f"{pct:.0f}&thinsp;%" if pct >= 0.5 else "0&thinsp;%"
    return f'<td class="td-pct" style="background:{bg};color:{fc};">{text}</td>'


def _cov_bar_td(pct: float, row_bg: str) -> str:
    """CSS gradient bar cell proportional to raw percentage."""
    if np.isnan(pct):
        return '<td class="td-bar"><div class="bar-wrap" style="background:#f5f5f5;"></div></td>'
    r, g, b = _PARTY_BLUE
    if pct < 0.5:
        return (
            f'<td class="td-bar">'
            f'<div class="bar-wrap" style="background:{row_bg};">'
            f'<span class="bar-label" style="color:#aaa;">0&thinsp;%</span>'
            f'</div></td>'
        )
    grad = (
        f"linear-gradient(to right,"
        f"rgba({r},{g},{b},0.82) {pct:.1f}%,"
        f"{row_bg} {pct:.1f}%)"
    )
    text = f"{pct:.0f}&thinsp;%"
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    if pct >= 50:
        txt_color = "white" if lum < 60 else "#333"
        ls = f"color:{txt_color}; padding-left:4px;"
    else:
        ls = f"color:#333; padding-left:calc({pct:.1f}% + 4px);"
    return (
        f'<td class="td-bar">'
        f'<div class="bar-wrap" style="background:{grad};">'
        f'<span class="bar-label" style="{ls}">{text}</span>'
        f'</div></td>'
    )


def _build_coverage_html(
    show_ids: list[str],
    prop_keys: list[str],
    prop_labels: list[str],
    show_names: list[str],
    show_colors: dict[str, str],
    cov_matrix: dict,
    col_avgs: dict,
    show_col_label: str,
    avg_label: str,
    lang: str,
    mode: str,
) -> str:
    """Build HTML for the coverage table. mode='gradient'|'bars'."""
    _td = _cov_grad_td if mode == "gradient" else None

    # Header — property columns use rotated text via writing-mode; wrap at ~10 chars
    header_cells = f'<th class="th-show">{show_col_label}</th>'
    for lbl in prop_labels:
        header_cells += f'<th class="th-prop">{_wrap_label_html(lbl, max_chars=10)}</th>'
    header_html = f'<tr>{header_cells}</tr>'

    # Data rows
    rows_html = []
    for i, (sid, sname) in enumerate(zip(show_ids, show_names)):
        shex = show_colors.get(sid, "#999999")
        row_bg = "#f7f7f7" if (i % 2 == 0) else "#ffffff"
        cells = f'<td class="td-show" style="border-left-color:{shex};">{sname}</td>'
        for pk in prop_keys:
            pct = cov_matrix.get((sid, pk), float("nan"))
            if mode == "gradient":
                cells += _cov_grad_td(pct)
            else:
                cells += _cov_bar_td(pct, row_bg)
        rows_html.append(f'<tr>{cells}</tr>')

    # Footer: column averages
    foot_cells = f'<td class="td-show" style="border-left-color:#888;">{avg_label}</td>'
    for pk in prop_keys:
        avg = col_avgs.get(pk, float("nan"))
        if mode == "gradient":
            foot_cells += _cov_grad_td(avg)
        else:
            foot_cells += _cov_bar_td(avg, "#d8e4f0")
    foot_html = f'<tr>{foot_cells}</tr>'

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><style>{_COVERAGE_CSS}</style></head>
<body>
<table>
<thead>{header_html}</thead>
<tbody>{"".join(rows_html)}</tbody>
<tfoot>{foot_html}</tfoot>
</table>
</body>
</html>"""


_COVERAGE_CSS_T = _COVERAGE_CSS + """
thead th.th-show-col {
  writing-mode: vertical-rl; transform: rotate(180deg);
  text-align: left; vertical-align: bottom; white-space: nowrap;
  padding: 8px 4px 4px 4px; height: 90px;
  border: 1px solid #ccc;
}
thead th.th-show { background: white; border: 1px solid #ccc; }
td.td-show { border-left-width: 1px !important; border-left-color: #ccc !important; }
tbody td { height: 22px; }
"""


def _build_coverage_html_T(
    show_ids: list[str],
    prop_keys: list[str],
    prop_labels: list[str],
    show_names: list[str],
    show_colors: dict[str, str],
    cov_matrix: dict,
    col_avgs: dict,
    show_col_label: str,
    avg_label: str,
    lang: str,
    mode: str,
) -> str:
    """Transposed version: rows=properties, cols=shows.

    Column order: Property label | Total (global avg) | Show1 | Show2 | ...
    Show column headers carry the show's colour as a bottom border (appears at top
    of the rotated cell, adjacent to the data rows).
    """
    # Header: Property | Total | Show1…N (rotated, full-cell show colour)
    _TOTAL_BG = "#c8d4e4"  # same as total-row in show_stats_table
    header_cells = f'<th class="th-show"></th>'
    header_cells += f'<th class="th-show-col" style="background:{_TOTAL_BG};">{avg_label}</th>'
    for sid, sname in zip(show_ids, show_names):
        shex = show_colors.get(sid, "#999999")
        h = shex.lstrip("#")
        sr, sg, sb = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        bg = f"rgba({sr},{sg},{sb},0.22)"
        header_cells += (
            f'<th class="th-show-col" style="background:{bg};">'
            f'{_wrap_label_html(sname, max_chars=12)}</th>'
        )
    header_html = f'<tr>{header_cells}</tr>'

    # Data rows: one per property — Total column first, then shows
    rows_html = []
    for i, (pk, plbl) in enumerate(zip(prop_keys, prop_labels)):
        row_bg = "#f7f7f7" if (i % 2 == 0) else "#ffffff"
        cells = f'<td class="td-show">{plbl}</td>'
        avg = col_avgs.get(pk, float("nan"))
        if mode == "gradient":
            cells += _cov_grad_td(avg)
        else:
            cells += _cov_bar_td(avg, row_bg)
        for sid in show_ids:
            pct = cov_matrix.get((sid, pk), float("nan"))
            if mode == "gradient":
                cells += _cov_grad_td(pct)
            else:
                cells += _cov_bar_td(pct, row_bg)
        rows_html.append(f'<tr>{cells}</tr>')

    # No tfoot — per-show averages are meaningless and removed per spec.
    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head><meta charset="utf-8"><style>{_COVERAGE_CSS_T}</style></head>
<body>
<table>
<thead>{header_html}</thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
</body>
</html>"""


def build_property_coverage_table(
    coverage_by_show: pd.DataFrame,
    show_colors: dict[str, str],
    show_order: list[str],
    output_dir: Path,
    *,
    exclude_labels: list[str] | None = None,
    show_labels: dict[str, str] | None = None,
    wikidata_coverage_by_show: dict[str, float] | None = None,
    episode_counts_by_show: dict[str, int] | None = None,
    unique_guests_by_show: dict[str, int] | None = None,
    global_coverage_by_property: dict[str, float] | None = None,
    lang: str = "en",
    short_labels: dict | None = None,
) -> None:
    """Viz 5: Property coverage table — HTML/CSS, rows=shows, columns=properties.

    Rows are shows sorted by episode count descending.
    First column after show name: 'Wikidata guest coverage' (if provided).
    Two versions exported: gradient and bars.
    """
    _sl = short_labels if short_labels is not None else load_short_labels()
    T = lambda k, **fmt: _t(lang, k, **fmt)

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

    # Determine show order: episode count desc, then show_order fallback
    available_shows = [s for s in show_cols_raw]
    if episode_counts_by_show:
        available_shows = sorted(
            available_shows,
            key=lambda s: episode_counts_by_show.get(s, 0),
            reverse=True,
        )
    else:
        available_shows = _sort_by_order(available_shows, show_order)

    # Build prop_keys / prop_labels: Wikidata coverage first, then properties by mean desc
    df["_mean_cov"] = df[show_cols_raw].mean(axis=1)
    df = df.sort_values("_mean_cov", ascending=False).drop(columns=["_mean_cov"]).reset_index(drop=True)

    prop_keys: list[str] = []
    prop_labels: list[str] = []

    if wikidata_coverage_by_show:
        prop_keys.append("__wikidata__")
        prop_labels.append(T("wikidata_entry"))

    for _, row in df.iterrows():
        prop_keys.append(str(row[id_col]))
        prop_labels.append(str(row[lbl_col]))

    # Build coverage matrix: (show_id, prop_key) → pct
    cov_matrix: dict = {}
    for sid in available_shows:
        if wikidata_coverage_by_show:
            cov_matrix[(sid, "__wikidata__")] = wikidata_coverage_by_show.get(sid, float("nan"))
        for _, row in df.iterrows():
            pk = str(row[id_col])
            val = row.get(sid, float("nan"))
            try:
                cov_matrix[(sid, pk)] = float(val) if pd.notna(val) else float("nan")
            except (TypeError, ValueError):
                cov_matrix[(sid, pk)] = float("nan")

    # Average per property: use pre-computed global coverage (cross-show deduplicated)
    # when provided by the notebook. Falls back to a weighted mean of per-show
    # coverages (weighted by unique guests) as an approximation when not available,
    # with the caveat that guests shared across shows are double-counted in weights.
    _gcov = global_coverage_by_property or {}
    _weights = unique_guests_by_show or {}

    col_avgs: dict = {}
    for pk in prop_keys:
        # Map prop_key back to label for global lookup (wikidata key uses "__wikidata__")
        if pk in _gcov:
            col_avgs[pk] = float(_gcov[pk])
        else:
            pairs = [
                (cov_matrix.get((sid, pk), float("nan")), _weights.get(sid, 1))
                for sid in available_shows
            ]
            valid = [(v, w) for v, w in pairs if not np.isnan(v) and w > 0]
            if valid:
                total_w = sum(w for _, w in valid)
                col_avgs[pk] = sum(v * w for v, w in valid) / total_w
            else:
                col_avgs[pk] = float("nan")

    # Show display names
    show_names = [
        _short(sid, (show_labels.get(sid, sid) if show_labels else sid), lang, _sl)
        for sid in available_shows
    ]
    show_col_label = T("broadcasting_program")
    avg_label = T("05_col_avg")

    shared = dict(
        show_ids=available_shows,
        prop_keys=prop_keys,
        prop_labels=prop_labels,
        show_names=show_names,
        show_colors=show_colors,
        cov_matrix=cov_matrix,
        col_avgs=col_avgs,
        show_col_label=show_col_label,
        avg_label=avg_label,
        lang=lang,
    )
    # T version: avg column is first and labelled "Total".
    shared_T = dict(
        show_ids=available_shows,
        prop_keys=prop_keys,
        prop_labels=prop_labels,
        show_names=show_names,
        show_colors=show_colors,
        cov_matrix=cov_matrix,
        col_avgs=col_avgs,
        show_col_label=show_col_label,
        avg_label=T("total"),
        lang=lang,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Rows=shows (current orientation) + rows=props (transposed)
    for mode in ("gradient", "bars"):
        suffix = "_bars" if mode == "bars" else ""
        # rows=shows, cols=props (rotated headers)
        stem = f"05_property_coverage_{lang}{suffix}"
        html_path = output_dir / f"{stem}.html"
        html_path.write_text(_build_coverage_html(**shared, mode=mode), encoding="utf-8")
        _render_html_table(html_path, output_dir / f"{stem}.png", output_dir / f"{stem}.pdf")
        # rows=props, cols=shows (transposed)
        stem_t = f"05_property_coverage_{lang}_T{suffix}"
        html_path_t = output_dir / f"{stem_t}.html"
        html_path_t.write_text(_build_coverage_html_T(**shared_T, mode=mode), encoding="utf-8")
        _render_html_table(html_path_t, output_dir / f"{stem_t}.png", output_dir / f"{stem_t}.pdf")

    print(f"  Viz 5: coverage table ({len(prop_keys)} props × {len(available_shows)} shows, both orientations) → {output_dir.name}/")


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
