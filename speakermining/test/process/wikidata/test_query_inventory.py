from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.wikidata.query_inventory import rebuild_query_inventory
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _write_event(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_query_inventory_dedup_keep_latest_success(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.raw_queries_dir.mkdir(parents=True, exist_ok=True)

    base = {
        "event_version": "v2",
        "event_type": "query_response",
        "endpoint": "wikidata_api",
        "normalized_query": "entity:Q1",
        "query_hash": "hash-1",
        "source_step": "entity_fetch",
        "status": "http_error",
        "key": "Q1",
        "http_status": 500,
        "error": "boom",
        "payload": {},
    }

    e1 = {**base, "timestamp_utc": "2026-03-31T10:00:00Z"}
    e2 = {**base, "status": "success", "http_status": 200, "error": None, "timestamp_utc": "2026-03-31T10:05:00Z"}
    e3 = {**base, "status": "cache_hit", "http_status": 200, "error": None, "timestamp_utc": "2026-03-31T10:10:00Z"}

    _write_event(paths.raw_queries_dir / "a.json", e1)
    _write_event(paths.raw_queries_dir / "b.json", e2)
    _write_event(paths.raw_queries_dir / "c.json", e3)

    rows = rebuild_query_inventory(tmp_path)
    assert len(rows) == 1
    assert rows[0]["status"] == "success"
