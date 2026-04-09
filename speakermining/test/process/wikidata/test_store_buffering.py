from __future__ import annotations

# pyright: reportMissingImports=false

import hashlib
import json
from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata import event_log, node_store, query_inventory, triple_store
from process.candidate_generation.wikidata.bootstrap import ensure_output_bootstrap
from process.candidate_generation.wikidata.event_writer import EventStore
from process.candidate_generation.wikidata.materializer import materialize_final
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _qid_bucket(qid: str) -> str:
    return hashlib.sha1(str(qid).encode("utf-8")).hexdigest()[:2]


def _qids_with_unique_buckets(count: int) -> list[str]:
    qids: list[str] = []
    seen_buckets: set[str] = set()
    candidate = 1
    while len(qids) < count:
        qid = f"Q{candidate}"
        bucket = _qid_bucket(qid)
        if bucket not in seen_buckets:
            qids.append(qid)
            seen_buckets.add(bucket)
        candidate += 1
    return qids


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


def test_seed_neighbor_degrees_returns_minimal_two_hop_distances(tmp_path: Path) -> None:
    triple_store.record_item_edges(
        tmp_path,
        "Q100",
        [{"pid": "P50", "to_qid": "Q200"}],
        discovered_at_utc="2026-04-09T12:00:00Z",
        source_query_file="test",
    )
    triple_store.record_item_edges(
        tmp_path,
        "Q200",
        [{"pid": "P50", "to_qid": "Q300"}],
        discovered_at_utc="2026-04-09T12:00:01Z",
        source_query_file="test",
    )
    triple_store.record_item_edges(
        tmp_path,
        "Q300",
        [{"pid": "P50", "to_qid": "Q400"}],
        discovered_at_utc="2026-04-09T12:00:02Z",
        source_query_file="test",
    )

    degrees = triple_store.seed_neighbor_degrees(tmp_path, {"Q100"}, max_degree=2)

    assert degrees.get("Q200") == 1
    assert degrees.get("Q300") == 2
    assert "Q400" not in degrees


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


def test_materializer_writes_entity_lookup_and_chunks(tmp_path: Path) -> None:
    ensure_output_bootstrap(tmp_path)
    node_store.upsert_discovered_item(
        tmp_path,
        "Q130638552",
        {
            "id": "Q130638552",
            "labels": {"de": {"value": "Markus Lanz (October 24th, 2024)"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q1983062"}
                            }
                        }
                    }
                ]
            },
            "discovered_at_utc": "2026-04-09T10:00:00Z",
        },
        "2026-04-09T10:00:00Z",
    )
    materialize_final(tmp_path, run_id="test_lookup_chunks")

    paths = build_artifact_paths(tmp_path)
    lookup_df = pd.read_csv(paths.entity_lookup_index_csv)
    assert "Q130638552" in set(lookup_df["qid"].astype(str))
    assert len(list(paths.entity_chunks_dir.glob("*.jsonl"))) > 0


def test_materializer_keeps_small_records_in_a_single_chunk(tmp_path: Path) -> None:
    ensure_output_bootstrap(tmp_path)
    for qid in _qids_with_unique_buckets(4):
        node_store.upsert_discovered_item(
            tmp_path,
            qid,
            {
                "id": qid,
                "labels": {},
                "descriptions": {},
                "aliases": {},
                "claims": {"P31": [], "P279": []},
            },
            "2026-04-09T10:00:00Z",
        )

    materialize_final(tmp_path, run_id="single_chunk")

    paths = build_artifact_paths(tmp_path)
    chunk_files = sorted(paths.entity_chunks_dir.glob("*.jsonl"))
    assert len(chunk_files) == 1
    lookup_df = pd.read_csv(paths.entity_lookup_index_csv)
    assert lookup_df["chunk_file"].nunique() == 1


def test_get_item_can_resolve_from_chunk_lookup_without_entities_json(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)
    paths.entity_chunks_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "qid": "Q130638552",
        "entity": {
            "id": "Q130638552",
            "labels": {"de": {"value": "Chunk Lookup Entity"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
    }
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
    payload = line.encode("utf-8")
    chunk_name = "entities_ff_0001.jsonl"
    (paths.entity_chunks_dir / chunk_name).write_bytes(payload)

    index_df = pd.DataFrame(
        [
            {
                "qid": "Q130638552",
                "chunk_file": chunk_name,
                "record_key": f"0:{len(payload)}",
                "resolved_core_class_id": "",
                "subclass_of_core_class": False,
                "discovered_at_utc": "",
                "expanded_at_utc": "",
                "byte_offset": 0,
                "byte_length": len(payload),
            }
        ]
    )
    index_df.to_csv(paths.entity_lookup_index_csv, index=False)

    resolved = node_store.get_item(tmp_path, "Q130638552")
    assert isinstance(resolved, dict)
    assert resolved.get("id") == "Q130638552"


def test_iter_items_can_read_from_chunk_lookup_without_entities_json(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.projections_dir.mkdir(parents=True, exist_ok=True)
    paths.entity_chunks_dir.mkdir(parents=True, exist_ok=True)

    records = [
        {
            "qid": "Q100",
            "entity": {"id": "Q100", "labels": {}, "descriptions": {}, "aliases": {}, "claims": {"P31": [], "P279": []}},
        },
        {
            "qid": "Q200",
            "entity": {"id": "Q200", "labels": {}, "descriptions": {}, "aliases": {}, "claims": {"P31": [], "P279": []}},
        },
    ]

    chunk_name = "entities_aa_0001.jsonl"
    payload_lines = [json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n" for rec in records]
    payload = "".join(payload_lines).encode("utf-8")
    (paths.entity_chunks_dir / chunk_name).write_bytes(payload)

    offset = 0
    index_rows: list[dict] = []
    for line, rec in zip(payload_lines, records):
        byte_length = len(line.encode("utf-8"))
        index_rows.append(
            {
                "qid": rec["qid"],
                "chunk_file": chunk_name,
                "record_key": f"{offset}:{byte_length}",
                "resolved_core_class_id": "",
                "subclass_of_core_class": False,
                "discovered_at_utc": "",
                "expanded_at_utc": "",
                "byte_offset": offset,
                "byte_length": byte_length,
            }
        )
        offset += byte_length
    pd.DataFrame(index_rows).to_csv(paths.entity_lookup_index_csv, index=False)

    seen = [item.get("id") for item in node_store.iter_items(tmp_path)]
    assert seen == ["Q100", "Q200"]
