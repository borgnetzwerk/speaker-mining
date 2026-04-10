from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.runtime_evidence import write_notebook21_runtime_evidence


def test_write_notebook21_runtime_evidence_writes_json_and_csv(tmp_path: Path) -> None:
    payload = write_notebook21_runtime_evidence(
        tmp_path,
        run_context={
            "resume_mode": "append",
            "cache_max_age_days": 365,
            "fallback_enabled_mention_types_resolved": ["episode", "season"],
        },
        stage_summaries={
            "stage_a_queries_this_run": 12,
            "node_integrity_timeout_warnings": 1,
            "fallback_candidates": 4,
        },
    )

    summary_json = Path(payload["artifacts"]["summary_json"])
    summary_csv = Path(payload["artifacts"]["summary_csv"])
    latest_json = (
        tmp_path
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "evidence"
        / "notebook21_runtime_evidence_latest.json"
    )

    assert summary_json.exists()
    assert summary_csv.exists()
    assert latest_json.exists()

    loaded = json.loads(summary_json.read_text(encoding="utf-8"))
    assert loaded["run_context"]["resume_mode"] == "append"
    assert int(loaded["stage_summaries"]["stage_a_queries_this_run"]) == 12

    df = pd.read_csv(summary_csv)
    assert len(df) == 1
    assert str(df.iloc[0]["resume_mode"]) == "append"


def test_write_notebook21_runtime_evidence_includes_benchmark_fields(tmp_path: Path) -> None:
    payload = write_notebook21_runtime_evidence(
        tmp_path,
        run_context={"resume_mode": "append"},
        stage_summaries={"fallback_candidates": 0},
        benchmark_summary={
            "rounds": 2,
            "aggregate_rows": [
                {
                    "mode": "incremental",
                    "historical_replay_events_mean": 0.0,
                }
            ],
        },
    )

    summary_csv = Path(payload["artifacts"]["summary_csv"])
    df = pd.read_csv(summary_csv)
    assert len(df) == 1
    assert "benchmark_rounds" in set(df.columns)
    assert int(df.iloc[0]["benchmark_rounds"]) == 2