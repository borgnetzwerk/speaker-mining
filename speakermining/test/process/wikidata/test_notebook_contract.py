from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
NOTEBOOK_PATH = ROOT / "speakermining" / "src" / "process" / "notebooks" / "21_candidate_generation_wikidata.ipynb"


def _cell_sources(nb: dict) -> list[str]:
    out: list[str] = []
    for cell in nb.get("cells", []):
        source = cell.get("source", [])
        if isinstance(source, list):
            out.extend([str(line) for line in source])
    return out


def test_notebook_contains_bootstrap_and_ordered_stage_markers() -> None:
    nb = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    lines = _cell_sources(nb)
    joined = "\n".join(lines)

    assert "## 4) Bootstrap and Load Broadcasting Program Seeds" in joined
    assert "initialize_bootstrap_files(ROOT, setup_core_classes, setup_seeds)" in joined

    graph_header = joined.find("## 6) Execute Graph-First Expansion Stage")
    fallback_header = joined.find("## 8) Run Fallback String Matching Stage")
    assert graph_header >= 0
    assert fallback_header >= 0
    assert graph_header < fallback_header
