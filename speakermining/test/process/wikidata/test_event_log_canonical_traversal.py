from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.wikidata.event_log import iter_all_events, iter_query_events


def _write_events(path: Path, events: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(json.dumps(event) + "\n")


def _query_event(seq: int, key: str) -> dict:
    return {
        "sequence_num": seq,
        "event_version": "v3",
        "event_type": "query_response",
        "timestamp_utc": "2026-04-02T10:00:00Z",
        "recorded_at": "2026-04-02T10:00:00Z",
        "payload": {
            "endpoint": "wikidata_api",
            "normalized_query": f"entity:{key}",
            "query_hash": f"hash-{key}",
            "source_step": "entity_fetch",
            "status": "success",
            "key": key,
            "http_status": 200,
            "error": None,
            "response_data": {"entities": {key: {"id": key}}},
        },
    }


def test_iter_all_events_follows_boundary_chain_not_filename_order(tmp_path: Path) -> None:
    chunks_dir = tmp_path / "data" / "20_candidate_generation" / "wikidata" / "chunks"

    chunk_a = chunks_dir / "eventstore_chunk_2026-04-02_9999.jsonl"
    chunk_b = chunks_dir / "eventstore_chunk_2026-04-02_0001.jsonl"

    _write_events(
        chunk_a,
        [
            {
                "sequence_num": 1,
                "event_version": "v3",
                "event_type": "eventstore_opened",
                "timestamp_utc": "2026-04-02T10:00:00Z",
                "recorded_at": "2026-04-02T10:00:00Z",
                "payload": {"chunk_id": "chunk_A", "prev_chunk_id": ""},
            },
            _query_event(2, "Q1"),
            {
                "sequence_num": 3,
                "event_version": "v3",
                "event_type": "eventstore_closed",
                "timestamp_utc": "2026-04-02T10:00:00Z",
                "recorded_at": "2026-04-02T10:00:00Z",
                "payload": {"chunk_id": "chunk_A", "next_chunk_id": "chunk_B"},
            },
        ],
    )

    _write_events(
        chunk_b,
        [
            {
                "sequence_num": 4,
                "event_version": "v3",
                "event_type": "eventstore_opened",
                "timestamp_utc": "2026-04-02T10:00:00Z",
                "recorded_at": "2026-04-02T10:00:00Z",
                "payload": {"chunk_id": "chunk_B", "prev_chunk_id": "chunk_A"},
            },
            _query_event(5, "Q2"),
        ],
    )

    seqs = [event["sequence_num"] for event in iter_all_events(tmp_path)]
    assert seqs == [1, 2, 3, 4, 5]

    query_seqs = [event["sequence_num"] for event in iter_query_events(tmp_path)]
    assert query_seqs == [2, 5]
