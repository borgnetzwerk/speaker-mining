from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.handlers.classes_handler import ClassesHandler
from process.candidate_generation.wikidata.node_store import upsert_discovered_item


def _class_event(seq: int, class_id: str, path_to_core_class: str, subclass_of_core_class: bool, ts: str = "2026-04-02T10:00:00Z") -> dict:
    return {
        "sequence_num": seq,
        "event_type": "class_membership_resolved",
        "timestamp_utc": ts,
        "payload": {
            "entity_qid": class_id,
            "class_id": class_id,
            "path_to_core_class": path_to_core_class,
            "subclass_of_core_class": subclass_of_core_class,
            "is_class_node": False,
        },
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

    upsert_discovered_item(tmp_path, "Q5", q5, "2026-04-02T10:00:00Z")
    upsert_discovered_item(tmp_path, "Q215627", q215627, "2026-04-02T10:00:00Z")

    handler = ClassesHandler(tmp_path)
    handler.bootstrap_from_projection(tmp_path / "classes.csv")
    handler.process_batch([
        _class_event(1, "Q5", "Q5|Q215627", True),
    ])

    out = tmp_path / "classes.csv"
    handler.materialize(out)
    df = pd.read_csv(out)

    row = df.loc[df["id"] == "Q5"].iloc[0]
    assert row["path_to_core_class"] == "Q5|Q215627"
    assert bool(row["subclass_of_core_class"]) is True
    assert row["label_en"] == "human"


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
    }
    cls = {"id": "Q5", "labels": {}, "descriptions": {}, "aliases": {}, "claims": {}}

    upsert_discovered_item(tmp_path, "Q5", cls, "2026-04-02T10:00:00Z")
    upsert_discovered_item(tmp_path, "Q100", e, "2026-04-02T10:00:00Z")

    events = [_class_event(2, "Q5", "Q5|Q215627", True), _class_event(1, "Q100", "Q5|Q215627", True)]
    handler1.process_batch(events)
    handler2.process_batch(events)

    upsert_discovered_item(tmp_path, "Q5", cls, "2026-04-02T10:00:00Z")
    upsert_discovered_item(tmp_path, "Q100", e, "2026-04-02T10:00:00Z")

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
