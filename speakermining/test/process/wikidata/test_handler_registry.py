"""Tests for event handler base class and registry."""

from __future__ import annotations

# pyright: reportMissingImports=false

import csv
from pathlib import Path

from process.candidate_generation.wikidata.event_handler import EventHandler
from process.candidate_generation.wikidata.handler_registry import HandlerProgress, HandlerRegistry


class DummyHandler(EventHandler):
    """Test implementation of EventHandler for unit testing."""

    def __init__(self, name: str):
        self._name = name
        self._last_seq = 0
        self._state: list[dict] = []

    def name(self) -> str:
        return self._name

    def last_processed_sequence(self) -> int:
        return self._last_seq

    def process_batch(self, events: list[dict]) -> None:
        self._state.extend(events)
        if events:
            self._last_seq = events[-1].get("sequence_num", 0)

    def materialize(self, output_path: Path) -> None:
        output_path.write_text(f"state_count={len(self._state)}\n")


def test_registry_initialization(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    # Registry should exist with header
    assert registry_path.exists()
    lines = registry_path.read_text().strip().split("\n")
    assert lines[0] == "handler_name,last_processed_sequence,artifact_path,updated_at"
    assert registry.list_handlers() == []


def test_register_handler(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    registry.register_handler("Handler1", artifact_path="output1.csv")
    registry.register_handler("Handler2", artifact_path="output2.csv")
    
    assert registry.list_handlers() == ["Handler1", "Handler2"]
    assert registry.get_progress("Handler1") == 0
    assert registry.get_progress("Handler2") == 0


def test_update_progress(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    registry.register_handler("InstancesHandler")
    registry.update_progress("InstancesHandler", 100)
    
    # Verify in registry
    assert registry.get_progress("InstancesHandler") == 100
    
    # Verify persisted to CSV
    registry2 = HandlerRegistry(registry_path)
    assert registry2.get_progress("InstancesHandler") == 100


def test_multiple_handler_updates(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    registry.register_handler("H1")
    registry.register_handler("H2")
    registry.register_handler("H3")
    
    registry.update_progress("H1", 50)
    registry.update_progress("H2", 75)
    registry.update_progress("H3", 25)
    
    # Verify all updated
    assert registry.get_progress("H1") == 50
    assert registry.get_progress("H2") == 75
    assert registry.get_progress("H3") == 25
    
    # Verify persistence and reload
    registry2 = HandlerRegistry(registry_path)
    assert registry2.get_progress("H1") == 50
    assert registry2.get_progress("H2") == 75
    assert registry2.get_progress("H3") == 25


def test_update_nonexistent_handler(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    # Should auto-create handler on update
    registry.update_progress("NewHandler", 42)
    assert registry.get_progress("NewHandler") == 42


def test_all_handlers_caught_up(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    registry.register_handler("H1")
    registry.register_handler("H2")
    
    # Initially caught up (no events)
    assert registry.all_handlers_caught_up(0)
    
    # Not caught up: latest is 100, handlers at 0
    assert not registry.all_handlers_caught_up(100)
    
    # Update one handler
    registry.update_progress("H1", 50)
    assert not registry.all_handlers_caught_up(100)
    
    # Update both
    registry.update_progress("H1", 100)
    registry.update_progress("H2", 100)
    assert registry.all_handlers_caught_up(100)


def test_csv_format(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    registry = HandlerRegistry(registry_path)
    
    registry.register_handler("TestHandler", artifact_path="/path/to/output.csv")
    registry.update_progress("TestHandler", 123)
    
    # Read CSV directly to verify format
    with registry_path.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 1
    assert rows[0]["handler_name"] == "TestHandler"
    assert rows[0]["last_processed_sequence"] == "123"
    assert rows[0]["artifact_path"] == "/path/to/output.csv"
    assert rows[0]["updated_at"]  # Should have a timestamp


def test_recover_from_missing_file(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    
    # Registry doesn't exist yet
    assert not registry_path.exists()
    
    registry = HandlerRegistry(registry_path)
    
    # Should create it
    assert registry_path.exists()
    assert registry.list_handlers() == []


def test_recover_from_corrupted_registry(tmp_path: Path) -> None:
    registry_path = tmp_path / "eventhandler.csv"
    
    # Write invalid CSV
    registry_path.write_text("This is not valid\ninvalid csv content\n")
    
    # Should recover silently
    registry = HandlerRegistry(registry_path)
    assert registry.list_handlers() == []


def test_handler_progress_dict(tmp_path: Path) -> None:
    progress = HandlerProgress("TestHandler", last_seq=99, artifact_path="/output.csv", updated_at="2026-04-02T10:00:00Z")
    
    d = progress.to_dict()
    assert d["handler_name"] == "TestHandler"
    assert d["last_processed_sequence"] == 99
    assert d["artifact_path"] == "/output.csv"
    assert d["updated_at"] == "2026-04-02T10:00:00Z"
