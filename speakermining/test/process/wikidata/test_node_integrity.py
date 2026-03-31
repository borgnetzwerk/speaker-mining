from __future__ import annotations

# pyright: reportMissingImports=false

import json
from pathlib import Path

from process.candidate_generation.wikidata.node_integrity import (
    NodeIntegrityConfig,
    run_node_integrity_pass,
)
from process.candidate_generation.wikidata.schemas import build_artifact_paths
from process.candidate_generation.wikidata.triple_store import record_item_edges


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
