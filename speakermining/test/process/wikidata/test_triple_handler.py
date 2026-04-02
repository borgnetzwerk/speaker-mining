from __future__ import annotations

# pyright: reportMissingImports=false

from pathlib import Path

import pandas as pd

from process.candidate_generation.wikidata.handlers.triple_handler import TripleHandler


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


def test_triple_handler_extracts_claim_triples(tmp_path: Path) -> None:
    doc = {
        "id": "Q100",
        "claims": {
            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
            "P50": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q200"}}}}],
        },
    }
    handler = TripleHandler(tmp_path)
    handler.process_batch([_entity_event(1, "Q100", doc)])
    out = tmp_path / "triples.csv"
    handler.materialize(out)

    df = pd.read_csv(out)
    triples = {(r.subject, r.predicate, r.object) for r in df.itertuples(index=False)}
    assert ("Q100", "P31", "Q5") in triples
    assert ("Q100", "P50", "Q200") in triples


def test_triple_handler_deduplicates(tmp_path: Path) -> None:
    doc = {
        "id": "Q100",
        "claims": {
            "P31": [{"mainsnak": {"datavalue": {"value": {"entity-type": "item", "id": "Q5"}}}}],
        },
    }
    handler = TripleHandler(tmp_path)
    handler.process_batch([_entity_event(1, "Q100", doc), _entity_event(2, "Q100", doc)])
    out = tmp_path / "triples.csv"
    handler.materialize(out)
    df = pd.read_csv(out)
    assert len(df) == 1


def test_triple_handler_empty_materialization(tmp_path: Path) -> None:
    handler = TripleHandler(tmp_path)
    out = tmp_path / "triples.csv"
    handler.materialize(out)
    df = pd.read_csv(out)
    assert list(df.columns) == ["subject", "predicate", "object", "discovered_at_utc", "source_query_file"]


def test_triple_handler_sequence_tracking(tmp_path: Path) -> None:
    handler = TripleHandler(tmp_path)
    assert handler.last_processed_sequence() == 0
    handler.process_batch([_entity_event(42, "Q1", {"id": "Q1", "claims": {}})])
    assert handler.last_processed_sequence() == 42
