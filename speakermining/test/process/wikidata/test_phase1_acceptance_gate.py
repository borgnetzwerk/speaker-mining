from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

from process.candidate_generation.wikidata.event_writer import EventStore
from process.candidate_generation.wikidata.handlers.orchestrator import run_handlers
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _seed_events(root: Path) -> None:
    store = EventStore(root)
    store.append_event(
        {
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q100",
            "query_hash": "h1",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q100",
            "payload": {
                "entities": {
                    "Q100": {
                        "id": "Q100",
                        "labels": {"en": {"value": "Alice"}},
                        "descriptions": {"en": {"value": "person"}},
                        "aliases": {"en": [{"value": "A"}]},
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
                            "P50": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q200"}}}}],
                        },
                    }
                }
            },
            "http_status": 200,
            "error": None,
        }
    )
    store.append_event(
        {
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": "entity:Q5",
            "query_hash": "h2",
            "source_step": "entity_fetch",
            "status": "success",
            "key": "Q5",
            "payload": {
                "entities": {
                    "Q5": {
                        "id": "Q5",
                        "labels": {"en": {"value": "human"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {
                            "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}]
                        },
                    }
                }
            },
            "http_status": 200,
            "error": None,
        }
    )


def test_phase1_orchestrator_outputs_are_deterministic(tmp_path: Path) -> None:
    root1 = tmp_path / "run1"
    root2 = tmp_path / "run2"

    for root in (root1, root2):
        setup_dir = root / "data" / "00_setup"
        setup_dir.mkdir(parents=True, exist_ok=True)
        (setup_dir / "classes.csv").write_text(
            "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
            "Q215627,persons,person,,,,,,Q215627,\n",
            encoding="utf-8",
        )
        _seed_events(root)
        run_handlers(root)

    p1 = build_artifact_paths(root1)
    p2 = build_artifact_paths(root2)

    assert p1.instances_csv.read_bytes() == p2.instances_csv.read_bytes()
    assert p1.classes_csv.read_bytes() == p2.classes_csv.read_bytes()
    assert p1.triples_csv.read_bytes() == p2.triples_csv.read_bytes()
    assert p1.query_inventory_csv.read_bytes() == p2.query_inventory_csv.read_bytes()
