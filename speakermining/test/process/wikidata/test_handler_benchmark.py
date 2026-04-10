from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.event_writer import EventStore
from process.candidate_generation.wikidata.handler_benchmark import run_handler_materialization_benchmark
from process.candidate_generation.wikidata.handlers.orchestrator import run_handlers
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _append_entity_event(store: EventStore, qid: str, payload_entity: dict, seq_key: str) -> None:
    store.append_event(
        {
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": f"entity:{qid}:{seq_key}",
            "query_hash": f"hash-{seq_key}",
            "source_step": "entity_fetch",
            "status": "success",
            "key": qid,
            "payload": {"entities": {qid: payload_entity}},
            "http_status": 200,
            "error": None,
        }
    )


def test_handler_materialization_benchmark_writes_artifacts(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    _append_entity_event(
        store,
        "Q1",
        {
            "id": "Q1",
            "labels": {"en": {"value": "Node 1"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "A",
    )

    benchmark = run_handler_materialization_benchmark(
        tmp_path,
        rounds=1,
        include_full_rebuild=True,
        run_context={"mode": "cache_first", "workload_targets": 1},
    )

    assert benchmark["modes"] == ["incremental", "full_rebuild"]
    assert len(benchmark["run_rows"]) == 2
    assert len(benchmark["aggregate_rows"]) == 2

    artifacts = benchmark["artifacts"]
    for key in ("run_csv", "summary_csv", "summary_json"):
        assert Path(artifacts[key]).exists()

    summary_payload = json.loads(Path(artifacts["summary_json"]).read_text(encoding="utf-8"))
    assert summary_payload["run_context"]["mode"] == "cache_first"
    assert int(summary_payload["run_context"]["workload_targets"]) == 1


def test_handler_materialization_benchmark_captures_replay_delta(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    _append_entity_event(
        store,
        "Q1",
        {
            "id": "Q1",
            "labels": {"en": {"value": "Node 1"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "A",
    )

    run_handlers(tmp_path)

    _append_entity_event(
        store,
        "Q2",
        {
            "id": "Q2",
            "labels": {"en": {"value": "Node 2"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "B",
    )

    benchmark = run_handler_materialization_benchmark(
        tmp_path,
        rounds=1,
        include_full_rebuild=True,
    )

    runs_by_mode = {row["mode"]: row for row in benchmark["run_rows"]}
    assert set(runs_by_mode) == {"incremental", "full_rebuild"}

    assert int(runs_by_mode["incremental"]["total_historical_replay_events"]) <= int(
        runs_by_mode["full_rebuild"]["total_historical_replay_events"]
    )

    latest_summary = (
        build_artifact_paths(tmp_path).wikidata_dir / "benchmarks" / "handler_materialization_summary_latest.json"
    )
    payload = json.loads(latest_summary.read_text(encoding="utf-8"))
    assert payload["modes"] == ["incremental", "full_rebuild"]

    summary_csv = Path(payload["artifacts"]["summary_csv"])
    summary_df = pd.read_csv(summary_csv)
    assert set(summary_df["mode"]) == {"incremental", "full_rebuild"}


def test_handler_materialization_benchmark_writes_parity_report(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    work_root = tmp_path / "work"

    reference_store = EventStore(reference_root)
    work_store = EventStore(work_root)
    for store, seq_key in ((reference_store, "A"), (work_store, "A")):
        _append_entity_event(
            store,
            "Q1",
            {
                "id": "Q1",
                "labels": {"en": {"value": "Node 1"}},
                "descriptions": {},
                "aliases": {},
                "claims": {},
            },
            seq_key,
        )

    run_handlers(reference_root, materialization_mode="full_rebuild")

    benchmark = run_handler_materialization_benchmark(
        work_root,
        rounds=1,
        include_full_rebuild=False,
        parity_reference_repo_root=reference_root,
    )

    parity_report = benchmark["parity_report"]
    assert parity_report["matches"] is True

    parity_json = Path(parity_report["artifacts"]["parity_json"])
    parity_csv = Path(parity_report["artifacts"]["parity_csv"])
    assert parity_json.exists()
    assert parity_csv.exists()

    payload = json.loads(parity_json.read_text(encoding="utf-8"))
    assert payload["matches"] is True
    assert payload["artifacts_compared"]
