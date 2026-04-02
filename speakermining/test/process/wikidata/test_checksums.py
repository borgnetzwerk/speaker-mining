from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.checksums import (
    compute_checksum,
    validate_chunk_checksum,
    write_chunk_checksum,
)
from process.candidate_generation.wikidata.event_writer import EventStore


def test_compute_checksum_changes_on_file_change(tmp_path: Path) -> None:
    chunk = tmp_path / "chunk.jsonl"
    chunk.write_text('{"a":1}\n', encoding="utf-8")
    first = compute_checksum(chunk)
    chunk.write_text('{"a":2}\n', encoding="utf-8")
    second = compute_checksum(chunk)
    assert first != second


def test_write_and_validate_chunk_checksum(tmp_path: Path) -> None:
    chunk = tmp_path / "chunk.jsonl"
    chunk.write_text('{"a":1}\n', encoding="utf-8")
    write_chunk_checksum(tmp_path, chunk)
    assert validate_chunk_checksum(tmp_path, chunk) is True
    chunk.write_text('{"a":2}\n', encoding="utf-8")
    assert validate_chunk_checksum(tmp_path, chunk) is False


def test_eventstore_rotation_records_checksum(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:00Z", "payload": {}})
    old_path, _new_path = store.rotate_chunk()
    # rotate_chunk should write checksum entry for closed chunk
    assert validate_chunk_checksum(tmp_path, old_path) is True
