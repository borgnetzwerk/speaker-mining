from __future__ import annotations

# pyright: reportMissingImports=false

import json
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


def _append_domain_events(store: EventStore, qid: str) -> None:
    store.append_event(
        {
            "event_type": "entity_discovered",
            "timestamp_utc": "2026-04-08T10:00:00Z",
            "payload": {
                "qid": qid,
                "label": f"Label-{qid}",
                "source_step": "entity_fetch",
                "discovery_method": "seed_neighbor",
            },
        }
    )
    store.append_event(
        {
            "event_type": "entity_expanded",
            "timestamp_utc": "2026-04-08T10:00:01Z",
            "payload": {
                "qid": qid,
                "label": f"Label-{qid}",
                "expansion_type": "neighbors",
                "inlink_count": 0,
                "outlink_count": 0,
            },
        }
    )
    store.append_event(
        {
            "event_type": "triple_discovered",
            "timestamp_utc": "2026-04-08T10:00:02Z",
            "payload": {
                "subject_qid": qid,
                "predicate_pid": "P31",
                "object_qid": "Q5",
                "source_step": "outlinks_build",
            },
        }
    )
    store.append_event(
        {
            "event_type": "expansion_decision",
            "timestamp_utc": "2026-04-08T10:00:04Z",
            "payload": {
                "qid": qid,
                "label": f"Label-{qid}",
                "decision": "queue_for_expansion",
                "decision_reason": "eligible_neighbor",
                "eligibility": {"p31_core_match": True},
            },
        }
    )


def _append_class_membership_event(store: EventStore, qid: str) -> None:
    store.append_event(
        {
            "event_type": "class_membership_resolved",
            "timestamp_utc": "2026-04-08T10:00:03Z",
            "payload": {
                "entity_qid": qid,
                "class_id": "Q5",
                "path_to_core_class": "Q5|Q215627",
                "subclass_of_core_class": True,
                "is_class_node": False,
            },
        }
    )


def _normalized_records(path: Path) -> list[dict]:
    df = pd.read_csv(path)
    if df.empty:
        return []
    df = df.fillna("")
    sort_cols = list(df.columns)
    return df.sort_values(sort_cols).to_dict(orient="records")


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
    _append_class_membership_event(store, "Q5")

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
    assert (paths.projections_dir / "backoff_pattern_windows.csv").exists()

    instances_df = pd.read_csv(paths.instances_csv)
    assert "Q100" in set(instances_df["qid"])

    classes_df = pd.read_csv(paths.classes_csv)
    assert "Q5" in set(classes_df["id"])
    assert bool(classes_df.loc[classes_df["id"] == "Q5", "subclass_of_core_class"].iloc[0]) is True

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
        "BackoffLearningHandler",
    }


def test_orchestrator_projections_invariant_with_interleaved_domain_events(tmp_path: Path) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        "Q215627,persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )

    baseline_root = tmp_path / "baseline"
    interleaved_root = tmp_path / "interleaved"
    baseline_root.mkdir(parents=True, exist_ok=True)
    interleaved_root.mkdir(parents=True, exist_ok=True)

    for root in (baseline_root, interleaved_root):
        setup_target = root / "data" / "00_setup"
        setup_target.mkdir(parents=True, exist_ok=True)
        (setup_target / "classes.csv").write_text(
            (setup_dir / "classes.csv").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    baseline_store = EventStore(baseline_root)
    interleaved_store = EventStore(interleaved_root)

    for store in (baseline_store, interleaved_store):
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

    _append_domain_events(interleaved_store, "Q100")
    _append_class_membership_event(baseline_store, "Q5")

    _append_class_membership_event(interleaved_store, "Q5")
    run_handlers(baseline_root)
    run_handlers(interleaved_root)

    baseline_paths = build_artifact_paths(baseline_root)
    interleaved_paths = build_artifact_paths(interleaved_root)

    assert _normalized_records(baseline_paths.instances_csv) == _normalized_records(interleaved_paths.instances_csv)
    assert _normalized_records(baseline_paths.classes_csv) == _normalized_records(interleaved_paths.classes_csv)
    assert _normalized_records(baseline_paths.triples_csv) == _normalized_records(interleaved_paths.triples_csv)
    assert _normalized_records(baseline_paths.query_inventory_csv) == _normalized_records(interleaved_paths.query_inventory_csv)
    assert _normalized_records(baseline_paths.fallback_stage_candidates_csv) == _normalized_records(interleaved_paths.fallback_stage_candidates_csv)


def test_orchestrator_replay_after_domain_only_events_keeps_projections_stable(tmp_path: Path) -> None:
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
            "aliases": {},
            "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}]},
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

    _append_class_membership_event(store, "Q5")
    run_handlers(tmp_path)
    paths = build_artifact_paths(tmp_path)
    before_instances = _normalized_records(paths.instances_csv)
    before_classes = _normalized_records(paths.classes_csv)
    before_triples = _normalized_records(paths.triples_csv)

    _append_domain_events(store, "Q100")
    run_handlers(tmp_path)

    assert before_instances == _normalized_records(paths.instances_csv)
    assert before_classes == _normalized_records(paths.classes_csv)
    assert before_triples == _normalized_records(paths.triples_csv)


def test_orchestrator_writes_handler_run_summary_artifact(tmp_path: Path) -> None:
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

    run_handlers(tmp_path)

    paths = build_artifact_paths(tmp_path)
    latest_summary = paths.wikidata_dir / "handler_runs" / "handler_run_summary_latest.json"
    assert latest_summary.exists()

    payload = json.loads(latest_summary.read_text(encoding="utf-8"))
    assert isinstance(payload.get("handler_stats"), list)
    assert payload.get("run_timestamp_utc")
    assert any(row.get("handler_name") == "InstancesHandler" for row in payload.get("handler_stats", []))


def test_orchestrator_prunes_stale_registry_handlers(tmp_path: Path) -> None:
    paths = build_artifact_paths(tmp_path)
    registry_path = paths.wikidata_dir / "eventhandler.csv"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(
        "handler_name,last_processed_sequence,artifact_path,updated_at\n"
        "StaleHandler,42,stale.csv,2026-04-09T10:00:00Z\n",
        encoding="utf-8",
    )

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

    run_handlers(tmp_path)

    registry_df = pd.read_csv(registry_path)
    assert "StaleHandler" not in set(registry_df["handler_name"])


def test_orchestrator_incremental_mode_skips_materialize_when_no_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
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

    run_handlers(tmp_path)

    def _forbidden_materialize(*_args, **_kwargs):
        raise AssertionError("materialize must be skipped in incremental mode when no events are pending")

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.handlers.instances_handler.InstancesHandler.materialize",
        _forbidden_materialize,
    )

    summary = run_handlers(tmp_path)
    assert int(summary["InstancesHandler"]) >= 1

    latest_summary_path = (
        build_artifact_paths(tmp_path).wikidata_dir / "handler_runs" / "handler_run_summary_latest.json"
    )
    payload = json.loads(latest_summary_path.read_text(encoding="utf-8"))
    assert payload.get("materialization_mode") == "incremental"
    instance_row = next(
        row for row in payload.get("handler_stats", []) if row.get("handler_name") == "InstancesHandler"
    )
    assert instance_row.get("materialization_status") == "skipped_up_to_date"


def test_orchestrator_full_rebuild_materializes_when_no_pending(
    tmp_path: Path,
    monkeypatch,
) -> None:
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

    run_handlers(tmp_path)

    from process.candidate_generation.wikidata.handlers.instances_handler import InstancesHandler

    original_materialize = InstancesHandler.materialize
    calls = {"count": 0}

    def _counting_materialize(self, output_path):
        calls["count"] += 1
        return original_materialize(self, output_path)

    monkeypatch.setattr(InstancesHandler, "materialize", _counting_materialize)

    summary = run_handlers(tmp_path, materialization_mode="full_rebuild")

    assert int(summary["InstancesHandler"]) >= 1
    assert calls["count"] >= 1

    latest_summary_path = (
        build_artifact_paths(tmp_path).wikidata_dir / "handler_runs" / "handler_run_summary_latest.json"
    )
    payload = json.loads(latest_summary_path.read_text(encoding="utf-8"))
    assert payload.get("materialization_mode") == "full_rebuild"
    instance_row = next(
        row for row in payload.get("handler_stats", []) if row.get("handler_name") == "InstancesHandler"
    )
    assert instance_row.get("materialization_status") == "materialized_no_pending"


def test_orchestrator_incremental_pending_run_uses_projection_bootstrap(tmp_path: Path) -> None:
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
    run_handlers(tmp_path)

    _append_entity_event(
        store,
        "Q2",
        {
            "id": "Q2",
            "labels": {"en": {"value": "Node 2"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "B",
    )

    run_handlers(tmp_path)

    paths = build_artifact_paths(tmp_path)
    latest_summary = paths.wikidata_dir / "handler_runs" / "handler_run_summary_latest.json"
    payload = json.loads(latest_summary.read_text(encoding="utf-8"))
    instance_row = next(
        row for row in payload.get("handler_stats", []) if row.get("handler_name") == "InstancesHandler"
    )
    assert int(instance_row.get("pending_events", 0)) >= 1
    assert int(instance_row.get("historical_replay_events", 0)) == 0
    assert instance_row.get("bootstrap_status") == "bootstrapped"

    instances_df = pd.read_csv(paths.instances_csv)
    assert set(instances_df["qid"]) == {"Q1", "Q2"}
