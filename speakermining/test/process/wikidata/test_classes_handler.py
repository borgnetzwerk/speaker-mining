from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.handlers.classes_handler import ClassesHandler


def _entity_event(seq: int, qid: str, entity_doc: dict, ts: str = "2026-04-02T10:00:00Z") -> dict:
    return {
        "sequence_num": seq,
        "event_type": "query_response",
        "source_step": "entity_fetch",
        "status": "success",
        "endpoint": "wikidata_api",
        "normalized_query": f"entity:{qid}",
        "query_hash": f"h-{seq}",
        "key": qid,
        "timestamp_utc": ts,
        "payload": {"entities": {qid: entity_doc}},
    }


def test_classes_handler_resolves_path_to_core(tmp_path: Path) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        "Q215627,persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )

    q200 = {
        "id": "Q200",
        "labels": {"en": {"value": "Alice"}},
        "descriptions": {},
        "aliases": {},
        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}]},
    }
    q5 = {
        "id": "Q5",
        "labels": {"en": {"value": "human"}},
        "descriptions": {},
        "aliases": {},
        "claims": {"P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}]},
    }
    q215627 = {
        "id": "Q215627",
        "labels": {"en": {"value": "person"}},
        "descriptions": {},
        "aliases": {},
        "claims": {},
    }

    handler = ClassesHandler(tmp_path)
    handler.process_batch([
        _entity_event(1, "Q200", q200),
        _entity_event(2, "Q5", q5),
        _entity_event(3, "Q215627", q215627),
    ])

    out = tmp_path / "classes.csv"
    handler.materialize(out)
    df = pd.read_csv(out)

    row = df.loc[df["id"] == "Q5"].iloc[0]
    assert row["path_to_core_class"] == "Q5|Q215627"
    assert bool(row["subclass_of_core_class"]) is True


def test_classes_handler_is_deterministic(tmp_path: Path) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n",
        encoding="utf-8",
    )
    handler1 = ClassesHandler(tmp_path)
    handler2 = ClassesHandler(tmp_path)

    e = {
        "id": "Q100",
        "labels": {"en": {"value": "node"}},
        "descriptions": {},
        "aliases": {},
        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}]},
    }
    cls = {"id": "Q5", "labels": {}, "descriptions": {}, "aliases": {}, "claims": {}}

    events = [_entity_event(2, "Q5", cls), _entity_event(1, "Q100", e)]
    handler1.process_batch(events)
    handler2.process_batch(events)

    out1 = tmp_path / "classes1.csv"
    out2 = tmp_path / "classes2.csv"
    handler1.materialize(out1)
    handler2.materialize(out2)

    assert out1.read_bytes() == out2.read_bytes()


def test_classes_handler_empty_materialization(tmp_path: Path) -> None:
    handler = ClassesHandler(tmp_path)
    out = tmp_path / "classes.csv"
    handler.materialize(out)
    df = pd.read_csv(out)
    assert list(df.columns) == [
        "id", "class_filename", "label_en", "label_de", "description_en", "description_de",
        "alias_en", "alias_de", "path_to_core_class", "subclass_of_core_class", "discovered_count", "expanded_count",
    ]
