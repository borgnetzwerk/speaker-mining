from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata import event_log, node_store, query_inventory, triple_store
from process.candidate_generation.wikidata.event_writer import EventStore


def test_node_store_defers_writes_until_flush(tmp_path: Path, monkeypatch) -> None:
    writes: list[str] = []

    def _fake_atomic_write_text(path: Path, text: str) -> None:
        _ = text
        writes.append(Path(path).name)

    monkeypatch.setattr(node_store, "_atomic_write_text", _fake_atomic_write_text)

    entity_doc = {
        "id": "Q1",
        "labels": {"en": {"value": "Example"}},
        "descriptions": {},
        "aliases": {},
        "claims": {
            "P31": [],
            "P279": [],
        },
    }

    node_store.upsert_discovered_item(tmp_path, "Q1", entity_doc, "2026-03-31T12:00:00Z")
    node_store.upsert_expanded_item(tmp_path, "Q1", entity_doc, "2026-03-31T12:01:00Z")

    assert writes == []

    node_store.flush_node_store(tmp_path)

    assert writes == ["entities.json"]


def test_triple_store_defers_writes_until_flush(tmp_path: Path, monkeypatch) -> None:
    writes: list[str] = []

    def _fake_atomic_write_text(path: Path, text: str) -> None:
        _ = text
        writes.append(Path(path).name)

    monkeypatch.setattr(triple_store, "_atomic_write_text", _fake_atomic_write_text)

    triple_store.record_item_edges(
        tmp_path,
        "Q1",
        [{"pid": "P31", "to_qid": "Q2"}],
        discovered_at_utc="2026-03-31T12:00:00Z",
        source_query_file="test",
    )
    triple_store.record_item_edges(
        tmp_path,
        "Q1",
        [{"pid": "P50", "to_qid": "Q3"}],
        discovered_at_utc="2026-03-31T12:01:00Z",
        source_query_file="test",
    )

    assert writes == []

    triple_store.flush_triple_events(tmp_path)

    assert writes == ["triple_events.json"]


def test_triple_store_emits_triple_discovered_events(tmp_path: Path) -> None:
    emitted: list[dict] = []

    def _emit(**kwargs):
        emitted.append(kwargs)

    triple_store.record_item_edges(
        tmp_path,
        "Q1",
        [{"pid": "P31", "to_qid": "Q5"}],
        discovered_at_utc="2026-03-31T12:00:00Z",
        source_query_file="test",
        event_emitter=_emit,
        event_phase="stage_a_graph_expansion",
    )

    assert len(emitted) == 1
    assert emitted[0]["event_type"] == "triple_discovered"
    assert emitted[0]["phase"] == "stage_a_graph_expansion"
    assert emitted[0]["extra"]["subject_qid"] == "Q1"
    assert emitted[0]["extra"]["predicate_pid"] == "P31"
    assert emitted[0]["extra"]["object_qid"] == "Q5"


def test_write_query_event_reuses_event_store_and_updates_inventory(tmp_path: Path, monkeypatch) -> None:
    init_calls = {"count": 0}

    original_init = EventStore.__init__

    def _counting_init(self, repo_root):
        init_calls["count"] += 1
        original_init(self, repo_root)

    monkeypatch.setattr(EventStore, "__init__", _counting_init)

    event_log.write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q1",
        source_step="entity_fetch",
        status="success",
        key="Q1",
        payload={"entities": {"Q1": {"id": "Q1"}}},
        http_status=200,
        error=None,
    )
    event_log.write_query_event(
        tmp_path,
        endpoint="wikidata_api",
        normalized_query="entity:Q2",
        source_step="entity_fetch",
        status="success",
        key="Q2",
        payload={"entities": {"Q2": {"id": "Q2"}}},
        http_status=200,
        error=None,
    )

    assert init_calls["count"] == 1

    def _unexpected_iter(*args, **kwargs):
        _ = (args, kwargs)
        raise AssertionError("query inventory should not scan the event log after incremental updates")

    monkeypatch.setattr(query_inventory, "iter_query_events", _unexpected_iter)

    df = query_inventory.materialize_query_inventory(tmp_path)

    assert set(df["key"]) == {"Q1", "Q2"}
    assert len(df) == 2
