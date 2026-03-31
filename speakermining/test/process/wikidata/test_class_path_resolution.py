from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.materializer import materialize_final
from process.candidate_generation.wikidata.node_store import upsert_discovered_item
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def test_materializer_resolves_parent_class_path_from_local_store(tmp_path: Path) -> None:
    # Q100 is an instance whose class parent chain reaches core class Q300 via Q200.
    upsert_discovered_item(
        tmp_path,
        "Q100",
        {
            "id": "Q100",
            "labels": {"en": {"value": "Child"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                    "value": {"entity-type": "item", "id": "Q200"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-03-31T12:00:00Z",
    )

    upsert_discovered_item(
        tmp_path,
        "Q200",
        {
            "id": "Q200",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [
                    {
                        "mainsnak": {
                            "datavalue": {
                                "value": {"entity-type": "item", "id": "Q300"}
                            }
                        }
                    }
                ]
            },
        },
        "2026-03-31T12:01:00Z",
    )

    upsert_discovered_item(
        tmp_path,
        "Q300",
        {
            "id": "Q300",
            "labels": {"en": {"value": "Topic"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "2026-03-31T12:02:00Z",
    )

    classes_csv = tmp_path / "data" / "00_setup" / "classes.csv"
    classes_csv.parent.mkdir(parents=True, exist_ok=True)
    classes_csv.write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        "Q300,topics,Topic,,,,,,Q300,\n",
        encoding="utf-8",
    )

    materialize_final(tmp_path, run_id="run-1")
    paths = build_artifact_paths(tmp_path)
    instances_text = paths.instances_csv.read_text(encoding="utf-8")

    assert "Q200|Q300" in instances_text
