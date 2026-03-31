from __future__ import annotations

# pyright: reportMissingImports=false

import pytest

from process.candidate_generation.wikidata.event_log import build_query_event, compute_query_hash


def test_event_schema_required_fields() -> None:
    event = build_query_event(
        endpoint="wikidata_api",
        normalized_query="entity:Q1499182",
        source_step="entity_fetch",
        status="success",
        key="Q1499182",
        payload={"entities": {}},
        http_status=200,
        error=None,
    )

    required = {
        "event_version",
        "event_type",
        "endpoint",
        "normalized_query",
        "query_hash",
        "timestamp_utc",
        "source_step",
        "status",
        "key",
        "http_status",
        "error",
        "payload",
    }
    assert required.issubset(set(event.keys()))
    assert event["event_version"] == "v2"
    assert event["query_hash"] == compute_query_hash("wikidata_api", "entity:Q1499182")


def test_query_hash_is_deterministic() -> None:
    h1 = compute_query_hash("wikidata_sparql", "inlinks:target=Q1;page_size=200;offset=0;order=source_prop")
    h2 = compute_query_hash("wikidata_sparql", "inlinks:target=Q1;page_size=200;offset=0;order=source_prop")
    assert h1 == h2


def test_event_rejects_unknown_source_step() -> None:
    with pytest.raises(ValueError, match="Unsupported source_step"):
        build_query_event(
            endpoint="wikidata_api",
            normalized_query="entity:Q1499182",
            source_step="unknown_step",
            status="success",
            key="Q1499182",
            payload={"entities": {}},
            http_status=200,
            error=None,
        )
