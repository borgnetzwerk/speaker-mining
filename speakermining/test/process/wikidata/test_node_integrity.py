from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.wikidata.node_integrity import (
    NodeIntegrityConfig,
    run_node_integrity_pass,
)
from process.candidate_generation.wikidata.schemas import build_artifact_paths
from process.candidate_generation.wikidata.triple_store import flush_triple_events, record_item_edges


def test_node_integrity_repairs_discovery_and_expands_eligible_node(tmp_path: Path, monkeypatch) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n"
        ",broadcasting_programs,broadcasting program,,,,,,Q11578774,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q100": {
                        "id": "Q100",
                        "labels": {"en": {"value": "Seed Program"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q11578774"}}}}],
                            "P279": [],
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                    # Deliberately incomplete discovered payload: missing labels/descriptions/aliases and P279 key.
                    "Q200": {
                        "id": "Q200",
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Create a direct seed link to make Q200 expandable by graph rules.
    record_item_edges(
        tmp_path,
        "Q100",
        [{"pid": "P50", "to_qid": "Q200"}],
        discovered_at_utc="2026-03-31T12:00:00Z",
        source_query_file="test_seed_link",
    )
    flush_triple_events(tmp_path)

    entity_docs = {
        "Q100": {
            "id": "Q100",
            "labels": {"en": {"value": "Seed Program"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q11578774"}}}}],
                "P279": [],
                "P50": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q200"}}}}],
            },
        },
        "Q200": {
            "id": "Q200",
            "labels": {"en": {"value": "Alice Example"}, "de": {"value": "Alice Beispiel"}},
            "descriptions": {"en": {"value": "person"}},
            "aliases": {"en": [{"value": "Alice"}]},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
                "P279": [],
            },
        },
        "Q5": {
            "id": "Q5",
            "labels": {"en": {"value": "human"}, "de": {"value": "Mensch"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [],
                "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}],
            },
        },
        "Q215627": {
            "id": "Q215627",
            "labels": {"en": {"value": "person"}, "de": {"value": "Person"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
        "Q11578774": {
            "id": "Q11578774",
            "labels": {"en": {"value": "broadcasting program"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
    }

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        return {"entities": {qid: entity_docs[qid]}}

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        _fake_get_or_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_entity",
        _fake_get_or_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_inlinks",
        lambda *_args, **_kwargs: {"results": {"bindings": []}},
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.parse_inlinks_results",
        lambda _payload: [],
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.expansion_engine.get_or_fetch_property",
        lambda *_args, **_kwargs: {"entities": {}},
    )

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=5,
            query_delay_seconds=0.0,
            network_progress_every=0,
            discovery_query_budget=-1,
            per_node_expansion_query_budget=-1,
            total_expansion_query_budget=-1,
            inlinks_limit=50,
        ),
    )

    repaired = json.loads(paths.entities_json.read_text(encoding="utf-8"))["entities"]
    q200 = repaired["Q200"]
    assert q200["labels"]["en"]["value"] == "Alice Example"
    assert "P279" in q200["claims"]
    assert q200.get("expanded_at_utc") not in (None, "")

    q5 = repaired["Q5"]
    assert q5["labels"]["en"]["value"] == "human"
    assert result.repaired_discovery_qids >= 1
    assert "Q200" in result.repaired_qids
    assert "Q200" in result.expanded_qids


def test_node_integrity_budget_zero_makes_no_network_calls_and_never_logs_unlimited(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q200": {
                        "id": "Q200",
                        # Deliberately incomplete to trigger a refresh attempt.
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"entity-type": "item", "id": "Q5"}
                                        }
                                    }
                                }
                            ]
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    network_calls = {"count": 0}

    class _FakeResponse:
        def __init__(self, payload: str) -> None:
            self._payload = payload.encode("utf-8")

        def read(self) -> bytes:
            return self._payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            _ = (exc_type, exc, tb)
            return None

    def _fake_urlopen(*args, **kwargs):
        _ = (args, kwargs)
        network_calls["count"] += 1
        return _FakeResponse('{"entities": {}}')

    monkeypatch.setattr("process.candidate_generation.wikidata.cache.urlopen", _fake_urlopen)

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=5,
            query_delay_seconds=0.0,
            network_progress_every=1,
            discovery_query_budget=0,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            inlinks_limit=50,
            max_nodes_to_expand=0,
        ),
    )

    out = capsys.readouterr().out.lower()
    assert network_calls["count"] == 0
    assert result.network_queries_discovery == 0
    assert "unlimited" not in out


def test_node_integrity_stops_gracefully_and_skips_materialization_on_user_interrupt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity._termination_requested",
        lambda _repo_root: True,
    )

    def _fail_if_materialize_called(*args, **kwargs):
        _ = (args, kwargs)
        raise AssertionError("materialize_final must not be called when user interruption is requested")

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        _fail_if_materialize_called,
    )

    result = run_node_integrity_pass(tmp_path, config=NodeIntegrityConfig(discovery_query_budget=-1))

    assert result.stop_reason == "user_interrupted"
    assert result.materialize_stats.get("skipped_due_to_user_interrupted") is True


def test_node_integrity_continues_after_timeout_error(tmp_path: Path, monkeypatch) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q200": {
                        "id": "Q200",
                        # Deliberately incomplete to trigger refresh.
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"entity-type": "item", "id": "Q5"}
                                        }
                                    }
                                }
                            ]
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def _timeout_fetch(*_args, **_kwargs):
        raise TimeoutError("The read operation timed out")

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        _timeout_fetch,
    )

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=5,
            query_delay_seconds=0.0,
            network_progress_every=0,
            discovery_query_budget=-1,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            inlinks_limit=50,
            max_nodes_to_expand=0,
        ),
    )

    assert result.stop_reason != "user_interrupted"
    assert result.checked_qids >= 1
    assert result.repaired_discovery_qids == 0
    assert result.timeout_warnings >= 1


def test_node_integrity_forwards_http_retry_policy_to_request_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(json.dumps({"entities": {}}, ensure_ascii=False, indent=2), encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_begin_request_context(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.begin_request_context",
        _fake_begin_request_context,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.end_request_context",
        lambda: 0,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        lambda *_args, **_kwargs: {
            "entities": {
                "Q100": {
                    "id": "Q100",
                    "labels": {"en": {"value": "Seed Program"}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {"P31": [], "P279": []},
                }
            }
        },
    )

    run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=7,
            query_delay_seconds=0.0,
            network_progress_every=0,
            discovery_query_budget=0,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            inlinks_limit=50,
            max_nodes_to_expand=0,
            http_max_retries=3,
            http_backoff_base_seconds=0.25,
        ),
    )

    assert captured.get("http_max_retries") == 3
    assert captured.get("http_backoff_base_seconds") == 0.25


def test_node_integrity_limits_non_core_class_frontier_expansion(tmp_path: Path, monkeypatch) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q200": {
                        "id": "Q200",
                        # Deliberately incomplete to trigger refresh.
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"entity-type": "item", "id": "Q300"}
                                        }
                                    }
                                }
                            ]
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    fetch_calls: list[str] = []
    entity_docs = {
        "Q100": {
            "id": "Q100",
            "labels": {"en": {"value": "Seed"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
        "Q5": {
            "id": "Q5",
            "labels": {"en": {"value": "human"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
        "Q200": {
            "id": "Q200",
            "labels": {"en": {"value": "Example Item"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q300"}}}}],
                "P279": [],
            },
        },
        "Q300": {
            "id": "Q300",
            "labels": {"en": {"value": "Example Class"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [],
                "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q400"}}}}],
            },
        },
        "Q400": {
            "id": "Q400",
            "labels": {"en": {"value": "Parent Class"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [],
                "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q500"}}}}],
            },
        },
        "Q500": {
            "id": "Q500",
            "labels": {"en": {"value": "Grandparent Class"}},
            "descriptions": {},
            "aliases": {},
            "claims": {"P31": [], "P279": []},
        },
    }

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        fetch_calls.append(str(qid))
        return {"entities": {qid: entity_docs[qid]}}

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        _fake_get_or_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        lambda *_args, **_kwargs: {},
    )

    run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=5,
            query_delay_seconds=0.0,
            network_progress_every=0,
            discovery_query_budget=-1,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            inlinks_limit=50,
            max_nodes_to_expand=0,
        ),
        seed_qids={"Q100"},
        core_class_qids={"Q5"},
    )

    assert "Q300" in fetch_calls
    assert "Q400" not in fetch_calls
    assert "Q500" not in fetch_calls


def test_node_integrity_handles_keyboard_interrupt_gracefully(tmp_path: Path, monkeypatch) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q200": {
                        "id": "Q200",
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"entity-type": "item", "id": "Q5"}
                                        }
                                    }
                                }
                            ]
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def _interrupt_fetch(*_args, **_kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        _interrupt_fetch,
    )

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=5,
            query_delay_seconds=0.0,
            network_progress_every=0,
            discovery_query_budget=-1,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            inlinks_limit=50,
            max_nodes_to_expand=0,
        ),
        seed_qids={"Q100"},
        core_class_qids={"Q5"},
    )

    assert result.stop_reason == "user_interrupted"
    assert result.materialize_stats.get("skipped_due_to_user_interrupted") is True


def test_node_integrity_handles_keyboard_interrupt_during_materialization(tmp_path: Path, monkeypatch) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(json.dumps({"entities": {}}, ensure_ascii=False, indent=2), encoding="utf-8")

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            discovery_query_budget=0,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            max_nodes_to_expand=0,
            network_progress_every=0,
        ),
        seed_qids={"Q100"},
        core_class_qids={"Q215627"},
    )

    assert result.stop_reason == "user_interrupted"
    assert result.materialize_stats.get("skipped_due_to_user_interrupted") is True


def test_node_integrity_skips_triple_only_qids_from_discovery_by_default(tmp_path: Path, monkeypatch) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q100": {
                        "id": "Q100",
                        "labels": {"en": {"value": "Seed Program"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {"P31": [], "P279": []},
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Q999 appears only in triples and has no item record.
    record_item_edges(
        tmp_path,
        "Q100",
        [{"pid": "P50", "to_qid": "Q999"}],
        discovered_at_utc="2026-03-31T12:00:00Z",
        source_query_file="test_triple_only",
    )

    fetch_calls: list[str] = []

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        fetch_calls.append(str(qid))
        return {
            "entities": {
                qid: {
                    "id": qid,
                    "labels": {"en": {"value": qid}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {"P31": [], "P279": []},
                }
            }
        }

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        _fake_get_or_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        lambda *_args, **_kwargs: {},
    )

    run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            discovery_query_budget=-1,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            max_nodes_to_expand=0,
            network_progress_every=0,
        ),
        seed_qids={"Q100"},
        core_class_qids={"Q215627"},
    )

    assert "Q999" not in fetch_calls


def test_node_integrity_batches_discovery_refreshes_when_enabled(tmp_path: Path, monkeypatch) -> None:
    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q200": {
                        "id": "Q200",
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"entity-type": "item", "id": "Q300"}
                                        }
                                    }
                                }
                            ]
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                    "Q201": {
                        "id": "Q201",
                        "claims": {
                            "P31": [
                                {
                                    "mainsnak": {
                                        "datavalue": {
                                            "value": {"entity-type": "item", "id": "Q300"}
                                        }
                                    }
                                }
                            ]
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    batch_calls: list[list[str]] = []

    def _fake_batch_fetch(_repo_root, qids, _cache_max_age_days, timeout=30):
        _ = timeout
        canonical = sorted({str(qid) for qid in qids})
        batch_calls.append(canonical)
        payloads: dict[str, dict] = {}
        for qid in canonical:
            payloads[qid] = {
                "entities": {
                    qid: {
                        "id": qid,
                        "labels": {"en": {"value": qid}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {"P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q300"}}}}], "P279": []},
                    }
                }
            }
        return payloads

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entities_batch",
        _fake_batch_fetch,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        lambda _repo_root, qid, _cache_max_age_days, timeout=30: {
            "entities": {
                str(qid): {
                    "id": str(qid),
                    "labels": {"en": {"value": str(qid)}},
                    "descriptions": {},
                    "aliases": {},
                    "claims": {"P31": [], "P279": []},
                }
            }
        },
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        lambda *_args, **_kwargs: {},
    )

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            discovery_query_budget=-1,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            max_nodes_to_expand=0,
            network_progress_every=0,
            discovery_batch_fetch_size=25,
        ),
        seed_qids={"Q100"},
        core_class_qids={"Q5"},
    )

    assert any({"Q200", "Q201"}.issubset(set(call)) for call in batch_calls)
    assert result.repaired_discovery_qids >= 2


def test_node_integrity_reports_ineligible_to_eligible_transition(tmp_path: Path, monkeypatch) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "classes.csv").write_text(
        "wikibase_id,filename,label,description,alias,label_de,description_de,alias_de,wikidata_id,fernsehserien_de_id\n"
        ",persons,person,,,,,,Q215627,\n"
        ",broadcasting_programs,broadcasting program,,,,,,Q11578774,\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q100\n",
        encoding="utf-8",
    )

    paths = build_artifact_paths(tmp_path)
    paths.entities_json.parent.mkdir(parents=True, exist_ok=True)
    paths.entities_json.write_text(
        json.dumps(
            {
                "entities": {
                    "Q100": {
                        "id": "Q100",
                        "labels": {"en": {"value": "Seed Program"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q11578774"}}}}],
                            "P279": [],
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                    # Initially missing labels/aliases/descriptions and P279, so integrity will refresh it.
                    "Q200": {
                        "id": "Q200",
                        "claims": {
                            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                    "Q5": {
                        "id": "Q5",
                        "labels": {"en": {"value": "human"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {
                            "P31": [],
                            "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}],
                        },
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                    "Q215627": {
                        "id": "Q215627",
                        "labels": {"en": {"value": "person"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {"P31": [], "P279": []},
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                    "Q11578774": {
                        "id": "Q11578774",
                        "labels": {"en": {"value": "broadcasting program"}},
                        "descriptions": {},
                        "aliases": {},
                        "claims": {"P31": [], "P279": []},
                        "discovered_at_utc": "2026-03-31T12:00:00Z",
                        "discovered_at_utc_history": ["2026-03-31T12:00:00Z"],
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    refreshed_entity_q200 = {
        "id": "Q200",
        "labels": {"en": {"value": "Alice Example"}},
        "descriptions": {"en": {"value": "person"}},
        "aliases": {"en": [{"value": "Alice"}]},
        "claims": {
            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
            "P50": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q100"}}}}],
            "P279": [],
        },
    }

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        if qid == "Q200":
            return {"entities": {qid: refreshed_entity_q200}}
        data = json.loads(paths.entities_json.read_text(encoding="utf-8")).get("entities", {}).get(qid, {})
        return {"entities": {qid: data}}

    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.get_or_fetch_entity",
        _fake_get_or_fetch_entity,
    )
    monkeypatch.setattr(
        "process.candidate_generation.wikidata.node_integrity.materialize_final",
        lambda *_args, **_kwargs: {},
    )

    result = run_node_integrity_pass(
        tmp_path,
        config=NodeIntegrityConfig(
            cache_max_age_days=365,
            query_timeout_seconds=5,
            query_delay_seconds=0.0,
            network_progress_every=0,
            discovery_query_budget=-1,
            per_node_expansion_query_budget=0,
            total_expansion_query_budget=0,
            inlinks_limit=50,
            max_nodes_to_expand=0,
        ),
        seed_qids={"Q100"},
        core_class_qids={"Q215627"},
    )

    transitions_for_q200 = [row for row in result.eligibility_transitions if row.get("qid") == "Q200"]
    assert len(transitions_for_q200) == 1
    transition = transitions_for_q200[0]
    assert transition["previous_eligible"] is False
    assert transition["current_eligible"] is True
    assert transition["previous_reason"] == "not_seed_neighbor_degree_1_or_2"
    assert transition["current_reason"] == "seed_neighbor_degree_1_or_2_and_direct_or_subclass_core_match"
    assert transition["path_to_core_class"] in {"Q215627", "Q5|Q215627"}
