from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata import node_store, triple_store


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
