from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.event_log import iter_query_events, write_query_event
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_event_file_uniqueness_for_same_key(tmp_path: Path) -> None:
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {}},
        http_status=200,
        error=None,
    )
    write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q1?revision=latest",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {"Q1": {"id": "Q1"}}},
        http_status=200,
        error=None,
    )

    paths = build_artifact_paths(tmp_path)
    chunk_files = sorted((paths.wikidata_dir / "chunks").glob("*.jsonl"))
    assert len(chunk_files) == 1

    events = list(iter_query_events(tmp_path) or [])
    assert len(events) == 2
    assert events[0]["payload"]["query_hash"] != events[1]["payload"]["query_hash"]
