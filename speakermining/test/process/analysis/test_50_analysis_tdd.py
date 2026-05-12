from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "speakermining" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from process.analysis.readme_generator import generate_all_readmes
from process.analysis.viz_base import save_fig
from process.analysis.viz_final import build_show_color_registry


NOTEBOOK_PATH = ROOT / "speakermining" / "src" / "process" / "notebooks" / "50_analysis.ipynb"


def _load_notebook_code() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [cell for cell in notebook.get("cells", []) if cell.get("cell_type") == "code"]
    return "\n\n".join("\n".join(cell.get("source", [])) for cell in code_cells)


def test_age_distribution_uses_appearance_count_not_age_sum() -> None:
    code = _load_notebook_code()
    assert "age_df[\"appearance_count\"] = 1" in code
    assert "appearance_column=\"appearance_count\"" in code


def test_analysis_summary_json_written_once() -> None:
    code = _load_notebook_code()
    writes = [
        line for line in code.splitlines()
        if "atomic_write_text" in line and "analysis_summary.json" in line
    ]
    assert len(writes) == 1


def test_notebook_uses_explicit_guest_and_coverage_per_show_tables() -> None:
    code = _load_notebook_code()
    assert "guest_per_show_stats" in code
    assert "coverage_per_show_stats" in code
    assert "    guest_per_show_stats," in code


def test_generate_all_readmes_requires_guest_stats_columns(tmp_path: Path) -> None:
    output_dir = tmp_path / "50_analysis"
    (output_dir / "all").mkdir(parents=True, exist_ok=True)

    malformed = pd.DataFrame(
        {
            "show_id": ["show-1"],
            "program_name": ["Show One"],
            "coverage_pct": [95.0],
        }
    )

    with pytest.raises(ValueError):
        generate_all_readmes(output_dir, malformed, top_guests_by_show={})


def test_build_show_color_registry_ignores_none_sentinel() -> None:
    per_show_stats = pd.DataFrame(
        [
            {"show_id": "show-a", "guest_appearances": 200},
            {"show_id": "NONE", "guest_appearances": 150},
            {"show_id": "show-b", "guest_appearances": 100},
        ]
    )

    show_colors, show_order = build_show_color_registry(per_show_stats)

    assert "NONE" not in show_order
    assert "NONE" not in show_colors
    assert show_order == ["show-a", "show-b"]


def test_save_fig_cache_requires_complete_bundle(tmp_path: Path) -> None:
    class FakeFig:
        def __init__(self) -> None:
            self.image_calls = 0
            self.html_calls = 0

        def to_json(self) -> str:
            return "stable-figure"

        def write_image(self, path: str, scale: int | None = None) -> None:
            self.image_calls += 1
            Path(path).write_text("img", encoding="utf-8")

        def write_html(self, path: str) -> None:
            self.html_calls += 1
            Path(path).write_text("html", encoding="utf-8")

    fig = FakeFig()
    base = tmp_path / "viz" / "chart"

    save_fig(fig, base, html=True)
    assert fig.image_calls == 2
    assert fig.html_calls == 1

    (tmp_path / "viz" / "chart.pdf").unlink()
    (tmp_path / "viz" / "chart.html").unlink()

    save_fig(fig, base, html=True)

    assert fig.image_calls == 4
    assert fig.html_calls == 2