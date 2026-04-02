from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.event_writer import EventStore
from process.candidate_generation.wikidata.handlers.orchestrator import run_handlers
from process.candidate_generation.wikidata.schemas import build_artifact_paths


def _append_entity_event(store: EventStore, qid: str, payload_entity: dict, seq_key: str) -> None:
    store.append_event(
        {
            "event_type": "query_response",
            "endpoint": "wikidata_api",
            "normalized_query": f"entity:{qid}:{seq_key}",
            "query_hash": f"hash-{seq_key}",
            "source_step": "entity_fetch",
            "status": "success",
            "key": qid,
            "payload": {"entities": {qid: payload_entity}},
            "http_status": 200,
            "error": None,
        }
    )


def test_orchestrator_runs_handlers_and_writes_outputs(tmp_path: Path) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        "Q215627,persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )

    store = EventStore(tmp_path)
    _append_entity_event(
        store,
        "Q100",
        {
            "id": "Q100",
            "labels": {"en": {"value": "Alice"}},
            "descriptions": {"en": {"value": "person"}},
            "aliases": {"en": [{"value": "A"}]},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
                "P50": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q200"}}}}],
            },
        },
        "1",
    )
    _append_entity_event(
        store,
        "Q5",
        {
            "id": "Q5",
            "labels": {"en": {"value": "human"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}]
            },
        },
        "2",
    )
    _append_entity_event(
        store,
        "Q215627",
        {
            "id": "Q215627",
            "labels": {"en": {"value": "person"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "3",
    )

    summary = run_handlers(tmp_path)
    paths = build_artifact_paths(tmp_path)

    assert summary["InstancesHandler"] >= 1
    assert summary["ClassesHandler"] >= 1
    assert summary["TripleHandler"] >= 1
    assert summary["QueryInventoryHandler"] >= 1

    assert paths.instances_csv.exists()
    assert paths.classes_csv.exists()
    assert paths.triples_csv.exists()
    assert paths.query_inventory_csv.exists()
    assert paths.fallback_stage_candidates_csv.exists()

    instances_df = pd.read_csv(paths.instances_csv)
    assert "Q100" in set(instances_df["qid"])

    triples_df = pd.read_csv(paths.triples_csv)
    triples = {(r.subject, r.predicate, r.object) for r in triples_df.itertuples(index=False)}
    assert ("Q100", "P31", "Q5") in triples


def test_orchestrator_resume_is_idempotent(tmp_path: Path) -> None:
    store = EventStore(tmp_path)
    _append_entity_event(
        store,
        "Q1",
        {
            "id": "Q1",
            "labels": {"en": {"value": "Node 1"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "A",
    )

    first = run_handlers(tmp_path)
    second = run_handlers(tmp_path)

    assert first == second

    paths = build_artifact_paths(tmp_path)
    registry_df = pd.read_csv(paths.wikidata_dir / "eventhandler.csv")
    assert set(registry_df["handler_name"]) == {
        "InstancesHandler",
        "ClassesHandler",
        "TripleHandler",
        "QueryInventoryHandler",
        "CandidatesHandler",
    }
