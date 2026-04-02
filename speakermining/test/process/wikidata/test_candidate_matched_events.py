"""Tests for candidate_matched event emission."""

from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.event_log import (
    write_candidate_matched_event,
    iter_query_events,
    _iter_jsonl_events,
    _chunks_dir,
)


def test_write_candidate_matched_event(tmp_path: Path) -> None:
    """Test that candidate_matched events are written correctly."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Write a candidate_matched event
    write_candidate_matched_event(
        repo_root,
        mention_id="m1",
        mention_type="person",
        mention_label="John Doe",
        candidate_id="Q42",
        candidate_label="John Doe (Q42)",
        source="fallback_string",
        context="Test context",
    )
    
    # Read back all events from chunks
    chunks_dir = _chunks_dir(repo_root)
    events = []
    for chunk_path in sorted(chunks_dir.glob("*.jsonl")):
        for event in _iter_jsonl_events(chunk_path):
            if event.get("event_type") == "candidate_matched":
                events.append(event)
    
    assert len(events) >= 1
    event = events[0]
    payload = event.get("payload", {})
    assert event["event_type"] == "candidate_matched"
    assert event["event_version"] == "v3"
    assert payload["mention_id"] == "m1"
    assert payload["mention_type"] == "person"
    assert payload["mention_label"] == "John Doe"
    assert payload["candidate_id"] == "Q42"
    assert payload["candidate_label"] == "John Doe (Q42)"
    assert payload["source"] == "fallback_string"
    assert payload["context"] == "Test context"
    assert "timestamp_utc" in event
    assert "sequence_num" in event


def test_multiple_candidate_matched_events(tmp_path: Path) -> None:
    """Test that multiple candidate_matched events are tracked correctly."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Write multiple events
    for i in range(3):
        write_candidate_matched_event(
            repo_root,
            mention_id=f"m{i}",
            mention_type="person",
            mention_label=f"Person {i}",
            candidate_id=f"Q{i}",
            candidate_label=f"Person {i}",
            source="fallback_string",
        )
    
    # Read back all events
    chunks_dir = _chunks_dir(repo_root)
    events = []
    for chunk_path in sorted(chunks_dir.glob("*.jsonl")):
        for event in _iter_jsonl_events(chunk_path):
            if event.get("event_type") == "candidate_matched":
                events.append(event)
    
    assert len(events) >= 3
    for i in range(3):
        payload = events[i].get("payload", {})
        assert payload["mention_id"] == f"m{i}"
        assert payload["candidate_id"] == f"Q{i}"


def test_candidate_matched_event_sequence_numbering(tmp_path: Path) -> None:
    """Test that sequence numbers are assigned correctly."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    
    # Write two events
    write_candidate_matched_event(
        repo_root,
        mention_id="m1",
        mention_type="person",
        mention_label="First",
        candidate_id="Q1",
        candidate_label="First",
        source="fallback_string",
    )
    
    write_candidate_matched_event(
        repo_root,
        mention_id="m2",
        mention_type="person",
        mention_label="Second",
        candidate_id="Q2",
        candidate_label="Second",
        source="fallback_string",
    )
    
    # Verify sequence numbers are consecutive
    chunks_dir = _chunks_dir(repo_root)
    events = []
    for chunk_path in sorted(chunks_dir.glob("*.jsonl")):
        for event in _iter_jsonl_events(chunk_path):
            events.append(event)
    
    # Filter to just candidate_matched events (skip eventstore_opened/closed)
    candidate_events = [e for e in events if e.get("event_type") == "candidate_matched"]
    assert len(candidate_events) >= 2
    
    seq_nums = [e["sequence_num"] for e in candidate_events[:2]]
    assert seq_nums[1] > seq_nums[0]  # Verify they're in order

