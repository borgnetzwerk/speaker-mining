"""
test_bar_rendering.py — PDF compatibility test for bar-chart table cells.

Generates a single HTML/PDF containing three rendering approaches so you can
open the PDF in different viewers and see which columns render correctly.

  Approach A  rgba() with alpha 0.82 in linear-gradient  ← current (broken in some viewers)
  Approach B  pre-blended opaque RGB                      ← our fix
  Approach C  CSS color-mix()                             ← alternative (Chromium resolves before PDF)

Run:
    python speakermining/src/process/analysis/test_bar_rendering.py

Output: data/50_analysis/all/final_visualizations/bar_render_test/
"""

import os, sys, tempfile, subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
SHOWS = [
    ("#c0392b", "Show 1 — Red"),
    ("#2980b9", "Show 2 — Blue"),
    ("#27ae60", "Show 3 — Green"),
    ("#e67e22", "Show 4 — Orange"),
    ("#8e44ad", "Show 5 — Purple"),
    ("#16a085", "Show 6 — Teal"),
]
PCTS = [2, 18, 36, 53, 78, 92]

OUTPUT_DIR = Path(__file__).resolve().parents[4] / "data" / "50_analysis" / "all" / "final_visualizations" / "bar_render_test"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; background:#fff; padding:16px; }
h2 { font-size:12px; margin:16px 0 6px; color:#333; }
p.note { font-size:10px; color:#888; margin-bottom:4px; }
table { border-collapse:collapse; font-size:11px; margin-bottom:8px; }
th { padding:4px 10px; background:#dde; border:1px solid #bbb; font-size:10px; }
td { border:1px solid #e0e0e0; height:28px; vertical-align:middle; }
td.td-name { padding:3px 8px; white-space:nowrap; width:130px; }
td.td-bar  { padding:0 !important; width:260px; overflow:visible; }
.bar-wrap  { display:flex; align-items:center; height:28px; min-width:260px; }
.bar-label { position:relative; z-index:1; font-size:10px; white-space:nowrap; padding:0 5px; }
tbody tr:nth-child(odd)  td { background:#fff; }
tbody tr:nth-child(even) td { background:#f7f7f7; }
"""


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _blend(r: int, g: int, b: int, bg_rgb: tuple, alpha: float = 0.82) -> tuple[int, int, int]:
    return (
        int(r * alpha + bg_rgb[0] * (1 - alpha)),
        int(g * alpha + bg_rgb[1] * (1 - alpha)),
        int(b * alpha + bg_rgb[2] * (1 - alpha)),
    )


def _label_style(pct: float) -> str:
    if pct >= 50:
        return "color:#333; padding-left:5px;"
    return f"color:#333; padding-left:calc({pct:.1f}% + 5px);"


# ---------------------------------------------------------------------------
# Row renderers — one per approach
# ---------------------------------------------------------------------------

def row_A(name: str, hex_color: str, pct: float, row_bg: str) -> str:
    """A: rgba() with alpha — current approach, broken in some PDF viewers."""
    r, g, b = _hex_to_rgb(hex_color)
    grad = f"linear-gradient(to right, rgba({r},{g},{b},0.82) {pct:.1f}%, {row_bg} {pct:.1f}%)"
    return (
        f'<tr><td class="td-name">{name} ({pct:.0f} %)</td>'
        f'<td class="td-bar"><div class="bar-wrap" style="background:{grad};">'
        f'<span class="bar-label" style="{_label_style(pct)}">{pct:.0f} %</span>'
        f'</div></td></tr>'
    )


def row_B(name: str, hex_color: str, pct: float, row_bg: str) -> str:
    """B: pre-blended opaque RGB — no PDF transparency group."""
    r, g, b = _hex_to_rgb(hex_color)
    bg_rgb = (247, 247, 247) if row_bg == "#f7f7f7" else (255, 255, 255)
    br, bgg, bb = _blend(r, g, b, bg_rgb)
    grad = f"linear-gradient(to right, rgb({br},{bgg},{bb}) {pct:.1f}%, {row_bg} {pct:.1f}%)"
    return (
        f'<tr><td class="td-name">{name} ({pct:.0f} %)</td>'
        f'<td class="td-bar"><div class="bar-wrap" style="background:{grad};">'
        f'<span class="bar-label" style="{_label_style(pct)}">{pct:.0f} %</span>'
        f'</div></td></tr>'
    )


def row_C(name: str, hex_color: str, pct: float, row_bg: str) -> str:
    """C: CSS color-mix() — Chromium resolves this to an opaque color before writing PDF."""
    grad = f"linear-gradient(to right, color-mix(in srgb, {hex_color} 82%, {row_bg}) {pct:.1f}%, {row_bg} {pct:.1f}%)"
    return (
        f'<tr><td class="td-name">{name} ({pct:.0f} %)</td>'
        f'<td class="td-bar"><div class="bar-wrap" style="background:{grad};">'
        f'<span class="bar-label" style="{_label_style(pct)}">{pct:.0f} %</span>'
        f'</div></td></tr>'
    )


# ---------------------------------------------------------------------------
# Build HTML
# ---------------------------------------------------------------------------

def build_html() -> str:
    def table(row_fn, label, note):
        rows = []
        for i, ((hex_color, show_name), pct) in enumerate(zip(SHOWS, PCTS)):
            row_bg = "#f7f7f7" if (i % 2 == 0) else "#ffffff"
            rows.append(row_fn(show_name, hex_color, pct, row_bg))
        return (
            f'<h2>{label}</h2>'
            f'<p class="note">{note}</p>'
            f'<table>'
            f'<thead><tr><th>Show / fill %</th><th>Bar cell</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody>'
            f'</table>'
        )

    sections = [
        table(
            row_A,
            "Approach A — rgba() with alpha 0.82 (current, known broken)",
            "Uses rgba(r,g,b,0.82) in linear-gradient → PDF transparency group → pink in some viewers.",
        ),
        table(
            row_B,
            "Approach B — pre-blended opaque RGB (our fix)",
            "Alpha composited in Python before emitting CSS; fully opaque rgb() → no PDF transparency group.",
        ),
        table(
            row_C,
            "Approach C — CSS color-mix() (alternative)",
            "color-mix(in srgb, hex 82%, rowbg) resolved by Chromium to opaque colour before PDF write.",
        ),
    ]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Bar rendering test</title>
<style>{_CSS}</style>
</head>
<body>
{"".join(sections)}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Playwright rendering (same pipeline as viz_final._render_html_table)
# ---------------------------------------------------------------------------

def render(html_path: Path, png_path: Path, pdf_path: Path, dpr: int = 3) -> None:
    script = "\n".join([
        "from playwright.sync_api import sync_playwright",
        f"html_uri = {html_path.resolve().as_uri()!r}",
        f"png_path = {str(png_path.resolve())!r}",
        f"pdf_path = {str(pdf_path.resolve())!r}",
        f"dpr = {dpr}",
        "with sync_playwright() as pw:",
        "    browser = pw.chromium.launch()",
        "    ctx = browser.new_context(",
        "        viewport={'width': 800, 'height': 2400},",
        "        device_scale_factor=dpr,",
        "    )",
        "    page = ctx.new_page()",
        "    page.goto(html_uri, wait_until='domcontentloaded')",
        "    page.screenshot(path=png_path, full_page=True, scale='device')",
        "    page.pdf(",
        "        path=pdf_path,",
        "        width='210mm',",
        "        height='297mm',",
        "        print_background=True,",
        "        margin={'top':'10mm','right':'10mm','bottom':'10mm','left':'10mm'},",
        "    )",
        "    browser.close()",
    ])
    fd, script_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(script)
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode != 0:
            print(f"  ! playwright failed: {result.stderr.strip()}")
        else:
            print(f"  -> {png_path.name}")
            print(f"  -> {pdf_path.name}")
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = build_html()
    html_path = OUTPUT_DIR / "bar_render_test.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML -> {html_path}")
    render(
        html_path,
        OUTPUT_DIR / "bar_render_test.png",
        OUTPUT_DIR / "bar_render_test.pdf",
    )
    print("Done. Open bar_render_test.pdf in different viewers to compare approaches A, B, C.")
