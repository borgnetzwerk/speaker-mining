from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.expansion_engine import ExpansionConfig, run_graph_expansion_stage
from process.candidate_generation.wikidata.class_resolver import resolve_class_path
from process.candidate_generation.wikidata.materializer import materialize_final
from process.candidate_generation.wikidata.node_store import upsert_discovered_item
from process.candidate_generation.wikidata.schemas import build_artifact_paths
from process.candidate_generation.wikidata.triple_store import record_item_edges


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


def test_graph_stage_hydrates_class_chain_and_persists_class_triples(tmp_path: Path, monkeypatch) -> None:
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

    entity_docs = {
        "Q100": {
            "id": "Q100",
            "labels": {"en": {"value": "Seed Program"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q11578774"}}}}],
                "P50": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q200"}}}}],
            },
        },
        "Q200": {
            "id": "Q200",
            "labels": {"en": {"value": "Alice Example"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
            },
        },
        "Q5": {
            "id": "Q5",
            "labels": {"en": {"value": "human"}, "de": {"value": "Mensch"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}],
            },
        },
        "Q215627": {
            "id": "Q215627",
            "labels": {"en": {"value": "person"}, "de": {"value": "Person"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "Q11578774": {
            "id": "Q11578774",
            "labels": {"en": {"value": "broadcasting program"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
    }

    def _fake_get_or_fetch_entity(_repo_root, qid, _cache_max_age_days, timeout=30):
        _ = timeout
        return {"entities": {qid: entity_docs[qid]}}

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

    run_graph_expansion_stage(
        tmp_path,
        seeds=[],
        targets=[],
        core_class_qids={"Q215627", "Q11578774"},
        config=ExpansionConfig(
            max_depth=1,
            max_nodes=10,
            total_query_budget=-1,
            per_seed_query_budget=-1,
            hydrate_class_chains_for_discovered_entities=True,
        ),
        requested_mode="append",
    )

    paths = build_artifact_paths(tmp_path)
    instances_df = pd.read_csv(paths.instances_csv)
    classes_df = pd.read_csv(paths.classes_csv)
    triples_df = pd.read_csv(paths.triples_csv)

    person_row = instances_df.loc[instances_df["id"] == "Q200"].iloc[0]
    assert person_row["path_to_core_class"] == "Q5|Q215627"
    assert bool(person_row["subclass_of_core_class"]) is True

    q5_row = classes_df.loc[classes_df["id"] == "Q5"].iloc[0]
    assert q5_row["label_en"] == "human"
    assert bool(q5_row["subclass_of_core_class"]) is True

    triples = {(row.subject, row.predicate, row.object) for row in triples_df.itertuples(index=False)}
    assert ("Q200", "P31", "Q5") in triples
    assert ("Q5", "P279", "Q215627") in triples


def test_resolve_class_path_emits_resolution_callback() -> None:
    emitted: list[dict] = []
    docs = {
        "Q5": {
            "id": "Q5",
            "claims": {
                "P279": [
                    {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}
                ]
            },
        }
    }

    entity_doc = {
        "id": "Q200",
        "claims": {
            "P31": [
                {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}
            ]
        },
    }

    def _get_entity(qid: str) -> dict:
        return docs.get(qid, {})

    result = resolve_class_path(
        entity_doc,
        {"Q215627"},
        _get_entity,
        on_resolved=lambda payload: emitted.append(payload),
    )

    assert result["subclass_of_core_class"] is True
    assert result["path_to_core_class"] == "Q5|Q215627"
    assert len(emitted) == 1
    assert emitted[0]["resolution_reason"] == "core_match"
    assert emitted[0]["class_id"] == "Q5"


def test_materializer_writes_per_core_and_leftovers_projections(tmp_path: Path) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "core_classes.csv").write_text(
        "filename,label,wikidata_id\n"
        "persons,person,Q215627\n"
        "episodes,episode,Q1983062\n",
        encoding="utf-8",
    )

    # Q100 reaches persons core class through Q5 -> Q215627.
    upsert_discovered_item(
        tmp_path,
        "Q100",
        {
            "id": "Q100",
            "labels": {"en": {"value": "Alice Example"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}
                ]
            },
        },
        "2026-04-08T12:00:00Z",
    )
    upsert_discovered_item(
        tmp_path,
        "Q5",
        {
            "id": "Q5",
            "labels": {"en": {"value": "human"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [
                    {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}
                ]
            },
        },
        "2026-04-08T12:01:00Z",
    )
    upsert_discovered_item(
        tmp_path,
        "Q215627",
        {
            "id": "Q215627",
            "labels": {"en": {"value": "person"}},
            "descriptions": {},
            "aliases": {},
            "claims": {},
        },
        "2026-04-08T12:02:00Z",
    )

    # Q300 has no path to any configured core class and should end up in leftovers.
    upsert_discovered_item(
        tmp_path,
        "Q300",
        {
            "id": "Q300",
            "labels": {"en": {"value": "Unrelated Node"}},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P31": [
                    {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q999999"}}}}
                ]
            },
        },
        "2026-04-08T12:03:00Z",
    )

    materialize_final(tmp_path, run_id="run-wdt-012")
    paths = build_artifact_paths(tmp_path)

    persons_core_projection = paths.projections_dir / "instances_core_persons.csv"
    episodes_core_projection = paths.projections_dir / "instances_core_episodes.csv"
    leftovers_projection = paths.instances_leftovers_csv

    assert persons_core_projection.exists()
    assert episodes_core_projection.exists()
    assert leftovers_projection.exists()

    persons_df = pd.read_csv(persons_core_projection)
    episodes_df = pd.read_csv(episodes_core_projection)
    leftovers_df = pd.read_csv(leftovers_projection)

    assert set(persons_df["id"].tolist()) == {"Q100"}
    assert episodes_df.empty
    assert set(leftovers_df["id"].tolist()) == {"Q300"}


def test_materializer_core_projections_enforce_two_hop_boundary(tmp_path: Path) -> None:
    setup_dir = tmp_path / "data" / "00_setup"
    setup_dir.mkdir(parents=True, exist_ok=True)
    (setup_dir / "core_classes.csv").write_text(
        "filename,label,wikidata_id\n"
        "persons,person,Q215627\n",
        encoding="utf-8",
    )
    (setup_dir / "broadcasting_programs.csv").write_text(
        "label,wikidata_id\n"
        "Seed Program,Q10\n",
        encoding="utf-8",
    )

    # Seed node and class chain for person resolution.
    upsert_discovered_item(
        tmp_path,
        "Q10",
        {"id": "Q10", "labels": {}, "descriptions": {}, "aliases": {}, "claims": {}},
        "2026-04-09T11:00:00Z",
    )
    upsert_discovered_item(
        tmp_path,
        "Q5",
        {
            "id": "Q5",
            "labels": {},
            "descriptions": {},
            "aliases": {},
            "claims": {
                "P279": [
                    {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q215627"}}}}
                ]
            },
        },
        "2026-04-09T11:01:00Z",
    )
    upsert_discovered_item(
        tmp_path,
        "Q215627",
        {"id": "Q215627", "labels": {}, "descriptions": {}, "aliases": {}, "claims": {}},
        "2026-04-09T11:02:00Z",
    )

    # Persons at different graph distances from seed Q10.
    for person_qid in ("Q200", "Q300", "Q400"):
        upsert_discovered_item(
            tmp_path,
            person_qid,
            {
                "id": person_qid,
                "labels": {},
                "descriptions": {},
                "aliases": {},
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}
                    ]
                },
            },
            "2026-04-09T11:03:00Z",
        )

    # Two-hop neighborhood from seed: Q10 -> Q200 -> Q300; Q400 is third hop.
    record_item_edges(
        tmp_path,
        "Q10",
        [{"pid": "P463", "to_qid": "Q200"}],
        discovered_at_utc="2026-04-09T11:10:00Z",
        source_query_file="test_boundary",
    )
    record_item_edges(
        tmp_path,
        "Q200",
        [{"pid": "P50", "to_qid": "Q300"}],
        discovered_at_utc="2026-04-09T11:10:01Z",
        source_query_file="test_boundary",
    )
    record_item_edges(
        tmp_path,
        "Q300",
        [{"pid": "P50", "to_qid": "Q400"}],
        discovered_at_utc="2026-04-09T11:10:02Z",
        source_query_file="test_boundary",
    )

    materialize_final(tmp_path, run_id="run-two-hop-boundary")
    paths = build_artifact_paths(tmp_path)
    persons_projection = paths.projections_dir / "instances_core_persons.csv"
    persons_df = pd.read_csv(persons_projection)

    assert set(persons_df["id"].tolist()) == {"Q200", "Q300"}
