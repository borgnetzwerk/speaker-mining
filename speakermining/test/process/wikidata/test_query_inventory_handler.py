"""Tests for QueryInventoryHandler."""

from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.handlers.query_inventory_handler import QueryInventoryHandler


def test_query_inventory_dedup_by_hash(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        },
        {
            "sequence_num": 2,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "cache_hit",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:01:00Z",
        },
    ]
    
    handler.process_batch(events)
    
    # Should have one record (deduped by hash)
    assert len(handler.queries) == 1
    assert handler.queries["hash-1"].count == 2
    assert handler.queries["hash-1"].status == "success"  # Higher rank than cache_hit


def test_query_inventory_keeps_highest_status(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "http_error",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        },
        {
            "sequence_num": 2,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:01:00Z",
        },
    ]
    
    handler.process_batch(events)
    
    assert handler.queries["hash-1"].status == "success"


def test_query_inventory_tracks_count(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    
    events = [
        {
            "sequence_num": i,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": f"2026-04-02T10:{i:02d}:00Z",
        }
        for i in range(5)
    ]
    
    handler.process_batch(events)
    assert handler.queries["hash-1"].count == 5


def test_query_inventory_multiple_queries(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        },
        {
            "sequence_num": 2,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q2",
            "query_hash": "hash-2",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q2",
            "timestamp_utc": "2026-04-02T10:01:00Z",
        },
    ]
    
    handler.process_batch(events)
    assert len(handler.queries) == 2


def test_query_inventory_ignores_non_query_response(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "entity_discovered",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        }
    ]
    
    handler.process_batch(events)
    assert len(handler.queries) == 0


def test_query_inventory_materialization_sorted(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "endpoint": "wikidata_sparql",
            "normalized_query": "inlinks",
            "query_hash": "hash-3",
            "source_step": "inlinks_fetch",
            "status": "success",
            "key": "target:Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        },
        {
            "sequence_num": 2,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:01:00Z",
        },
        {
            "sequence_num": 3,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q2",
            "query_hash": "hash-2",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q2",
            "timestamp_utc": "2026-04-02T10:02:00Z",
        },
    ]
    
    handler.process_batch(events)
    
    output_path = tmp_path / "query_inventory.csv"
    handler.materialize(output_path)
    
    content = output_path.read_text()
    lines = content.strip().split("\n")
    
    # Should have header + 3 data rows
    assert len(lines) >= 4
    
    # Data should be sorted by endpoint first (wikidata_api before wikidata_sparql)
    data = lines[1:]
    assert "wikidata_api" in data[0]
    assert "wikidata_api" in data[1]
    assert "wikidata_sparql" in data[2]


def test_query_inventory_determinism(tmp_path: Path) -> None:
    """Materialize same data twice; outputs should be byte-identical."""
    events = [
        {
            "sequence_num": i,
            "event_type": "query_response",
            "endpoint": "wikidata_api" if i % 2 == 0 else "wikidata_sparql",
            "normalized_query": f"query-{i}",
            "query_hash": f"hash-{i}",
            "source_step": "entity_fetch",
            "status": "success",
            "key": f"key-{i}",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        }
        for i in [5, 2, 8, 1, 3]  # Intentionally out of order
    ]
    
    # First run
    handler1 = QueryInventoryHandler(tmp_path)
    handler1.process_batch(events)
    output1 = tmp_path / "query_inventory_1.csv"
    handler1.materialize(output1)
    
    # Second run
    handler2 = QueryInventoryHandler(tmp_path)
    handler2.process_batch(events)
    output2 = tmp_path / "query_inventory_2.csv"
    handler2.materialize(output2)
    
    # Should be byte-identical
    assert output1.read_bytes() == output2.read_bytes()


def test_query_inventory_empty_materialization(tmp_path: Path) -> None:
    """Materialize empty handler; should create CSV with headers."""
    handler = QueryInventoryHandler(tmp_path)
    
    output_path = tmp_path / "query_inventory.csv"
    handler.materialize(output_path)
    
    assert output_path.exists()
    content = output_path.read_text()
    assert "endpoint" in content
    assert "query_hash" in content


def test_query_inventory_sequence_tracking(tmp_path: Path) -> None:
    handler = QueryInventoryHandler(tmp_path)
    assert handler.last_processed_sequence() == 0
    
    events = [
        {
            "sequence_num": 42,
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q1",
            "query_hash": "hash-1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
        }
    ]
    
    handler.process_batch(events)
    assert handler.last_processed_sequence() == 42
