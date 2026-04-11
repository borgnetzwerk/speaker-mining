from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.handlers.backoff_learning_handler import BackoffLearningHandler


def _query_event(*, seq: int, endpoint: str, source_step: str, status: str, http_status: int | None = None) -> dict:
    return {
        "event_type": "query_response",
        "sequence_num": int(seq),
        "timestamp_utc": "2026-04-11T10:00:00Z",
        "payload": {
            "endpoint": endpoint,
            "source_step": source_step,
            "status": status,
            "http_status": http_status,
        },
    }


def test_backoff_learning_handler_materializes_windowed_patterns(tmp_path: Path) -> None:
    handler = BackoffLearningHandler(tmp_path)
    events = []
    # First 100 calls are mostly successful (example cold-start leniency pattern)
    for i in range(1, 101):
        events.append(_query_event(seq=i, endpoint="wikidata_api", source_step="entity_fetch", status="success", http_status=200))
    # Next 100 include more pressure / backoff-like responses
    for i in range(101, 201):
        status = "http_error" if i % 10 == 0 else "success"
        code = 429 if status == "http_error" else 200
        events.append(_query_event(seq=i, endpoint="wikidata_api", source_step="entity_fetch", status=status, http_status=code))

    handler.process_batch(events)
    out_csv = tmp_path / "backoff_pattern_windows.csv"
    handler.materialize(out_csv)

    df = pd.read_csv(out_csv)
    assert len(df) == 2
    assert set(df["window_index"]) == {0, 1}

    first = df[df["window_index"] == 0].iloc[0]
    second = df[df["window_index"] == 1].iloc[0]

    assert int(first["calls"]) == 100
    assert int(second["calls"]) == 100
    assert float(first["backoff_like_ratio"]) == 0.0
    assert float(second["backoff_like_ratio"]) > 0.0


def test_backoff_learning_handler_bootstrap_then_incremental(tmp_path: Path) -> None:
    output_path = tmp_path / "backoff_pattern_windows.csv"

    first = BackoffLearningHandler(tmp_path)
    first.process_batch([
        _query_event(seq=1, endpoint="wikidata_api", source_step="entity_fetch", status="success", http_status=200),
        _query_event(seq=2, endpoint="wikidata_api", source_step="entity_fetch", status="success", http_status=200),
    ])
    first.materialize(output_path)

    second = BackoffLearningHandler(tmp_path)
    assert second.bootstrap_from_projection(output_path) is True
    second.process_batch([
        _query_event(seq=3, endpoint="wikidata_api", source_step="entity_fetch", status="http_error", http_status=429),
    ])
    second.materialize(output_path)

    df = pd.read_csv(output_path)
    row = df.iloc[0]
    assert int(row["calls"]) == 3
    assert int(row["http_status_429"]) == 1
    assert int(row["rate_limited_like"]) == 1
