from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _evidence_dir(repo_root: Path) -> Path:
    return (
        Path(repo_root)
        / "data"
        / "20_candidate_generation"
        / "wikidata"
        / "evidence"
    )


def _flatten_summary(summary: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in (summary or {}).items():
        if isinstance(value, (dict, list)):
            out[str(key)] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            out[str(key)] = "" if value is None else str(value)
    return out


def write_notebook21_runtime_evidence(
    repo_root: Path | str,
    *,
    run_context: dict,
    stage_summaries: dict,
    phase_outcomes: list[dict] | None = None,
    benchmark_summary: dict | None = None,
) -> dict:
    """Persist a reproducible Notebook 21 evidence bundle.

    The evidence bundle is a machine-readable closeout artifact used to track
    runtime behavior for GRW-005/GRW-006/GRW-009/GRW-004 gates.
    """

    repo_root = Path(repo_root)
    evidence_dir = _evidence_dir(repo_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)

    token = _ts_token()
    summary_json_path = evidence_dir / f"notebook21_runtime_evidence_{token}.json"
    summary_csv_path = evidence_dir / f"notebook21_runtime_evidence_{token}.csv"
    latest_json_path = evidence_dir / "notebook21_runtime_evidence_latest.json"

    payload = {
        "timestamp_utc": _iso_now(),
        "notebook_id": "notebook_21_candidate_generation_wikidata",
        "run_context": dict(run_context or {}),
        "stage_summaries": dict(stage_summaries or {}),
        "phase_outcomes": list(phase_outcomes or []),
        "benchmark_summary": dict(benchmark_summary or {}),
        "artifacts": {
            "summary_json": str(summary_json_path),
            "summary_csv": str(summary_csv_path),
        },
    }

    atomic_write_text(
        summary_json_path,
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    atomic_write_text(
        latest_json_path,
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    csv_row = {
        "timestamp_utc": payload["timestamp_utc"],
        "notebook_id": payload["notebook_id"],
        **_flatten_summary(payload.get("run_context", {})),
        **{f"stage_{k}": v for k, v in _flatten_summary(payload.get("stage_summaries", {})).items()},
    }
    if payload.get("benchmark_summary"):
        csv_row.update(
            {
                f"benchmark_{k}": v
                for k, v in _flatten_summary(payload.get("benchmark_summary", {})).items()
            }
        )
    if payload.get("phase_outcomes"):
        csv_row["phase_outcomes"] = json.dumps(payload.get("phase_outcomes", []), ensure_ascii=False, sort_keys=True)

    row_df = pd.DataFrame([csv_row], columns=sorted(csv_row.keys()))
    atomic_write_csv(summary_csv_path, row_df, index=False)

    return payload