from __future__ import annotations

# pyright: reportMissingImports=false

import re
from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.bootstrap import ensure_output_bootstrap
from process.candidate_generation.wikidata.materializer import materialize_final
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _parse_documented_csv_headers(contracts_text: str) -> dict[str, list[str]]:
    """Extract `filename.csv`: `col1`, `col2` style lines from contracts.md."""
    headers: dict[str, list[str]] = {}
    for line in contracts_text.splitlines():
        match = re.match(r"^\s*\d+\.\s+`([^`]+\.csv)`:\s+(.+)$", line)
        if not match:
            continue
        filename = match.group(1)
        cols = re.findall(r"`([^`]+)`", match.group(2))
        if cols:
            headers[filename] = cols
    return headers


def test_contracts_md_wikidata_headers_match_runtime_contract(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[4]
    contracts_path = repo_root / "documentation" / "contracts.md"

    ensure_output_bootstrap(tmp_path)
    materialize_final(tmp_path, run_id="docs_contract_smoke")
    paths = build_artifact_paths(tmp_path)

    expected_headers = {
        "classes.csv": list(pd.read_csv(paths.classes_csv).columns),
        "instances.csv": list(pd.read_csv(paths.instances_csv).columns),
        "properties.csv": list(pd.read_csv(paths.properties_csv).columns),
        "aliases_en.csv": list(pd.read_csv(paths.aliases_en_csv).columns),
        "aliases_de.csv": list(pd.read_csv(paths.aliases_de_csv).columns),
        "triples.csv": list(pd.read_csv(paths.triples_csv).columns),
        "query_inventory.csv": list(pd.read_csv(paths.query_inventory_csv).columns),
        "graph_stage_resolved_targets.csv": list(pd.read_csv(paths.graph_stage_resolved_targets_csv).columns),
        "graph_stage_unresolved_targets.csv": list(pd.read_csv(paths.graph_stage_unresolved_targets_csv).columns),
        "fallback_stage_candidates.csv": list(pd.read_csv(paths.fallback_stage_candidates_csv).columns),
        "fallback_stage_eligible_for_expansion.csv": list(
            pd.read_csv(paths.fallback_stage_eligible_for_expansion_csv).columns
        ),
        "fallback_stage_ineligible.csv": list(pd.read_csv(paths.fallback_stage_ineligible_csv).columns),
    }

    documented_headers = _parse_documented_csv_headers(contracts_path.read_text(encoding="utf-8"))

    for filename, actual_columns in expected_headers.items():
        assert filename in documented_headers, f"Missing documented schema in contracts.md for {filename}"
        assert documented_headers[filename] == actual_columns
