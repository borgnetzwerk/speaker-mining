from __future__ import annotations

import json
from pathlib import Path

from process.candidate_generation.wikidata.chunk_catalog import rebuild_chunk_catalog
from process.candidate_generation.wikidata.event_writer import EventStore


def _all_events(repo_root: Path) -> list[dict]:
    chunks_dir = repo_root / "data" / "20_candidate_generation" / "wikidata" / "chunks"
    events: list[dict] = []
    for path in sorted(chunks_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                break
    return events


def test_event_store_assigns_sequence_and_v3_envelope(tmp_path: Path) -> None:
    store = EventStore(tmp_path)

    seq1 = store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:00Z", "payload": {"endpoint": "wikidata_api"}})
    seq2 = store.append_event({"event_type": "entity_discovered", "timestamp_utc": "2026-04-02T10:00:01Z", "payload": {"qid": "Q1"}})

    # Sequence 1 is reserved for initial eventstore_opened.
    assert seq1 == 2
    assert seq2 == 3

    events = _all_events(tmp_path)
    assert len(events) == 3
    assert events[0]["event_type"] == "eventstore_opened"
    assert events[0]["event_version"] == "v3"
    assert events[1]["event_version"] == "v3"
    assert events[2]["event_version"] == "v3"
    assert events[0]["sequence_num"] == 1
    assert events[1]["sequence_num"] == 2
    assert events[2]["sequence_num"] == 3


def test_event_store_truncates_partial_tail_on_restart(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:00Z", "payload": {"k": "v"}})

    chunk_file = store.active_chunk_path
    with chunk_file.open("ab") as f:
        f.write(b'{"sequence_num":3,"event_type":"broken"')

    restarted = EventStore(tmp_path)
    seq = restarted.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:01:00Z", "payload": {"k": "v2"}})

    assert seq == 3
    events = _all_events(tmp_path)
    assert [e.get("sequence_num") for e in events] == [1, 2, 3]


def test_rotate_chunk_emits_boundary_events_and_continuous_sequence(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:00Z", "payload": {"qid": "Q1"}})

    old_path, new_path = store.rotate_chunk()
    assert old_path != new_path
    assert old_path.exists()
    assert new_path.exists()

    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:01Z", "payload": {"qid": "Q2"}})

    events = _all_events(tmp_path)
    assert [e.get("sequence_num") for e in events] == [1, 2, 3, 4, 5]
    assert events[2].get("event_type") == "eventstore_closed"
    assert events[3].get("event_type") == "eventstore_opened"


def test_rebuild_chunk_catalog_marks_closed_and_active(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:00Z", "payload": {"qid": "Q1"}})
    store.rotate_chunk()
    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:01Z", "payload": {"qid": "Q2"}})

    rows = rebuild_chunk_catalog(tmp_path)
    assert len(rows) == 2

    statuses = [row["status"] for row in rows]
    assert "closed" in statuses
    assert "active" in statuses

    catalog_path = tmp_path / "data" / "20_candidate_generation" / "wikidata" / "chunk_catalog.csv"
    assert catalog_path.exists()


def test_rebuild_chunk_catalog_skips_identical_rewrites(tmp_path: Path, monkeypatch) -> None:
    store = EventStore(tmp_path)
    store.append_event({"event_type": "query_response", "timestamp_utc": "2026-04-02T10:00:00Z", "payload": {"qid": "Q1"}})
    rebuild_chunk_catalog(tmp_path)

    def fail_replace(self, target):
        raise AssertionError("expected chunk catalog rewrite to be skipped")

    monkeypatch.setattr(Path, "replace", fail_replace)

    rows = rebuild_chunk_catalog(tmp_path)
    assert len(rows) == 1
