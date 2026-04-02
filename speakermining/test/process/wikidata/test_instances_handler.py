"""Tests for InstancesHandler."""

from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.wikidata.handlers.instances_handler import InstancesHandler


def test_instances_handler_extracts_entity_metadata(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "entities": {
                    "Q1": {
                        "type": "item",
                        "labels": {"en": {"value": "Universe"}},
                        "descriptions": {"en": {"value": "everything"}},
                        "aliases": {"en": [{"value": "cosmos"}]},
                    }
                }
            },
        }
    ]
    
    handler.process_batch(events)
    assert "Q1" in handler.entities
    assert handler.entities["Q1"]["label"] == "Universe"
    assert handler.entities["Q1"]["description"] == "everything"


def test_instances_handler_ignores_non_success_status(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "http_error",
            "key": "Q1",
            "payload": {"entities": {}},
        }
    ]
    
    handler.process_batch(events)
    assert "Q1" not in handler.entities


def test_instances_handler_ignores_wrong_source_step(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "source_step": "property_fetch",
            "status": "success",
            "key": "Q1",
            "payload": {"entities": {}},
        }
    ]
    
    handler.process_batch(events)
    assert "Q1" not in handler.entities


def test_instances_handler_ignores_non_query_response(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "entity_discovered",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "payload": {"entities": {}},
        }
    ]
    
    handler.process_batch(events)
    assert "Q1" not in handler.entities


def test_instances_handler_materializes_csv_sorted(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q3",
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "entities": {
                    "Q3": {
                        "labels": {"en": {"value": "Earth"}},
                        "descriptions": {"en": {"value": "planet"}},
                        "aliases": {"en": []},
                    }
                }
            },
        },
        {
            "sequence_num": 2,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:01:00Z",
            "payload": {
                "entities": {
                    "Q1": {
                        "labels": {"en": {"value": "Universe"}},
                        "descriptions": {"en": {"value": "everything"}},
                        "aliases": {"en": []},
                    }
                }
            },
        },
    ]
    
    handler.process_batch(events)
    
    output_path = tmp_path / "instances.csv"
    handler.materialize(output_path)
    
    assert output_path.exists()
    content = output_path.read_text()
    lines = content.strip().split("\n")
    
    # Should have header + 2 data rows
    assert len(lines) >= 2
    
    # Data rows should be sorted by QID (Q1 before Q3)
    data = lines[1:]  # Skip header
    assert data[0].startswith("Q1")
    assert data[1].startswith("Q3")


def test_instances_handler_determinism(tmp_path: Path) -> None:
    """Materialize same data twice; outputs should be byte-identical."""
    events = [
        {
            "sequence_num": i,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "success",
            "key": f"Q{i}",
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "entities": {
                    f"Q{i}": {
                        "labels": {"en": {"value": f"Entity {i}"}},
                        "descriptions": {"en": {"value": f"Description {i}"}},
                        "aliases": {"en": []},
                    }
                }
            },
        }
        for i in [5, 2, 8, 1, 3]  # Intentionally out of order
    ]
    
    # First run
    handler1 = InstancesHandler(tmp_path)
    handler1.process_batch(events)
    output1 = tmp_path / "instances_1.csv"
    handler1.materialize(output1)
    
    # Second run
    handler2 = InstancesHandler(tmp_path)
    handler2.process_batch(events)
    output2 = tmp_path / "instances_2.csv"
    handler2.materialize(output2)
    
    # Should be byte-identical
    assert output1.read_bytes() == output2.read_bytes()


def test_instances_handler_multiple_languages(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    
    events = [
        {
            "sequence_num": 1,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {
                "entities": {
                    "Q1": {
                        "labels": {
                            "en": {"value": "Universe"},
                            "de": {"value": "Universum"},
                        },
                        "descriptions": {"en": {"value": "everything"}},
                        "aliases": {"en": [{"value": "cosmos"}]},
                    }
                }
            },
        }
    ]
    
    handler.process_batch(events)
    assert handler.entities["Q1"]["labels_en"] == "Universe"
    assert handler.entities["Q1"]["labels_de"] == "Universum"


def test_instances_handler_empty_materialization(tmp_path: Path) -> None:
    """Materialize empty handler; should create CSV with headers."""
    handler = InstancesHandler(tmp_path)
    
    output_path = tmp_path / "instances.csv"
    handler.materialize(output_path)
    
    assert output_path.exists()
    content = output_path.read_text()
    assert "qid" in content
    assert "label" in content


def test_instances_handler_sequence_tracking(tmp_path: Path) -> None:
    handler = InstancesHandler(tmp_path)
    assert handler.last_processed_sequence() == 0
    
    events = [
        {
            "sequence_num": 42,
            "event_type": "query_response",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q1",
            "timestamp_utc": "2026-04-02T10:00:00Z",
            "payload": {"entities": {"Q1": {"labels": {}, "descriptions": {}, "aliases": {}}}},
        }
    ]
    
    handler.process_batch(events)
    assert handler.last_processed_sequence() == 42
