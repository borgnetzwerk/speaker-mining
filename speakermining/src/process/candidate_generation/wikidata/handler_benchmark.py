from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

import pandas as pd

from process.io_guardrails import atomic_write_csv, atomic_write_text
from process.candidate_generation.wikidata.materializer import compare_materialization_snapshots
from process.candidate_generation.wikidata.handlers.orchestrator import run_handlers
from process.candidate_generation.wikidata.schemas import build_artifact_paths


@dataclass(frozen=True)
class HandlerBenchmarkRun:
    mode: str
    round_index: int
    elapsed_seconds: float
    latest_event_sequence: int
    total_historical_replay_events: int
    total_processed_events: int
    total_pending_events: int
    total_materialization_elapsed_seconds: float
    total_artifact_size_bytes: int


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_latest_handler_run_summary(repo_root: Path) -> dict:
    paths = build_artifact_paths(repo_root)
    latest_path = paths.wikidata_dir / "handler_runs" / "handler_run_summary_latest.json"
    if not latest_path.exists():
        return {}
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _extract_totals(summary_payload: dict) -> tuple[int, int, int, int, float, int]:
    latest_event_sequence = int(summary_payload.get("latest_event_sequence", 0) or 0)
    rows = summary_payload.get("handler_stats", []) or []
    if not isinstance(rows, list):
        return latest_event_sequence, 0, 0, 0, 0.0, 0

    historical = 0
    processed = 0
    pending = 0
    materialization_elapsed = 0.0
    artifact_size_bytes = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        historical += int(row.get("historical_replay_events", 0) or 0)
        processed += int(row.get("processed_events", 0) or 0)
        pending += int(row.get("pending_events", 0) or 0)
        materialization_elapsed += float(row.get("materialization_elapsed_seconds", 0.0) or 0.0)
        artifact_size_bytes += int(row.get("artifact_size_bytes", 0) or 0)
    return latest_event_sequence, historical, processed, pending, materialization_elapsed, artifact_size_bytes


def _write_parity_artifacts(
    benchmark_dir: Path,
    parity_report,
) -> dict:
    ts_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = benchmark_dir / f"handler_materialization_parity_{ts_token}.json"
    csv_path = benchmark_dir / f"handler_materialization_parity_{ts_token}.csv"
    latest_json_path = benchmark_dir / "handler_materialization_parity_latest.json"

    rows = [row.__dict__ for row in parity_report.artifacts_compared]
    row_df = pd.DataFrame(rows)
    if row_df.empty:
        row_df = pd.DataFrame(
            columns=[
                "artifact_name",
                "left_exists",
                "right_exists",
                "left_rows",
                "right_rows",
                "left_digest",
                "right_digest",
                "matches",
            ]
        )
    atomic_write_csv(csv_path, row_df, index=False)

    payload = {
        "timestamp_utc": _iso_now(),
        "left_root": parity_report.left_root,
        "right_root": parity_report.right_root,
        "matches": bool(parity_report.matches),
        "artifacts_compared": rows,
        "artifacts": {
            "parity_json": str(json_path),
            "parity_csv": str(csv_path),
        },
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    atomic_write_text(json_path, content, encoding="utf-8")
    atomic_write_text(latest_json_path, content, encoding="utf-8")
    return payload


def run_handler_materialization_benchmark(
    repo_root: Path | str,
    *,
    rounds: int = 1,
    batch_size: int = 1000,
    include_full_rebuild: bool = True,
    run_context: dict | None = None,
    parity_reference_repo_root: Path | str | None = None,
) -> dict:
    """Benchmark orchestrator throughput for incremental vs full_rebuild modes.

    This helper is intended for GRW-004/Workstream-2 evidence collection.
    It produces one timestamped JSON artifact and one compact CSV summary.
    """

    repo_root = Path(repo_root)
    rounds = max(1, int(rounds))
    batch_size = max(1, int(batch_size))

    modes = ["incremental"]
    if include_full_rebuild:
        modes.append("full_rebuild")

    run_rows: list[HandlerBenchmarkRun] = []
    for mode in modes:
        for round_index in range(1, rounds + 1):
            t0 = perf_counter()
            run_handlers(repo_root, batch_size=batch_size, materialization_mode=mode)
            elapsed = perf_counter() - t0

            latest_summary = _load_latest_handler_run_summary(repo_root)
            latest_seq, historical, processed, pending, materialization_elapsed, artifact_size_bytes = _extract_totals(latest_summary)
            run_rows.append(
                HandlerBenchmarkRun(
                    mode=mode,
                    round_index=round_index,
                    elapsed_seconds=float(round(elapsed, 6)),
                    latest_event_sequence=int(latest_seq),
                    total_historical_replay_events=int(historical),
                    total_processed_events=int(processed),
                    total_pending_events=int(pending),
                    total_materialization_elapsed_seconds=float(round(materialization_elapsed, 6)),
                    total_artifact_size_bytes=int(artifact_size_bytes),
                )
            )

    run_df = pd.DataFrame([row.__dict__ for row in run_rows])
    if run_df.empty:
        aggregate_df = pd.DataFrame(
            columns=[
                "mode",
                "rounds",
                "elapsed_seconds_mean",
                "elapsed_seconds_min",
                "elapsed_seconds_max",
                "historical_replay_events_mean",
                "processed_events_mean",
                "pending_events_mean",
                "latest_event_sequence_max",
            ]
        )
    else:
        aggregate_df = (
            run_df.groupby("mode", as_index=False)
            .agg(
                rounds=("round_index", "count"),
                elapsed_seconds_mean=("elapsed_seconds", "mean"),
                elapsed_seconds_min=("elapsed_seconds", "min"),
                elapsed_seconds_max=("elapsed_seconds", "max"),
                historical_replay_events_mean=("total_historical_replay_events", "mean"),
                processed_events_mean=("total_processed_events", "mean"),
                pending_events_mean=("total_pending_events", "mean"),
                materialization_elapsed_seconds_mean=("total_materialization_elapsed_seconds", "mean"),
                artifact_size_bytes_mean=("total_artifact_size_bytes", "mean"),
                latest_event_sequence_max=("latest_event_sequence", "max"),
            )
            .sort_values("mode")
            .reset_index(drop=True)
        )

    ts_token = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = build_artifact_paths(repo_root)
    benchmark_dir = paths.wikidata_dir / "benchmarks"
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    run_csv_path = benchmark_dir / f"handler_materialization_runs_{ts_token}.csv"
    aggregate_csv_path = benchmark_dir / f"handler_materialization_summary_{ts_token}.csv"
    summary_json_path = benchmark_dir / f"handler_materialization_summary_{ts_token}.json"
    latest_json_path = benchmark_dir / "handler_materialization_summary_latest.json"

    atomic_write_csv(run_csv_path, run_df, index=False)
    atomic_write_csv(aggregate_csv_path, aggregate_df, index=False)

    benchmark_summary = {
        "timestamp_utc": _iso_now(),
        "rounds": int(rounds),
        "batch_size": int(batch_size),
        "modes": modes,
        "run_context": dict(run_context or {}),
        "run_rows": run_df.to_dict(orient="records"),
        "aggregate_rows": aggregate_df.to_dict(orient="records"),
        "artifacts": {
            "run_csv": str(run_csv_path),
            "summary_csv": str(aggregate_csv_path),
            "summary_json": str(summary_json_path),
        },
    }

    if parity_reference_repo_root is not None:
        parity_report = compare_materialization_snapshots(parity_reference_repo_root, repo_root)
        benchmark_summary["parity_report"] = _write_parity_artifacts(benchmark_dir, parity_report)

    content = json.dumps(benchmark_summary, ensure_ascii=False, indent=2)
    atomic_write_text(summary_json_path, content, encoding="utf-8")
    atomic_write_text(latest_json_path, content, encoding="utf-8")

    return benchmark_summary
