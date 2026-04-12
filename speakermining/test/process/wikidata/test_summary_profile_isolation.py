from __future__ import annotations

import json
from pathlib import Path

from process.candidate_generation.wikidata.materializer import _write_summary
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_non_operational_profile_does_not_overwrite_primary_summary(tmp_path: Path, monkeypatch) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.summary_json.write_text(json.dumps({"stage": "baseline", "run_profile": "operational"}), encoding="utf-8")

    monkeypatch.setenv("WIKIDATA_RUN_PROFILE", "smoke")
    monkeypatch.delenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", raising=False)

    _write_summary(paths, run_id="smoke-1", stage="final", stats={"instances_rows": 1})

    baseline = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert baseline["stage"] == "baseline"
    assert baseline["run_profile"] == "operational"

    profile_latest = paths.projections_dir / "summary_profiles" / "smoke" / "summary_latest.json"
    assert profile_latest.exists()
    profile_summary = json.loads(profile_latest.read_text(encoding="utf-8"))
    assert profile_summary["run_id"] == "smoke-1"
    assert profile_summary["run_profile"] == "smoke"
    assert bool(profile_summary["summary_primary_updated"]) is False


def test_non_operational_profile_can_overwrite_primary_summary_with_explicit_override(tmp_path: Path, monkeypatch) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.summary_json.write_text(json.dumps({"stage": "baseline", "run_profile": "operational"}), encoding="utf-8")

    monkeypatch.setenv("WIKIDATA_RUN_PROFILE", "smoke")
    monkeypatch.setenv("WIKIDATA_ALLOW_NON_OPERATIONAL_SUMMARY_OVERWRITE", "1")

    _write_summary(paths, run_id="smoke-override", stage="final", stats={"instances_rows": 2})

    baseline = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert baseline["run_id"] == "smoke-override"
    assert baseline["run_profile"] == "smoke"
    assert bool(baseline["summary_primary_updated"]) is True
